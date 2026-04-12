# XAUUSD 高位上影线做空EA - 改进方案

## 一、改进目标

将原策略从"低位上影线做空"改进为"1小时40美金大涨后的上影线反转做空"。

## 二、核心改进点

### 2.1 入场条件加强

| 条件 | 原策略 | 改进后 |
|------|--------|--------|
| 1小时涨幅 | >= 5美金 | **>= 40美金** |
| 收盘位置 | 区间上半部分 | 保持不变（>= 70%） |
| 上影线 | 原有条件 | 保持不变 |
| 盈亏比 | 无检查 | **>= 1.5** |

### 2.2 止盈止损优化

| 参数 | 原策略 | 改进后 |
|------|--------|--------|
| 止盈 | 固定10美金 | **动态 = 涨幅 × 0.5（最小15美金）** |
| 止损缓冲 | 固定5美金 | **动态 = max(8美金, ATR×0.5)** |

## 三、完整改进代码

### 3.1 输入参数（更新注释）

```mq5
input group "===== 基础交易参数 ====="
input double FixedLots                  = 0.01;       // 单次下单手数（同时也是最大总持仓上限）
input ulong  MagicNumber                = 20260317;   // EA 订单唯一标识
input ulong  SlippagePoints             = 50;         // 市价下单最大滑点（points）
input string TradeSymbol                = "XAUUSDr";  // 允许交易品种

input group "===== 上影线做空参数 ====="
input double StopBufferUsd              = 8.0;        // 止损缓冲基础值（美元）
input double StopBufferAtrRatio         = 0.5;        // 止损缓冲ATR比例（动态止损 = max(基础值, ATR*比例)）
input double TakeProfitRatio            = 0.5;        // 止盈比例（止盈 = 1小时涨幅 * 比例）
input double TakeProfitMinUsd           = 15.0;       // 最小止盈（美元，防止涨幅过小时止盈太小）
input double MinRiskRewardRatio         = 1.5;        // 最小盈亏比（不足则放弃该信号）
input double UpperWickMinBodyRatio      = 1.5;        // 上影线至少达到实体长度的倍数
input double UpperWickMinLowerRatio     = 3.0;        // 上影线至少达到下影线长度的倍数
input double UpperWickMinAbsUsd         = 2.0;        // 上影线最小绝对长度（美元价格单位）

input group "===== 1小时高位判断参数 ====="
input int    HourlyLookbackBars         = 12;         // 回看K线数（12根M5=1小时）
input double HourlyRiseMinUsd           = 40.0;       // 【关键】1小时最小涨幅阈值（美元），必须达到才算"大涨高位"
input double HighPositionRatio          = 0.70;       // 收盘价在1小时区间中的位置比例阈值（0.7=上方30%区域）

input group "===== 入场观察确认参数 ====="
input int    EntryObserveSeconds        = 2;          // 下单前观察秒数
input double EntryObserveMinMoveUsd     = 0.30;       // 观察期内至少同向净移动价格
input int    EntryObserveSampleMs       = 200;        // 观察期采样间隔（毫秒）
input double EntryObserveMinDirRatio    = 0.60;       // 观察期内同向步数占比阈值

input group "===== 日内风控参数 ====="
input double DailyPriceTargetUsd        = 40.0;       // 北京时间日内累计净价格差封顶值
input int    ServerToBeijingHours       = 6;          // 服务器时间+该值=北京时间
input bool   EnableDailySummaryLog      = true;       // 北京时间跨日时输出昨日汇总
input bool   EnablePerBarDailyStats     = true;       // 每根新K线输出今日累计统计

input group "===== 调试参数 ====="
input bool   EnableDebugLogs            = false;      // 是否输出调试日志
```

### 3.2 IsAtHourlyHighPosition 函数（改进版）

