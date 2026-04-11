//+------------------------------------------------------------------+
//|                                                   Indicators.mqh   |
//|                    Sanqing EA MT5 - Technical Indicators          |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "../Main/Common.mqh"

//+------------------------------------------------------------------+
//| Read indicator buffer value from an MQL5 handle                  |
//+------------------------------------------------------------------+
double ReadIndicatorValue(int handle, int bufferIndex, int shift)
{
   if(handle == INVALID_HANDLE)
      return 0.0;

   double values[];
   ArraySetAsSeries(values, true);
   if(CopyBuffer(handle, bufferIndex, shift, 1, values) < 1)
   {
      IndicatorRelease(handle);
      return 0.0;
   }

   double value = values[0];
   IndicatorRelease(handle);
   return value;
}

//+------------------------------------------------------------------+
//| Calculate EMA using MQL5 iMA                                     |
//+------------------------------------------------------------------+
double CalculateEMA(string symbol, int timeframe, int period, int shift = 0)
{
   int handle = iMA(symbol, (ENUM_TIMEFRAMES)timeframe, period, 0, MODE_EMA, PRICE_CLOSE);
   return ReadIndicatorValue(handle, 0, shift);
}

//+------------------------------------------------------------------+
//| Calculate ATR using MQL5 iATR                                    |
//+------------------------------------------------------------------+
double CalculateATR(string symbol, int timeframe, int period, int shift = 0)
{
   int handle = iATR(symbol, (ENUM_TIMEFRAMES)timeframe, period);
   return ReadIndicatorValue(handle, 0, shift);
}

//+------------------------------------------------------------------+
//| Calculate EMA for array of closes                                 |
//+------------------------------------------------------------------+
double CalculateEMAArray(double &closes[], int period)
{
   if(ArraySize(closes) < period)
      return 0.0;
      
   // Use the built-in iMA on the chart
   int handle = iMA(_Symbol, PERIOD_CURRENT, period, 0, MODE_EMA, PRICE_CLOSE);
   return ReadIndicatorValue(handle, 0, 0);
}

//+------------------------------------------------------------------+
//| Get EMA value from history (for prev bars)                        |
//+------------------------------------------------------------------+
double GetEMAPrevValue(string symbol, int timeframe, int period, int barsBack)
{
   if(barsBack < 1)
      barsBack = 1;
      
   int handle = iMA(symbol, (ENUM_TIMEFRAMES)timeframe, period, 0, MODE_EMA, PRICE_CLOSE);
   return ReadIndicatorValue(handle, 0, barsBack);
}

//+------------------------------------------------------------------+
//| Calculate ATR manually from high/low/close arrays                 |
//+------------------------------------------------------------------+
double CalculateATRArray(double &highs[], double &lows[], double &closes[], int period)
{
   int size = ArraySize(closes);
   if(size < period + 1)
      return 0.0;
      
   // Use the built-in iATR
   int handle = iATR(_Symbol, PERIOD_CURRENT, period);
   return ReadIndicatorValue(handle, 0, 0);
}

//+------------------------------------------------------------------+
//| Calculate Simple Moving Average                                   |
//+------------------------------------------------------------------+
double CalculateSMA(double &values[], int period)
{
   int size = ArraySize(values);
   if(size < period)
      return 0.0;
      
   double sum = 0.0;
   for(int i = size - period; i < size; i++)
      sum += values[i];
      
   return sum / period;
}

//+------------------------------------------------------------------+
//| Calculate Median of an array                                      |
//+------------------------------------------------------------------+
double CalculateMedian(double &values[])
{
   int size = ArraySize(values);
   if(size == 0)
      return 0.0;
      
   // Copy to temp array for sorting
   double temp[];
   ArrayCopy(temp, values);
   ArraySort(temp);
   
   int mid = size / 2;
   if(size % 2 == 0)
      return (temp[mid - 1] + temp[mid]) / 2.0;
   else
      return temp[mid];
}

//+------------------------------------------------------------------+
//| Calculate K-line Body Size                                      |
//+------------------------------------------------------------------+
double CalculateBodySize(double open, double close)
{
   return MathAbs(close - open);
}

//+------------------------------------------------------------------+
//| Calculate K-line Range (High - Low)                              |
//+------------------------------------------------------------------+
double CalculateRange(double high, double low)
{
   return high - low;
}

//+------------------------------------------------------------------+
//| Calculate Upper Shadow                                           |
//+------------------------------------------------------------------+
double CalculateUpperShadow(double high, double open, double close)
{
   double bodyTop = MathMax(open, close);
   return high - bodyTop;
}

//+------------------------------------------------------------------+
//| Calculate Lower Shadow                                           |
//+------------------------------------------------------------------+
double CalculateLowerShadow(double low, double open, double close)
{
   double bodyBottom = MathMin(open, close);
   return bodyBottom - low;
}

//+------------------------------------------------------------------+
//| Check if Bullish Candle (Close > Open)                           |
//+------------------------------------------------------------------+
bool IsBullishCandle(double open, double close)
{
   return close > open;
}

//+------------------------------------------------------------------+
//| Check if Bearish Candle (Close < Open)                           |
//+------------------------------------------------------------------+
bool IsBearishCandle(double open, double close)
{
   return close < open;
}

//+------------------------------------------------------------------+
//| Get Spread in Points                                              |
//+------------------------------------------------------------------+
double GetSpreadPoints()
{
   return (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
}

//+------------------------------------------------------------------+
//| Calculate ADX using MQL5 iADX                                    |
//+------------------------------------------------------------------+
double CalculateADX(string symbol, int timeframe, int period, int shift = 0)
{
   int handle = iADX(symbol, (ENUM_TIMEFRAMES)timeframe, period);
   return ReadIndicatorValue(handle, 0, shift);
}

//+------------------------------------------------------------------+
//| Calculate ADX from arrays (wrapper using iADX)                   |
//+------------------------------------------------------------------+
double CalculateADXArray(double &highs[], double &lows[], double &closes[], int period)
{
   // Use the built-in iADX on the chart
   int handle = iADX(_Symbol, PERIOD_CURRENT, period);
   return ReadIndicatorValue(handle, 0, 0);
}

//+------------------------------------------------------------------+
//| Calculate Channel Width Ratio                                     |
//| Formula: (high_20 - low_20) / atr14                              |
//| Returns:                                                           |
//|   < 3: Narrow range (consolidation)                               |
//|   3-5: Normal trend movement                                      |
//|   > 5: Wide chop (false breakout risk)                            |
//+------------------------------------------------------------------+
double CalculateChannelWidthRatio(double high20, double low20, double atr14)
{
   if(high20 <= 0 || low20 <= 0 || atr14 <= 0)
      return 0.0;

   double channelWidth = high20 - low20;
   if(channelWidth <= 0)
      return 0.0;

   return channelWidth / atr14;
}
