//+------------------------------------------------------------------+
//|                                              ContextBuilder.mqh   |
//|                 Sanqing EA MT5 - Market Context Builder           |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "../Main/Common.mqh"
#include "Indicators.mqh"

//+------------------------------------------------------------------+
//| Copy Rates to Arrays                                             |
//+------------------------------------------------------------------+
bool CopyRatesToArrays(string symbol, int timeframe, int count, 
                       double &opens[], double &highs[], double &lows[], 
                       double &closes[], long &volumes[])
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   
   int copied = CopyRates(symbol, (ENUM_TIMEFRAMES)timeframe, 0, count, rates);
   if(copied <= 0)
   {
      LogError("Failed to copy rates, error: " + (string)GetLastError());
      return false;
   }
   
   ArrayResize(opens, copied);
   ArrayResize(highs, copied);
   ArrayResize(lows, copied);
   ArrayResize(closes, copied);
   ArrayResize(volumes, copied);
   
   for(int i = 0; i < copied; i++)
   {
      opens[i] = rates[i].open;
      highs[i] = rates[i].high;
      lows[i] = rates[i].low;
      closes[i] = rates[i].close;
      volumes[i] = rates[i].tick_volume;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Get Current Tick                                                 |
//+------------------------------------------------------------------+
bool GetCurrentTick(string symbol, double &bid, double &ask)
{
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
   {
      LogError("Failed to get tick for " + symbol);
      return false;
   }
   
   bid = tick.bid;
   ask = tick.ask;
   return true;
}

//+------------------------------------------------------------------+
//| Get Last Closed Bar Time                                         |
//+------------------------------------------------------------------+
datetime GetLastClosedBarTime(string symbol, int timeframe)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   
   if(CopyRates(symbol, (ENUM_TIMEFRAMES)timeframe, 0, 2, rates) < 2)
      return 0;
      
   return rates[1].time;  // Index 1 is the last closed bar
}

