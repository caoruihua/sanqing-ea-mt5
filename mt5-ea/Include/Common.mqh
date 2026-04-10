//+------------------------------------------------------------------+
//|                                                      Common.mqh   |
//|                    Sanqing EA MT5 - Core Constants & Structures  |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

//+------------------------------------------------------------------+
//| Constants - Default Parameters                                    |
//+------------------------------------------------------------------+
#define DEFAULT_MAGIC_NUMBER           20260313
#define DEFAULT_SYMBOL                 "XAUUSD"
#define DEFAULT_TIMEFRAME              PERIOD_M5
#define DEFAULT_DIGITS                 2

// Logging
#define DEFAULT_LOG_LEVEL              1
#define LOG_LEVEL_OFF                  0
#define LOG_LEVEL_MINIMAL              1
#define LOG_LEVEL_DETAILED             2
#define LOG_LEVEL_DEBUG                3

// Daily Risk
#define DEFAULT_MAX_TRADES_PER_DAY     30
#define DEFAULT_DAILY_PROFIT_STOP_USD  50.0

// Trading
#define DEFAULT_FIXED_LOTS             0.01
#define DEFAULT_SLIPPAGE               30
#define DEFAULT_MAX_RETRIES            6

// Indicators
#define DEFAULT_EMA_FAST_PERIOD        9
#define DEFAULT_EMA_SLOW_PERIOD        21
#define DEFAULT_ATR_PERIOD             14

// Volatility Filter
#define DEFAULT_LOW_VOL_ATR_POINTS_FLOOR      300.0
#define DEFAULT_LOW_VOL_ATR_SPREAD_RATIO_FLOOR 3.0

// TrendContinuation Parameters
#define TREND_CONTINUATION_ATR_MULTIPLIER_BREAKOUT  0.20
#define TREND_CONTINUATION_ATR_MULTIPLIER_BODY      0.35
#define TREND_CONTINUATION_INITIAL_SL_ATR           1.2
#define TREND_CONTINUATION_INITIAL_TP_ATR           2.0

// Pullback Parameters
#define PULLBACK_EMA_TOLERANCE_ATR       0.15
#define PULLBACK_INITIAL_SL_ATR          1.2
#define PULLBACK_INITIAL_TP_ATR         2.0

// ExpansionFollow Parameters
#define EXPANSION_FOLLOW_BODY_ATR_MIN            4.0
#define EXPANSION_FOLLOW_BODY_MEDIAN_RATIO_MIN   2.20
#define EXPANSION_FOLLOW_BODY_PREV3_MAX_RATIO_MIN 1.80
#define EXPANSION_FOLLOW_VOLUME_MA_RATIO_MIN     1.90
#define EXPANSION_FOLLOW_BODY_RANGE_RATIO_MIN    0.65
#define EXPANSION_FOLLOW_BREAKOUT_ATR_BUFFER      0.10
#define EXPANSION_FOLLOW_STOP_LOSS_RANGE_RATIO   0.6
#define EXPANSION_FOLLOW_INITIAL_TP_ATR          2.0

// Protection Engine Parameters
#define PROTECTION_STAGE1_ATR_MULTIPLIER      1.0
#define PROTECTION_STAGE1_SL_BUFFER_ATR       0.1
#define PROTECTION_STAGE1_TP_ATR              2.5
#define PROTECTION_STAGE2_ATR_MULTIPLIER      1.5
#define PROTECTION_STAGE2_SL_DISTANCE_ATR     0.9
#define PROTECTION_STAGE2_TP_DISTANCE_ATR     0.8

// State File
#define STATE_FILE_NAME            "sanqing_ea_state.json"

//+------------------------------------------------------------------+
//| Enums                                                            |
//+------------------------------------------------------------------+
enum ENUM_ORDER_TYPE
{
   ORDER_TYPE_BUY = 0,
   ORDER_TYPE_SELL = 1
};

enum ENUM_PROTECTION_STAGE
{
   PROTECTION_NONE = 0,
   PROTECTION_STAGE1 = 1,
   PROTECTION_STAGE2 = 2
};

enum ENUM_REJECTION_REASON
{
   REJECT_NONE = 0,
   REJECT_NOT_NEW_CLOSED_BAR,
   REJECT_DAILY_LOCKED,
   REJECT_MAX_TRADES_EXCEEDED,
   REJECT_EXISTING_POSITION,
   REJECT_LOW_VOLATILITY,
   REJECT_STRATEGY_CANNOT_TRADE,
   REJECT_NO_STRATEGY_SIGNAL,
   REJECT_INSUFFICIENT_BARS
};

