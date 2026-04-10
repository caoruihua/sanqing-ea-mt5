#property strict

// Python 本地唤醒入口（仅允许 localhost）
input string InpEndpoint = "http://127.0.0.1:8765/tick";
// 定时器周期（毫秒）：用于在 OnTimer 中异步推送，避免在 OnTick 阻塞
input int InpTimerMs = 10;
// WebRequest 超时时间（毫秒）
input int InpTimeoutMs = 200;

// 脏标记：有新 tick 但尚未成功推送
// 仅首次连通时打印一次“已连接”提示
bool g_logged_ready = false;

struct PendingTickPayload
{
   string symbol;
   long closed_bar_time;
   long time_msc;
   double bid;
   double ask;
   long sequence;
};

PendingTickPayload g_pending_payloads[];
// 推送序号：每次 OnTick 自增，便于定位乱序/重复问题
long g_sequence = 0;

// 仅允许本机回环地址，禁止外部端点
bool IsLocalhostEndpoint(const string endpoint)
{
   return StringFind(endpoint, "http://127.0.0.1:", 0) == 0 || StringFind(endpoint, "http://localhost:", 0) == 0;
}

// JSON 字符串安全转义
string EscapeJson(const string value)
{
   string escaped = value;
   StringReplace(escaped, "\\", "\\\\");
   StringReplace(escaped, "\"", "\\\"");
   return escaped;
}

// 构造发送给 Python 的 tick 唤醒 payload
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

// EA 初始化：参数校验 + 启动毫秒级定时器
int OnInit()
{
   if(!IsLocalhostEndpoint(InpEndpoint))
   {
      Print("TickRelay 启动失败：只允许使用 localhost 端点，当前配置=", InpEndpoint);
      return INIT_PARAMETERS_INCORRECT;
   }

   if(InpTimerMs < 10)
   {
      Print("TickRelay 启动失败：InpTimerMs 必须 >= 10，当前值=", InpTimerMs);
      return INIT_PARAMETERS_INCORRECT;
   }

   EventSetMillisecondTimer(InpTimerMs);
   Print("TickRelay 启动成功：symbol=", _Symbol, ", endpoint=", InpEndpoint, ", timerMs=", InpTimerMs, ", timeoutMs=", InpTimeoutMs);
   return INIT_SUCCEEDED;
}

// EA 卸载：关闭定时器
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("TickRelay 已停止：reason=", reason, ", symbol=", _Symbol);
}

// OnTick 只做“缓存最新 tick + 标脏”，不做网络请求
void OnTick()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;

   EnqueueTick(tick);
}

// OnTimer 负责按 FIFO 推送等待中的 bar 唤醒事件
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

   ResetLastError();
   int status = WebRequest("POST", InpEndpoint, headers, InpTimeoutMs, post_data, response, response_headers);
   if(status == 200)
   {
      if(!g_logged_ready)
      {
         Print("TickRelay 已连接 Python 唤醒入口：endpoint=", InpEndpoint, ", symbol=", payload.symbol);
         g_logged_ready = true;
      }
      DequeueFront();
      return;
   }

   Print("TickRelay 推送失败：status=", status, ", error=", GetLastError(), ", endpoint=", InpEndpoint);
}
