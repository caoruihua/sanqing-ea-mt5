//+------------------------------------------------------------------+
//|                                              TimeProfitEA.mq5     |
//|                        Integer Level Trend EA                     |
//+------------------------------------------------------------------+
#property copyright   "Author"
#property link        ""
#property version     "2.00"
#property description "H2 trend + M5 entry confirmation + integer-level filter + ATR stop + integer-target TP"

#include "TimeProfitEA.mqh"

//--- Input Parameters
input group "=== Symbol Settings ==="
input string TradeSymbol = "XAUUSD";        // Trading Symbol

input group "=== Trend Settings ==="
input ENUM_TIMEFRAMES TrendTimeframe = PERIOD_H2; // Trend timeframe
input int    Trend_Fast_EMA_Period = 10;    // Trend fast EMA period
input int    Trend_Slow_EMA_Period = 30;    // Trend slow EMA period
input double MinTrendGapDollars = 1.0;      // Minimum trend EMA gap in dollars

input group "=== M5 Entry Settings ==="
input int    M5_Entry_EMA_Period = 10;      // M5 entry EMA period
input bool   RequireCandleDirection = true; // Require bullish/bearish closed M5 candle
input bool   UsePullbackEntry = true;       // Trade pullbacks inside the 100-dollar box
input bool   UseBreakoutEntry = true;       // Chase strong 100-dollar box breakouts
input double PullbackEntryDistanceDollars = 70.0; // Pullback zone from box edge

input group "=== Integer Level Settings ==="
input double IntegerLevelStepDollars = 100.0;      // Major integer level interval
input double NoTradeDistanceDollars = 4.0;         // Do not enter within this distance to nearest level
input double TakeProfitBufferDollars = 3.0;        // TP before next level by this distance
input double MinTakeProfitDollars = 10.0;          // Skip if TP distance is too small

input group "=== ATR Risk Settings ==="
input int    ATR_Period = 14;               // M5 ATR period
input double ATR_Stop_Multiplier = 3.0;     // Stop loss = ATR * multiplier
input double MinStopLossDollars = 5.0;      // Minimum ATR stop distance

input group "=== Trading Settings ==="
input double LotSize = 0.01;                // Lot Size
input int    MagicNumber = 20260530;        // Magic Number
input int    CooldownMinutes = 10;          // Cooldown after any close
input int    MaxSlippagePoints = 30;        // Max slippage in points
input bool   EnableDebugLog = true;         // Print detailed Chinese decision logs

//--- Retry settings
#define MAX_RETRY    3
#define RETRY_DELAY  2000

//+------------------------------------------------------------------+
//| Print verbose strategy logs when enabled                          |
//+------------------------------------------------------------------+
void DebugLog(string message)
  {
   if(EnableDebugLog)
      Print(EA_NAME, ": ", message);
  }