```mq5
//+------------------------------------------------------------------+
//| 判断最近1小时是否处于明显上涨高位                                   |
//| 【改进】涨幅阈值从5美金提高到40美金，过滤掉小幅波动                  |
//| 返回 netRise 供后续计算动态止盈使用                                 |
//+------------------------------------------------------------------+
bool IsAtHourlyHighPosition(double &netRise)
{
   double highestHigh = -DBL_MAX;
   double lowestLow   = DBL_MAX;

   // 遍历最近 HourlyLookbackBars 根已收盘K线 (shift 1 ~ HourlyLookbackBars)
   for(int i = 1; i <= HourlyLookbackBars; i++)
   {
      double h = iHigh(_Symbol, PERIOD_M5, i);
      double l = iLow(_Symbol, PERIOD_M5, i);

      if(h > highestHigh) highestHigh = h;
      if(l < lowestLow)   lowestLow   = l;
   }

   double range = highestHigh - lowestLow;
   if(range <= 0.0)
      return false;

   double latestClose = iClose(_Symbol, PERIOD_M5, 1);
   double startOpen   = iOpen(_Symbol, PERIOD_M5, HourlyLookbackBars);

   // 【核心改进】计算1小时涨幅：最新收盘 - 区间最低
   netRise = latestClose - lowestLow;
   
   // 条件1：涨幅必须 >= 40美金（关键过滤）
   if(netRise < HourlyRiseMinUsd)
   {
      LogDebug("1小时涨幅=" + DoubleToString(netRise, 2) +
               " < 阈值" + DoubleToString(HourlyRiseMinUsd, 2) + "，不满足。");
      return false;
   }

   // 条件2：收盘价处于区间高位
   double positionRatio = (latestClose - lowestLow) / range;
   if(positionRatio < HighPositionRatio)
   {
      LogDebug("1小时高位判断：位置比=" + DoubleToString(positionRatio, 2) +
               " < 阈值" + DoubleToString(HighPositionRatio, 2) + "，不满足。");
      return false;
   }

   // 条件3：整体方向确认（最新收盘 > 1小时前开盘）
   if(latestClose <= startOpen)
   {
      LogDebug("1小时高位判断：最新收盘=" + DoubleToString(latestClose, _Digits) +
               " <= 起点开盘=" + DoubleToString(startOpen, _Digits) + "，方向不是上涨。");
      return false;
   }

   LogInfo("★ 1小时高位确认。涨幅=" + DoubleToString(netRise, 2) +
           " 位置比=" + DoubleToString(positionRatio, 2) +
           " 区间=[" + DoubleToString(lowestLow, _Digits) + ", " +
           DoubleToString(highestHigh, _Digits) + "]");

   return true;
}
```

### 3.3 SendSellOrder 函数（改进版）

```mq5
//+------------------------------------------------------------------+
//| 执行做空下单（改进版）                                              |
//| 【改进】                                                          |
//| 1. 动态止盈 = 涨幅 × TakeProfitRatio（最小TakeProfitMinUsd）       |
//| 2. 动态止损缓冲 = max(StopBufferUsd, ATR14 × StopBufferAtrRatio)   |
//| 3. 盈亏比检查：不足MinRiskRewardRatio则放弃信号                    |
//+------------------------------------------------------------------+
void SendSellOrder(double signalHigh, double netRise, string comment = "高位上影线空单")
{
   // 【改进】动态止盈：基于涨幅比例，但有最小值保护
   double takeProfitUsd = netRise * TakeProfitRatio;
   takeProfitUsd = MathMax(takeProfitUsd, TakeProfitMinUsd);

   // 【改进】动态止损缓冲：结合固定值和ATR
   double atr14 = iATR(_Symbol, PERIOD_M5, 14, 1);
   double stopBuffer = MathMax(StopBufferUsd, atr14 * StopBufferAtrRatio);
   double stopLoss = NormalizePrice(signalHigh + stopBuffer);
   
   int maxRetries = 3;

   for(int attempt = 1; attempt <= maxRetries; attempt++)
   {
      MqlTick tick;
      if(!SymbolInfoTick(_Symbol, tick))
      {
         LogInfo("第" + IntegerToString(attempt) + "次下单：获取报价失败。");
         if(attempt < maxRetries) Sleep(300);
         continue;
      }

      double entryPrice = NormalizePrice(tick.bid);
      double takeProfit = NormalizePrice(entryPrice - takeProfitUsd);

      // 【新增】盈亏比检查
      double risk = stopLoss - entryPrice;
      double reward = entryPrice - takeProfit;
      
      if(risk <= 0 || reward <= 0)
      {
         LogInfo("第" + IntegerToString(attempt) + "次下单：风险或收益计算错误。" +
                 " 风险=" + DoubleToString(risk, _Digits) +
                 " 收益=" + DoubleToString(reward, _Digits));
         return;
      }
      
      double rrRatio = reward / risk;
      
      if(rrRatio < MinRiskRewardRatio)
      {
         LogInfo("★ 盈亏比不足=" + DoubleToString(rrRatio, 2) +
                 " < 最小要求" + DoubleToString(MinRiskRewardRatio, 2) +
                 "，放弃本次信号。" +
                 " 入场=" + DoubleToString(entryPrice, _Digits) +
                 " 止损=" + DoubleToString(stopLoss, _Digits) +
                 " 止盈=" + DoubleToString(takeProfit, _Digits));
         return;
      }

      if(!ValidateStops(entryPrice, stopLoss, takeProfit))
      {
         LogInfo("第" + IntegerToString(attempt) + "/" + IntegerToString(maxRetries) +
                 "次下单跳过：止损/止盈距离不满足券商要求。");
         if(attempt < maxRetries) Sleep(300);
         continue;
      }

      LogInfo("准备发送空单（第" + IntegerToString(attempt) + "/" + IntegerToString(maxRetries) + "次）。" +
              " 1小时涨幅=" + DoubleToString(netRise, 2) +
              " 入场=" + DoubleToString(entryPrice, _Digits) +
              " 止损=" + DoubleToString(stopLoss, _Digits) +
              " 止盈=" + DoubleToString(takeProfit, _Digits) +
              " 盈亏比=" + DoubleToString(rrRatio, 2) +
              " 手数=" + DoubleToString(FixedLots, 2));

      g_trade.SetExpertMagicNumber(MagicNumber);
      g_trade.SetDeviationInPoints(SlippagePoints);

      bool result = g_trade.Sell(FixedLots, _Symbol, entryPrice, stopLoss, takeProfit, comment);

      if(result && g_trade.ResultRetcode() == TRADE_RETCODE_DONE)
      {
         LogInfo("★★★ 空单开仓成功！" +
                 " Ticket=" + IntegerToString((int)g_trade.ResultDeal()) +
                 " 入场=" + DoubleToString(entryPrice, _Digits) +
                 " 止损=" + DoubleToString(stopLoss, _Digits) +
                 " 止盈=" + DoubleToString(takeProfit, _Digits) +
                 " 盈亏比=" + DoubleToString(rrRatio, 2));
         return;
      }

      LogInfo("空单下单失败。第" + IntegerToString(attempt) + "/" + IntegerToString(maxRetries) +
              "次。RetCode=" + IntegerToString((int)g_trade.ResultRetcode()) +
              " Comment=" + g_trade.ResultComment());

      if(attempt < maxRetries) Sleep(300);
   }

   LogInfo("空单重试" + IntegerToString(maxRetries) + "次后仍失败，放弃本次信号。");
}
```

