//+------------------------------------------------------------------+
//|                                            StrategySelector.mqh    |
//|              Sanqing EA MT5 - Strategy Selector                   |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "Common.mqh"
#include "Strategies/ExpansionFollowStrategy.mqh"
#include "Strategies/PullbackStrategy.mqh"
#include "Strategies/TrendContinuationStrategy.mqh"

//+------------------------------------------------------------------+
//| Strategy Selection Result                                         |
//+------------------------------------------------------------------+
struct SStrategySelectionResult
{
   bool        hasSignal;              // Has valid signal
   SSignalDecision signal;            // The selected signal
   ENUM_REJECTION_REASON rejectionReason;  // Rejection reason if no signal
   string      suppressedStrategies[]; // Strategies that were suppressed
};

//+------------------------------------------------------------------+
//| Select Best Strategy by Priority                                  |
//+------------------------------------------------------------------+
SStrategySelectionResult SelectStrategy(SMarketSnapshot &snapshot)
{
   SStrategySelectionResult result;
   result.hasSignal = false;
   result.rejectionReason = REJECT_NONE;
   
   // Array to track suppressed strategies
   string suppressed[];
   
   // Priority 1: ExpansionFollow
   if(ExpansionFollowCanTrade(snapshot))
   {
      if(BuildExpansionFollowSignal(snapshot, result.signal))
      {
         result.hasSignal = true;
         LogInfo("Strategy selected: ExpansionFollow");
         return result;
      }
   }
   else
   {
      AddCondition(suppressed, "ExpansionFollow");
   }
   
   // Priority 2: Pullback
   if(PullbackCanTrade(snapshot))
   {
      if(BuildPullbackSignal(snapshot, result.signal))
      {
         result.hasSignal = true;
         AddConditions(suppressed, result.suppressedStrategies);
         LogInfo("Strategy selected: Pullback");
         return result;
      }
   }
   else
   {
      AddCondition(suppressed, "Pullback");
   }
   
   // Priority 3: TrendContinuation
   if(TrendContinuationCanTrade(snapshot))
   {
      if(BuildTrendContinuationSignal(snapshot, result.signal))
      {
         result.hasSignal = true;
         AddConditions(suppressed, result.suppressedStrategies);
         LogInfo("Strategy selected: TrendContinuation");
         return result;
      }
   }
   else
   {
      AddCondition(suppressed, "TrendContinuation");
   }
   
   // No signal found
   result.hasSignal = false;
   result.rejectionReason = REJECT_NO_STRATEGY_SIGNAL;
   result.suppressedStrategies = suppressed;
   
   LogDetailed("No strategy signal generated");
   
   return result;
}

//+------------------------------------------------------------------+
//| Add Conditions to Array                                           |
//+------------------------------------------------------------------+
void AddConditions(string &dest[], string &src[])
{
   int srcSize = ArraySize(src);
   int destSize = ArraySize(dest);
   ArrayResize(dest, destSize + srcSize);
   
   for(int i = 0; i < srcSize; i++)
      dest[destSize + i] = src[i];
}

//+------------------------------------------------------------------+
//| Check if Specific Strategy Can Trade                               |
//+------------------------------------------------------------------+
bool CanStrategyTrade(SMarketSnapshot &snapshot, string strategyName)
{
   if(strategyName == "ExpansionFollow")
      return ExpansionFollowCanTrade(snapshot);
   else if(strategyName == "Pullback")
      return PullbackCanTrade(snapshot);
   else if(strategyName == "TrendContinuation")
      return TrendContinuationCanTrade(snapshot);
   
   return false;
}
