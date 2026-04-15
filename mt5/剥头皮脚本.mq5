//+------------------------------------------------------------------+
//|                                              剥头皮脚本.mq5        |
//|              XAUUSD M5 快速剥头皮EA                               |
//+------------------------------------------------------------------+
//| 版本历史：                                                        |
//| v1.4 (2026-04-15)                                                |
//|   - 新增最大止损距离限制：止损超过MaxStopLossUsd时自动限制        |
//|                                                                   |
//| v1.3 (2026-04-15)                                                |
//|   - 新增持续趋势入场：连续N根K线在EMA同侧且偏离>0.1%时入场        |
//|   - 解决单边行情踏空问题                                          |
//|                                                                   |
//| v1.2 (2026-04-15)                                                |
//|   - 加强空仓检查：有持仓时严禁开新仓（原逻辑仅检查是否>=配置手数）  |
//|                                                                   |
//| v1.1 (2026-04-15)                                                |
//|   - 修正时区偏移：服务器时间比北京时间晚5小时（原6小时）           |
//|   - ServerToBeijingHours 默认值从6改为5                          |
//|                                                                   |
//| v1.0 (2026-04-14)                                                 |
//|   - 初始版本：EMA趋势判断+回调入场剥头皮策略                       |
//+------------------------------------------------------------------+
//| 策略说明：                                                        |
//| 1. 使用EMA判断大趋势方向                                          |
//| 2. 大趋势向上时只做多，向下时只做空                                |
//| 3. 无持仓时立即开单，止盈2美元就跑                                |
//| 4. 每tick检查，不等K线闭合                                        |
//| 5. 0.01手最大，空仓才能下一单                                     |
//+------------------------------------------------------------------+
#property copyright   "Scalping EA"
#property version     "1.4"
#property description "XAUUSD M5 快速剥头皮EA"
#property strict

#include <Trade\Trade.mqh>

//--- 输入参数
input group "===== 基础交易参数 ====="
input double FixedLots           = 0.01;       // 单次下单手数；也作为最大持仓手数
input ulong  MagicNumber         = 20260414;   // EA订单唯一识别号
input ulong  SlippagePoints      = 50;         // 市价单允许的最大滑点
input string TradeSymbol         = "XAUUSD";   // 交易品种

input group "===== 剥头皮参数 ====="
input double TakeProfitUsd       = 5.0;        // 止盈距离（美元）
input double StopLossBufferUsd   = 3.0;        // 止损缓冲（美元），在最近5根K线极值外侧
input int    StopLossLookbackBars = 5;         // 止损回看K线数
input double MaxStopLossUsd      = 15.0;       // 最大止损距离（美元），超过则限制为此值
input int    MinTradeIntervalMs  = 1000;       // 最小交易间隔（毫秒），防止过快下单
input int    StopLossCooldownSec = 120;        // 止损后冷却时间（秒），默认2分钟

input group "===== 趋势判断参数 ====="
input int    TrendEmaPeriod      = 20;         // 趋势EMA周期
input int    TrendEmaTimeframe   = PERIOD_M5;  // 趋势判断时间框架
input bool   EnableDeviationFilter = false;    // 是否启用偏离过滤，关闭则只看价格在EMA哪边
input double TrendStrengthRatio  = 0.002;      // 趋势强度比例，价格偏离EMA的比例（需启用偏离过滤）
input double PullbackRatio       = 0.3;        // 回调比例，0.3=回调到EMA距离的30%以内入场
input int    PullbackMaxBars     = 10;         // 回调最多等待多少根K线
input double StrongTrendRatio    = 0.004;      // 强趋势比例，价格偏离EMA超过此比例直接入场，不等回调
input int    SustainedTrendBars  = 5;          // 持续趋势入场：连续N根K线在EMA同侧
input double SustainedTrendMinDeviation = 0.001; // 持续趋势入场：最小偏离比例（默认0.1%）

