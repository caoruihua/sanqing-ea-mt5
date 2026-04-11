//+------------------------------------------------------------------+
//|                                                 StateStore.mqh    |
//|              Sanqing EA MT5 - State Store (JSON Persistence)      |
//+------------------------------------------------------------------+
#property copyright "Sanqing EA MT5"
#property strict

#include "../Main/Common.mqh"

//+------------------------------------------------------------------+
//| Get State File Path                                              |
//+------------------------------------------------------------------+
string GetStateFilePath()
{
   return TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + STATE_FILE_NAME;
}

//+------------------------------------------------------------------+
//| Convert RuntimeState to JSON                                      |
//+------------------------------------------------------------------+
string RuntimeStateToJson(SRuntimeState &state)
{
   string json = "{";
   json += "\"dayKey\":\"" + state.dayKey + "\",";
   json += "\"dailyLocked\":" + (state.dailyLocked ? "true" : "false") + ",";
   json += "\"dailyClosedProfit\":" + DoubleToString(state.dailyClosedProfit, 2) + ",";
   json += "\"tradesToday\":" + IntegerToString(state.tradesToday) + ",";
   json += "\"lastEntryBarTime\":" + IntegerToString(state.lastEntryBarTime) + ",";
   json += "\"lastProcessedBarTime\":" + IntegerToString(state.lastProcessedBarTime) + ",";
   json += "\"positionTicket\":" + IntegerToString(state.positionTicket) + ",";
   json += "\"lastPositionTicket\":" + IntegerToString(state.lastPositionTicket) + ",";
   json += "\"positionStrategy\":\"" + state.positionStrategy + "\",";
   json += "\"entryPrice\":" + DoubleToString(state.entryPrice, g_digits) + ",";
   json += "\"entryAtr\":" + DoubleToString(state.entryAtr, g_digits) + ",";
   json += "\"highestCloseSinceEntry\":" + DoubleToString(state.highestCloseSinceEntry, g_digits) + ",";
   json += "\"lowestCloseSinceEntry\":" + DoubleToString(state.lowestCloseSinceEntry, g_digits) + ",";
   json += "\"trailingActive\":" + (state.trailingActive ? "true" : "false") + ",";
   json += "\"protectionStage\":" + IntegerToString(state.protectionStage) + ",";
   json += "\"stage1ActivatedAt\":" + IntegerToString(state.stage1ActivatedAt) + ",";
   json += "\"stage2ActivatedAt\":" + IntegerToString(state.stage2ActivatedAt);
   json += "}";
   
   return json;
}

//+------------------------------------------------------------------+
//| Parse JSON value (simplified)                                     |
//+------------------------------------------------------------------+
string ParseJsonString(string json, string key)
{
   string searchKey = "\"" + key + "\":\"";
   int start = StringFind(json, searchKey);
   if(start == -1)
      return "";
   
   start += StringLen(searchKey);
   int end = StringFind(json, "\"", start);
   if(end == -1)
      return "";
   
   return StringSubstr(json, start, end - start);
}

double ParseJsonDouble(string json, string key)
{
   string searchKey = "\"" + key + "\":";
   int start = StringFind(json, searchKey);
   if(start == -1)
      return 0.0;
   
   start += StringLen(searchKey);
   int end = StringFind(json, ",", start);
   if(end == -1)
      end = StringFind(json, "}", start);
   if(end == -1)
      return 0.0;
   
   string value = StringSubstr(json, start, end - start);
   return StringToDouble(value);
}

int ParseJsonInt(string json, string key)
{
   string searchKey = "\"" + key + "\":";
   int start = StringFind(json, searchKey);
   if(start == -1)
      return 0;
   
   start += StringLen(searchKey);
   int end = StringFind(json, ",", start);
   if(end == -1)
      end = StringFind(json, "}", start);
   if(end == -1)
      return 0;
   
   string value = StringSubstr(json, start, end - start);
   return (int)StringToInteger(value);
}

bool ParseJsonBool(string json, string key)
{
   string searchKey = "\"" + key + "\":";
   int start = StringFind(json, searchKey);
   if(start == -1)
      return false;
   
   start += StringLen(searchKey);
   int end = StringFind(json, ",", start);
   if(end == -1)
      end = StringFind(json, "}", start);
   if(end == -1)
      return false;
   
   string value = StringSubstr(json, start, end - start);
   return value == "true";
}

