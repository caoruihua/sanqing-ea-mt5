//+------------------------------------------------------------------+
//|                              XAUUSD_DarkCloudSell_EA.mq5         |
//|          M5 高位乌云压顶做空EA for XAUUSD（MQL5版）                 |
//+------------------------------------------------------------------+
//| 策略说明：                                                        |
//| 1. 每根新M5 K线收盘后判断信号                                     |
//| 2. 判断最近 HourlyLookbackBars 根已收盘 M5 是否处于上涨高位          |
//|    - 最新收盘价 - 回看区间最低价 >= HourlyRiseMinUsd                |
//|    - 最新收盘价处于该区间高位（可配置比例）                           |
//|    - 最新收盘价高于回看区间起点开盘价，确认整体方向向上                |
//| 3. 最近两根已收盘K线出现宽松乌云压顶                                |
//|    - 前一根K线为阳线，且实体长度 >= DarkCloudPrevBodyMinUsd         |
//|    - 压顶K线为阴线，最高价刺破或接近前高                             |
//|    - 压顶K线收盘深入前一根阳线实体 DarkCloudPenetrationMin 以上      |
//| 4. 满足条件则做空：                                               |
//|    - 止盈 = 入场价 - TakeProfitUsd                               |
//|    - 止损 = 压顶K线最高价 + StopBufferUsd                         |
//| 5. 北京时间日内已平仓订单的净价格移动达到封顶值后停止开新仓            |
//+------------------------------------------------------------------+
#property copyright   "XAUUSD DarkCloud Sell EA"
#property version     "2.0"
#property description "伦敦金M5高位乌云压顶做空EA（MQL5版）"
#property strict

#include <Trade\Trade.mqh>

//--- 输入参数
input group "===== 基础交易参数 ====="
input double FixedLots                  = 0.01;       // 单次下单手数；也作为本EA当前品种最大持仓手数，已持仓>=该值时不再开新仓
input ulong  MagicNumber                = 20260317;   // EA订单唯一识别号；只统计和管理同MagicNumber、同品种的持仓/历史成交
input ulong  SlippagePoints             = 50;         // 市价单允许的最大滑点，单位points；数值越大越容易成交但成交价容忍更宽
input string TradeSymbol                = "XAUUSDr";  // 允许交易的品种名；当前图表品种不等于该值时EA暂停交易

input group "===== 乌云压顶做空参数 ====="
input double TakeProfitUsd              = 10.0;       // 固定止盈距离，单位为XAUUSD价格；空单TP=入场价-TakeProfitUsd
input double StopBufferUsd              = 5.0;        // 止损缓冲距离，单位为XAUUSD价格；空单SL=压顶K线最高价+StopBufferUsd
input double DarkCloudPenetrationMin    = 0.50;       // 乌云压顶深入比例阈值；0.50表示压顶阴线收盘至少打入前阳线实体50%
input double DarkCloudPrevBodyMinUsd    = 0.50;       // 前阳线最小实体长度，单位为XAUUSD价格；用于过滤实体太小的假形态
input double DarkCloudNearHighToleranceUsd = 0.50;    // 压顶K线最高价接近前高的容差；0.50表示允许比前高低最多0.50价格单位
input bool   RequireBreakSignalLowBeforeEntry = true; // true时，二次确认期间必须跌破压顶K线低点才允许下空单
input double BreakSignalLowBufferUsd    = 0.0;        // 跌破压顶K线低点的额外缓冲；实际跌破价=压顶K线低点-BreakSignalLowBufferUsd

input group "===== 1小时高位判断参数 ====="
input int    HourlyLookbackBars         = 12;         // 高位过滤的回看K线数；M5周期下12根约等于1小时
input double HourlyRiseMinUsd           = 5.0;        // 最新已收盘价相对回看区间最低价的最小涨幅；小于该值不认为处于上涨高位
input double HighPositionRatio          = 0.70;       // 最新已收盘价在回看高低区间的位置阈值；0.70表示必须位于区间上方30%