//+------------------------------------------------------------------+
//| MarketSnapshot Structure                                         |
//+------------------------------------------------------------------+
struct SMarketSnapshot
{
   string     symbol;                 // Trading symbol
   int        timeframe;              // Timeframe (minutes)
   int        digits;                 // Price digits
   int        magicNumber;            // Magic number
   
   double     bid;                    // Current bid
   double     ask;                    // Current ask
   
   double     emaFast;                // EMA fast value
   double     emaSlow;                // EMA slow value
   double     atr14;                  // ATR(14) value
   double     spreadPoints;            // Spread in points
   
   datetime   lastClosedBarTime;      // Last closed bar time
   
   // Current bar data
   double     close;                  // Close price
   double     open;                   // Open price
   double     high;                   // High price
   double     low;                    // Low price
   double     volume;                 // Volume
   
   // Historical data for trend calculation
   double     emaFastPrev3;           // EMA fast 3 bars ago
   double     emaSlowPrev3;           // EMA slow 3 bars ago
   double     highPrev2;              // High 2 bars ago
   double     highPrev3;              // High 3 bars ago
   double     lowPrev2;               // Low 2 bars ago
   double     lowPrev3;               // Low 3 bars ago
   
   // ExpansionFollow extended fields
   double     medianBody20;           // Median body of last 20 bars
   double     prev3BodyMax;            // Max body of last 3 bars
   double     volumeMA20;             // Volume MA of last 20 bars
   double     high20;                 // High of last 20 bars
   double     low20;                  // Low of last 20 bars
};

//+------------------------------------------------------------------+
//| SignalDecision Structure                                         |
//+------------------------------------------------------------------+
struct SSignalDecision
{
   string     strategyName;           // Strategy name
   ENUM_ORDER_TYPE orderType;         // BUY or SELL
   double     entryPrice;             // Entry price
   double     stopLoss;               // Stop loss
   double     takeProfit;             // Take profit
   double     atrValue;               // ATR value used
   double     lots;                   // Lot size
   
   double     confidenceScore;         // Confidence score (0.0-1.0)
   double     signalStrength;          // Relative strength indicator
   string     conditionsMet[];         // Conditions that were met
};

//+------------------------------------------------------------------+
//| TradeIntent Structure                                            |
//+------------------------------------------------------------------+
struct STradeIntent
{
   SSignalDecision signal;             // Signal decision
   string         actionId;           // Unique action identifier
   int            slippage;           // Slippage in points
   string         comment;             // Order comment
   datetime       timestamp;           // Timestamp
};

//+------------------------------------------------------------------+
//| ProtectionState Structure                                        |
//+------------------------------------------------------------------+
struct SProtectionState
{
   ENUM_PROTECTION_STAGE protectionStage;      // Current protection stage
   double     entryPrice;             // Entry price
   double     entryAtr;               // Entry ATR value
   double     highestCloseSinceEntry;  // Highest close since entry
   double     lowestCloseSinceEntry;   // Lowest close since entry
   bool       trailingActive;         // Trailing active flag
   
   datetime   stage1ActivatedAt;      // Stage 1 activation time
   datetime   stage2ActivatedAt;      // Stage 2 activation time
};

//+------------------------------------------------------------------+
//| RuntimeState Structure                                           |
//+------------------------------------------------------------------+
struct SRuntimeState
{
   string     dayKey;                 // Server day key (YYYY.MM.DD)
   bool       dailyLocked;            // Daily lock status
   double     dailyClosedProfit;       // Daily closed profit
   int        tradesToday;             // Trades today count
   
   datetime   lastEntryBarTime;       // Last entry bar time
   datetime   lastProcessedBarTime;    // Last processed bar time
   
   // Position management
   int        positionTicket;          // Current position ticket
   int        lastPositionTicket;      // Last position ticket (for detection)
   string     positionStrategy;        // Current position strategy name
   
   // Entry tracking
   double     entryPrice;              // Entry price
   double     entryAtr;               // Entry ATR
   double     highestCloseSinceEntry;  // Highest close since entry
   double     lowestCloseSinceEntry;   // Lowest close since entry
   bool       trailingActive;          // Trailing active flag
   
   // Protection state
   ENUM_PROTECTION_STAGE protectionStage;
   datetime   stage1ActivatedAt;
   datetime   stage2ActivatedAt;
};

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
input group "=== Trading ==="
input int      InpMagicNumber = DEFAULT_MAGIC_NUMBER;          // Magic Number
input double    InpFixedLots = DEFAULT_FIXED_LOTS;             // Fixed Lots
input int      InpSlippage = DEFAULT_SLIPPAGE;                 // Slippage (points)
input int      InpMaxRetries = DEFAULT_MAX_RETRIES;            // Max Retries