input group "===== 日内风控参数 ====="
input double DailyProfitTargetUsd = 50.0;      // 日内盈利目标（美元），达到后停止开新仓
input double DailyLossLimitUsd    = 100.0;      // 日内亏损限额（美元），达到后停止开新仓
input int    ServerToBeijingHours = 5;         // 服务器时间到北京时间的小时偏移（服务器+此值=北京时间）

input group "===== 调试参数 ====="
input bool   EnableDebugLogs     = true;       // 是否输出调试日志
input int    DebugLogIntervalSec = 5;          // 调试日志最小输出间隔（秒）

//--- 全局变量
datetime g_lastTradeTime         = 0;
datetime g_lastStopLossTime      = 0;  // 最后一次止损平仓时间
datetime g_lastDebugLogTime      = 0;
int      g_lastBeijingDayKey     = -1;
bool     g_loggedWrongSymbol     = false;
int      g_trendEmaHandle        = INVALID_HANDLE;

//--- 回调入场状态
int      g_pullbackTrend         = 0;     // 检测到的趋势方向: 1=多, -1=空
datetime g_pullbackBarTime       = 0;     // 趋势确认的K线时间
double   g_pullbackMaxDistance   = 0;     // 趋势确认时价格距EMA的最大距离

//--- 持续趋势入场状态
int      g_sustainedTrendBars    = 0;     // 持续趋势计数：连续在EMA同侧的K线数
int      g_sustainedTrendDirection = 0;   // 持续趋势方向: 1=多, -1=空
datetime g_sustainedLastBarTime  = 0;     // 上次计数的K线时间，防止同一根K线重复计数

CTrade   g_trade;

//+------------------------------------------------------------------+
//| 日志工具                                                          |
//+------------------------------------------------------------------+
void LogInfo(string msg)
{
   Print("[剥头皮] ", msg);
}

void LogDebug(string msg)
{
   if(!EnableDebugLogs)
      return;

   datetime now = TimeCurrent();
   if(g_lastDebugLogTime > 0 && (now - g_lastDebugLogTime) < DebugLogIntervalSec)
      return;

   g_lastDebugLogTime = now;
   Print("[剥头皮][调试] ", msg);
}

//+------------------------------------------------------------------+
//| 北京时间日期键                                                    |
//+------------------------------------------------------------------+
int GetCurrentBeijingDayKey()
{
   datetime beijingNow = TimeCurrent() + ServerToBeijingHours * 3600;
   MqlDateTime dt;
   TimeToStruct(beijingNow, dt);
   return (dt.year * 10000 + dt.mon * 100 + dt.day);
}

//+------------------------------------------------------------------+
//| 获取服务器时间窗口                                                |
//+------------------------------------------------------------------+
void GetBeijingDayWindow(int dayKey, datetime &dayStart, datetime &dayEnd)
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

   datetime beijingStart = StructToTime(dt);
   dayStart = beijingStart - ServerToBeijingHours * 3600;
   dayEnd   = dayStart + 24 * 3600;
}

//+------------------------------------------------------------------+
//| 统计日内盈亏                                                      |
//+------------------------------------------------------------------+
double GetDailyPnL(int dayKey)
{
   datetime dayStart = 0, dayEnd = 0;
   GetBeijingDayWindow(dayKey, dayStart, dayEnd);

   double totalPnL = 0.0;

   HistorySelect(dayStart, dayEnd);
   int totalDeals = HistoryDealsTotal();

   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)MagicNumber) continue;

      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT) continue;

      totalPnL += HistoryDealGetDouble(ticket, DEAL_PROFIT)
                + HistoryDealGetDouble(ticket, DEAL_SWAP)
                + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   }

   return totalPnL;
}

//+------------------------------------------------------------------+
//| 统计当前持仓手数                                                  |
//+------------------------------------------------------------------+
double GetOpenLots()
{
   double lots = 0.0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)MagicNumber) continue;

      lots += PositionGetDouble(POSITION_VOLUME);
   }

   return lots;
}

