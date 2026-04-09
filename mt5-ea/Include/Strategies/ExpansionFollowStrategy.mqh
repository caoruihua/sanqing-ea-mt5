//+------------------------------------------------------------------+
//|                                       ExpansionFollowStrategy.mqh  |
//|           Sanqing EA MT5 - Expansion Follow Strategy             |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "Common.mqh"

//+------------------------------------------------------------------+
//| Check if Strategy Can Trade                                       |
//+------------------------------------------------------------------+
bool ExpansionFollowCanTrade(SMarketSnapshot &snapshot)
{
   return snapshot.atr14 > 0 &&
          snapshot.medianBody20 > 0 &&
          snapshot.prev3BodyMax > 0 &&
          snapshot.volumeMA20 > 0 &&
          snapshot.high20 > 0 &&
          snapshot.low20 > 0;
}

//+------------------------------------------------------------------+
//| Build Expansion Follow Signal                                      |
//+------------------------------------------------------------------+
bool BuildExpansionFollowSignal(SMarketSnapshot &snapshot, SSignalDecision &signal)
{
   if(!ExpansionFollowCanTrade(snapshot))
      return false;
   
   // Calculate current bar metrics
   double body = MathAbs(snapshot.close - snapshot.open);
   double range = snapshot.high - snapshot.low;
   
   if(body <= 0 || range <= 0)
      return false;
   
   // Check explosive body threshold
   if(body / snapshot.atr14 < EXPANSION_FOLLOW_BODY_ATR_MIN)
      return false;
   
   // Check body vs median
   if(body / snapshot.medianBody20 < EXPANSION_FOLLOW_BODY_MEDIAN_RATIO_MIN)
      return false;
   
   // Check body vs prev3 max
   if(body / snapshot.prev3BodyMax < EXPANSION_FOLLOW_BODY_PREV3_MAX_RATIO_MIN)
      return false;
   
   // Check volume expansion
   if(snapshot.volume / snapshot.volumeMA20 < EXPANSION_FOLLOW_VOLUME_MA_RATIO_MIN)
      return false;
   
   // Check body/range ratio
   if(body / range < EXPANSION_FOLLOW_BODY_RANGE_RATIO_MIN)
      return false;
   
   // Calculate shadows
   double lowerShadow = MathMin(snapshot.open, snapshot.close) - snapshot.low;
   double upperShadow = snapshot.high - MathMax(snapshot.open, snapshot.close);
   
   // Check for bullish signal
   if(snapshot.close > snapshot.open &&
      lowerShadow / body <= 0.25 &&
      snapshot.close > snapshot.high20 + EXPANSION_FOLLOW_BREAKOUT_ATR_BUFFER * snapshot.atr14)
   {
      signal.strategyName = "ExpansionFollow";
      signal.orderType = ORDER_TYPE_BUY;
      signal.entryPrice = snapshot.ask;
      signal.stopLoss = NormalizePrice(snapshot.low + range * EXPANSION_FOLLOW_STOP_LOSS_RANGE_RATIO);
      signal.takeProfit = NormalizePrice(snapshot.ask + EXPANSION_FOLLOW_INITIAL_TP_ATR * snapshot.atr14);
      signal.atrValue = snapshot.atr14;
      signal.lots = InpFixedLots;
      signal.confidenceScore = 1.0;
      signal.signalStrength = body / snapshot.atr14;
      
      // Add conditions
      ArrayResize(signal.conditionsMet, 3);
      signal.conditionsMet[0] = "explosive_body";
      signal.conditionsMet[1] = "volume_expansion";
      signal.conditionsMet[2] = "breakout_up";
      
      LogDetailed("ExpansionFollow BUY signal: Entry=" + DoubleToString(signal.entryPrice, g_digits) +
                   " SL=" + DoubleToString(signal.stopLoss, g_digits) +
                   " TP=" + DoubleToString(signal.takeProfit, g_digits));
      
      return true;
   }
   
   // Check for bearish signal
   if(snapshot.close < snapshot.open &&
      upperShadow / body <= 0.25 &&
      snapshot.close < snapshot.low20 - EXPANSION_FOLLOW_BREAKOUT_ATR_BUFFER * snapshot.atr14)
   {
      signal.strategyName = "ExpansionFollow";
      signal.orderType = ORDER_TYPE_SELL;
      signal.entryPrice = snapshot.bid;
      signal.stopLoss = NormalizePrice(snapshot.high - range * EXPANSION_FOLLOW_STOP_LOSS_RANGE_RATIO);
      signal.takeProfit = NormalizePrice(snapshot.bid - EXPANSION_FOLLOW_INITIAL_TP_ATR * snapshot.atr14);
      signal.atrValue = snapshot.atr14;
      signal.lots = InpFixedLots;
      signal.confidenceScore = 1.0;
      signal.signalStrength = body / snapshot.atr14;
      
      // Add conditions
      ArrayResize(signal.conditionsMet, 3);
      signal.conditionsMet[0] = "explosive_body";
      signal.conditionsMet[1] = "volume_expansion";
      signal.conditionsMet[2] = "breakout_down";
      
      LogDetailed("ExpansionFollow SELL signal: Entry=" + DoubleToString(signal.entryPrice, g_digits) +
                   " SL=" + DoubleToString(signal.stopLoss, g_digits) +
                   " TP=" + DoubleToString(signal.takeProfit, g_digits));
      
      return true;
   }
   
   return false;
}
