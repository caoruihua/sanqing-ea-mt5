//+------------------------------------------------------------------+
//|                                                   Indicators.mqh   |
//|                    Sanqing EA MT5 - Technical Indicators          |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "Common.mqh"

//+------------------------------------------------------------------+
//| Calculate EMA using MQL5 iMA                                     |
//+------------------------------------------------------------------+
double CalculateEMA(string symbol, int timeframe, int period, int shift = 0)
{
   double ema = iMA(symbol, timeframe, period, 0, MODE_EMA, PRICE_CLOSE, shift);
   return ema;
}

//+------------------------------------------------------------------+
//| Calculate ATR using MQL5 iATR                                    |
//+------------------------------------------------------------------+
double CalculateATR(string symbol, int timeframe, int period, int shift = 0)
{
   double atr = iATR(symbol, timeframe, period, shift);
   return atr;
}

//+------------------------------------------------------------------+
//| Calculate EMA for array of closes                                 |
//+------------------------------------------------------------------+
double CalculateEMAArray(double &closes[], int period)
{
   if(ArraySize(closes) < period)
      return 0.0;
      
   // Use the built-in iMA on the chart
   double ema = iMA(_Symbol, PERIOD_CURRENT, period, 0, MODE_EMA, PRICE_CLOSE, 0);
   return ema;
}

//+------------------------------------------------------------------+
//| Get EMA value from history (for prev bars)                        |
//+------------------------------------------------------------------+
double GetEMAPrevValue(string symbol, int timeframe, int period, int barsBack)
{
   if(barsBack < 1)
      barsBack = 1;
      
   double ema = iMA(symbol, timeframe, period, 0, MODE_EMA, PRICE_CLOSE, barsBack);
   return ema;
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
   double atr = iATR(_Symbol, PERIOD_CURRENT, period, 0);
   return atr;
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
