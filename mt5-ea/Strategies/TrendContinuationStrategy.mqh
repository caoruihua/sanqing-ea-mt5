//+------------------------------------------------------------------+
//|                                      TrendContinuationStrategy.mqh |
//|           Sanqing EA MT5 - Trend Continuation Strategy            |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "../Main/Common.mqh"

//+------------------------------------------------------------------+
//| Trend/Chop Filter Thresholds                                      |
//+------------------------------------------------------------------+
#define TREND_CONTINUATION_ADX_THRESHOLD       25.0   // ADX > 25 = trend
#define TREND_CONTINUATION_CHANNEL_WIDTH_MAX   5.0    // > 5 = wide chop

//+------------------------------------------------------------------+
//| Check if Strategy Can Trade                                       |
//+------------------------------------------------------------------+
bool TrendContinuationCanTrade(SMarketSnapshot &snapshot)
{
   // Basic data check - relaxed to only need current bar high/low
   if(!(snapshot.atr14 > 0 &&
        snapshot.high > 0 &&
        snapshot.low > 0))
   {
      LogDebug("TrendContinuation cannot trade: basic data check failed");
      return false;
   }

   // ADX filter: must be in trend (ADX > 25)
   if(snapshot.adx14 < TREND_CONTINUATION_ADX_THRESHOLD)
   {
      LogDebug("TrendContinuation filtered: ADX=" + DoubleToString(snapshot.adx14, 2) +
               " < threshold=" + DoubleToString(TREND_CONTINUATION_ADX_THRESHOLD, 2));
      return false;
   }

   // Channel width filter: avoid wide chop (width < 5x ATR)
   if(snapshot.channelWidthRatio > TREND_CONTINUATION_CHANNEL_WIDTH_MAX)
   {
      LogDebug("TrendContinuation filtered: ChannelWidth=" + DoubleToString(snapshot.channelWidthRatio, 2) +
               " > max=" + DoubleToString(TREND_CONTINUATION_CHANNEL_WIDTH_MAX, 2));
      return false;
   }

   return true;
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
   
   // Calculate breakout levels based on previous 2 bars' high/low (not current bar)
   double breakoutBuffer = TREND_CONTINUATION_ATR_MULTIPLIER_BREAKOUT * snapshot.atr14;
   double upperBreakout = snapshot.highPrev2 + breakoutBuffer;  // Break above previous bars high
   double lowerBreakout = snapshot.lowPrev2 - breakoutBuffer;   // Break below previous bars low

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
