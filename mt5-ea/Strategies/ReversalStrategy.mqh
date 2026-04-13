//+------------------------------------------------------------------+
//|                                           ReversalStrategy.mqh    |
//|              Sanqing EA MT5 - Reversal Strategy                   |
//|                   Dark Cloud Cover + Long Shadows                 |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "../Main/Common.mqh"

//+------------------------------------------------------------------+
//| Reversal Strategy Parameters                                      |
//+------------------------------------------------------------------+
#define REVERSAL_EMA_TOLERANCE_ATR         0.5    // Not used in current logic
#define REVERSAL_SHADOW_BODY_RATIO_MIN     1.5    // Shadow vs body ratio
#define REVERSAL_DARKCLOUD_COVERAGE_MIN    0.5    // Dark cloud penetration 50%
#define REVERSAL_STOP_BUFFER_POINTS        3.0    // Stop loss buffer in points
#define REVERSAL_SHADOW_OPPOSITE_RATIO     3.0    // Main shadow must be 3x opposite shadow

//+------------------------------------------------------------------+
//| Check if Strategy Can Trade                                       |
//+------------------------------------------------------------------+
bool ReversalCanTrade(SMarketSnapshot &snapshot)
{
   // Basic data check
   if(!(snapshot.atr14 > 0 &&
        snapshot.prevOpen > 0 &&
        snapshot.prevClose > 0 &&
        snapshot.prevHigh > 0 &&
        snapshot.high3 > 0 &&
        snapshot.low3 > 0 &&
        snapshot.emaFast > 0 &&
        snapshot.emaSlow > 0 &&
        snapshot.emaFastPrev3 > 0))
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Check if Has Significant Move (Sprint Detection)                 |
//+------------------------------------------------------------------+
bool HasSignificantMove(SMarketSnapshot &snapshot)
{
   // Check if price move data is valid
   if(snapshot.priceMove24 == 0.0 || snapshot.atr14 <= 0)
      return false;
   
   double threshold = snapshot.atr14 * REVERSAL_MOVE_ATR_MULTIPLIER;
   
   // Check for significant up move (potential bearish reversal)
   if(snapshot.priceMove24 >= threshold)
      return true;
   
   // Check for significant down move (potential bullish reversal)
   if(snapshot.priceMove24 <= -threshold)
      return true;
   
   return false;
}

//+------------------------------------------------------------------+
//| Check if Uptrend (for bearish reversal)                           |
//+------------------------------------------------------------------+
bool IsReversalUptrend(SMarketSnapshot &snapshot)
{
   return snapshot.close > snapshot.emaFast &&
          snapshot.emaFast > snapshot.emaFastPrev3;
}

//+------------------------------------------------------------------+
//| Check if Downtrend (for bullish reversal)                         |
//+------------------------------------------------------------------+
bool IsReversalDowntrend(SMarketSnapshot &snapshot)
{
   return snapshot.close < snapshot.emaFast &&
          snapshot.emaFast < snapshot.emaFastPrev3;
}

//+------------------------------------------------------------------+
//| Detect Dark Cloud Cover Pattern                                   |
//+------------------------------------------------------------------+
bool DetectDarkCloudCover(SMarketSnapshot &snapshot)
{
   double prevOpen = snapshot.prevOpen;
   double prevClose = snapshot.prevClose;
   double prevHigh = snapshot.prevHigh;
   double currOpen = snapshot.open;
   double currClose = snapshot.close;

   // 1. Previous bar must be bullish (close > open)
   if(prevClose <= prevOpen)
      return false;

   // 2. Current bar must gap up (open > prevHigh)
   if(currOpen <= prevHigh)
      return false;

   // 3. Current bar must be bearish (close < open)
   if(currClose >= currOpen)
      return false;

   // 4. Calculate penetration depth
   double prevBody = prevClose - prevOpen;
   if(prevBody <= 0)
      return false;

   double penetration = (prevClose - currClose) / prevBody;

   // Must penetrate at least 50%
   return penetration >= REVERSAL_DARKCLOUD_COVERAGE_MIN;
}

//+------------------------------------------------------------------+
//| Detect Long Upper Shadow (bearish reversal)                       |
//+------------------------------------------------------------------+
bool DetectLongUpperShadow(SMarketSnapshot &snapshot)
{
   double openPrice = snapshot.open;
   double closePrice = snapshot.close;
   double high = snapshot.high;
   double low = snapshot.low;

   // Calculate body
   double body = MathAbs(closePrice - openPrice);
   if(body <= 0)
      return false;

   // Calculate shadows
   double upperShadow = high - MathMax(openPrice, closePrice);
   double lowerShadow = MathMin(openPrice, closePrice) - low;

   // Upper shadow must be >= 1.5x body
   if(upperShadow < body * REVERSAL_SHADOW_BODY_RATIO_MIN)
      return false;

   // Upper shadow must dominate (3x lower shadow) to exclude doji
   if(lowerShadow > 0 && upperShadow < lowerShadow * REVERSAL_SHADOW_OPPOSITE_RATIO)
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Detect Long Lower Shadow (bullish reversal)                       |
//+------------------------------------------------------------------+
bool DetectLongLowerShadow(SMarketSnapshot &snapshot)
{
   double openPrice = snapshot.open;
   double closePrice = snapshot.close;
   double high = snapshot.high;
   double low = snapshot.low;

   // Calculate body
   double body = MathAbs(closePrice - openPrice);
   if(body <= 0)
      return false;

   // Calculate shadows
   double lowerShadow = MathMin(openPrice, closePrice) - low;
   double upperShadow = high - MathMax(openPrice, closePrice);

   // Lower shadow must be >= 1.5x body
   if(lowerShadow < body * REVERSAL_SHADOW_BODY_RATIO_MIN)
      return false;

   // Lower shadow must dominate (3x upper shadow) to exclude doji
   if(upperShadow > 0 && lowerShadow < upperShadow * REVERSAL_SHADOW_OPPOSITE_RATIO)
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Build Reversal Signal                                             |
//+------------------------------------------------------------------+
bool BuildReversalSignal(SMarketSnapshot &snapshot, SSignalDecision &signal)
{
   if(!ReversalCanTrade(snapshot))
      return false;

   // NEW: Hard prerequisite - must have significant move (sprint detection)
   if(!HasSignificantMove(snapshot))
   {
      LogDebug("Reversal: No significant move detected, skipping signal");
      return false;
   }

   // Check if we have high24 and low24 for SL calculation
   if(snapshot.high24 <= 0 || snapshot.low24 <= 0)
      return false;

   string conditionMet = "";
   ENUM_ORDER_TYPE orderType = (ENUM_ORDER_TYPE)0;
   double entryPrice = 0.0;
   double stopLoss = 0.0;
   double takeProfit = 0.0;

   // Check Dark Cloud Cover (bearish reversal after significant up move)
   if(snapshot.priceMove24 > 0 && DetectDarkCloudCover(snapshot))
   {
      conditionMet = "dark_cloud_cover";
      orderType = ORDER_TYPE_SELL;
      entryPrice = snapshot.bid;
      // NEW: SL = high24 + 6 dollars
      stopLoss = snapshot.high24 + REVERSAL_STOP_BUFFER_DOLLAR;
      // NEW: TP = entry - ATR * 2.5
      takeProfit = entryPrice - snapshot.atr14 * REVERSAL_TP_ATR_MULTIPLIER;
   }
   // Check Long Upper Shadow (bearish reversal after significant up move)
   else if(snapshot.priceMove24 > 0 && DetectLongUpperShadow(snapshot))
   {
      conditionMet = "long_upper_shadow";
      orderType = ORDER_TYPE_SELL;
      entryPrice = snapshot.bid;
      // NEW: SL = high24 + 6 dollars
      stopLoss = snapshot.high24 + REVERSAL_STOP_BUFFER_DOLLAR;
      // NEW: TP = entry - ATR * 2.5
      takeProfit = entryPrice - snapshot.atr14 * REVERSAL_TP_ATR_MULTIPLIER;
   }
   // Check Long Lower Shadow (bullish reversal after significant down move)
   else if(snapshot.priceMove24 < 0 && DetectLongLowerShadow(snapshot))
   {
      conditionMet = "long_lower_shadow";
      orderType = ORDER_TYPE_BUY;
      entryPrice = snapshot.ask;
      // NEW: SL = low24 - 6 dollars
      stopLoss = snapshot.low24 - REVERSAL_STOP_BUFFER_DOLLAR;
      // NEW: TP = entry + ATR * 2.5
      takeProfit = entryPrice + snapshot.atr14 * REVERSAL_TP_ATR_MULTIPLIER;
   }
   else
   {
      return false;
   }

   // Fill signal structure
   signal.strategyName = "Reversal";
   signal.orderType = orderType;
   signal.entryPrice = entryPrice;
   signal.stopLoss = NormalizePrice(stopLoss);
   signal.takeProfit = NormalizePrice(takeProfit);
   signal.atrValue = snapshot.atr14;
   signal.lots = InpFixedLots;
   signal.confidenceScore = 1.0;
   signal.signalStrength = 1.0;

   // Add conditions
   ArrayResize(signal.conditionsMet, 1);
   signal.conditionsMet[0] = conditionMet;

   LogDetailed("Reversal " + (orderType == ORDER_TYPE_BUY ? "BUY" : "SELL") +
                " signal: Entry=" + DoubleToString(signal.entryPrice, g_digits) +
                " SL=" + DoubleToString(signal.stopLoss, g_digits) +
                " TP=" + DoubleToString(signal.takeProfit, g_digits) +
                " Move24=" + DoubleToString(snapshot.priceMove24, g_digits) +
                " Condition=" + conditionMet);

   return true;
}
//+------------------------------------------------------------------+