//+------------------------------------------------------------------+
//| Expert initialization function                                    |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(StringLen(TradeSymbol) <= 0)
     {
      Alert(EA_NAME, ": 交易品种参数不能为空");
      return INIT_FAILED;
     }

   if(_Symbol != TradeSymbol)
     {
      Alert(EA_NAME, ": 品种错误，参数品种=", TradeSymbol, "，当前图表品种=", _Symbol);
      return INIT_FAILED;
     }

   if(_Period != PERIOD_M5)
     {
      Alert(EA_NAME, ": 周期错误，仅支持 M5，当前周期=", EnumToString(_Period));
      return INIT_FAILED;
     }

   if(Trend_Fast_EMA_Period <= 0 || Trend_Slow_EMA_Period <= 0 ||
      Trend_Fast_EMA_Period >= Trend_Slow_EMA_Period)
     {
      Alert(EA_NAME, ": 长周期 EMA 参数错误，快线必须为正数且小于慢线");
      return INIT_FAILED;
     }

   if(M5_Entry_EMA_Period <= 0 || ATR_Period <= 0)
     {
      Alert(EA_NAME, ": M5 EMA 和 ATR 周期必须为正数");
      return INIT_FAILED;
     }

   if(!UsePullbackEntry && !UseBreakoutEntry)
     {
      Alert(EA_NAME, ": 回弹入场和突破追单不能同时关闭");
      return INIT_FAILED;
     }

   if(IntegerLevelStepDollars <= 0.0 || NoTradeDistanceDollars < 0.0 ||
      TakeProfitBufferDollars < 0.0 || MinTakeProfitDollars < 0.0)
     {
      Alert(EA_NAME, ": 整数关口参数错误");
      return INIT_FAILED;
     }

   if(NoTradeDistanceDollars * 2.0 >= IntegerLevelStepDollars)
     {
      Alert(EA_NAME, ": 禁止交易距离过大，会覆盖整个整数关口区间");
      return INIT_FAILED;
     }

   if(PullbackEntryDistanceDollars <= NoTradeDistanceDollars ||
      PullbackEntryDistanceDollars >= IntegerLevelStepDollars)
     {
      Alert(EA_NAME, ": 回弹入场区域必须大于禁入距离且小于整数关口间隔");
      return INIT_FAILED;
     }

   if(TakeProfitBufferDollars >= IntegerLevelStepDollars)
     {
      Alert(EA_NAME, ": 止盈缓冲必须小于整数关口间隔");
      return INIT_FAILED;
     }

   if(ATR_Stop_Multiplier <= 0.0 || MinStopLossDollars <= 0.0)
     {
      Alert(EA_NAME, ": ATR 止损参数必须为正数");
      return INIT_FAILED;
     }

   if(LotSize <= 0.0 || CooldownMinutes < 0 || MaxSlippagePoints < 0)
     {
      Alert(EA_NAME, ": 交易参数错误");
      return INIT_FAILED;
     }

   g_trendFastHandle = iMA(_Symbol, TrendTimeframe, Trend_Fast_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   g_trendSlowHandle = iMA(_Symbol, TrendTimeframe, Trend_Slow_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   g_m5EntryEmaHandle = iMA(_Symbol, PERIOD_M5, M5_Entry_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   g_m5AtrHandle = iATR(_Symbol, PERIOD_M5, ATR_Period);

   if(g_trendFastHandle == INVALID_HANDLE || g_trendSlowHandle == INVALID_HANDLE ||
      g_m5EntryEmaHandle == INVALID_HANDLE || g_m5AtrHandle == INVALID_HANDLE)
     {
      Alert(EA_NAME, ": 创建指标句柄失败，错误=", GetLastError());
      return INIT_FAILED;
     }

   g_lastBarTime = 0;
   g_lastCloseTime = 0;
   g_hadOpenPosition = HasOpenPosition();

   Print(EA_NAME, " v", EA_VERSION, " 初始化完成，品种=", _Symbol, "，挂载周期=", EnumToString(_Period));
   Print("  策略：", EnumToString(TrendTimeframe), " 判断大方向；M5 做回弹/突破确认；靠近整数关口观望");
   Print("  长周期 EMA：快线=", Trend_Fast_EMA_Period,
         "，慢线=", Trend_Slow_EMA_Period,
         "，最小差距=", DoubleToString(MinTrendGapDollars, 2), "美元");
   Print("  M5 入场：EMA=", M5_Entry_EMA_Period,
         "，要求K线方向=", RequireCandleDirection,
         "，回弹入场=", UsePullbackEntry,
         "，突破追单=", UseBreakoutEntry,
         "，回弹区域=", DoubleToString(PullbackEntryDistanceDollars, 2), "美元");
   Print("  整数关口：间隔=", DoubleToString(IntegerLevelStepDollars, 2),
         "美元，禁入距离=", DoubleToString(NoTradeDistanceDollars, 2),
         "美元，TP距关口=", DoubleToString(TakeProfitBufferDollars, 2), "美元");
   Print("  ATR止损：周期=", ATR_Period,
         "，倍数=", DoubleToString(ATR_Stop_Multiplier, 2),
         "，最小止损=", DoubleToString(MinStopLossDollars, 2), "美元");
   Print("  交易：手数=", LotSize, "，魔术编号=", MagicNumber,
         "，冷却=", CooldownMinutes, "分钟，调试日志=", EnableDebugLog ? "开启" : "关闭");

   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_trendFastHandle != INVALID_HANDLE)
      IndicatorRelease(g_trendFastHandle);
   if(g_trendSlowHandle != INVALID_HANDLE)
      IndicatorRelease(g_trendSlowHandle);
   if(g_m5EntryEmaHandle != INVALID_HANDLE)
      IndicatorRelease(g_m5EntryEmaHandle);
   if(g_m5AtrHandle != INVALID_HANDLE)
      IndicatorRelease(g_m5AtrHandle);

   g_trendFastHandle = INVALID_HANDLE;
   g_trendSlowHandle = INVALID_HANDLE;
   g_m5EntryEmaHandle = INVALID_HANDLE;
   g_m5AtrHandle = INVALID_HANDLE;

   Print(EA_NAME, " 已卸载，原因代码=", reason);
  }

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
  {
   bool hasPosition = HasOpenPosition();
   SyncClosedPositionState(hasPosition);

   if(!IsNewBar())
      return;

   if(hasPosition)
     {
      DebugLog("当前已有本 EA 持仓，等待 SL/TP 或手动平仓，本根 M5 不再开新仓");
      return;
     }

   if(IsCooldownActive())
     {
      DebugLog("平仓后冷却期内，暂不开新仓");
      return;
     }

   int signal = CheckEntrySignal();
   if(signal == SIGNAL_BUY || signal == SIGNAL_SELL)
      OpenPosition(signal);
  }

//+------------------------------------------------------------------+
//| Check if a new M5 bar has formed                                  |
//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime times[];
   ArraySetAsSeries(times, true);
   if(CopyTime(_Symbol, PERIOD_M5, 0, 1, times) < 1)
     {
      Print(EA_NAME, ": 获取当前 M5 K 线时间失败，错误=", GetLastError());
      return false;
     }

   if(times[0] != g_lastBarTime)
     {
      g_lastBarTime = times[0];
      return true;
     }

   return false;
  }

