//+------------------------------------------------------------------+
//|                                             ProtectionEngine.mqh  |
//|              Sanqing EA MT5 - Protection Engine                   |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "../Main/Common.mqh"

//+------------------------------------------------------------------+
//| Protection Decision Structure                                    |
//+------------------------------------------------------------------+
struct SProtectionDecision
{
   string       action;                // "hold" or "modify"
   double       newSL;                // New stop loss
   double       newTP;                // New take profit
   ENUM_PROTECTION_STAGE stage;       // Current stage after evaluation
};

//+------------------------------------------------------------------+
//| Calculate Profit Distance                                        |
//+------------------------------------------------------------------+
double CalculateProfitDistance(ENUM_ORDER_TYPE orderType, double closePrice, double entryPrice)
{
   if(orderType == ORDER_TYPE_BUY)
      return closePrice - entryPrice;
   else
      return entryPrice - closePrice;
}

//+------------------------------------------------------------------+
//| Evaluate Protection for Position                                 |
//+------------------------------------------------------------------+
SProtectionDecision EvaluateProtection(ENUM_ORDER_TYPE orderType, 
                                       double currentClose,
                                       SProtectionState &protState,
                                       double currentSL,
                                       double currentTP)
{
   SProtectionDecision decision;
   decision.action = "hold";
   decision.stage = protState.protectionStage;
   
   // Check if we have entry info
   if(protState.entryPrice <= 0 || protState.entryAtr <= 0)
      return decision;
   
   double entry = protState.entryPrice;
   double atr = protState.entryAtr;
   
   // Update highest/lowest close tracking
   if(protState.highestCloseSinceEntry == 0)
      protState.highestCloseSinceEntry = currentClose;
   else if(orderType == ORDER_TYPE_BUY)
      protState.highestCloseSinceEntry = MathMax(protState.highestCloseSinceEntry, currentClose);
   else
      protState.highestCloseSinceEntry = MathMax(protState.highestCloseSinceEntry, currentClose);
   
   if(protState.lowestCloseSinceEntry == 0)
      protState.lowestCloseSinceEntry = currentClose;
   else if(orderType == ORDER_TYPE_SELL)
      protState.lowestCloseSinceEntry = MathMin(protState.lowestCloseSinceEntry, currentClose);
   else
      protState.lowestCloseSinceEntry = MathMin(protState.lowestCloseSinceEntry, currentClose);
   
   // Calculate current profit distance
   double pnlDistance = CalculateProfitDistance(orderType, currentClose, entry);
   
   // STAGE 1: When profit >= 1.0 * ATR
   if(protState.protectionStage == PROTECTION_NONE && 
      pnlDistance >= PROTECTION_STAGE1_ATR_MULTIPLIER * atr)
   {
      protState.protectionStage = PROTECTION_STAGE1;
      
      double sl, tp;
      CalculateStage1Levels(orderType, entry, atr, sl, tp);
      
      // Only improve TP, never reduce it
      if(orderType == ORDER_TYPE_BUY)
         tp = MathMax(tp, currentTP);
      else
         tp = MathMin(tp, currentTP);
      
      decision.action = "modify";
      decision.newSL = NormalizePrice(sl);
      decision.newTP = NormalizePrice(tp);
      decision.stage = PROTECTION_STAGE1;
      
      LogInfo("保护阶段1激活: 止损=" + DoubleToString(decision.newSL, g_digits) +
              " 止盈=" + DoubleToString(decision.newTP, g_digits));
      
      return decision;
   }
   
   // STAGE 2: When profit >= 1.5 * ATR
   if(pnlDistance >= PROTECTION_STAGE2_ATR_MULTIPLIER * atr)
   {
      protState.protectionStage = PROTECTION_STAGE2;
      protState.trailingActive = true;
      
      double sl, tp;
      CalculateStage2Levels(orderType, currentClose, atr, sl, tp);
      
      // Only improve SL/TP, never reduce
      if(orderType == ORDER_TYPE_BUY)
      {
         sl = MathMax(sl, currentSL);
         tp = MathMax(tp, currentTP);
      }
      else
      {
         sl = MathMin(sl, currentSL);
         tp = MathMin(tp, currentTP);
      }
      
      decision.action = "modify";
      decision.newSL = NormalizePrice(sl);
      decision.newTP = NormalizePrice(tp);
      decision.stage = PROTECTION_STAGE2;
      
      LogDetailed("保护阶段2追踪: 止损=" + DoubleToString(decision.newSL, g_digits) +
                  " 止盈=" + DoubleToString(decision.newTP, g_digits));
      
      return decision;
   }
   
   return decision;
}

//+------------------------------------------------------------------+
//| Calculate Stage 1 SL/TP Levels                                   |
//+------------------------------------------------------------------+
void CalculateStage1Levels(ENUM_ORDER_TYPE orderType, double entryPrice, 
                           double atr, double &sl, double &tp)
{
   if(orderType == ORDER_TYPE_BUY)
   {
      sl = entryPrice + PROTECTION_STAGE1_SL_BUFFER_ATR * atr;
      tp = entryPrice + PROTECTION_STAGE1_TP_ATR * atr;
   }
   else
   {
      sl = entryPrice - PROTECTION_STAGE1_SL_BUFFER_ATR * atr;
      tp = entryPrice - PROTECTION_STAGE1_TP_ATR * atr;
   }
}

//+------------------------------------------------------------------+
//| Calculate Stage 2 SL/TP Levels (Trailing)                        |
//+------------------------------------------------------------------+
void CalculateStage2Levels(ENUM_ORDER_TYPE orderType, double closePrice,
                           double atr, double &sl, double &tp)
{
   if(orderType == ORDER_TYPE_BUY)
   {
      sl = closePrice - PROTECTION_STAGE2_SL_DISTANCE_ATR * atr;
      tp = closePrice + PROTECTION_STAGE2_TP_DISTANCE_ATR * atr;
   }
   else
   {
      sl = closePrice + PROTECTION_STAGE2_SL_DISTANCE_ATR * atr;
      tp = closePrice - PROTECTION_STAGE2_TP_DISTANCE_ATR * atr;
   }
}

//+------------------------------------------------------------------+
//| Initialize Protection State for New Position                      |
//+------------------------------------------------------------------+
void InitializeProtectionState(SProtectionState &state, double entryPrice, double atr)
{
   state.protectionStage = PROTECTION_NONE;
   state.entryPrice = entryPrice;
   state.entryAtr = atr;
   state.highestCloseSinceEntry = entryPrice;
   state.lowestCloseSinceEntry = entryPrice;
   state.trailingActive = false;
   state.stage1ActivatedAt = 0;
   state.stage2ActivatedAt = 0;
}