//+------------------------------------------------------------------+
//| 判断大趋势方向                                                    |
//| 返回: 1=多头趋势, -1=空头趋势, 0=无明确趋势                        |
//+------------------------------------------------------------------+
int GetTrendDirection()
{
   if(g_trendEmaHandle == INVALID_HANDLE)
      return 0;

   double emaValue[];
   ArraySetAsSeries(emaValue, true);

   if(CopyBuffer(g_trendEmaHandle, 0, 0, 1, emaValue) < 1)
      return 0;

   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(currentPrice <= 0 || emaValue[0] <= 0)
      return 0;

   double priceDistance = currentPrice - emaValue[0];
   double deviationRatio = MathAbs(priceDistance) / emaValue[0];

   bool hasEnoughDeviation = (!EnableDeviationFilter || deviationRatio >= TrendStrengthRatio);

   // 价格在EMA之上，启用偏离过滤时还需偏离足够大 = 多头趋势
   if(priceDistance > 0 && hasEnoughDeviation)
   {
      LogDebug("多头趋势。价格=" + DoubleToString(currentPrice, _Digits) +
               " EMA=" + DoubleToString(emaValue[0], _Digits) +
               " 偏离=" + DoubleToString(deviationRatio * 100, 2) + "%");
      return 1;
   }

   // 价格在EMA之下，启用偏离过滤时还需偏离足够大 = 空头趋势
   if(priceDistance < 0 && hasEnoughDeviation)
   {
      LogDebug("空头趋势。价格=" + DoubleToString(currentPrice, _Digits) +
               " EMA=" + DoubleToString(emaValue[0], _Digits) +
               " 偏离=" + DoubleToString(deviationRatio * 100, 2) + "%");
      return -1;
   }

   LogDebug("无明确趋势。价格=" + DoubleToString(currentPrice, _Digits) +
            " EMA=" + DoubleToString(emaValue[0], _Digits) +
            " 偏离=" + DoubleToString(deviationRatio * 100, 2) + "%");
   return 0;
}

//+------------------------------------------------------------------+
//| 标准化价格                                                        |
//+------------------------------------------------------------------+
double NormalizePrice(double price)
{
   return NormalizeDouble(price, _Digits);
}

//+------------------------------------------------------------------+
//| 获取最近N根K线的最低点                                            |
//+------------------------------------------------------------------+
double GetRecentLow(int bars)
{
   double lowestLow = DBL_MAX;
   
   for(int i = 1; i <= bars; i++)
   {
      double low = iLow(_Symbol, PERIOD_M5, i);
      if(low < lowestLow)
         lowestLow = low;
   }
   
   return lowestLow;
}

//+------------------------------------------------------------------+
//| 获取最近N根K线的最高点                                            |
//+------------------------------------------------------------------+
double GetRecentHigh(int bars)
{
   double highestHigh = 0;
   
   for(int i = 1; i <= bars; i++)
   {
      double high = iHigh(_Symbol, PERIOD_M5, i);
      if(high > highestHigh)
         highestHigh = high;
   }
   
   return highestHigh;
}