//+------------------------------------------------------------------+
//| Track broker-side SL/TP closes for cooldown                       |
//+------------------------------------------------------------------+
void SyncClosedPositionState(bool hasPosition)
  {
   if(g_hadOpenPosition && !hasPosition)
     {
      g_lastCloseTime = TimeCurrent();
      Print(EA_NAME, ": 检测到持仓已结束，进入冷却，时间=", TimeToString(g_lastCloseTime));
     }

   g_hadOpenPosition = hasPosition;
  }

//+------------------------------------------------------------------+
//| Cooldown check                                                    |
//+------------------------------------------------------------------+
bool IsCooldownActive()
  {
   if(g_lastCloseTime == 0)
      return false;

   long elapsedMinutes = (TimeCurrent() - g_lastCloseTime) / 60;
   return elapsedMinutes < CooldownMinutes;
  }

//+------------------------------------------------------------------+
//| Check if this EA has an open position                             |
//+------------------------------------------------------------------+
bool HasOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(PositionGetInteger(POSITION_MAGIC) == MagicNumber &&
         PositionGetString(POSITION_SYMBOL) == _Symbol)
         return true;
     }

   return false;
  }

//+------------------------------------------------------------------+
//| Read one closed indicator value                                   |
//+------------------------------------------------------------------+
double GetIndicatorValue(int handle, ENUM_TIMEFRAMES timeframe, int shift)
  {
   double values[];
   ArraySetAsSeries(values, true);
   if(CopyBuffer(handle, 0, shift, 1, values) < 1)
     {
      Print(EA_NAME, ": 读取指标失败，周期=", EnumToString(timeframe), "，错误=", GetLastError());
      return EMPTY_VALUE;
     }

   return values[0];
  }