input group "===== 入场观察确认参数 ====="
input int    EntryObserveSeconds        = 2;          // 信号出现后的观察时长，单位秒；<=0时跳过方向观察，仅按跌破低点开关判断
input double EntryObserveMinMoveUsd     = 0.30;       // 观察期内最小空单同向净位移；Bid从起点至少下跌该距离才算方向确认
input int    EntryObserveSampleMs       = 200;        // 观察期采样间隔，单位毫秒；数值越小采样越密，回测/运行等待更频繁
input double EntryObserveMinDirRatio    = 0.60;       // 观察期内下跌步数占有效变动步数的最低比例；0.60表示至少60%为下跌

input group "===== 日内风控参数 ====="
input double DailyPriceTargetUsd        = 40.0;       // 北京时间当日已平仓净价格移动封顶值；达到后停止开新仓，数值由成交盈亏近似反推
input int    ServerToBeijingHours       = 6;          // 服务器时间到北京时间的小时偏移；北京时间=服务器时间+该值小时
input bool   EnableDailySummaryLog      = true;       // true时，北京时间跨日后输出上一北京日的净价格移动和美元净盈亏汇总
input bool   EnablePerBarDailyStats     = true;       // true时，每根新M5 K线输出当日累计统计；实际输出受EnableDebugLogs控制

input group "===== 调试参数 ====="
input bool   EnableDebugLogs            = false;      // true时输出调试日志，包括过滤失败原因、统计窗口和每根K线日内统计

//--- 全局变量
datetime g_lastBarTime              = 0;
bool     g_loggedWrongSymbol        = false;
bool     g_loggedWrongPeriod        = false;
bool     g_loggedTradeNotAllow      = false;
bool     g_loggedBarsNotEnough      = false;
bool     g_loggedDailyTargetReached = false;
int      g_lastBeijingDayKey        = -1;
int      g_loggedDayWindowKey       = -1;

CTrade   g_trade;

//+------------------------------------------------------------------+
//| 日志工具                                                          |
//+------------------------------------------------------------------+
void LogInfo(string msg)
{
   Print("[UWS] ", msg);
}

void LogDebug(string msg)
{
   if(EnableDebugLogs)
      Print("[UWS][DEBUG] ", msg);
}

//+------------------------------------------------------------------+
//| 检测是否出现新的 M5 K线                                           |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_M5, 0);
   if(currentBarTime == 0)
      return false;

   if(g_lastBarTime == 0)
   {
      g_lastBarTime = currentBarTime;
      return false;
   }

   if(currentBarTime == g_lastBarTime)
      return false;

   g_lastBarTime = currentBarTime;
   return true;
}

//+------------------------------------------------------------------+
//| 基础历史数据保护                                                   |
//+------------------------------------------------------------------+
bool HasEnoughBars()
{
   return (iBars(_Symbol, PERIOD_M5) > HourlyLookbackBars + 5);
}

//+------------------------------------------------------------------+
//| 北京时间日期键 YYYYMMDD                                           |
//+------------------------------------------------------------------+
int GetBeijingDayKey(datetime t)
{
   MqlDateTime dt;
   TimeToStruct(t, dt);
   return (dt.year * 10000 + dt.mon * 100 + dt.day);
}

int GetCurrentBeijingDayKey()
{
   datetime beijingNow = TimeCurrent() + ServerToBeijingHours * 3600;
   return GetBeijingDayKey(beijingNow);
}

//+------------------------------------------------------------------+
//| 按北京时间日期键计算服务器时间窗口                                  |
//+------------------------------------------------------------------+
void GetBeijingDayWindowByKeyInServerTime(int dayKey, datetime &dayStartServer, datetime &dayEndServer)
{
   int year  = dayKey / 10000;
   int month = (dayKey / 100) % 100;
   int day   = dayKey % 100;

   MqlDateTime dt;
   ZeroMemory(dt);
   dt.year = year;
   dt.mon  = month;
   dt.day  = day;
   dt.hour = 0;
   dt.min  = 0;
   dt.sec  = 0;

   datetime beijingDayStart = StructToTime(dt);
   dayStartServer = beijingDayStart - ServerToBeijingHours * 3600;
   dayEndServer   = dayStartServer + 24 * 3600;
}