//+------------------------------------------------------------------+
//| 执行做多                                                          |
//+------------------------------------------------------------------+
bool SendBuyOrder()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
   {
      LogDebug("获取报价失败");
      return false;
   }

   double entryPrice = NormalizePrice(tick.ask);

   // 止损=最近N根K线最低点-缓冲
   double recentLow = GetRecentLow(StopLossLookbackBars);
   double stopLoss = NormalizePrice(recentLow - StopLossBufferUsd);
   double takeProfit = NormalizePrice(entryPrice + TakeProfitUsd);

   // 止损距离限制：超过最大值则调整
   double stopLossDistance = entryPrice - stopLoss;
   if(stopLossDistance > MaxStopLossUsd)
   {
      stopLoss = NormalizePrice(entryPrice - MaxStopLossUsd);
      LogInfo("止损距离过大(" + DoubleToString(stopLossDistance, 2) + ")，限制为" + DoubleToString(MaxStopLossUsd, 2) + "美元");
   }

   // 检查止损止盈距离
   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDistance = stopLevel * _Point;

   if((entryPrice - stopLoss) < minDistance || (takeProfit - entryPrice) < minDistance)
   {
      LogDebug("止损止盈距离不足，券商最小距离=" + DoubleToString(minDistance, _Digits));
      return false;
   }

   LogInfo("★ 开多单 入场=" + DoubleToString(entryPrice, _Digits) +
           " 止损=" + DoubleToString(stopLoss, _Digits) +
           " (最近" + IntegerToString(StopLossLookbackBars) + "根低点=" + DoubleToString(recentLow, _Digits) + "-" + DoubleToString(StopLossBufferUsd, 2) + ")" +
           " 止盈=" + DoubleToString(takeProfit, _Digits) +
           " 手数=" + DoubleToString(FixedLots, 2));

   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints(SlippagePoints);

   bool result = g_trade.Buy(FixedLots, _Symbol, entryPrice, stopLoss, takeProfit, "剥头皮多单");

   if(result && g_trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
      LogInfo("多单开仓成功 Ticket=" + IntegerToString((int)g_trade.ResultOrder()));
      g_lastTradeTime = TimeCurrent();
      return true;
   }

   LogInfo("多单开仓失败 RetCode=" + IntegerToString((int)g_trade.ResultRetcode()) +
           " Comment=" + g_trade.ResultComment());
   return false;
}

//+------------------------------------------------------------------+
//| 执行做空                                                          |
//+------------------------------------------------------------------+
bool SendSellOrder()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
   {
      LogDebug("获取报价失败");
      return false;
   }

   double entryPrice = NormalizePrice(tick.bid);

   // 止损=最近N根K线最高点+缓冲
   double recentHigh = GetRecentHigh(StopLossLookbackBars);
   double stopLoss = NormalizePrice(recentHigh + StopLossBufferUsd);
   double takeProfit = NormalizePrice(entryPrice - TakeProfitUsd);

   // 止损距离限制：超过最大值则调整
   double stopLossDistance = stopLoss - entryPrice;
   if(stopLossDistance > MaxStopLossUsd)
   {
      stopLoss = NormalizePrice(entryPrice + MaxStopLossUsd);
      LogInfo("止损距离过大(" + DoubleToString(stopLossDistance, 2) + ")，限制为" + DoubleToString(MaxStopLossUsd, 2) + "美元");
   }

   // 检查止损止盈距离
   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDistance = stopLevel * _Point;

   if((stopLoss - entryPrice) < minDistance || (entryPrice - takeProfit) < minDistance)
   {
      LogDebug("止损止盈距离不足，券商最小距离=" + DoubleToString(minDistance, _Digits));
      return false;
   }

   LogInfo("★ 开空单 入场=" + DoubleToString(entryPrice, _Digits) +
           " 止损=" + DoubleToString(stopLoss, _Digits) +
           " (最近" + IntegerToString(StopLossLookbackBars) + "根高点=" + DoubleToString(recentHigh, _Digits) + "+" + DoubleToString(StopLossBufferUsd, 2) + ")" +
           " 止盈=" + DoubleToString(takeProfit, _Digits) +
           " 手数=" + DoubleToString(FixedLots, 2));

   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints(SlippagePoints);

   bool result = g_trade.Sell(FixedLots, _Symbol, entryPrice, stopLoss, takeProfit, "剥头皮空单");

   if(result && g_trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
      LogInfo("空单开仓成功 Ticket=" + IntegerToString((int)g_trade.ResultOrder()));
      g_lastTradeTime = TimeCurrent();
      return true;
   }

   LogInfo("空单开仓失败 RetCode=" + IntegerToString((int)g_trade.ResultRetcode()) +
           " Comment=" + g_trade.ResultComment());
   return false;
}

