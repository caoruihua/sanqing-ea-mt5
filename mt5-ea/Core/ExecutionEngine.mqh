//+------------------------------------------------------------------+
//|                                            ExecutionEngine.mqh    |
//|              Sanqing EA MT5 - Execution Engine                    |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "../Main/Common.mqh"

//+------------------------------------------------------------------+
//| Execution Result                                                 |
//+------------------------------------------------------------------+
struct SExecutionResult
{
   bool     success;           // Execution success
   int      ticket;            // Order/Position ticket
   double   filledPrice;       // Filled price
   string   reason;            // Failure reason
   bool     retryable;         // Is retryable
   int      retryCount;        // Number of retries
};

//+------------------------------------------------------------------+
//| Get Current Price for Order Type                                  |
//+------------------------------------------------------------------+
double GetCurrentPrice(string symbol, ENUM_ORDER_TYPE orderType)
{
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
      return 0.0;
   
   return orderType == ORDER_TYPE_BUY ? tick.ask : tick.bid;
}

//+------------------------------------------------------------------+
//| Check if Position Exists                                          |
//+------------------------------------------------------------------+
bool PositionExists(string symbol, int magicNumber)
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
//| Send Order                                                       |
//+------------------------------------------------------------------+
SExecutionResult SendOrder(STradeIntent &intent, SMarketSnapshot &snapshot)
{
   SExecutionResult result;
   result.success = false;
   result.ticket = 0;
   result.filledPrice = 0.0;
   result.reason = "";
   result.retryable = false;
   result.retryCount = 0;
   
   // Final position check
   if(PositionExists(g_symbol, InpMagicNumber))
   {
      result.reason = "EXISTING_POSITION";
      result.retryable = false;
      return result;
   }
   
   double entryPrice = intent.signal.entryPrice;
   int slippage = intent.slippage;
   
   // Attempt order with retries
   for(int attempt = 0; attempt <= InpMaxRetries; attempt++)
   {
      result.retryCount = attempt;
      
      // Update price on retry (except first attempt uses signal price)
      if(attempt > 0)
      {
         double currentPrice = GetCurrentPrice(g_symbol, intent.signal.orderType);
         if(currentPrice > 0)
            entryPrice = currentPrice;
      }
      
      // Prepare order request
      MqlTradeRequest request = {};
      MqlTradeResult tradeResult = {};
      
      request.action = TRADE_ACTION_DEAL;
      request.symbol = g_symbol;
      request.volume = intent.signal.lots;
      request.price = NormalizePrice(entryPrice);
      request.sl = NormalizePrice(intent.signal.stopLoss);
      request.tp = NormalizePrice(intent.signal.takeProfit);
      request.deviation = slippage;
      request.magic = InpMagicNumber;
      request.comment = intent.comment;
      // Use IOC filling mode for better compatibility in backtesting
      request.type_filling = ORDER_FILLING_IOC;
      
      if(intent.signal.orderType == ORDER_TYPE_BUY)
      {
         request.type = ORDER_TYPE_BUY;
         request.price = NormalizePrice(GetCurrentPrice(g_symbol, ORDER_TYPE_BUY));
      }
      else
      {
         request.type = ORDER_TYPE_SELL;
         request.price = NormalizePrice(GetCurrentPrice(g_symbol, ORDER_TYPE_SELL));
      }
      
      // Send order
      bool sent = OrderSend(request, tradeResult);
      
      if(sent && tradeResult.retcode == TRADE_RETCODE_DONE)
      {
         result.success = true;
         result.ticket = (int)tradeResult.order;
         result.filledPrice = tradeResult.price;
         result.reason = "SUCCESS";
         result.retryable = false;
         
         LogInfo("Order filled: " + intent.comment + 
                 " Ticket=" + IntegerToString(result.ticket) +
                 " Price=" + DoubleToString(result.filledPrice, g_digits) +
                 " Retries=" + IntegerToString(attempt));
         
         return result;
      }
      
      // Check error code
      result.reason = "RETCODE_" + IntegerToString(tradeResult.retcode);
      
      // Determine if retryable
      switch(tradeResult.retcode)
      {
         case TRADE_RETCODE_REQUOTE:
         case TRADE_RETCODE_PRICE_OFF:
         case TRADE_RETCODE_TOO_MANY_REQUESTS:
         case TRADE_RETCODE_CONNECTION:
         case TRADE_RETCODE_TIMEOUT:
            result.retryable = true;
            break;
         default:
            result.retryable = false;
            break;
      }
      
      LogDetailed("Order attempt " + IntegerToString(attempt) + " failed: " + 
                  result.reason + " Retryable=" + (result.retryable ? "Yes" : "No"));
      
      if(!result.retryable)
         break;
      
      // Wait before retry
      Sleep(100);
   }
   
   LogError("Order failed after " + IntegerToString(InpMaxRetries) + " retries: " + result.reason);
   
   return result;
}

//+------------------------------------------------------------------+
//| Modify Position                                                  |
//+------------------------------------------------------------------+
bool ModifyPosition(int ticket, double newSL, double newTP)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.sl = NormalizePrice(newSL);
   request.tp = NormalizePrice(newTP);
   request.symbol = g_symbol;
   request.magic = InpMagicNumber;
   
   bool sent = OrderSend(request, result);
   
   if(sent && result.retcode == TRADE_RETCODE_DONE)
   {
      LogDetailed("Position modified: Ticket=" + IntegerToString(ticket) +
                  " SL=" + DoubleToString(newSL, g_digits) +
                  " TP=" + DoubleToString(newTP, g_digits));
      return true;
   }
   
   LogError("Modify position failed: " + IntegerToString(result.retcode));
   return false;
}

//+------------------------------------------------------------------+
//| Close Position                                                   |
//+------------------------------------------------------------------+
bool ClosePosition(int ticket)
{
   if(!PositionSelectByTicket(ticket))
      return false;

   ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   request.action = TRADE_ACTION_DEAL;
   request.position = ticket;
   request.symbol = g_symbol;
   request.volume = PositionGetDouble(POSITION_VOLUME);
   request.magic = InpMagicNumber;
   request.type_filling = ORDER_FILLING_IOC;

   if(posType == POSITION_TYPE_BUY)
   {
      request.type = ORDER_TYPE_SELL;
      request.price = GetCurrentPrice(g_symbol, ORDER_TYPE_SELL);
   }
   else
   {
      request.type = ORDER_TYPE_BUY;
      request.price = GetCurrentPrice(g_symbol, ORDER_TYPE_BUY);
   }
   
   bool sent = OrderSend(request, result);
   
   if(sent && result.retcode == TRADE_RETCODE_DONE)
   {
      LogInfo("Position closed: Ticket=" + IntegerToString(ticket));
      return true;
   }
   
   LogError("Close position failed: " + IntegerToString(result.retcode));
   return false;
}

//+------------------------------------------------------------------+
//| Get Position Info                                                 |
//+------------------------------------------------------------------+
bool GetPositionInfo(int ticket, double &entryPrice, double &currentSL, 
                     double &currentTP, double &volume, ENUM_ORDER_TYPE &type)
{
   if(!PositionSelectByTicket(ticket))
      return false;
   
   entryPrice = PositionGetDouble(POSITION_PRICE_OPEN);
   currentSL = PositionGetDouble(POSITION_SL);
   currentTP = PositionGetDouble(POSITION_TP);
   volume = PositionGetDouble(POSITION_VOLUME);
   type = (ENUM_ORDER_TYPE)PositionGetInteger(POSITION_TYPE);
   
   return true;
}