input group "=== Indicators ==="
input int      InpEmaFastPeriod = DEFAULT_EMA_FAST_PERIOD;     // EMA Fast Period
input int      InpEmaSlowPeriod = DEFAULT_EMA_SLOW_PERIOD;     // EMA Slow Period
input int      InpAtrPeriod = DEFAULT_ATR_PERIOD;              // ATR Period

input group "=== Risk Control ==="
input int      InpMaxTradesPerDay = DEFAULT_MAX_TRADES_PER_DAY; // Max Trades Per Day
input double    InpDailyProfitStopUsd = DEFAULT_DAILY_PROFIT_STOP_USD; // Daily Profit Stop (USD)

input group "=== Volatility Filter ==="
input double    InpLowVolAtrPointsFloor = DEFAULT_LOW_VOL_ATR_POINTS_FLOOR;     // Low Vol ATR Points Floor
input double    InpLowVolAtrSpreadRatioFloor = DEFAULT_LOW_VOL_ATR_SPREAD_RATIO_FLOOR; // Low Vol ATR/Spread Ratio Floor

input group "=== Logging ==="
input int      InpLogLevel = DEFAULT_LOG_LEVEL;                // Log Level (0=Off, 1=Minimal, 2=Detailed, 3=Debug)

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
string  g_symbol = DEFAULT_SYMBOL;
int     g_digits = DEFAULT_DIGITS;
double  g_point = 0.01;  // Will be initialized in OnInit

//+------------------------------------------------------------------+
//| Logging Functions                                                |
//+------------------------------------------------------------------+
void LogInfo(string message)
{
   if(InpLogLevel >= LOG_LEVEL_MINIMAL)
      Print("[INFO] ", message);
}

void LogDetailed(string message)
{
   if(InpLogLevel >= LOG_LEVEL_DETAILED)
      Print("[DETAILED] ", message);
}

void LogDebug(string message)
{
   if(InpLogLevel >= LOG_LEVEL_DEBUG)
      Print("[DEBUG] ", message);
}

void LogError(string message)
{
   Print("[ERROR] ", message);
}

//+------------------------------------------------------------------+
//| Helper Functions                                                 |
//+------------------------------------------------------------------+
string OrderTypeToString(ENUM_ORDER_TYPE orderType)
{
   return orderType == ORDER_TYPE_BUY ? "BUY" : "SELL";
}

string ProtectionStageToString(ENUM_PROTECTION_STAGE stage)
{
   switch(stage)
   {
      case PROTECTION_NONE:    return "NONE";
      case PROTECTION_STAGE1: return "STAGE1";
      case PROTECTION_STAGE2: return "STAGE2";
   }
   return "UNKNOWN";
}

string RejectionReasonToString(ENUM_REJECTION_REASON reason)
{
   switch(reason)
   {
      case REJECT_NONE:                  return "NONE";
      case REJECT_NOT_NEW_CLOSED_BAR:    return "NOT_NEW_CLOSED_BAR";
      case REJECT_DAILY_LOCKED:          return "DAILY_LOCKED";
      case REJECT_MAX_TRADES_EXCEEDED:   return "MAX_TRADES_EXCEEDED";
      case REJECT_EXISTING_POSITION:     return "EXISTING_POSITION";
      case REJECT_LOW_VOLATILITY:        return "LOW_VOLATILITY";
      case REJECT_STRATEGY_CANNOT_TRADE: return "STRATEGY_CANNOT_TRADE";
      case REJECT_NO_STRATEGY_SIGNAL:    return "NO_STRATEGY_SIGNAL";
      case REJECT_INSUFFICIENT_BARS:     return "INSUFFICIENT_BARS";
   }
   return "UNKNOWN";
}

//+------------------------------------------------------------------+
//| String Array Helper                                              |
//+------------------------------------------------------------------+
void AddCondition(string& arr[], string condition)
{
   int size = ArraySize(arr);
   ArrayResize(arr, size + 1);
   arr[size] = condition;
}

//+------------------------------------------------------------------+
//| Price Normalization                                              |
//+------------------------------------------------------------------+
double NormalizePrice(double price)
{
   return NormalizeDouble(price, g_digits);
}

double NormalizeLots(double lots)
{
   return NormalizeDouble(lots, 2);
}

//+------------------------------------------------------------------+
//| ATR Points Conversion                                            |
//+------------------------------------------------------------------+
double AtrToPoints(double atrValue)
{
   return atrValue * MathPow(10, g_digits);
}
