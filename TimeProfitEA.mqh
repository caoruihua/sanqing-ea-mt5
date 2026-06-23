//+------------------------------------------------------------------+
//|                                              TimeProfitEA.mqh     |
//|                        Time Profit EA - Header File               |
//+------------------------------------------------------------------+
#ifndef TIMEPROFIT_EA_MQH
#define TIMEPROFIT_EA_MQH

//--- Constants
#define EA_NAME      "TimeProfitEA"
#define EA_VERSION   "2.00"
#define EA_AUTHOR    "Author"

//--- Enumerations
enum ENUM_SIGNAL
  {
   SIGNAL_NONE = 0,
   SIGNAL_BUY  = 1,
   SIGNAL_SELL = -1
  };

//--- Global variables
int g_trendFastHandle = INVALID_HANDLE;
int g_trendSlowHandle = INVALID_HANDLE;
int g_m5EntryEmaHandle = INVALID_HANDLE;
int g_m5AtrHandle = INVALID_HANDLE;

datetime g_lastBarTime = 0;
datetime g_lastCloseTime = 0;
bool g_hadOpenPosition = false;

//--- Function declarations
bool   IsNewBar();
bool   HasOpenPosition();
int    CheckTrend();
int    CheckEntrySignal();
bool   OpenPosition(int signal);
bool   ClosePosition();
double DistanceToNearestIntegerLevel(double price);
double NextTakeProfitPrice(int signal, double entryPrice);
void   GetIntegerBox(double price, double &lowerLevel, double &upperLevel);
double GetIndicatorValue(int handle, ENUM_TIMEFRAMES timeframe, int shift);
bool   GetLastClosedM5Bar(MqlRates &bar);
bool   GetLastClosedM5Bars(MqlRates &lastBar, MqlRates &previousBar);
bool   IsCooldownActive();
void   SyncClosedPositionState(bool hasPosition);

#endif // TIMEPROFIT_EA_MQH
//+------------------------------------------------------------------+