//+------------------------------------------------------------------+
//| 统计指定北京日期已平仓成交的累计净价格移动（由盈亏/手数近似反推）       |
//+------------------------------------------------------------------+
double GetNetPriceMoveByBeijingDayKey(int dayKey)
{
   datetime dayStartServer = 0, dayEndServer = 0;
   GetBeijingDayWindowByKeyInServerTime(dayKey, dayStartServer, dayEndServer);

   double totalMove = 0.0;

   // MQL5: 从历史成交中读取
   HistorySelect(dayStartServer, dayEndServer);
   int totalDeals = HistoryDealsTotal();

   for(int i = 0; i < totalDeals; i++)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket == 0) continue;

      if(HistoryDealGetString(dealTicket, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != (long)MagicNumber) continue;

      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT) continue;

      double dealProfit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
      double dealVolume = HistoryDealGetDouble(dealTicket, DEAL_VOLUME);

      // 通过 profit 和 volume 反推价格移动（近似）
      // 对于 XAUUSD，1手=100盎司，profit = volume * 100 * priceMove
      if(dealVolume > 0.0)
         totalMove += dealProfit / (dealVolume * 100.0);
   }

   return totalMove;
}

//+------------------------------------------------------------------+
//| 统计指定北京日期已平仓成交的美元净盈亏                               |
//+------------------------------------------------------------------+
double GetNetUsdByBeijingDayKey(int dayKey)
{
   datetime dayStartServer = 0, dayEndServer = 0;
   GetBeijingDayWindowByKeyInServerTime(dayKey, dayStartServer, dayEndServer);

   double totalUsd = 0.0;

   HistorySelect(dayStartServer, dayEndServer);
   int totalDeals = HistoryDealsTotal();

   for(int i = 0; i < totalDeals; i++)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket == 0) continue;

      if(HistoryDealGetString(dealTicket, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != (long)MagicNumber) continue;

      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT) continue;

      totalUsd += HistoryDealGetDouble(dealTicket, DEAL_PROFIT)
                + HistoryDealGetDouble(dealTicket, DEAL_SWAP)
                + HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
   }

   return totalUsd;
}

//+------------------------------------------------------------------+
//| 统计本EA当前品种的已开仓总手数                                     |
//+------------------------------------------------------------------+
double GetManagedOpenLots()
{
   double lots = 0.0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)MagicNumber) continue;

      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      if(posType == POSITION_TYPE_BUY || posType == POSITION_TYPE_SELL)
         lots += PositionGetDouble(POSITION_VOLUME);
   }

   return lots;
}

//+------------------------------------------------------------------+
//| 判断最近1小时是否处于明显上涨高位                                   |
//| 条件：                                                            |
//| 1. 最近 HourlyLookbackBars 根K线的 (最高-最低) 区间内，            |
//|    最新close - 区间最低 >= HourlyRiseMinUsd                      |
//| 2. 最新收盘价在区间中的位置 >= HighPositionRatio                   |
//| 3. 最新close > 区间起点open，确认整体方向向上                       |
//+------------------------------------------------------------------+
bool IsAtHourlyHighPosition()
{
   double highestHigh = -DBL_MAX;
   double lowestLow   = DBL_MAX;

   // 遍历最近 HourlyLookbackBars 根已收盘K线 (shift 1 ~ HourlyLookbackBars)
   for(int i = 1; i <= HourlyLookbackBars; i++)
   {
      double h = iHigh(_Symbol, PERIOD_M5, i);
      double l = iLow(_Symbol, PERIOD_M5, i);

      if(h > highestHigh) highestHigh = h;
      if(l < lowestLow)   lowestLow   = l;
   }

   double range = highestHigh - lowestLow;
   if(range <= 0.0)
      return false;

   double latestClose = iClose(_Symbol, PERIOD_M5, 1);
   double startOpen   = iOpen(_Symbol, PERIOD_M5, HourlyLookbackBars);

   // 条件1：最新收盘价相对回看区间最低价的净涨幅达标
   double netRise = latestClose - lowestLow;
   if(netRise < HourlyRiseMinUsd)
   {
      LogDebug("1小时高位判断：净涨幅=" + DoubleToString(netRise, 2) +
               " < 阈值" + DoubleToString(HourlyRiseMinUsd, 2) + "，不满足。");
      return false;
   }

   // 条件2：收盘价处于区间高位
   double positionRatio = (latestClose - lowestLow) / range;
   if(positionRatio < HighPositionRatio)
   {
      LogDebug("1小时高位判断：位置比=" + DoubleToString(positionRatio, 2) +
               " < 阈值" + DoubleToString(HighPositionRatio, 2) + "，不满足。");
      return false;
   }

   // 条件3：整体方向确认
   if(latestClose <= startOpen)
   {
      LogDebug("1小时高位判断：最新收盘=" + DoubleToString(latestClose, _Digits) +
               " <= 起点开盘=" + DoubleToString(startOpen, _Digits) + "，方向不是上涨。");
      return false;
   }

   LogInfo("1小时高位确认。区间=[" + DoubleToString(lowestLow, _Digits) + ", " +
           DoubleToString(highestHigh, _Digits) + "]" +
           " 净涨=" + DoubleToString(netRise, 2) +
           " 位置比=" + DoubleToString(positionRatio, 2) +
           " 最新收盘=" + DoubleToString(latestClose, _Digits));

   return true;
}