//+------------------------------------------------------------------+
//| Get last closed M5 bar                                            |
//+------------------------------------------------------------------+
bool GetLastClosedM5Bar(MqlRates &bar)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M5, 1, 1, rates) < 1)
     {
      Print(EA_NAME, ": 获取上一根 M5 K 线失败，错误=", GetLastError());
      return false;
     }

   bar = rates[0];
   return true;
  }

//+------------------------------------------------------------------+
//| Get last two closed M5 bars                                       |
//+------------------------------------------------------------------+
bool GetLastClosedM5Bars(MqlRates &lastBar, MqlRates &previousBar)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_M5, 1, 2, rates) < 2)
     {
      Print(EA_NAME, ": 获取最近两根已收盘 M5 K 线失败，错误=", GetLastError());
      return false;
     }

   lastBar = rates[0];
   previousBar = rates[1];
   return true;
  }

//+------------------------------------------------------------------+
//| Trend: fast EMA above/below slow EMA with minimum gap             |
//+------------------------------------------------------------------+
int CheckTrend()
  {
   double fast = GetIndicatorValue(g_trendFastHandle, TrendTimeframe, 1);
   double slow = GetIndicatorValue(g_trendSlowHandle, TrendTimeframe, 1);
   if(fast == EMPTY_VALUE || slow == EMPTY_VALUE)
      return SIGNAL_NONE;

   double gap = fast - slow;
   if(gap >= MinTrendGapDollars)
     {
      DebugLog("长周期趋势=看多；" + EnumToString(TrendTimeframe) +
               " EMA快线=" + DoubleToString(fast, _Digits) +
               "，EMA慢线=" + DoubleToString(slow, _Digits) +
               "，差距=" + DoubleToString(gap, 2) + "美元");
      return SIGNAL_BUY;
     }

   if(gap <= -MinTrendGapDollars)
     {
      DebugLog("长周期趋势=看空；" + EnumToString(TrendTimeframe) +
               " EMA快线=" + DoubleToString(fast, _Digits) +
               "，EMA慢线=" + DoubleToString(slow, _Digits) +
               "，差距=" + DoubleToString(gap, 2) + "美元");
      return SIGNAL_SELL;
     }

   DebugLog("长周期趋势不明确，跳过；差距=" + DoubleToString(gap, 2) +
            "美元，小于阈值=" + DoubleToString(MinTrendGapDollars, 2));
   return SIGNAL_NONE;
  }

//+------------------------------------------------------------------+
//| Distance to nearest major integer level                           |
//+------------------------------------------------------------------+
double DistanceToNearestIntegerLevel(double price)
  {
   double nearest = MathRound(price / IntegerLevelStepDollars) * IntegerLevelStepDollars;
   return MathAbs(price - nearest);
  }

//+------------------------------------------------------------------+
//| Get current 100-dollar box levels                                 |
//+------------------------------------------------------------------+
void GetIntegerBox(double price, double &lowerLevel, double &upperLevel)
  {
   lowerLevel = MathFloor(price / IntegerLevelStepDollars) * IntegerLevelStepDollars;
   upperLevel = lowerLevel + IntegerLevelStepDollars;
  }

//+------------------------------------------------------------------+
//| TP before next major integer level                                |
//+------------------------------------------------------------------+
double NextTakeProfitPrice(int signal, double entryPrice)
  {
   double level = 0.0;
   double tp = 0.0;

   if(signal == SIGNAL_BUY)
     {
      level = MathCeil(entryPrice / IntegerLevelStepDollars) * IntegerLevelStepDollars;
      tp = level - TakeProfitBufferDollars;
      if(tp <= entryPrice)
        {
         level += IntegerLevelStepDollars;
         tp = level - TakeProfitBufferDollars;
        }
     }
   else if(signal == SIGNAL_SELL)
     {
      level = MathFloor(entryPrice / IntegerLevelStepDollars) * IntegerLevelStepDollars;
      tp = level + TakeProfitBufferDollars;
      if(tp >= entryPrice)
        {
         level -= IntegerLevelStepDollars;
         tp = level + TakeProfitBufferDollars;
        }
     }

   return NormalizeDouble(tp, _Digits);
  }