//+------------------------------------------------------------------+
//| Build Market Snapshot                                            |
//+------------------------------------------------------------------+
bool BuildMarketSnapshot(SMarketSnapshot &snapshot)
{
   // Initialize with input parameters
   snapshot.symbol = g_symbol;
   snapshot.timeframe = Period();
   snapshot.digits = g_digits;
   snapshot.magicNumber = InpMagicNumber;
   
   // Get current tick
   if(!GetCurrentTick(g_symbol, snapshot.bid, snapshot.ask))
      return false;
      
   snapshot.bid = NormalizePrice(snapshot.bid);
   snapshot.ask = NormalizePrice(snapshot.ask);
   
   // Copy rate data (need enough bars for EMA + ATR + historical data)
   int barsNeeded = MathMax(InpEmaSlowPeriod, InpAtrPeriod) + 25;
   
   double opens[], highs[], lows[], closes[];
   long volumes[];
   
   if(!CopyRatesToArrays(g_symbol, PERIOD_CURRENT, barsNeeded, 
                         opens, highs, lows, closes, volumes))
      return false;
   
   // Get last closed bar (index 1, index 0 is current unclosed bar)
   snapshot.lastClosedBarTime = GetLastClosedBarTime(g_symbol, PERIOD_CURRENT);
   
   // Current bar data (index 1 = last closed bar)
   snapshot.close = closes[1];
   snapshot.open = opens[1];
   snapshot.high = highs[1];
   snapshot.low = lows[1];
   snapshot.volume = (double)volumes[1];
   
   // Calculate indicators for closed bar
   snapshot.emaFast = CalculateEMA(g_symbol, PERIOD_CURRENT, InpEmaFastPeriod, 1);
   snapshot.emaSlow = CalculateEMA(g_symbol, PERIOD_CURRENT, InpEmaSlowPeriod, 1);
   snapshot.atr14 = CalculateATR(g_symbol, PERIOD_CURRENT, InpAtrPeriod, 1);
   snapshot.spreadPoints = GetSpreadPoints();
   
   // Historical EMA values (3 bars back)
   snapshot.emaFastPrev3 = GetEMAPrevValue(g_symbol, PERIOD_CURRENT, InpEmaFastPeriod, 4);
   snapshot.emaSlowPrev3 = GetEMAPrevValue(g_symbol, PERIOD_CURRENT, InpEmaSlowPeriod, 4);
   
   // Historical high/low (2 and 3 bars back)
   snapshot.highPrev2 = highs[3];
   snapshot.highPrev3 = highs[4];
   snapshot.lowPrev2 = lows[3];
   snapshot.lowPrev3 = lows[4];

   // Reversal strategy fields (previous bar data)
   snapshot.prevOpen = opens[2];
   snapshot.prevClose = closes[2];
   snapshot.prevHigh = highs[2];
   snapshot.prevLow = lows[2];

   // High/Low of last 3 bars (indices 2,3,4 - excluding current 0,1)
   snapshot.high3 = MathMax(highs[2], MathMax(highs[3], highs[4]));
   snapshot.low3 = MathMin(lows[2], MathMin(lows[3], lows[4]));

   // ExpansionFollow extended fields
   snapshot.medianBody20 = CalculateMedianBody20(opens, closes);
   snapshot.prev3BodyMax = CalculatePrev3BodyMax(opens, closes);
   snapshot.volumeMA20 = CalculateVolumeMA20(volumes);
   snapshot.high20 = CalculateHigh20(highs);
   snapshot.low20 = CalculateLow20(lows);

   // Trend/Chop filtering fields
   snapshot.adx14 = CalculateADX(g_symbol, PERIOD_CURRENT, 14, 1);
   snapshot.channelWidthRatio = CalculateChannelWidthRatio(snapshot.high20, snapshot.low20, snapshot.atr14);

   // Sprint detection fields (2-hour window)
   snapshot.close24Ago = CalculateClose24Ago(closes);
   snapshot.priceMove24 = CalculatePriceMove24(closes);
   snapshot.high24 = CalculateHigh24(highs);
   snapshot.low24 = CalculateLow24(lows);

   LogDebug("Snapshot built: EMA_F=" + DoubleToString(snapshot.emaFast, g_digits) +
            " EMA_S=" + DoubleToString(snapshot.emaSlow, g_digits) +
            " ATR=" + DoubleToString(snapshot.atr14, g_digits) +
            " ADX=" + DoubleToString(snapshot.adx14, 2) +
            " CH_WR=" + DoubleToString(snapshot.channelWidthRatio, 2));
   
   return true;
}

//+------------------------------------------------------------------+
//| Calculate Median Body of Last 20 Bars (excluding current)        |
//+------------------------------------------------------------------+
double CalculateMedianBody20(double &opens[], double &closes[])
{
   int size = ArraySize(opens);
   if(size < 22)
      return 0.0;
   
   double bodies[];
   ArrayResize(bodies, 20);
   
   // Calculate bodies for bars 2 to 21 (excluding current bar 1 and 0)
   for(int i = 0; i < 20; i++)
      bodies[i] = MathAbs(closes[i + 2] - opens[i + 2]);
   
   return CalculateMedian(bodies);
}

//+------------------------------------------------------------------+
//| Calculate Max Body of Last 3 Bars (excluding current)           |
//+------------------------------------------------------------------+
double CalculatePrev3BodyMax(double &opens[], double &closes[])
{
   int size = ArraySize(opens);
   if(size < 5)
      return 0.0;
   
   double maxBody = 0.0;
   // Bars 2, 3, 4 (excluding current bar 1 and 0)
   for(int i = 2; i <= 4; i++)
   {
      double body = MathAbs(closes[i] - opens[i]);
      if(body > maxBody)
         maxBody = body;
   }
   
   return maxBody;
}