//+------------------------------------------------------------------+
//| 判断最近两根已收盘K线是否形成宽松乌云压顶                            |
//| shift 2 为前阳线，shift 1 为压顶阴线；返回压顶K线高低点用于风控/确认   |
//+------------------------------------------------------------------+
bool IsDarkCloudCoverSellSetup(datetime &prevTime, double &prevOpen, double &prevHigh,
                               double &prevLow, double &prevClose,
                               datetime &signalTime, double &signalOpen, double &signalHigh,
                               double &signalLow, double &signalClose,
                               double &prevBody, double &penetration)
{
   prevTime    = iTime(_Symbol, PERIOD_M5, 2);
   prevOpen    = iOpen(_Symbol, PERIOD_M5, 2);
   prevHigh    = iHigh(_Symbol, PERIOD_M5, 2);
   prevLow     = iLow(_Symbol, PERIOD_M5, 2);
   prevClose   = iClose(_Symbol, PERIOD_M5, 2);
   signalTime  = iTime(_Symbol, PERIOD_M5, 1);
   signalOpen  = iOpen(_Symbol, PERIOD_M5, 1);
   signalHigh  = iHigh(_Symbol, PERIOD_M5, 1);
   signalLow   = iLow(_Symbol, PERIOD_M5, 1);
   signalClose = iClose(_Symbol, PERIOD_M5, 1);

   prevBody = prevClose - prevOpen;
   if(prevBody <= 0.0)
      return false;

   if(prevBody < DarkCloudPrevBodyMinUsd)
   {
      LogDebug("乌云压顶判断：前阳线实体=" + DoubleToString(prevBody, _Digits) +
               " < 最小值" + DoubleToString(DarkCloudPrevBodyMinUsd, 2) + "，不满足。");
      return false;
   }

   if(signalClose >= signalOpen)
   {
      LogDebug("乌云压顶判断：压顶K线不是阴线，O=" + DoubleToString(signalOpen, _Digits) +
               " C=" + DoubleToString(signalClose, _Digits) + "，不满足。");
      return false;
   }

   if(signalHigh + DarkCloudNearHighToleranceUsd < prevHigh)
   {
      LogDebug("乌云压顶判断：压顶K线最高价=" + DoubleToString(signalHigh, _Digits) +
               " 未接近前高=" + DoubleToString(prevHigh, _Digits) +
               "，容差=" + DoubleToString(DarkCloudNearHighToleranceUsd, 2));
      return false;
   }

   if(signalClose >= prevClose)
   {
      LogDebug("乌云压顶判断：压顶K线收盘未压回前阳线实体内，C=" +
               DoubleToString(signalClose, _Digits) +
               " 前收=" + DoubleToString(prevClose, _Digits));
      return false;
   }

   penetration = (prevClose - signalClose) / prevBody;
   if(penetration < DarkCloudPenetrationMin)
   {
      LogDebug("乌云压顶判断：深入比例=" + DoubleToString(penetration, 2) +
               " < 阈值" + DoubleToString(DarkCloudPenetrationMin, 2) + "，不满足。");
      return false;
   }

   return true;
}