//+------------------------------------------------------------------+
//| Entry signal: trend + M5 EMA/candle + integer filter              |
//+------------------------------------------------------------------+
int CheckEntrySignal()
  {
   int trend = CheckTrend();
   if(trend == SIGNAL_NONE)
      return SIGNAL_NONE;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double mid = (bid + ask) / 2.0;
   double distanceToLevel = DistanceToNearestIntegerLevel(mid);
   if(distanceToLevel <= NoTradeDistanceDollars)
     {
      DebugLog("距离整数关口过近，观望；当前中间价=" + DoubleToString(mid, _Digits) +
               "，距离最近关口=" + DoubleToString(distanceToLevel, 2) +
               "美元，禁入距离=" + DoubleToString(NoTradeDistanceDollars, 2) + "美元");
      return SIGNAL_NONE;
     }

   MqlRates bar, previousBar;
   if(!GetLastClosedM5Bars(bar, previousBar))
      return SIGNAL_NONE;

   double m5Ema = GetIndicatorValue(g_m5EntryEmaHandle, PERIOD_M5, 1);
   if(m5Ema == EMPTY_VALUE)
      return SIGNAL_NONE;

   double lowerLevel = 0.0;
   double upperLevel = 0.0;
   GetIntegerBox(bar.close, lowerLevel, upperLevel);

   double previousLower = 0.0;
   double previousUpper = 0.0;
   GetIntegerBox(previousBar.close, previousLower, previousUpper);

   DebugLog("信号检查：上一根M5 O=" + DoubleToString(bar.open, _Digits) +
            " H=" + DoubleToString(bar.high, _Digits) +
            " L=" + DoubleToString(bar.low, _Digits) +
            " C=" + DoubleToString(bar.close, _Digits) +
            "；箱体=" + DoubleToString(lowerLevel, 2) + "~" + DoubleToString(upperLevel, 2) +
            "；M5 EMA=" + DoubleToString(m5Ema, _Digits));

   if(trend == SIGNAL_BUY)
     {
      bool bullishCandle = (bar.close > bar.open);
      bool candleOk = (!RequireCandleDirection || bullishCandle);

      double distanceAboveLower = bar.close - lowerLevel;
      bool pullbackLong = UsePullbackEntry &&
                          distanceAboveLower > NoTradeDistanceDollars &&
                          distanceAboveLower <= PullbackEntryDistanceDollars &&
                          bar.low <= m5Ema &&
                          candleOk;

      bool breakoutLong = UseBreakoutEntry &&
                          previousBar.close <= previousUpper &&
                          bar.close > previousUpper + NoTradeDistanceDollars &&
                          bullishCandle;

      if(pullbackLong)
        {
         DebugLog("触发回落低位顺势做多：距箱体下沿=" + DoubleToString(distanceAboveLower, 2) +
                  "美元；上一根M5阳线，且最低价触碰/跌破 M5 EMA");
         return SIGNAL_BUY;
        }

      if(breakoutLong)
        {
         DebugLog("触发强势突破向上追多：收盘价=" + DoubleToString(bar.close, _Digits) +
                  "，突破关口=" + DoubleToString(previousUpper, 2));
         return SIGNAL_BUY;
        }

      DebugLog("长周期看多但未入场：未满足回落做多或向上突破追多条件");
     }

   if(trend == SIGNAL_SELL)
     {
      bool bearishCandle = (bar.close < bar.open);
      bool candleOk = (!RequireCandleDirection || bearishCandle);

      double distanceBelowUpper = upperLevel - bar.close;
      bool pullbackShort = UsePullbackEntry &&
                           distanceBelowUpper > NoTradeDistanceDollars &&
                           distanceBelowUpper <= PullbackEntryDistanceDollars &&
                           bar.high >= m5Ema &&
                           candleOk;

      bool breakoutShort = UseBreakoutEntry &&
                           previousBar.close >= previousLower &&
                           bar.close < previousLower - NoTradeDistanceDollars &&
                           bearishCandle;

      if(pullbackShort)
        {
         DebugLog("触发回弹高位顺势做空：距箱体上沿=" + DoubleToString(distanceBelowUpper, 2) +
                  "美元；上一根M5阴线，且最高价触碰/突破 M5 EMA");
         return SIGNAL_SELL;
        }

      if(breakoutShort)
        {
         DebugLog("触发强势突破向下追空：收盘价=" + DoubleToString(bar.close, _Digits) +
                  "，跌破关口=" + DoubleToString(previousLower, 2));
         return SIGNAL_SELL;
        }

      DebugLog("长周期看空但未入场：未满足回弹做空或向下突破追空条件");
     }

   return SIGNAL_NONE;
  }

