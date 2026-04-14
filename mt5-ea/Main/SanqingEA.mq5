//+------------------------------------------------------------------+
//|                                                   SanqingEA.mq5   |
//|              Sanqing EA MT5 - Main Entry Point                    |
//|                    XAUUSD M5 Automated Trading System             |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property version   "1.00"
#property strict

// Include main common definitions
#include "Common.mqh"

// Include Core modules
#include "../Core/Indicators.mqh"
#include "../Core/ContextBuilder.mqh"
#include "../Core/DailyRiskController.mqh"
#include "../Core/ProtectionEngine.mqh"
#include "../Core/EntryGate.mqh"
#include "../Core/ExecutionEngine.mqh"
#include "../Core/StateStore.mqh"

// Include Strategy implementations
#include "../Strategies/ExpansionFollowStrategy.mqh"
#include "../Strategies/PullbackStrategy.mqh"
#include "../Strategies/TrendContinuationStrategy.mqh"
#include "../Strategies/ReversalStrategy.mqh"

//+------------------------------------------------------------------+
//| Global State                                                     |
//+------------------------------------------------------------------+
SRuntimeState      g_runtimeState;
SProtectionState   g_protectionState;
bool               g_initialized = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                    |
//+------------------------------------------------------------------+
int OnInit()
{
   // Initialize random seed
   MathSrand((int)TimeCurrent());
   
   // Get symbol info
   g_symbol = _Symbol;
   g_digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);
   g_point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
   
   // Validate input parameters
   if(InpEmaFastPeriod >= InpEmaSlowPeriod)
   {
      Print("错误: 快速EMA周期必须小于慢速EMA周期");
      return INIT_PARAMETERS_INCORRECT;
   }
   
   if(InpEmaFastPeriod <= 0 || InpEmaSlowPeriod <= 0 || InpAtrPeriod <= 0)
   {
      Print("错误: 指标周期必须为正数");
      return INIT_PARAMETERS_INCORRECT;
   }
   
   if(InpFixedLots <= 0)
   {
      Print("错误: 固定手数必须为正数");
      return INIT_PARAMETERS_INCORRECT;
   }
   
   // Initialize runtime state
   if(LoadState(g_runtimeState))
   {
      LogInfo("从文件加载状态");
      
      // Reconcile with actual positions
      ReconcileState();
   }
   else
   {
      InitializeDefaultState(g_runtimeState);
      LogInfo("使用默认状态初始化");
   }
   
   // Initialize protection state from runtime state
   InitializeProtectionStateFromRuntime();
   
   g_initialized = true;
   
   // Print initialization summary
   Print("========================================");
   Print("三清EA MT5 v1.0 初始化完成");
   Print("品种: ", g_symbol, " 小数位: ", g_digits);
   Print("魔术号: ", InpMagicNumber);
   Print("快速EMA: ", InpEmaFastPeriod, " 慢速EMA: ", InpEmaSlowPeriod);
   Print("ATR周期: ", InpAtrPeriod);
   Print("固定手数: ", DoubleToString(InpFixedLots, 2));
   Print("每日最大交易次数: ", InpMaxTradesPerDay);
   Print("每日盈利停止: $", DoubleToString(InpDailyProfitStopUsd, 2));
   Print("日志级别: ", InpLogLevel);
   Print("========================================");
   
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Save state before exit
   if(g_initialized)
   {
      SaveState(g_runtimeState);
      LogInfo("退出时保存状态");
   }
   
   Print("三清EA已停止. 原因: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!g_initialized)
      return;
   
   // 1. Build market snapshot
   SMarketSnapshot snapshot;
   if(!BuildMarketSnapshot(snapshot))
   {
      LogError("Failed to build market snapshot");
      return;
   }
   
   // 2. Update daily risk state
   UpdateDailyRisk(g_runtimeState);
   
   // 3. Check for position changes
   CheckPositionChanges();
   
   // 4. Handle existing position protection
   if(g_runtimeState.positionTicket > 0)
   {
      HandlePositionProtection(snapshot);
   }
   
   // 5. Check for new closed bar
   if(snapshot.lastClosedBarTime == g_runtimeState.lastProcessedBarTime)
   {
      // Same bar, skip signal generation
      return;
   }

   // Log state for debugging
   LogDetailed("State check - tradesToday=" + IntegerToString(g_runtimeState.tradesToday) +
               " dailyLocked=" + (g_runtimeState.dailyLocked ? "true" : "false") +
               " positionTicket=" + IntegerToString(g_runtimeState.positionTicket));
   
   // Update last processed bar time
   g_runtimeState.lastProcessedBarTime = snapshot.lastClosedBarTime;
   
   LogDetailed("New closed bar detected: " + TimeToString(snapshot.lastClosedBarTime));
   
   // 6. Generate strategy signal
   SStrategySelectionResult selection = SelectStrategy(snapshot);
   
   if(!selection.hasSignal)
   {
      LogDetailed("No valid signal generated");
      return;
   }
   
   // 7. Evaluate entry gate
   SEntryGateResult gateResult = EvaluateEntryGate(
      selection.signal, 
      snapshot, 
      g_runtimeState,
      selection.signal.strategyName
   );
   
   if(!gateResult.passed)
   {
      LogDetailed("Entry gate rejected: " + GetRejectionReasonString(gateResult.reasonCode));
      return;
   }
   
   // 8. Execute order
   SExecutionResult execResult = SendOrder(gateResult.intent, snapshot);
   
   if(!execResult.success)
   {
      LogError("Order execution failed: " + execResult.reason);
      return;
   }
   
   // 9. Update state after successful order
   g_runtimeState.positionTicket = execResult.ticket;
   g_runtimeState.positionStrategy = selection.signal.strategyName;
   g_runtimeState.entryPrice = execResult.filledPrice;
   g_runtimeState.entryAtr = selection.signal.atrValue;
   g_runtimeState.highestCloseSinceEntry = execResult.filledPrice;
   g_runtimeState.lowestCloseSinceEntry = execResult.filledPrice;
   g_runtimeState.trailingActive = false;
   g_runtimeState.protectionStage = PROTECTION_NONE;
   g_runtimeState.stage1ActivatedAt = 0;
   g_runtimeState.stage2ActivatedAt = 0;

   // Increment trades today count
   g_runtimeState.tradesToday++;

   // 10. Save state
   SaveState(g_runtimeState);
   
   LogInfo("Position opened: " + selection.signal.strategyName + 
           " Ticket=" + IntegerToString(execResult.ticket) +
           " Type=" + OrderTypeToString(selection.signal.orderType) +
           " Price=" + DoubleToString(execResult.filledPrice, g_digits));
}

