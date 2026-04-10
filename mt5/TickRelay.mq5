#property strict

input string InpEndpoint = "http://127.0.0.1:8765/tick"; # Python 本地 tick 接口地址，只允许 localhost
input int InpTimerMs = 500;                              # 定时器周期（毫秒），OnTick 入队，OnTimer 发送
input int InpTimeoutMs = 3000;                          # WebRequest 超时（毫秒），过小会导致已发出但未等到响应

// 首次连通成功后只打印一次连通日志，避免重复刷屏。
bool g_logged_ready = false;

// 单次待发送的 tick 负载。
// closed_bar_time: 对应上一根已收盘 K 线时间
// time_msc: tick 的毫秒时间戳
// sequence: 本地自增序号，用于排查乱序/重复推送
struct PendingTickPayload
{
   string symbol;
   long closed_bar_time;
   long time_msc;
   double bid;
   double ask;
   long sequence;
};

// FIFO 待发送队列。
PendingTickPayload g_pending_payloads[];
// 每捕获一个新 tick 递增一次，便于 Python 侧做顺序判断。
long g_sequence = 0;

// 限制 endpoint 只能是本机回环地址。
bool IsLocalhostEndpoint(const string endpoint)
{
   return StringFind(endpoint, "http://127.0.0.1:", 0) == 0
       || StringFind(endpoint, "http://localhost:", 0) == 0;
}

// 最小 JSON 转义，只处理当前 payload 里会碰到的关键字符。
string EscapeJson(const string value)
{
   string escaped = value;
   StringReplace(escaped, "\\", "\\\\");
   StringReplace(escaped, "\"", "\\\"");
   return escaped;
}

// 把 PendingTickPayload 组装成发给 Python 的 JSON 文本。
string BuildPayload(const PendingTickPayload &payload)
{
   return StringFormat(
      "{\"symbol\":\"%s\",\"closed_bar_time\":%I64d,\"time_msc\":%I64d,\"bid\":%.10f,\"ask\":%.10f,\"sequence\":%I64d}",
      EscapeJson(payload.symbol),
      payload.closed_bar_time,
      payload.time_msc,
      payload.bid,
      payload.ask,
      payload.sequence
   );
}

// 把 WebRequest 返回的字节数组转成 UTF-8 字符串，方便写日志排障。
// 同时把换行转义，避免 Experts 日志被打散。
string ResponseToString(const char &buffer[])
{
   int size = ArraySize(buffer);
   if(size <= 0)
      return "";

   string text = CharArrayToString(buffer, 0, size, CP_UTF8);
   StringReplace(text, "\r", "\\r");
   StringReplace(text, "\n", "\\n");
   return text;
}

// 宽松成功判定。
// 正常情况应当返回 HTTP 200；
// 但如果 MT 状态码异常，而响应体里已经明确写了 accepted/ok/status/code 成功标记，
// 这里也视为成功，避免“Python 已处理但 MT 误判失败”。
bool ResponseIndicatesAccepted(const string response_text)
{
   string lowered = response_text;
   StringToLower(lowered);
   return StringFind(lowered, "\"accepted\":true", 0) >= 0
       || StringFind(lowered, "\"ok\":true", 0) >= 0
       || StringFind(lowered, "\"status\":0", 0) >= 0
       || StringFind(lowered, "\"code\":0", 0) >= 0;
}

// 把当前 tick 放进发送队列。
// 如果当前队尾和新 tick 属于同一根已收盘 K 线，则只保留最新一份数据。
void EnqueueTick(const MqlTick &tick)
{
   long closed_bar_time = (long)iTime(_Symbol, PERIOD_CURRENT, 1);
   if(closed_bar_time <= 0)
      return;

   PendingTickPayload payload;
   payload.symbol = _Symbol;
   payload.closed_bar_time = closed_bar_time;
   payload.time_msc = tick.time_msc;
   payload.bid = tick.bid;
   payload.ask = tick.ask;
   payload.sequence = ++g_sequence;

   int size = ArraySize(g_pending_payloads);
   if(size > 0 && g_pending_payloads[size - 1].closed_bar_time == payload.closed_bar_time)
   {
      g_pending_payloads[size - 1] = payload;
      return;
   }

   ArrayResize(g_pending_payloads, size + 1);
   g_pending_payloads[size] = payload;
}

// 发送成功后，从队列头部弹出。
void DequeueFront()
{
   int size = ArraySize(g_pending_payloads);
   if(size <= 0)
      return;
   if(size == 1)
   {
      ArrayResize(g_pending_payloads, 0);
      return;
   }

   for(int i = 1; i < size; i++)
      g_pending_payloads[i - 1] = g_pending_payloads[i];
   ArrayResize(g_pending_payloads, size - 1);
}

// 初始化阶段只做参数校验和定时器启动。
int OnInit()
{
   if(!IsLocalhostEndpoint(InpEndpoint))
   {
      Print("TickRelay init failed: localhost endpoint required, endpoint=", InpEndpoint);
      return INIT_PARAMETERS_INCORRECT;
   }

   if(InpTimerMs < 10)
   {
      Print("TickRelay init failed: InpTimerMs must be >= 10, value=", InpTimerMs);
      return INIT_PARAMETERS_INCORRECT;
   }

   EventSetMillisecondTimer(InpTimerMs);
   Print("TickRelay started: symbol=", _Symbol, ", endpoint=", InpEndpoint,
         ", timerMs=", InpTimerMs, ", timeoutMs=", InpTimeoutMs);
   return INIT_SUCCEEDED;
}

// 卸载时关闭定时器。
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("TickRelay stopped: reason=", reason, ", symbol=", _Symbol);
}

// OnTick 只负责抓取最新行情并入队。
// 这样即使 Python 端有短暂卡顿，也不会直接阻塞 MT 的行情线程。
void OnTick()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;

   EnqueueTick(tick);
}

// OnTimer 负责真正的 HTTP 推送。
// 当前策略：
// 1. 每次只处理队首一个 payload
// 2. 成功才出队，失败则保留，等待下一个定时器周期重试
// 3. 失败时记录响应头和响应体，便于定位连接/超时/协议问题
void OnTimer()
{
   if(ArraySize(g_pending_payloads) <= 0)
      return;

   PendingTickPayload payload = g_pending_payloads[0];
   string payload_json = BuildPayload(payload);
   string headers = "Content-Type: application/json\r\n";
   char post_data[];
   char response[];
   string response_headers;
   StringToCharArray(payload_json, post_data, 0, StringLen(payload_json), CP_UTF8);

   // 每次请求前清掉上一次错误码，避免干扰当前诊断。
   ResetLastError();
   int status = WebRequest("POST", InpEndpoint, headers, InpTimeoutMs, post_data, response, response_headers);
   int err = GetLastError();
   string response_text = ResponseToString(response);

   // 首先按 HTTP 200 判成功。
   // 如果状态码异常，但响应体已经明确表示 accepted/ok/status/code 成功，也允许出队。
   if(status == 200 || ResponseIndicatesAccepted(response_text))
   {
      if(!g_logged_ready)
      {
         Print("TickRelay connected to Python tick ingress: endpoint=", InpEndpoint,
               ", symbol=", payload.symbol);
         g_logged_ready = true;
      }
      DequeueFront();
      return;
   }

   // 失败时不出队，下个定时器周期继续尝试。
   Print("TickRelay push failed: status=", status, ", error=", err, ", endpoint=", InpEndpoint,
         ", response_headers=", response_headers, ", response_body=", response_text);
}