//+------------------------------------------------------------------+
//| 检查最近一次平仓是否为止损                                        |
//| 返回: 止损平仓时间，如果没有止损则返回0                           |
//+------------------------------------------------------------------+
datetime CheckLastStopLoss()
{
   // 查询最近10秒内的平仓记录
   datetime checkStart = TimeCurrent() - 10;
   HistorySelect(checkStart, TimeCurrent());
   
   int totalDeals = HistoryDealsTotal();
   
   for(int i = totalDeals - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)MagicNumber) continue;
      
      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT) continue;
      
      // 检查盈亏，小于0说明是止损
      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      if(profit < 0)
      {
         datetime dealTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
         return dealTime;
      }
   }
   
   return 0;
}

//+------------------------------------------------------------------+
//| 检查持续趋势入场条件                                              |
//| 返回: true=可以入场, false=不满足条件                             |
//+------------------------------------------------------------------+
bool CheckSustainedTrendEntry(int trend)
{
   if(g_trendEmaHandle == INVALID_HANDLE)
      return false;

   // 获取EMA值
   double emaValue[];
   ArraySetAsSeries(emaValue, true);
   if(CopyBuffer(g_trendEmaHandle, 0, 0, SustainedTrendBars + 1, emaValue) < SustainedTrendBars + 1)
      return false;

   // 获取最近N根K线的收盘价
   double closePrices[];
   ArraySetAsSeries(closePrices, true);
   if(CopyClose(_Symbol, PERIOD_M5, 0, SustainedTrendBars + 1, closePrices) < SustainedTrendBars + 1)
      return false;

   // 检查最近N根K线收盘价是否都在EMA同侧
   bool allOnSameSide = true;
   for(int i = 1; i <= SustainedTrendBars; i++)
   {
      if(trend == 1)  // 多头：收盘价应该 > EMA
      {
         if(closePrices[i] <= emaValue[i])
         {
            allOnSameSide = false;
            break;
         }
      }
      else  // 空头：收盘价应该 < EMA
      {
         if(closePrices[i] >= emaValue[i])
         {
            allOnSameSide = false;
            break;
         }
      }
   }

   if(!allOnSameSide)
   {
      LogDebug("持续趋势：最近" + IntegerToString(SustainedTrendBars) + "根K线不在EMA同侧");
      return false;
   }

   // 检查当前偏离是否满足最小要求
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double deviationRatio = MathAbs(currentPrice - emaValue[0]) / emaValue[0];

   if(deviationRatio < SustainedTrendMinDeviation)
   {
      LogDebug("持续趋势：偏离不足 当前=" + DoubleToString(deviationRatio * 100, 3) + "% < 阈值=" + DoubleToString(SustainedTrendMinDeviation * 100, 3) + "%");
      return false;
   }

   LogInfo("★ 持续趋势入场！连续" + IntegerToString(SustainedTrendBars) + "根K线在EMA" + (trend == 1 ? "上方" : "下方") +
           " 偏离=" + DoubleToString(deviationRatio * 100, 3) + "%");

   return true;
}

