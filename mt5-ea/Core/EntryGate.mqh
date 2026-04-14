//+------------------------------------------------------------------+
//|                                                   EntryGate.mqh    |
//|              Sanqing EA MT5 - Entry Gate                          |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "../Main/Common.mqh"

//+------------------------------------------------------------------+
//| Entry Gate Result                                                |
//+------------------------------------------------------------------+
struct SEntryGateResult
{
   bool                   passed;          // Gate passed
   STradeIntent           intent;         // Trade intent (if passed)
   ENUM_REJECTION_REASON  reasonCode;     // Rejection reason
   string                 strategyName;   // Strategy name
};

//+------------------------------------------------------------------+
//| Check Low Volatility                                              |
//+------------------------------------------------------------------+
bool IsLowVolatility(SMarketSnapshot &snapshot)
{
   double atrPoints = AtrToPoints(snapshot.atr14);

   // ATR floor check
   if(atrPoints < InpLowVolAtrPointsFloor)
   {
      LogDetailed("低波动性: ATR点数=" + DoubleToString(atrPoints, 2) +
                  " < 下限=" + DoubleToString(InpLowVolAtrPointsFloor, 2));
      return true;
   }

   // Skip spread check in backtesting or if spread is invalid (0 or negative)
   // In backtest, spread can be 0 in some modes
   if(snapshot.spreadPoints <= 0)
   {
      LogDetailed("跳过点差检查: 点差=" + DoubleToString(snapshot.spreadPoints, 2) + " (回测模式)");
      return false;  // Allow trading even with 0 spread in backtest
   }

   double atrSpreadRatio = atrPoints / snapshot.spreadPoints;
   if(atrSpreadRatio < InpLowVolAtrSpreadRatioFloor)
   {
      LogDetailed("低波动性: ATR/点差比=" + DoubleToString(atrSpreadRatio, 2) +
                  " < 下限=" + DoubleToString(InpLowVolAtrSpreadRatioFloor, 2));
      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Check if Existing Position Exists                                 |
//+------------------------------------------------------------------+
bool HasExistingPosition(string symbol, int magicNumber)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      
      string posSymbol = PositionGetString(POSITION_SYMBOL);
      long posMagic = PositionGetInteger(POSITION_MAGIC);
      
      if(posSymbol == symbol && posMagic == magicNumber)
         return true;
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Get Existing Position Ticket                                      |
//+------------------------------------------------------------------+
int GetExistingPositionTicket(string symbol, int magicNumber)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      
      string posSymbol = PositionGetString(POSITION_SYMBOL);
      long posMagic = PositionGetInteger(POSITION_MAGIC);
      
      if(posSymbol == symbol && posMagic == magicNumber)
         return (int)ticket;
   }
   
   return 0;
}

//+------------------------------------------------------------------+
//| Generate Action ID                                               |
//+------------------------------------------------------------------+
string GenerateActionId(string strategyName, datetime barTime)
{
   MqlDateTime dt;
   TimeToStruct(barTime, dt);
   
   string barKey = StringFormat("%04d%02d%02d%02d%02d", 
                                dt.year, dt.mon, dt.day, dt.hour, dt.min);
   
   // Generate random suffix
   int rand1 = MathRand() % 10000;
   int rand2 = MathRand() % 10000;
   
   return strategyName + "-" + barKey + "-" + IntegerToString(rand1) + IntegerToString(rand2);
}

//+------------------------------------------------------------------+
//| Evaluate Entry Gate                                              |
//+------------------------------------------------------------------+
SEntryGateResult EvaluateEntryGate(SSignalDecision &signal,
                                   SMarketSnapshot &snapshot,
                                   SRuntimeState &state,
                                   string strategyName)
{
   SEntryGateResult result;
   result.passed = false;
   result.reasonCode = REJECT_NONE;
   result.strategyName = strategyName;
   
   // 1. Check if same bar already processed
   if(state.lastEntryBarTime == snapshot.lastClosedBarTime)
   {
      result.reasonCode = REJECT_NOT_NEW_CLOSED_BAR;
      LogDetailed("入场拒绝: 非新闭合K线");
      return result;
   }
   
   // 2. Check daily lock
   if(state.dailyLocked)
   {
      result.reasonCode = REJECT_DAILY_LOCKED;
      LogDetailed("入场拒绝: 每日已锁定");
      return result;
   }
   
   // 3. Check max trades per day
   if(state.tradesToday >= InpMaxTradesPerDay)
   {
      result.reasonCode = REJECT_MAX_TRADES_EXCEEDED;
      LogDetailed("入场拒绝: 超过每日最大交易次数");
      return result;
   }
   
   // 4. Check existing position
   if(HasExistingPosition(g_symbol, InpMagicNumber))
   {
      result.reasonCode = REJECT_EXISTING_POSITION;
      LogDetailed("入场拒绝: 已有持仓");
      return result;
   }
   
   // 5. Check low volatility
   if(IsLowVolatility(snapshot))
   {
      result.reasonCode = REJECT_LOW_VOLATILITY;
      LogDetailed("入场拒绝: 低波动性");
      return result;
   }
   
   // 6. Check if strategy can trade
   if(!CanStrategyTrade(snapshot, strategyName))
   {
      result.reasonCode = REJECT_STRATEGY_CANNOT_TRADE;
      LogDetailed("入场拒绝: 策略无法交易");
      return result;
   }
   
   // All checks passed - create trade intent
   result.passed = true;
   result.intent.signal = signal;
   result.intent.actionId = GenerateActionId(strategyName, snapshot.lastClosedBarTime);
   result.intent.slippage = InpSlippage;
   result.intent.comment = strategyName;
   result.intent.timestamp = TimeCurrent();
   
   // Update state
   state.lastEntryBarTime = snapshot.lastClosedBarTime;
   
   LogInfo("Entry gate passed for " + strategyName + " - ActionId: " + result.intent.actionId);
   
   return result;
}

//+------------------------------------------------------------------+
//| Get Rejection Reason String                                       |
//+------------------------------------------------------------------+
string GetRejectionReasonString(ENUM_REJECTION_REASON reason)
{
   switch(reason)
   {
      case REJECT_NOT_NEW_CLOSED_BAR:    return "NOT_NEW_CLOSED_BAR";
      case REJECT_DAILY_LOCKED:          return "DAILY_LOCKED";
      case REJECT_MAX_TRADES_EXCEEDED:   return "MAX_TRADES_EXCEEDED";
      case REJECT_EXISTING_POSITION:     return "EXISTING_POSITION";
      case REJECT_LOW_VOLATILITY:        return "LOW_VOLATILITY";
      case REJECT_STRATEGY_CANNOT_TRADE: return "STRATEGY_CANNOT_TRADE";
      case REJECT_NO_STRATEGY_SIGNAL:    return "NO_STRATEGY_SIGNAL";
      case REJECT_INSUFFICIENT_BARS:     return "INSUFFICIENT_BARS";
      default:                           return "NONE";
   }
}
