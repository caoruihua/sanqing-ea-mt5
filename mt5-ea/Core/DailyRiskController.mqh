//+------------------------------------------------------------------+
//|                                       DailyRiskController.mqh    |
//|              Sanqing EA MT5 - Daily Risk Controller              |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "../Main/Common.mqh"

//+------------------------------------------------------------------+
//| Get Server Time as Day Key                                       |
//+------------------------------------------------------------------+
string GetDayKey()
{
   datetime serverTime = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(serverTime, dt);

   string dayKey = StringFormat("%04d.%02d.%02d", dt.year, dt.mon, dt.day);
   return dayKey;
}

//+------------------------------------------------------------------+
//| Update Daily Risk State                                          |
//+------------------------------------------------------------------+
void UpdateDailyRisk(SRuntimeState &state)
{
   string currentDayKey = GetDayKey();

   // Check for day change - reset daily counters
   if(state.dayKey != "" && state.dayKey != currentDayKey)
   {
      state.dayKey = currentDayKey;
      state.dailyLocked = false;
      state.dailyClosedProfit = 0.0;
      state.tradesToday = 0;

      LogInfo("Day change detected: " + currentDayKey + " - Daily counters reset");
   }

   // Calculate daily closed profit from history
   double dailyProfit = CalculateDailyClosedProfit();

   if(state.dayKey != currentDayKey)
   {
      state.dayKey = currentDayKey;
      state.dailyClosedProfit = 0.0;
   }

   state.dailyClosedProfit = dailyProfit;

   // Check if daily profit stop is triggered
   if(state.dailyClosedProfit >= InpDailyProfitStopUsd)
   {
      if(!state.dailyLocked)
      {
         state.dailyLocked = true;
         LogInfo("Daily profit lock triggered: " + DoubleToString(state.dailyClosedProfit, 2) +
                 " >= " + DoubleToString(InpDailyProfitStopUsd, 2));
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate Daily Closed Profit from History                       |
//+------------------------------------------------------------------+
double CalculateDailyClosedProfit()
{
   double totalProfit = 0.0;
   datetime serverTime = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(serverTime, dt);

   // Start of today
   MqlDateTime startDt = dt;
   startDt.hour = 0;
   startDt.min = 0;
   startDt.sec = 0;
   datetime startOfDay = StructToTime(startDt);

   // In backtesting mode, HistorySelect may not work as expected
   // Use HistorySelect with a wide range to ensure we capture all deals
   if(!HistorySelect(startOfDay, serverTime))
   {
      // If selection fails, return 0 profit (conservative approach)
      return 0.0;
   }

   int totalDeals = HistoryDealsTotal();

   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0)
         continue;

      // Only count deals with our magic number
      long dealMagic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      if(dealMagic != InpMagicNumber)
         continue;

      // Only count deals that closed today (position close deals)
      ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(dealEntry != DEAL_ENTRY_OUT && dealEntry != DEAL_ENTRY_OUT_BY)
         continue;

      // Get profit components
      double dealProfit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      double dealSwap = HistoryDealGetDouble(ticket, DEAL_SWAP);
      double dealCommission = HistoryDealGetDouble(ticket, DEAL_COMMISSION);

      totalProfit += dealProfit + dealSwap + dealCommission;
   }

   return totalProfit;
}

//+------------------------------------------------------------------+
//| Check if Daily Locked                                            |
//+------------------------------------------------------------------+
bool IsDailyLocked(SRuntimeState &state)
{
   return state.dailyLocked;
}

//+------------------------------------------------------------------+
//| Check if Trades Today Exceeded                                   |
//+------------------------------------------------------------------+
bool IsMaxTradesExceeded(SRuntimeState &state)
{
   return state.tradesToday >= InpMaxTradesPerDay;
}