### 3.4 OnTick 主逻辑调用（更新注释）

```mq5
//+------------------------------------------------------------------+
//| OnTick - 主逻辑                                                   |
//| 【策略说明】                                                       |
//| 1. 每根新M5 K线收盘后判断信号                                      |
//| 2. 【关键】判断最近1小时是否大涨 >= 40美金                         |
//|    - 涨幅 = 最新收盘价 - 1小时区间最低价                            |
//|    - 涨幅 >= 40美金 且 收盘处于高位                                 |
//| 3. 最近一根K线出现明显上影线（反转信号）                            |
//| 4. 【新增】盈亏比 >= 1.5 才下单                                    |
//| 5. 【改进】止盈 = 涨幅 × 0.5（最小15美金）                          |
//| 6. 【改进】止损 = 信号K线最高价 + 动态缓冲                          |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!CheckTradeEnvironment())
      return;

   if(!HasEnoughBars())
   {
      if(!g_loggedBarsNotEnough)
      {
         LogInfo("历史 M5 K线数量不足，等待数据加载。");
         g_loggedBarsNotEnough = true;
      }
      return;
   }
   g_loggedBarsNotEnough = false;

   if(!IsNewBar())
      return;

   //--- 北京时间跨日处理（省略...）

   //--- 日内风控（省略...）

   //--- 持仓上限检查（省略...）

   //--- ★★★ 核心信号判断 ★★★
   
   //--- 步骤1：判断最近1小时是否大涨（>= 40美金）
   double netRise = 0.0;
   if(!IsAtHourlyHighPosition(netRise))
   {
      LogDebug("最近1小时未达到40美金涨幅，不判断上影线信号。");
      return;
   }

   //--- 步骤2：判断最近一根已收盘K线是否出现明显上影线
   double signalHigh   = 0.0;
   double upperShadow  = 0.0;
   double wickBody     = 0.0;
   double lowerShadow  = 0.0;

   if(!IsUpperWickSellSetup(signalHigh, upperShadow, wickBody, lowerShadow))
   {
      LogDebug("最近一根K线未出现有效上影线信号。");
      return;
   }

   LogInfo("★★★ 检测到高位上影线做空信号！" +
           " 1小时涨幅=" + DoubleToString(netRise, 2) +
           " 上影线=" + DoubleToString(upperShadow, _Digits) +
           " 实体=" + DoubleToString(wickBody, _Digits) +
           " 下影线=" + DoubleToString(lowerShadow, _Digits) +
           " 信号最高价=" + DoubleToString(signalHigh, _Digits));

   //--- 步骤3：入场前短时间方向确认
   if(!ConfirmSellDirectionBeforeEntry())
   {
      LogInfo("空单二次确认未通过，本次不下单。");
      return;
   }

   //--- 步骤4：执行做空（传入netRise用于动态止盈）
   SendSellOrder(signalHigh, netRise);
}
```

