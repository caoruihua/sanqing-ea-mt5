//+------------------------------------------------------------------+
//|                                      TrendContinuationStrategy.mqh |
//|           Sanqing EA MT5 - Trend Continuation Strategy            |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "Common.mqh"

//+------------------------------------------------------------------+
//| Check if Strategy Can Trade                                       |
//+------------------------------------------------------------------+
bool TrendContinuationCanTrade(SMarketSnapshot &snapshot)
{
   return snapshot.atr14 > 0 &&
          snapshot.highPrev2 > 0 &&
          snapshot.highPrev3 > 0 &&
          snapshot.lowPrev2 > 0 &&
          snapshot.lowPrev3 > 0;
}

//+------------------------------------------------------------------+
//| Build Trend Continuation Signal                                    |
//+------------------------------------------------------------------+
bool BuildTrendContinuationSignal(SMarketSnapshot &snapshot, SSignalDecision &signal)
{
   if(!TrendContinuationCanTrade(snapshot))
      return false;
   
   double body = MathAbs(snapshot.close - snapshot.open);
   
   // Check body strength
   if(body < TREND_CONTINUATION_ATR_MULTIPLIER_BODY * snapshot.atr14)
      return false;
   
   // Calculate breakout levels
   double breakoutBuffer = TREND_CONTINUATION_ATR_MULTIPLIER_BREAKOUT * snapshot.atr14;
   double upperBreakout = MathMax(snapshot.highPrev2, snapshot.highPrev3) + breakoutBuffer;
   double lowerBreakout = MathMin(snapshot.lowPrev2, snapshot.lowPrev3) - breakoutBuffer;
   
   // Check for bullish breakout continuation
   if(snapshot.emaFast > snapshot.emaSlow &&          // Uptrend
      snapshot.close >= upperBreakout)                // Breakout above resistance
   {
      signal.strategyName = "TrendContinuation";
      signal.orderType = ORDER_TYPE_BUY;
      signal.entryPrice = snapshot.ask;
      signal.stopLoss = NormalizePrice(snapshot.ask - TREND_CONTINUATION_INITIAL_SL_ATR * snapshot.atr14);
      signal.takeProfit = NormalizePrice(snapshot.ask + TREND_CONTINUATION_INITIAL_TP_ATR * snapshot.atr14);
      signal.atrValue = snapshot.atr14;
      signal.lots = InpFixedLots;
      signal.confidenceScore = 1.0;
      signal.signalStrength = 1.0;
      
      // Add conditions
      ArrayResize(signal.conditionsMet, 3);
      signal.conditionsMet[0] = "trend_up";
      signal.conditionsMet[1] = "breakout_up";
      signal.conditionsMet[2] = "body_strength_ok";
      
      LogDetailed("TrendContinuation BUY signal: Entry=" + DoubleToString(signal.entryPrice, g_digits) +
                   " SL=" + DoubleToString(signal.stopLoss, g_digits) +
                   " TP=" + DoubleToString(signal.takeProfit, g_digits));
      
      return true;
   }
   
   // Check for bearish breakout continuation
   if(snapshot.emaFast < snapshot.emaSlow &&          // Downtrend
      snapshot.close <= lowerBreakout)                // Breakout below support
   {
      signal.strategyName = "TrendContinuation";
      signal.orderType = ORDER_TYPE_SELL;
      signal.entryPrice = snapshot.bid;
      signal.stopLoss = NormalizePrice(snapshot.bid + TREND_CONTINUATION_INITIAL_SL_ATR * snapshot.atr14);
      signal.takeProfit = NormalizePrice(snapshot.bid - TREND_CONTINUATION_INITIAL_TP_ATR * snapshot.atr14);
      signal.atrValue = snapshot.atr14;
      signal.lots = InpFixedLots;
      signal.confidenceScore = 1.0;
      signal.signalStrength = 1.0;
      
      // Add conditions
      ArrayResize(signal.conditionsMet, 3);
      signal.conditionsMet[0] = "trend_down";
      signal.conditionsMet[1] = "breakout_down";
      signal.conditionsMet[2] = "body_strength_ok";
      
      LogDetailed("TrendContinuation SELL signal: Entry=" + DoubleToString(signal.entryPrice, g_digits) +
                   " SL=" + DoubleToString(signal.stopLoss, g_digits) +
                   " TP=" + DoubleToString(signal.takeProfit, g_digits));
      
      return true;
   }
   
   return false;
}