//+------------------------------------------------------------------+
//| Calculate Volume MA of Last 20 Bars (excluding current)          |
//+------------------------------------------------------------------+
double CalculateVolumeMA20(long &volumes[])
{
   int size = ArraySize(volumes);
   if(size < 22)
      return 0.0;
   
   double sum = 0.0;
   // Bars 2 to 21 (excluding current bar 1 and 0)
   for(int i = 2; i <= 21; i++)
      sum += (double)volumes[i];
   
   return sum / 20.0;
}

//+------------------------------------------------------------------+
//| Calculate High of Last 20 Bars (excluding current)               |
//+------------------------------------------------------------------+
double CalculateHigh20(double &highs[])
{
   int size = ArraySize(highs);
   if(size < 22)
      return 0.0;
   
   double maxHigh = 0.0;
   // Bars 2 to 21 (excluding current bar 1 and 0)
   for(int i = 2; i <= 21; i++)
   {
      if(highs[i] > maxHigh)
         maxHigh = highs[i];
   }
   
   return maxHigh;
}

//+------------------------------------------------------------------+
//| Calculate Low of Last 20 Bars (excluding current)                |
//+------------------------------------------------------------------+
double CalculateLow20(double &lows[])
{
   int size = ArraySize(lows);
   if(size < 22)
      return 0.0;
   
   double minLow = DBL_MAX;
   // Bars 2 to 21 (excluding current bar 1 and 0)
   for(int i = 2; i <= 21; i++)
   {
      if(lows[i] < minLow)
         minLow = lows[i];
   }
   
   return minLow;
}

//+------------------------------------------------------------------+
//| Calculate Close 24 Bars Ago                                      |
//+------------------------------------------------------------------+
double CalculateClose24Ago(double &closes[])
{
   int size = ArraySize(closes);
   if(size < 26)
      return 0.0;
   
   return closes[25];  // Index 25 = 24 bars before current closed bar
}

//+------------------------------------------------------------------+
//| Calculate Price Move in 24 Bars                                  |
//+------------------------------------------------------------------+
double CalculatePriceMove24(double &closes[])
{
   int size = ArraySize(closes);
   if(size < 26)
      return 0.0;
   
   // close[1] is last closed bar, close[25] is 24 bars before
   return closes[1] - closes[25];
}

//+------------------------------------------------------------------+
//| Calculate High of Last 24 Bars (excluding current)               |
//+------------------------------------------------------------------+
double CalculateHigh24(double &highs[])
{
   int size = ArraySize(highs);
   if(size < 26)
      return 0.0;
   
   double maxHigh = 0.0;
   // Bars 1 to 24 (excluding current bar 0)
   for(int i = 1; i <= 24; i++)
   {
      if(highs[i] > maxHigh)
         maxHigh = highs[i];
   }
   
   return maxHigh;
}

//+------------------------------------------------------------------+
//| Calculate Low of Last 24 Bars (excluding current)                |
//+------------------------------------------------------------------+
double CalculateLow24(double &lows[])
{
   int size = ArraySize(lows);
   if(size < 26)
      return DBL_MAX;
   
   double minLow = DBL_MAX;
   // Bars 1 to 24 (excluding current bar 0)
   for(int i = 1; i <= 24; i++)
   {
      if(lows[i] < minLow)
         minLow = lows[i];
   }
   
   return minLow;
}

//+------------------------------------------------------------------+
//| Check Trend Direction                                           |
//+------------------------------------------------------------------+
bool IsUptrend(SMarketSnapshot &snapshot)
{
   return snapshot.emaFast > snapshot.emaSlow &&
          snapshot.emaFast > snapshot.emaFastPrev3 &&
          snapshot.emaSlow > snapshot.emaSlowPrev3;
}

bool IsDowntrend(SMarketSnapshot &snapshot)
{
   return snapshot.emaFast < snapshot.emaSlow &&
          snapshot.emaFast < snapshot.emaFastPrev3 &&
          snapshot.emaSlow < snapshot.emaSlowPrev3;
}