//+------------------------------------------------------------------+
//| 入场前短时间方向观察确认（空单方向，可要求跌破压顶K线低点）            |
//+------------------------------------------------------------------+
bool ConfirmSellDirectionBeforeEntry(double signalLow)
{
   double breakLevel = signalLow - BreakSignalLowBufferUsd;

   if(EntryObserveSeconds <= 0)
   {
      if(!RequireBreakSignalLowBeforeEntry)
         return true;

      MqlTick tickNow;
      if(!SymbolInfoTick(_Symbol, tickNow))
         return false;

      bool brokeNow = (tickNow.bid <= breakLevel);
      if(!brokeNow)
      {
         LogInfo("未跌破压顶K线低点，取消下单。Bid=" + DoubleToString(tickNow.bid, _Digits) +
                 " 跌破价=" + DoubleToString(breakLevel, _Digits));
      }
      return brokeNow;
   }

   int sampleMs      = MathMax(50, EntryObserveSampleMs);
   int totalObserveMs = EntryObserveSeconds * 1000;
   int sampleCount    = MathMax(1, totalObserveMs / sampleMs);
   datetime observedBarTime = iTime(_Symbol, PERIOD_M5, 0);

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return false;

   double startPrice    = tick.bid;
   double previousPrice = startPrice;
   double endPrice      = startPrice;
   bool brokeSignalLow  = (startPrice <= breakLevel);
   int sameDirSteps     = 0;
   int oppositeSteps    = 0;
   int flatSteps        = 0;

   LogInfo("空单信号观察开始。观察=" + IntegerToString(EntryObserveSeconds) + "秒" +
           " 起始Bid=" + DoubleToString(startPrice, _Digits) +
           " 最小净位移=" + DoubleToString(EntryObserveMinMoveUsd, 2) +
           " 采样间隔=" + IntegerToString(sampleMs) + "ms" +
           " 跌破价=" + DoubleToString(breakLevel, _Digits) +
           " 要求跌破=" + (RequireBreakSignalLowBeforeEntry ? "true" : "false"));

   for(int i = 0; i < sampleCount; i++)
   {
      Sleep(sampleMs);

      if(IsStopped())
         return false;

      // 检查是否已切换到新K线
      datetime currentBarTime = iTime(_Symbol, PERIOD_M5, 0);
      if(currentBarTime != observedBarTime)
      {
         LogInfo("观察期间已切换到新K线，放弃本次信号。");
         return false;
      }

      if(!SymbolInfoTick(_Symbol, tick))
         continue;

      endPrice = tick.bid;
      if(endPrice <= breakLevel)
         brokeSignalLow = true;

      double stepDelta = endPrice - previousPrice;

      if(stepDelta == 0.0)
         flatSteps++;
      else if(stepDelta < 0.0)   // 空单同向 = 价格下跌
         sameDirSteps++;
      else
         oppositeSteps++;

      previousPrice = endPrice;
   }

   double delta           = endPrice - startPrice;
   double directionalMove = -delta;  // 空单：价格下跌为正
   int    activeSteps     = sameDirSteps + oppositeSteps;
   double directionalRatio = 0.0;
   if(activeSteps > 0)
      directionalRatio = (double)sameDirSteps / activeSteps;

   bool directionConfirmed = (directionalMove >= EntryObserveMinMoveUsd &&
                     sameDirSteps > oppositeSteps &&
                     directionalRatio >= EntryObserveMinDirRatio);
   bool breakConfirmed = (!RequireBreakSignalLowBeforeEntry || brokeSignalLow);
   bool confirmed = (directionConfirmed && breakConfirmed);

   LogInfo("空单观察结束。" +
           " 起始=" + DoubleToString(startPrice, _Digits) +
           " 结束=" + DoubleToString(endPrice, _Digits) +
           " 净变化=" + DoubleToString(delta, _Digits) +
           " 同向步=" + IntegerToString(sameDirSteps) +
           " 反向步=" + IntegerToString(oppositeSteps) +
           " 平步=" + IntegerToString(flatSteps) +
           " 同向占比=" + DoubleToString(directionalRatio, 2) +
           " 跌破压顶低点=" + (brokeSignalLow ? "true" : "false") +
           " 结果=" + (confirmed ? "允许下单" : "取消下单"));

   return confirmed;
}

//+------------------------------------------------------------------+
//| 按券商报价精度标准化价格                                           |
//+------------------------------------------------------------------+
double NormalizePrice(double price)
{
   return NormalizeDouble(price, _Digits);
}