//+------------------------------------------------------------------+
//| 检查回调入场条件                                                   |
//| 返回: true=可以入场, false=等待回调                               |
//+------------------------------------------------------------------+
bool CheckPullbackEntry(int trend)
{
   // 获取EMA值
   double emaValue[];
   ArraySetAsSeries(emaValue, true);
   if(CopyBuffer(g_trendEmaHandle, 0, 0, 1, emaValue) < 1)
      return false;

   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double priceDistance = MathAbs(currentPrice - emaValue[0]);
   double deviationRatio = priceDistance / emaValue[0];

   // 强趋势检查：价格偏离EMA超过StrongTrendRatio，直接入场，不等回调
   if(deviationRatio >= StrongTrendRatio)
   {
      LogInfo("★ 强趋势直接入场！偏离=" + DoubleToString(deviationRatio * 100, 3) + "% > 阈值=" + DoubleToString(StrongTrendRatio * 100, 3) + "%");

      // 重置回调状态
      g_pullbackTrend = 0;
      g_pullbackBarTime = 0;
      g_pullbackMaxDistance = 0;

      return true;
   }

   // 检查是否是新的趋势确认
   datetime currentBarTime = iTime(_Symbol, PERIOD_M5, 0);

   if(g_pullbackTrend != trend || g_pullbackBarTime == 0)
   {
      // 新趋势确认，记录状态
      g_pullbackTrend = trend;
      g_pullbackBarTime = currentBarTime;
      g_pullbackMaxDistance = priceDistance;

      LogDebug("趋势确认。方向=" + (trend == 1 ? "多" : "空") +
               " EMA距离=" + DoubleToString(priceDistance, _Digits) +
               " 偏离=" + DoubleToString(deviationRatio * 100, 3) + "%");
      return false;  // 等待回调
   }

   // 检查是否超过最大等待K线数
   int barsSinceTrend = iBarShift(_Symbol, PERIOD_M5, g_pullbackBarTime);
   if(barsSinceTrend > PullbackMaxBars)
   {
      LogDebug("回调等待超时，重置趋势状态");
      g_pullbackTrend = 0;
      g_pullbackBarTime = 0;
      g_pullbackMaxDistance = 0;
      return false;
   }

   // 检查回调条件
   // 多头：价格回调到EMA距离的PullbackRatio以内
   // 空头：价格反弹到EMA距离的PullbackRatio以内
   double pullbackThreshold = g_pullbackMaxDistance * PullbackRatio;

   if(priceDistance <= pullbackThreshold)
   {
      LogInfo("回调入场条件满足。当前距离=" + DoubleToString(priceDistance, _Digits) +
              " 阈值=" + DoubleToString(pullbackThreshold, _Digits) +
              " 回调比例=" + DoubleToString(PullbackRatio * 100, 0) + "%");

      // 重置状态
      g_pullbackTrend = 0;
      g_pullbackBarTime = 0;
      g_pullbackMaxDistance = 0;

      return true;
   }

   LogDebug("等待回调。当前距离=" + DoubleToString(priceDistance, _Digits) +
            " 阈值=" + DoubleToString(pullbackThreshold, _Digits) +
            " 偏离=" + DoubleToString(deviationRatio * 100, 3) + "%" +
            " 已等待" + IntegerToString(barsSinceTrend) + "根K线");

   return false;
}

