//+------------------------------------------------------------------+
//|                                            PullbackStrategy.mqh    |
//|              Sanqing EA MT5 - Pullback Strategy                  |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "../Main/Common.mqh"
#include "../Core/ContextBuilder.mqh"

//+------------------------------------------------------------------+
//| Pullback ADX Threshold                                            |
//+------------------------------------------------------------------+
#define PULLBACK_ADX_THRESHOLD       25.0   // ADX > 25 = trend

//+------------------------------------------------------------------+
//| Check if Strategy Can Trade                                       |
//+------------------------------------------------------------------+
bool PullbackCanTrade(SMarketSnapshot &snapshot)
{
   if(snapshot.atr14 <= 0)
      return false;
   
   // ADX filter: must be in trend (ADX > 25)
   if(snapshot.adx14 < PULLBACK_ADX_THRESHOLD)
   {
      LogDebug("回调过滤: ADX=" + DoubleToString(snapshot.adx14, 2) +
               " < 阈值=" + DoubleToString(PULLBACK_ADX_THRESHOLD, 2));
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Build Pullback Signal                                              |
//+------------------------------------------------------------------+
bool BuildPullbackSignal(SMarketSnapshot &snapshot, SSignalDecision &signal)
{
   if(!PullbackCanTrade(snapshot))
      return false;
   
   double body = MathAbs(snapshot.close - snapshot.open);
   if(body <= 0)
      return false;
   
   double tolerance = PULLBACK_EMA_TOLERANCE_ATR * snapshot.atr14;
   double lowerShadow = MathMin(snapshot.open, snapshot.close) - snapshot.low;
   double upperShadow = snapshot.high - MathMax(snapshot.open, snapshot.close);
   
   // Check for bullish pullback
   if(snapshot.emaFast > snapshot.emaSlow &&                       // M5 Uptrend
      IsH1Uptrend(snapshot) &&                                     // H1 Uptrend filter
      snapshot.low <= snapshot.emaFast + tolerance &&              // Pulled back to EMA
      snapshot.close > snapshot.emaFast &&                         // Reclaimed EMA
      snapshot.close > snapshot.open &&                            // Bullish candle
      lowerShadow >= 0.5 * body)                                   // Lower shadow >= 50% body
   {
      signal.strategyName = "Pullback";
      signal.orderType = ORDER_TYPE_BUY;
      signal.entryPrice = snapshot.ask;
      signal.stopLoss = NormalizePrice(snapshot.ask - PULLBACK_INITIAL_SL_ATR * snapshot.atr14);
      signal.takeProfit = NormalizePrice(snapshot.ask + PULLBACK_INITIAL_TP_ATR * snapshot.atr14);
      signal.atrValue = snapshot.atr14;
      signal.lots = InpFixedLots;
      signal.confidenceScore = 1.0;
      signal.signalStrength = 1.0;
      
      // Add conditions
      ArrayResize(signal.conditionsMet, 3);
      signal.conditionsMet[0] = "trend_up";
      signal.conditionsMet[1] = "ema_reclaim";
      signal.conditionsMet[2] = "bullish_rejection";
      
      LogDetailed("回调做多信号: 入场=" + DoubleToString(signal.entryPrice, g_digits) +
                   " 止损=" + DoubleToString(signal.stopLoss, g_digits) +
                   " 止盈=" + DoubleToString(signal.takeProfit, g_digits));
      
      return true;
   }
   
   // Check for bearish pullback
   if(snapshot.emaFast < snapshot.emaSlow &&                       // M5 Downtrend
      IsH1Downtrend(snapshot) &&                                   // H1 Downtrend filter
      snapshot.high >= snapshot.emaFast - tolerance &&             // Pulled back to EMA
      snapshot.close < snapshot.emaFast &&                          // Dropped below EMA
      snapshot.close < snapshot.open &&                            // Bearish candle
      upperShadow >= 0.5 * body)                                  // Upper shadow >= 50% body
   {
      signal.strategyName = "Pullback";
      signal.orderType = ORDER_TYPE_SELL;
      signal.entryPrice = snapshot.bid;
      signal.stopLoss = NormalizePrice(snapshot.bid + PULLBACK_INITIAL_SL_ATR * snapshot.atr14);
      signal.takeProfit = NormalizePrice(snapshot.bid - PULLBACK_INITIAL_TP_ATR * snapshot.atr14);
      signal.atrValue = snapshot.atr14;
      signal.lots = InpFixedLots;
      signal.confidenceScore = 1.0;
      signal.signalStrength = 1.0;
      
      // Add conditions
      ArrayResize(signal.conditionsMet, 3);
      signal.conditionsMet[0] = "trend_down";
      signal.conditionsMet[1] = "ema_reject";
      signal.conditionsMet[2] = "bearish_rejection";
      
      LogDetailed("回调做空信号: 入场=" + DoubleToString(signal.entryPrice, g_digits) +
                   " 止损=" + DoubleToString(signal.stopLoss, g_digits) +
                   " 止盈=" + DoubleToString(signal.takeProfit, g_digits));
      
      return true;
   }
   
   return false;
}