## 四、策略逻辑图

```
┌─────────────────────────────────────────────────────────────┐
│                      每根M5 K线收盘                           │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. 环境检查                                                  │
│     - 品种、周期正确                                          │
│     - 允许交易                                                │
│     - 历史数据充足                                            │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. 日内风控                                                  │
│     - 跨日处理                                                │
│     - 日封顶检查（40美金）                                     │
│     - 持仓上限检查                                            │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. 【关键】1小时大涨判断（>= 40美金）                         │
│     - 涨幅 = 最新收盘 - 1小时最低                              │
│     - 涨幅 >= 40？                                            │
│     - 收盘在区间上半部分？                                     │
└─────────────────────────────┬───────────────────────────────┘
                              │ 否 → 放弃
                              │ 是
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. 上影线信号判断                                            │
│     - 上影线 >= 实体 × 1.5                                     │
│     - 上影线 >= 下影线 × 3                                     │
│     - 上影线 >= 2美金                                         │
└─────────────────────────────┬───────────────────────────────┘
                              │ 否 → 放弃
                              │ 是
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  5. 入场确认                                                  │
│     - 观察期内价格下跌                                        │
└─────────────────────────────┬───────────────────────────────┘
                              │ 否 → 放弃
                              │ 是
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  6. 盈亏比检查（>= 1.5）                                      │
│     - 止盈 = 涨幅 × 0.5（最小15美金）                          │
│     - 止损 = 信号最高 + 动态缓冲                               │
└─────────────────────────────┬───────────────────────────────┘
                              │ 否 → 放弃
                              │ 是
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  7. 执行做空下单                                              │
└─────────────────────────────────────────────────────────────┘
```

## 五、风险提示

### 5.1 仍需注意的问题

即使加上40美金涨幅过滤，策略仍存在以下风险：

1. **趋势延续风险**
   - 40美金涨幅可能是强势趋势的开始，而非顶部
   - 上影线可能只是短暂回调，后续继续上涨

2. **假突破风险**
   - 上影线可能是测试阻力后的继续突破
   - 需要额外的趋势强度判断（如ADX）

3. **波动率适应问题**
   - 固定40美金阈值在高波动/低波动市场可能不合适
   - 建议改为基于ATR的相对阈值

### 5.2 建议进一步添加的过滤器

```mq5
// 建议添加的过滤器
input group "===== 建议添加的过滤器 ====="
input int    TrendEmaPeriod      = 50;    // 趋势EMA周期
input double AdxThreshold        = 25;0;  // ADX阈值（>25表示趋势明确）
input bool   RequireDowntrend    = false; // 是否要求价格在EMA下方

// 过滤器函数
bool AdditionalFiltersPass()
{
   // 1. EMA趋势过滤
   if(RequireDowntrend)
   {
      double ema = iMA(_Symbol, PERIOD_M5, TrendEmaPeriod, 0, MODE_EMA, PRICE_CLOSE, 0);
      if(iClose(_Symbol, PERIOD_M5, 0) > ema)
      {
         LogDebug("价格在EMA上方，不做空。");
         return false;
      }
   }
   
   // 2. ADX强度过滤
   double adx = iADX(_Symbol, PERIOD_M5, 14, PRICE_CLOSE, MODE_MAIN, 0);
   if(adx < AdxThreshold)
   {
      LogDebug("ADX=" + DoubleToString(adx, 2) + " < 阈值" + 
               DoubleToString(AdxThreshold, 2) + "，趋势不明确。");
      return false;
   }
   
   return true;
}
```

## 六、参数调优建议

### 6.1 回测参数范围

| 参数 | 建议回测范围 | 说明 |
|------|-------------|------|
| HourlyRiseMinUsd | 30-60 | 40是平衡点，太小信号多质量差，太大信号极少 |
| TakeProfitRatio | 0.3-0.7 | 0.5=止盈是涨幅一半，可根据风险偏好调整 |
| StopBufferUsd | 5-10 | 8是推荐值，结合ATR更稳健 |
| MinRiskRewardRatio | 1.2-2.0 | 1.5是推荐值，低于1.2风险太高 |

### 6.2 建议回测时间

- 至少回测 **1年** 数据
- 包含不同市场状态（趋势、震荡、高波动）
- 特别关注 **非农数据日**、**美联储决议日** 等特殊日期表现

---

## 七、下一步行动

要应用此改进方案，需要：

1. **切换到 Code 模式** 修改 `.mq5` 文件
2. **逐项修改** 输入参数和核心函数
3. **编译测试** 确保无语法错误
4. **模拟盘回测** 验证策略效果

是否切换到 Code 模式执行修改？