//+------------------------------------------------------------------+
//| 检查运行环境                                                      |
//+------------------------------------------------------------------+
bool CheckEnvironment()
{
   if(_Symbol != TradeSymbol)
   {
      if(!g_loggedWrongSymbol)
      {
         LogInfo("配置品种=" + TradeSymbol + "，当前=" + _Symbol + "，暂停交易");
         g_loggedWrongSymbol = true;
      }
      return false;
   }
   g_loggedWrongSymbol = false;

   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      LogDebug("终端不允许交易");
      return false;
   }

   return true;
}

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   g_lastBeijingDayKey = GetCurrentBeijingDayKey();

   // 创建趋势EMA指标
   g_trendEmaHandle = iMA(_Symbol, (ENUM_TIMEFRAMES)TrendEmaTimeframe, TrendEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(g_trendEmaHandle == INVALID_HANDLE)
   {
      LogInfo("创建EMA指标失败");
      return INIT_FAILED;
   }

   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints(SlippagePoints);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);

   LogInfo("========================================");
   LogInfo("剥头皮EA 初始化完成");
   LogInfo("品种=" + _Symbol);
   LogInfo("趋势EMA周期=" + IntegerToString(TrendEmaPeriod) + " 时间框架=M5");
   LogInfo("止盈=" + DoubleToString(TakeProfitUsd, 2) + " 止损缓冲=" + DoubleToString(StopLossBufferUsd, 2) + " 回看" + IntegerToString(StopLossLookbackBars) + "根K线 最大止损=" + DoubleToString(MaxStopLossUsd, 2));
   LogInfo("强趋势阈值=" + DoubleToString(StrongTrendRatio * 100, 3) + "% (偏离超此值直接入场)");
   LogInfo("日内盈利目标=" + DoubleToString(DailyProfitTargetUsd, 2));
   LogInfo("日内亏损限额=" + DoubleToString(DailyLossLimitUsd, 2));
   LogInfo("========================================");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_trendEmaHandle != INVALID_HANDLE)
      IndicatorRelease(g_trendEmaHandle);

   LogInfo("EA卸载 原因=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
//| OnTick - 主逻辑                                                   |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!CheckEnvironment())
      return;

   // 北京时间跨日处理
   int currentDayKey = GetCurrentBeijingDayKey();
   if(currentDayKey != g_lastBeijingDayKey)
   {
      double prevPnL = GetDailyPnL(g_lastBeijingDayKey);
      LogInfo("===== 日终汇总 日期=" + IntegerToString(g_lastBeijingDayKey) +
              " 盈亏=$" + DoubleToString(prevPnL, 2) + " =====");
      g_lastBeijingDayKey = currentDayKey;
   }

   // 检查日内风控
   double todayPnL = GetDailyPnL(currentDayKey);

   if(todayPnL >= DailyProfitTargetUsd)
   {
      LogDebug("已达日内盈利目标 当前=$" + DoubleToString(todayPnL, 2));
      return;
   }

   if(todayPnL <= -DailyLossLimitUsd)
   {
      LogDebug("已达日内亏损限额 当前=$" + DoubleToString(todayPnL, 2));
      return;
   }

   // 检查止损冷却
   datetime lastStopLoss = CheckLastStopLoss();
   if(lastStopLoss > 0 && lastStopLoss > g_lastStopLossTime)
   {
      g_lastStopLossTime = lastStopLoss;
      LogInfo("检测到止损平仓，冷却" + IntegerToString(StopLossCooldownSec) + "秒后才能开新仓");
   }
   
   if(g_lastStopLossTime > 0)
   {
      int secondsSinceStopLoss = (int)(TimeCurrent() - g_lastStopLossTime);
      if(secondsSinceStopLoss < StopLossCooldownSec)
      {
         LogDebug("止损冷却中，还需等待" + IntegerToString(StopLossCooldownSec - secondsSinceStopLoss) + "秒");
         return;
      }
   }

   // 检查交易间隔
   if(TimeCurrent() - g_lastTradeTime < MinTradeIntervalMs / 1000)
      return;

   // 检查持仓 - 空仓检查，有持仓严禁开仓
   double openLots = GetOpenLots();
   if(openLots > 0)
   {
      LogDebug("持仓状态下禁止开仓，当前持仓=" + DoubleToString(openLots, 2) + "手");
      return;
   }

   // 判断趋势方向
   int trend = GetTrendDirection();
   if(trend == 0)
   {
      LogDebug("无明确趋势，不交易");
      
      // 重置回调状态
      g_pullbackTrend = 0;
      g_pullbackBarTime = 0;
      g_pullbackMaxDistance = 0;
      
      return;
   }

   // 检查回调入场条件
   if(CheckPullbackEntry(trend))
   {
      // 回调入场或强趋势入场满足
   }
   else if(CheckSustainedTrendEntry(trend))
   {
      // 持续趋势入场满足
   }
   else
   {
      // 等待回调或持续趋势
      return;
   }

   // 顺势交易
   if(trend == 1)
   {
      // 多头趋势，做多
      SendBuyOrder();
   }
   else if(trend == -1)
   {
      // 空头趋势，做空
      SendSellOrder();
   }
}
//+------------------------------------------------------------------+