//+------------------------------------------------------------------+
//| Open a new position                                               |
//+------------------------------------------------------------------+
bool OpenPosition(int signal)
  {
   if(signal != SIGNAL_BUY && signal != SIGNAL_SELL)
      return false;

   if(HasOpenPosition())
     {
      DebugLog("已有持仓，跳过本次开仓信号");
      return false;
     }

   string direction = (signal == SIGNAL_BUY) ? "做多" : "做空";
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double entryPrice = (signal == SIGNAL_BUY) ? ask : bid;
   double atr = GetIndicatorValue(g_m5AtrHandle, PERIOD_M5, 1);
   if(atr == EMPTY_VALUE || atr <= 0.0 || point <= 0.0)
     {
      DebugLog("跳过开仓：ATR 或 point 无效，ATR=" + DoubleToString(atr, _Digits) +
               "，point=" + DoubleToString(point, _Digits));
      return false;
     }

   double stopDistance = MathMax(atr * ATR_Stop_Multiplier, MinStopLossDollars);
   double stopLoss = (signal == SIGNAL_BUY) ? entryPrice - stopDistance : entryPrice + stopDistance;
   double takeProfit = NextTakeProfitPrice(signal, entryPrice);
   double tpDistance = MathAbs(takeProfit - entryPrice);

   DebugLog("准备开仓：" + direction +
            "，预估入场价=" + DoubleToString(entryPrice, _Digits) +
            "，ATR=" + DoubleToString(atr, _Digits) +
            "，止损距离=" + DoubleToString(stopDistance, 2) + "美元" +
            "，SL=" + DoubleToString(stopLoss, _Digits) +
            "，TP=" + DoubleToString(takeProfit, _Digits) +
            "，TP距离=" + DoubleToString(tpDistance, 2) + "美元");

   if(tpDistance < MinTakeProfitDollars)
     {
      DebugLog("跳过开仓：TP距离过小；方向=" + direction +
               "，入场价=" + DoubleToString(entryPrice, _Digits) +
               "，TP=" + DoubleToString(takeProfit, _Digits) +
               "，距离=" + DoubleToString(tpDistance, 2) +
               "美元，最小要求=" + DoubleToString(MinTakeProfitDollars, 2) + "美元");
      return false;
     }

   int stopsLevel = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDistance = stopsLevel * point;
   if(minDistance > 0.0)
     {
      if(signal == SIGNAL_BUY && (entryPrice - stopLoss < minDistance || takeProfit - entryPrice < minDistance))
        {
         DebugLog("跳过开仓：做多 SL/TP 距离小于券商最小限制；最小距离点数=" +
                  IntegerToString(stopsLevel));
         return false;
        }
      if(signal == SIGNAL_SELL && (stopLoss - entryPrice < minDistance || entryPrice - takeProfit < minDistance))
        {
         DebugLog("跳过开仓：做空 SL/TP 距离小于券商最小限制；最小距离点数=" +
                  IntegerToString(stopsLevel));
         return false;
        }
     }

   stopLoss = NormalizeDouble(stopLoss, _Digits);
   takeProfit = NormalizeDouble(takeProfit, _Digits);

   for(int attempt = 1; attempt <= MAX_RETRY; attempt++)
     {
      MqlTradeRequest request = {};
      MqlTradeResult result = {};

      request.action = TRADE_ACTION_DEAL;
      request.symbol = _Symbol;
      request.volume = LotSize;
      request.magic = MagicNumber;
      request.deviation = MaxSlippagePoints;
      request.type_filling = ORDER_FILLING_IOC;
      request.type = (signal == SIGNAL_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      request.price = (signal == SIGNAL_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      request.sl = stopLoss;
      request.tp = takeProfit;
      request.comment = EA_NAME + "_" + (signal == SIGNAL_BUY ? "INTEGER_BUY" : "INTEGER_SELL");

      if(attempt > 1 && HasOpenPosition())
        {
         Print(EA_NAME, ": 重试前检测到已有持仓，停止重复开仓");
         g_hadOpenPosition = true;
         return true;
        }

      if(!OrderSend(request, result))
        {
         Print(EA_NAME, ": 下单发送失败，尝试=", attempt, "/", MAX_RETRY,
               "，返回码=", result.retcode, "，信息=", result.comment);
         if(attempt < MAX_RETRY) Sleep(RETRY_DELAY);
         continue;
        }

      if(result.retcode != TRADE_RETCODE_DONE && result.retcode != TRADE_RETCODE_PLACED)
        {
         Print(EA_NAME, ": 订单未成交，尝试=", attempt, "/", MAX_RETRY,
               "，返回码=", result.retcode, "，信息=", result.comment);
         if(attempt < MAX_RETRY) Sleep(RETRY_DELAY);
         continue;
        }

      Print(EA_NAME, ": === 开仓成功 === 方向=", direction,
            "，成交价=", result.price,
            "，SL=", stopLoss,
            "，TP=", takeProfit,
            "，ATR=", DoubleToString(atr, _Digits),
            "，止损距离=", DoubleToString(stopDistance, 2), "美元",
            "，整数关口距离=", DoubleToString(DistanceToNearestIntegerLevel(entryPrice), 2), "美元",
            "，订单号=", result.order);
      g_hadOpenPosition = true;
      return true;
     }

   Print(EA_NAME, ": 开仓失败，已重试次数=", MAX_RETRY);
   return false;
  }

//+------------------------------------------------------------------+
//| Close the open position belonging to this EA                      |
//+------------------------------------------------------------------+
bool ClosePosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber ||
         PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      long posType = PositionGetInteger(POSITION_TYPE);
      double volume = PositionGetDouble(POSITION_VOLUME);

      for(int attempt = 1; attempt <= MAX_RETRY; attempt++)
        {
         MqlTradeRequest request = {};
         MqlTradeResult result = {};

         request.action = TRADE_ACTION_DEAL;
         request.symbol = _Symbol;
         request.volume = volume;
         request.magic = MagicNumber;
         request.deviation = MaxSlippagePoints;
         request.type_filling = ORDER_FILLING_IOC;
         request.position = ticket;
         request.type = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         request.price = (posType == POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         request.comment = EA_NAME + "_CLOSE";

         if(!OrderSend(request, result))
           {
            Print(EA_NAME, ": 平仓订单发送失败，尝试=", attempt, "/", MAX_RETRY,
                  "，返回码=", result.retcode, "，信息=", result.comment);
            if(attempt < MAX_RETRY) Sleep(RETRY_DELAY);
            continue;
           }

         if(result.retcode != TRADE_RETCODE_DONE && result.retcode != TRADE_RETCODE_PLACED)
           {
            Print(EA_NAME, ": 平仓订单未成交，尝试=", attempt, "/", MAX_RETRY,
                  "，返回码=", result.retcode, "，信息=", result.comment);
            if(attempt < MAX_RETRY) Sleep(RETRY_DELAY);
            continue;
           }

         g_lastCloseTime = TimeCurrent();
         g_hadOpenPosition = false;
         Print(EA_NAME, ": === 平仓成功 === 订单号=", ticket, "，平仓价=", result.price);
         return true;
        }
     }

   return false;
  }
//+------------------------------------------------------------------+