//+------------------------------------------------------------------+
//| Reconcile State with Actual Positions                            |
//+------------------------------------------------------------------+
void ReconcileState()
{
   // Check if we have a recorded position
   if(g_runtimeState.positionTicket > 0)
   {
      // Verify position still exists
      if(!PositionSelectByTicket(g_runtimeState.positionTicket))
      {
         LogInfo("Recorded position no longer exists, resetting state");
         
         g_runtimeState.lastPositionTicket = g_runtimeState.positionTicket;
         g_runtimeState.positionTicket = 0;
         g_runtimeState.positionStrategy = "";
         g_runtimeState.entryPrice = 0.0;
         g_runtimeState.entryAtr = 0.0;
         g_runtimeState.highestCloseSinceEntry = 0.0;
         g_runtimeState.lowestCloseSinceEntry = 0.0;
         g_runtimeState.trailingActive = false;
         g_runtimeState.protectionStage = PROTECTION_NONE;
         g_runtimeState.stage1ActivatedAt = 0;
         g_runtimeState.stage2ActivatedAt = 0;
      }
      else
      {
         LogInfo("Position reconciliation successful: Ticket=" + 
                 IntegerToString(g_runtimeState.positionTicket));
      }
   }
   else
   {
      // Check if there's an actual position with our magic
      int actualTicket = GetExistingPositionTicket(g_symbol, InpMagicNumber);
      if(actualTicket > 0)
      {
         LogInfo("Found unexpected position: Ticket=" + IntegerToString(actualTicket));
         // We found a position but don't have state for it
         // This could happen if EA was restarted mid-position
         // We'll take over management but won't have entry ATR
         g_runtimeState.positionTicket = actualTicket;
         
         if(PositionSelectByTicket(actualTicket))
         {
            g_runtimeState.entryPrice = PositionGetDouble(POSITION_PRICE_OPEN);
            // Set a default ATR for protection (will be updated on next tick)
            g_runtimeState.entryAtr = iATR(g_symbol, PERIOD_CURRENT, InpAtrPeriod);
            g_runtimeState.highestCloseSinceEntry = g_runtimeState.entryPrice;
            g_runtimeState.lowestCloseSinceEntry = g_runtimeState.entryPrice;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Initialize Protection State from Runtime State                    |
//+------------------------------------------------------------------+
void InitializeProtectionStateFromRuntime()
{
   g_protectionState.protectionStage = g_runtimeState.protectionStage;
   g_protectionState.entryPrice = g_runtimeState.entryPrice;
   g_protectionState.entryAtr = g_runtimeState.entryAtr;
   g_protectionState.highestCloseSinceEntry = g_runtimeState.highestCloseSinceEntry;
   g_protectionState.lowestCloseSinceEntry = g_runtimeState.lowestCloseSinceEntry;
   g_protectionState.trailingActive = g_runtimeState.trailingActive;
   g_protectionState.stage1ActivatedAt = g_runtimeState.stage1ActivatedAt;
   g_protectionState.stage2ActivatedAt = g_runtimeState.stage2ActivatedAt;
}

//+------------------------------------------------------------------+
//| Sync Runtime State from Protection State                          |
//+------------------------------------------------------------------+
void SyncRuntimeStateFromProtection()
{
   g_runtimeState.protectionStage = g_protectionState.protectionStage;
   g_runtimeState.highestCloseSinceEntry = g_protectionState.highestCloseSinceEntry;
   g_runtimeState.lowestCloseSinceEntry = g_protectionState.lowestCloseSinceEntry;
   g_runtimeState.trailingActive = g_protectionState.trailingActive;
   g_runtimeState.stage1ActivatedAt = g_protectionState.stage1ActivatedAt;
   g_runtimeState.stage2ActivatedAt = g_protectionState.stage2ActivatedAt;
}

//+------------------------------------------------------------------+
//| Check for Position Changes                                        |
//+------------------------------------------------------------------+
void CheckPositionChanges()
{
   if(g_runtimeState.positionTicket > 0)
   {
      if(!PositionSelectByTicket(g_runtimeState.positionTicket))
      {
         // Position closed
         LogInfo("Position closed: Ticket=" + IntegerToString(g_runtimeState.positionTicket));
         
         g_runtimeState.lastPositionTicket = g_runtimeState.positionTicket;
         g_runtimeState.positionTicket = 0;
         g_runtimeState.positionStrategy = "";
         g_runtimeState.entryPrice = 0.0;
         g_runtimeState.entryAtr = 0.0;
         g_runtimeState.highestCloseSinceEntry = 0.0;
         g_runtimeState.lowestCloseSinceEntry = 0.0;
         g_runtimeState.trailingActive = false;
         g_runtimeState.protectionStage = PROTECTION_NONE;
         g_runtimeState.stage1ActivatedAt = 0;
         g_runtimeState.stage2ActivatedAt = 0;
         
         SaveState(g_runtimeState);
      }
   }
}

//+------------------------------------------------------------------+
//| Handle Position Protection                                        |
//+------------------------------------------------------------------+
void HandlePositionProtection(SMarketSnapshot &snapshot)
{
   if(g_runtimeState.positionTicket <= 0)
      return;
   
   if(!PositionSelectByTicket(g_runtimeState.positionTicket))
      return;
   
   double currentSL = PositionGetDouble(POSITION_SL);
   double currentTP = PositionGetDouble(POSITION_TP);
   ENUM_ORDER_TYPE posType = (ENUM_ORDER_TYPE)PositionGetInteger(POSITION_TYPE);
   
   // Evaluate protection
   SProtectionDecision decision = EvaluateProtection(
      posType,
      snapshot.close,
      g_protectionState,
      currentSL,
      currentTP
   );
   
   // Apply protection if needed
   if(decision.action == "modify")
   {
      if(ModifyPosition(g_runtimeState.positionTicket, decision.newSL, decision.newTP))
      {
         SyncRuntimeStateFromProtection();
         
         if(decision.stage == PROTECTION_STAGE1)
         {
            g_runtimeState.stage1ActivatedAt = TimeCurrent();
            g_protectionState.stage1ActivatedAt = TimeCurrent();
         }
         else if(decision.stage == PROTECTION_STAGE2)
         {
            if(g_runtimeState.stage2ActivatedAt == 0)
               g_runtimeState.stage2ActivatedAt = TimeCurrent();
            if(g_protectionState.stage2ActivatedAt == 0)
               g_protectionState.stage2ActivatedAt = TimeCurrent();
         }
         
         SaveState(g_runtimeState);
      }
   }
}

//+------------------------------------------------------------------+
//| Timer function (optional)                                         |
//+------------------------------------------------------------------+
void OnTimer()
{
   // Can be used for periodic tasks
}

//+------------------------------------------------------------------+
//| Chart event function (optional)                                   |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,
                  const long &lparam,
                  const double &dparam,
                  const string &sparam)
{
   // Can be used for UI interactions
}

//+------------------------------------------------------------------+
//| STRATEGY SELECTOR - Integrated into Main                          |
//+------------------------------------------------------------------+

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
         LogInfo("Strategy selected: TrendContinuation");
         return result;
      }
   }
   else
   {
      AddCondition(suppressed, "TrendContinuation");
   }

   // Priority 4: Reversal
   if(ReversalCanTrade(snapshot))
   {
      if(BuildReversalSignal(snapshot, result.signal))
      {
         result.hasSignal = true;
         LogInfo("Strategy selected: Reversal");
         return result;
      }
   }
   else
   {
      AddCondition(suppressed, "Reversal");
   }

   // No signal found
   result.hasSignal = false;
   result.rejectionReason = REJECT_NO_STRATEGY_SIGNAL;
   ArrayCopy(result.suppressedStrategies, suppressed);

   LogDetailed("No strategy signal generated");

   return result;
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
   else if(strategyName == "Reversal")
      return ReversalCanTrade(snapshot);

   return false;
}
