//+------------------------------------------------------------------+
//|                                                   EntryGate.mqh    |
//|              Sanqing EA MT5 - Entry Gate                          |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "Common.mqh"

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
   
   if(atrPoints < InpLowVolAtrPointsFloor)
      return true;
   
   if(snapshot.spreadPoints <= 0)
      return true;
   
   double atrSpreadRatio = atrPoints / snapshot.spreadPoints;
   if(atrSpreadRatio < InpLowVolAtrSpreadRatioFloor)
      return true;
   
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
      LogDetailed("Entry rejected: Not new closed bar");
      return result;
   }
   
   // 2. Check daily lock
   if(state.dailyLocked)
   {
      result.reasonCode = REJECT_DAILY_LOCKED;
      LogDetailed("Entry rejected: Daily locked");
      return result;
   }
   
   // 3. Check max trades per day
   if(state.tradesToday >= InpMaxTradesPerDay)
   {
      result.reasonCode = REJECT_MAX_TRADES_EXCEEDED;
      LogDetailed("Entry rejected: Max trades exceeded");
      return result;
   }
   
   // 4. Check existing position
   if(HasExistingPosition(g_symbol, InpMagicNumber))
   {
      result.reasonCode = REJECT_EXISTING_POSITION;
      LogDetailed("Entry rejected: Existing position");
      return result;
   }
   
   // 5. Check low volatility
   if(IsLowVolatility(snapshot))
   {
      result.reasonCode = REJECT_LOW_VOLATILITY;
      LogDetailed("Entry rejected: Low volatility");
      return result;
   }
   
   // 6. Check if strategy can trade
   if(!CanStrategyTrade(snapshot, strategyName))
   {
      result.reasonCode = REJECT_STRATEGY_CANNOT_TRADE;
      LogDetailed("Entry rejected: Strategy cannot trade");
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