//+------------------------------------------------------------------+
//| Convert JSON to RuntimeState                                      |
//+------------------------------------------------------------------+
bool JsonToRuntimeState(string json, SRuntimeState &state)
{
   if(StringFind(json, "dayKey") == -1)
      return false;
   
   state.dayKey = ParseJsonString(json, "dayKey");
   state.dailyLocked = ParseJsonBool(json, "dailyLocked");
   state.dailyClosedProfit = ParseJsonDouble(json, "dailyClosedProfit");
   state.tradesToday = ParseJsonInt(json, "tradesToday");
   state.lastEntryBarTime = (datetime)ParseJsonInt(json, "lastEntryBarTime");
   state.lastProcessedBarTime = (datetime)ParseJsonInt(json, "lastProcessedBarTime");
   state.positionTicket = ParseJsonInt(json, "positionTicket");
   state.lastPositionTicket = ParseJsonInt(json, "lastPositionTicket");
   state.positionStrategy = ParseJsonString(json, "positionStrategy");
   state.entryPrice = ParseJsonDouble(json, "entryPrice");
   state.entryAtr = ParseJsonDouble(json, "entryAtr");
   state.highestCloseSinceEntry = ParseJsonDouble(json, "highestCloseSinceEntry");
   state.lowestCloseSinceEntry = ParseJsonDouble(json, "lowestCloseSinceEntry");
   state.trailingActive = ParseJsonBool(json, "trailingActive");
   state.protectionStage = (ENUM_PROTECTION_STAGE)ParseJsonInt(json, "protectionStage");
   state.stage1ActivatedAt = (datetime)ParseJsonInt(json, "stage1ActivatedAt");
   state.stage2ActivatedAt = (datetime)ParseJsonInt(json, "stage2ActivatedAt");
   
   return true;
}

//+------------------------------------------------------------------+
//| Save State to File                                               |
//+------------------------------------------------------------------+
bool SaveState(SRuntimeState &state)
{
   string filePath = GetStateFilePath();
   string json = RuntimeStateToJson(state);
   
   // Write to temp file first
   string tmpPath = filePath + ".tmp";
   int handle = FileOpen(tmpPath, FILE_WRITE | FILE_TXT | FILE_ANSI);
   
   if(handle == INVALID_HANDLE)
   {
      LogError("Failed to open temp file for writing");
      return false;
   }
   
   FileWrite(handle, json);
   FileClose(handle);
   
   // Rename temp file to actual file (atomic operation)
   if(!FileMove(tmpPath, 0, filePath, 0))
   {
      LogError("Failed to rename temp file to state file");
      return false;
   }
   
   LogDebug("State saved successfully");
   return true;
}

//+------------------------------------------------------------------+
//| Load State from File                                             |
//+------------------------------------------------------------------+
bool LoadState(SRuntimeState &state)
{
   string filePath = GetStateFilePath();
   
   if(!FileIsExist(filePath))
   {
      LogInfo("State file not found, starting fresh");
      return false;
   }
   
   int handle = FileOpen(filePath, FILE_READ | FILE_TXT | FILE_ANSI);
   if(handle == INVALID_HANDLE)
   {
      LogError("Failed to open state file");
      return false;
   }
   
   string json = "";
   while(!FileIsEnding(handle))
      json += FileReadString(handle);
   
   FileClose(handle);
   
   if(!JsonToRuntimeState(json, state))
   {
      LogError("Failed to parse state file");
      return false;
   }
   
   LogInfo("State loaded successfully");
   return true;
}

//+------------------------------------------------------------------+
//| Initialize Default State                                         |
//+------------------------------------------------------------------+
void InitializeDefaultState(SRuntimeState &state)
{
   state.dayKey = GetDayKey();
   state.dailyLocked = false;
   state.dailyClosedProfit = 0.0;
   state.tradesToday = 0;
   state.lastEntryBarTime = 0;
   state.lastProcessedBarTime = 0;
   state.positionTicket = 0;
   state.lastPositionTicket = 0;
   state.positionStrategy = "";
   state.entryPrice = 0.0;
   state.entryAtr = 0.0;
   state.highestCloseSinceEntry = 0.0;
   state.lowestCloseSinceEntry = 0.0;
   state.trailingActive = false;
   state.protectionStage = PROTECTION_NONE;
   state.stage1ActivatedAt = 0;
   state.stage2ActivatedAt = 0;
}
