//+------------------------------------------------------------------+
//|                                                   SanqingEA.mq5   |
//|              Sanqing EA MT5 - Main Entry Point                    |
//|                    XAUUSD M5 Automated Trading System             |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property version   "1.00"
#property strict

// Include all modules
#include "Include/Common.mqh"
#include "Include/Indicators.mqh"
#include "Include/ContextBuilder.mqh"
#include "Include/DailyRiskController.mqh"
#include "Include/ProtectionEngine.mqh"
#include "Include/StrategySelector.mqh"
#include "Include/EntryGate.mqh"
#include "Include/ExecutionEngine.mqh"
#include "Include/StateStore.mqh"

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
      Print("ERROR: EMA Fast Period must be less than Slow Period");
      return INIT_PARAMETERS_INCORRECT;
   }
   
   if(InpEmaFastPeriod <= 0 || InpEmaSlowPeriod <= 0 || InpAtrPeriod <= 0)
   {
      Print("ERROR: Indicator periods must be positive");
      return INIT_PARAMETERS_INCORRECT;
   }
   
   if(InpFixedLots <= 0)
   {
      Print("ERROR: Fixed Lots must be positive");
      return INIT_PARAMETERS_INCORRECT;
   }
   
   // Initialize runtime state
   if(LoadState(g_runtimeState))
   {
      LogInfo("State loaded from file");
      
      // Reconcile with actual positions
      ReconcileState();
   }
   else
   {
      InitializeDefaultState(g_runtimeState);
      LogInfo("Initialized with default state");
   }
   
   // Initialize protection state from runtime state
   InitializeProtectionStateFromRuntime();
   
   g_initialized = true;
   
   // Print initialization summary
   Print("========================================");
   Print("Sanqing EA MT5 v1.0 Initialized");
   Print("Symbol: ", g_symbol, " Digits: ", g_digits);
   Print("Magic: ", InpMagicNumber);
   Print("EMA Fast: ", InpEmaFastPeriod, " EMA Slow: ", InpEmaSlowPeriod);
   Print("ATR Period: ", InpAtrPeriod);
   Print("Fixed Lots: ", DoubleToString(InpFixedLots, 2));
   Print("Max Trades/Day: ", InpMaxTradesPerDay);
   Print("Daily Profit Stop: $", DoubleToString(InpDailyProfitStopUsd, 2));
   Print("Log Level: ", InpLogLevel);
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
      LogInfo("State saved on exit");
   }
   
   Print("Sanqing EA stopped. Reason: ", reason);
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
            g_runtimeState.entryAtr = iATR(g_symbol, PERIOD_CURRENT, InpAtrPeriod, 0);
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