//+------------------------------------------------------------------+
//| 检查止损止盈是否满足券商最小止损距离限制                             |
//+------------------------------------------------------------------+
bool ValidateStops(double entryPrice, double stopLoss, double takeProfit)
{
   long stopLevelPoints = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDistance = stopLevelPoints * _Point;

   // 空单：SL > entry, TP < entry
   if((stopLoss - entryPrice) < minDistance)
      return false;
   if((entryPrice - takeProfit) < minDistance)
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| 执行做空下单                                                      |
//+------------------------------------------------------------------+
void SendSellOrder(double signalHigh, string comment = "高位乌云压顶空单")
{
   double stopLoss   = NormalizePrice(signalHigh + StopBufferUsd);
   int    maxRetries = 3;

   for(int attempt = 1; attempt <= maxRetries; attempt++)
   {
      MqlTick tick;
      if(!SymbolInfoTick(_Symbol, tick))
      {
         LogInfo("第" + IntegerToString(attempt) + "次下单：获取报价失败。");
         if(attempt < maxRetries) Sleep(300);
         continue;
      }

      double entryPrice = NormalizePrice(tick.bid);
      double takeProfit = NormalizePrice(entryPrice - TakeProfitUsd);

      if(!ValidateStops(entryPrice, stopLoss, takeProfit))
      {
         LogInfo("第" + IntegerToString(attempt) + "/" + IntegerToString(maxRetries) +
                 "次下单跳过：止损/止盈距离不满足券商要求。" +
                 " 入场=" + DoubleToString(entryPrice, _Digits) +
                 " 止损=" + DoubleToString(stopLoss, _Digits) +
                 " 止盈=" + DoubleToString(takeProfit, _Digits));
         if(attempt < maxRetries) Sleep(300);
         continue;
      }

      LogInfo("准备发送空单（第" + IntegerToString(attempt) + "/" + IntegerToString(maxRetries) + "次）。" +
              " 入场=" + DoubleToString(entryPrice, _Digits) +
              " 止损=" + DoubleToString(stopLoss, _Digits) +
              " 止盈=" + DoubleToString(takeProfit, _Digits) +
              " 手数=" + DoubleToString(FixedLots, 2));

      g_trade.SetExpertMagicNumber(MagicNumber);
      g_trade.SetDeviationInPoints(SlippagePoints);

      bool result = g_trade.Sell(FixedLots, _Symbol, entryPrice, stopLoss, takeProfit, comment);

      if(result && g_trade.ResultRetcode() == TRADE_RETCODE_DONE)
      {
         LogInfo("空单开仓成功。Ticket=" + IntegerToString((int)g_trade.ResultDeal()) +
                 " 尝试=" + IntegerToString(attempt) +
                 " 入场=" + DoubleToString(entryPrice, _Digits) +
                 " 止损=" + DoubleToString(stopLoss, _Digits) +
                 " 止盈=" + DoubleToString(takeProfit, _Digits));
         return;
      }

      LogInfo("空单下单失败。第" + IntegerToString(attempt) + "/" + IntegerToString(maxRetries) +
              "次。RetCode=" + IntegerToString((int)g_trade.ResultRetcode()) +
              " Comment=" + g_trade.ResultComment());

      if(attempt < maxRetries) Sleep(300);
   }

   LogInfo("空单重试" + IntegerToString(maxRetries) + "次后仍失败，放弃本次信号。");
}

//+------------------------------------------------------------------+
//| 检查运行环境                                                      |
//+------------------------------------------------------------------+
bool CheckTradeEnvironment()
{
   if(_Symbol != TradeSymbol)
   {
      if(!g_loggedWrongSymbol)
      {
         LogInfo("EA 配置品种=" + TradeSymbol + "，当前图表=" + _Symbol + "，暂停交易。");
         g_loggedWrongSymbol = true;
      }
      return false;
   }
   g_loggedWrongSymbol = false;

   if(Period() != PERIOD_M5)
   {
      if(!g_loggedWrongPeriod)
      {
         LogInfo("EA 只能运行在 M5 周期，当前=" + IntegerToString(Period()) + "，暂停交易。");
         g_loggedWrongPeriod = true;
      }
      return false;
   }
   g_loggedWrongPeriod = false;

   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      if(!g_loggedTradeNotAllow)
      {
         LogInfo("当前终端或券商设置不允许交易，暂停交易。");
         g_loggedTradeNotAllow = true;
      }
      return false;
   }
   g_loggedTradeNotAllow = false;

   return true;
}

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   g_lastBeijingDayKey = GetCurrentBeijingDayKey();

   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints(SlippagePoints);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);  // 根据券商调整

   datetime initDayStart = 0, initDayEnd = 0;
   GetBeijingDayWindowByKeyInServerTime(g_lastBeijingDayKey, initDayStart, initDayEnd);

   LogInfo("EA 初始化完成。品种=" + _Symbol +
           " 周期=M5" +
           " MagicNumber=" + IntegerToString((int)MagicNumber) +
           " 手数=" + DoubleToString(FixedLots, 2) +
           " 止盈=" + DoubleToString(TakeProfitUsd, 2) +
           " 止损缓冲=" + DoubleToString(StopBufferUsd, 2) +
          " 乌云深入比例=" + DoubleToString(DarkCloudPenetrationMin, 2) +
          " 前阳线最小实体=" + DoubleToString(DarkCloudPrevBodyMinUsd, 2) +
          " 接近前高容差=" + DoubleToString(DarkCloudNearHighToleranceUsd, 2) +
          " 跌破低点确认=" + (RequireBreakSignalLowBeforeEntry ? "true" : "false") +
           " 1h回看=" + IntegerToString(HourlyLookbackBars) + "根" +
           " 1h最小涨幅=" + DoubleToString(HourlyRiseMinUsd, 2) +
           " 高位比例=" + DoubleToString(HighPositionRatio, 2) +
           " 日封顶=" + DoubleToString(DailyPriceTargetUsd, 2) +
           " 服务器→北京=" + IntegerToString(ServerToBeijingHours) + "h");

   LogInfo("初始统计窗口：北京日期=" + IntegerToString(g_lastBeijingDayKey) +
           " 窗口开始=" + TimeToString(initDayStart, TIME_DATE | TIME_SECONDS) +
           " 窗口结束=" + TimeToString(initDayEnd, TIME_DATE | TIME_SECONDS));

   if(Period() != PERIOD_M5)
      LogInfo("请把 EA 挂到 M5 图表。");
   if(_Symbol != TradeSymbol)
      LogInfo("请把 EA 挂到 " + TradeSymbol + " 图表。当前=" + _Symbol);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   LogInfo("EA 卸载。原因代码=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
//| OnTick - 主逻辑                                                   |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!CheckTradeEnvironment())
      return;

   if(!HasEnoughBars())
   {
      if(!g_loggedBarsNotEnough)
      {
         LogInfo("历史 M5 K线数量不足，等待数据加载。");
         g_loggedBarsNotEnough = true;
      }
      return;
   }
   g_loggedBarsNotEnough = false;

   if(!IsNewBar())
      return;

   //--- 北京时间跨日处理
   int currentBeijingDayKey = GetCurrentBeijingDayKey();
   if(currentBeijingDayKey != g_lastBeijingDayKey)
   {
      if(EnableDailySummaryLog && g_lastBeijingDayKey > 0)
      {
         double prevNetMove = GetNetPriceMoveByBeijingDayKey(g_lastBeijingDayKey);
         double prevNetUsd  = GetNetUsdByBeijingDayKey(g_lastBeijingDayKey);
         LogInfo("北京时间跨日汇总。日期=" + IntegerToString(g_lastBeijingDayKey) +
                 " 净价格差=" + DoubleToString(prevNetMove, 2) +
                 " 美元净盈亏=" + DoubleToString(prevNetUsd, 2));
      }
      g_lastBeijingDayKey = currentBeijingDayKey;
      g_loggedDailyTargetReached = false;
      g_loggedDayWindowKey = -1;
   }

   //--- 调试：输出统计窗口
   if(EnableDebugLogs && g_loggedDayWindowKey != currentBeijingDayKey)
   {
      datetime dayStartServer = 0, dayEndServer = 0;
      GetBeijingDayWindowByKeyInServerTime(currentBeijingDayKey, dayStartServer, dayEndServer);
      LogDebug("统计窗口：日期=" + IntegerToString(currentBeijingDayKey) +
               " 开始=" + TimeToString(dayStartServer, TIME_DATE | TIME_SECONDS) +
               " 结束=" + TimeToString(dayEndServer, TIME_DATE | TIME_SECONDS));
      g_loggedDayWindowKey = currentBeijingDayKey;
   }

   //--- 日内风控：用已平仓成交盈亏近似反推北京时间当日净价格移动
   double todayNetMove = GetNetPriceMoveByBeijingDayKey(currentBeijingDayKey);
   double todayNetUsd  = GetNetUsdByBeijingDayKey(currentBeijingDayKey);

   if(EnablePerBarDailyStats)
   {
      LogDebug("今日统计：净价格差=" + DoubleToString(todayNetMove, 2) +
               " 美元净盈亏=" + DoubleToString(todayNetUsd, 2) +
               " 封顶=" + DoubleToString(DailyPriceTargetUsd, 2));
   }

   if(todayNetMove >= DailyPriceTargetUsd)
   {
      if(!g_loggedDailyTargetReached)
      {
         LogInfo("今日累计净价格差已达封顶，停止开新仓。当前=" +
                 DoubleToString(todayNetMove, 2) +
                 " 美元净盈亏=" + DoubleToString(todayNetUsd, 2));
         g_loggedDailyTargetReached = true;
      }
      return;
   }

   //--- 持仓上限检查：本EA当前品种持仓手数达到/超过 FixedLots 时不再开新仓
   double managedLots = GetManagedOpenLots();
   if(managedLots >= FixedLots)
   {
      LogDebug("已达总手数上限。当前=" + DoubleToString(managedLots, 2) +
               " 上限=" + DoubleToString(FixedLots, 2));
      return;
   }

   //--- ★★★ 核心信号判断 ★★★
   //--- 步骤1：判断最近1小时是否处于上涨高位
   if(!IsAtHourlyHighPosition())
   {
      LogDebug("最近1小时未处于上涨高位，不判断乌云压顶信号。");
      return;
   }

   //--- 步骤2：判断最近两根已收盘K线是否形成宽松乌云压顶
   datetime prevTime   = 0;
   datetime signalTime = 0;
   double prevOpen     = 0.0;
   double prevHigh     = 0.0;
   double prevLow      = 0.0;
   double prevClose    = 0.0;
   double signalOpen   = 0.0;
   double signalHigh   = 0.0;
   double signalLow    = 0.0;
   double signalClose  = 0.0;
   double prevBody     = 0.0;
   double penetration  = 0.0;

   if(!IsDarkCloudCoverSellSetup(prevTime, prevOpen, prevHigh, prevLow, prevClose,
                                 signalTime, signalOpen, signalHigh, signalLow, signalClose,
                                 prevBody, penetration))
   {
      LogDebug("最近两根K线未形成有效乌云压顶信号。");
      return;
   }

   LogInfo("★ 检测到高位乌云压顶做空信号！" +
           " 前阳线=" + TimeToString(prevTime, TIME_DATE | TIME_MINUTES) +
           " O=" + DoubleToString(prevOpen, _Digits) +
           " H=" + DoubleToString(prevHigh, _Digits) +
           " L=" + DoubleToString(prevLow, _Digits) +
           " C=" + DoubleToString(prevClose, _Digits) +
           " 前阳线实体=" + DoubleToString(prevBody, _Digits) +
           " 压顶K线=" + TimeToString(signalTime, TIME_DATE | TIME_MINUTES) +
           " O=" + DoubleToString(signalOpen, _Digits) +
           " H=" + DoubleToString(signalHigh, _Digits) +
           " L=" + DoubleToString(signalLow, _Digits) +
           " C=" + DoubleToString(signalClose, _Digits) +
           " 深入比例=" + DoubleToString(penetration, 2) +
           " 阈值=" + DoubleToString(DarkCloudPenetrationMin, 2) +
           " 压顶最高价=" + DoubleToString(signalHigh, _Digits) +
           " 压顶低点=" + DoubleToString(signalLow, _Digits) +
           " 止损将设在=" + DoubleToString(signalHigh + StopBufferUsd, _Digits) +
           " 止盈距离=" + DoubleToString(TakeProfitUsd, 2));

   //--- 步骤3：入场前短时间方向确认
   if(!ConfirmSellDirectionBeforeEntry(signalLow))
   {
      LogInfo("空单二次确认未通过，本次不下单。");
      return;
   }

   //--- 步骤4：执行做空
   SendSellOrder(signalHigh);
}
//+------------------------------------------------------------------+
