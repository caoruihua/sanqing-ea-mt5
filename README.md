# TimeProfitEA

XAUUSD MT5 EA，运行周期固定为 M5。当前策略为：

```text
2H 大方向过滤 + 100 美金整数关口箱体 + 回弹/突破入场 + ATR 止损 + 整数关口前止盈
```

## 当前默认参数

这组默认值来自本机已有 XAUUSD HistData tick 数据聚合 M5 后的优化结果，数据范围为 2025-06-01 到 2026-01-30。

| 参数 | 默认值 | 说明 |
| --- | ---: | --- |
| `TradeSymbol` | XAUUSD | 只允许挂在该品种图表 |
| `TrendTimeframe` | PERIOD_H2 | 长周期方向过滤周期 |
| `Trend_Fast_EMA_Period` | 10 | 长周期快 EMA |
| `Trend_Slow_EMA_Period` | 30 | 长周期慢 EMA |
| `MinTrendGapDollars` | 1.0 | 快慢 EMA 至少相差多少美元才认为有方向 |
| `M5_Entry_EMA_Period` | 10 | M5 回弹/回落确认 EMA |
| `RequireCandleDirection` | true | 做多要求 M5 阳线，做空要求 M5 阴线 |
| `UsePullbackEntry` | true | 启用回弹/回落顺势入场 |
| `UseBreakoutEntry` | true | 启用强势突破追单 |
| `PullbackEntryDistanceDollars` | 70.0 | 回弹/回落入场区宽度 |
| `IntegerLevelStepDollars` | 100.0 | 整数关口间隔 |
| `NoTradeDistanceDollars` | 4.0 | 距离整数关口多少美元以内不开仓 |
| `TakeProfitBufferDollars` | 3.0 | 止盈距离下一个整数关口的缓冲 |
| `MinTakeProfitDollars` | 10.0 | 最小止盈距离 |
| `ATR_Period` | 14 | M5 ATR 周期 |
| `ATR_Stop_Multiplier` | 3.0 | ATR 止损倍数 |
| `MinStopLossDollars` | 5.0 | 最小止损美元距离 |
| `LotSize` | 0.01 | 固定交易手数 |
| `MagicNumber` | 20260530 | EA 魔术编号 |
| `CooldownMinutes` | 10 | 平仓后冷却分钟 |
| `MaxSlippagePoints` | 30 | 最大滑点点数 |
| `EnableDebugLog` | true | 是否打印详细中文决策日志 |

## 开仓逻辑

EA 必须运行在 XAUUSD 的 M5 图表。每根新的 M5 K 线形成时，只使用已经收盘的 K 线判断信号。

## 日志说明

`EnableDebugLog = true` 时，EA 会在 MT5 Experts 日志中输出较详细的中文决策过程，包括：

- 当前长周期趋势方向、EMA 快慢线数值和差距。
- 当前价格距离整数关口是否过近。
- 上一根 M5 K 线、所在 100 美金箱体、M5 EMA 数值。
- 未开仓原因，例如趋势不明确、靠近关口、未满足回弹/突破条件、TP 距离过小。
- 开仓前的 ATR、止损距离、SL、TP、TP 距离。
- 开仓成功后的成交价、SL、TP、整数关口距离和订单号。

如果实盘日志太多，可将 `EnableDebugLog` 改为 `false`，保留关键下单/错误日志。

### 1. 长周期方向

使用 `TrendTimeframe` 上的 EMA 判断方向：

- 快 EMA - 慢 EMA >= `MinTrendGapDollars`：只做多。
- 快 EMA - 慢 EMA <= -`MinTrendGapDollars`：只做空。
- 差距不足：不交易。

当前默认是 H2 EMA10 / EMA30。

### 2. 整数关口过滤

EA 按 `IntegerLevelStepDollars` 划分 100 美金箱体，例如：

```text
3300 ~ 3400
3400 ~ 3500
3500 ~ 3600
```

当前价格距离最近 100 美金整数关口小于等于 `NoTradeDistanceDollars` 时不开仓。当前默认是 4 美金以内观望。

### 3. 回弹/回落顺势入场

H2 看空时：

- 价格回弹到当前 100 美金箱体上沿下方 `4 ~ 70` 美金区域。
- 上一根 M5 最高价触碰或越过 M5 EMA10。
- 上一根 M5 为阴线。
- 满足后做空。

H2 看多时：

- 价格回落到当前 100 美金箱体下沿上方 `4 ~ 70` 美金区域。
- 上一根 M5 最低价触碰或越过 M5 EMA10。
- 上一根 M5 为阳线。
- 满足后做多。

### 4. 强势突破追单

H2 看空时：

- 前一根 M5 收盘价仍在下方 100 美金关口上方或附近。
- 上一根 M5 收盘价跌破该关口，并离开关口超过 `NoTradeDistanceDollars`。
- 上一根 M5 为阴线。
- 满足后追空。

H2 看多时：

- 前一根 M5 收盘价仍在上方 100 美金关口下方或附近。
- 上一根 M5 收盘价突破该关口，并离开关口超过 `NoTradeDistanceDollars`。
- 上一根 M5 为阳线。
- 满足后追多。

## 出场逻辑

### ATR 止损

开仓时附带止损：

```text
止损距离 = max(M5 ATR(14) * 3.0, 5.0 美金)
```

### 整数关口前止盈

止盈设置在顺势方向下一个 100 美金整数关口前 `TakeProfitBufferDollars` 美金。

当前默认 `TakeProfitBufferDollars = 3`：

- 做多 3425，下一关口 3500，TP = 3497。
- 做空 3375，下一关口 3300，TP = 3303。

如果止盈距离小于 `MinTakeProfitDollars`，EA 跳过该笔交易。

## 回测参考

基于本机已有历史 tick 数据完整聚合 M5 后的临时回测结果：

```text
长周期 = 2H
Fast EMA = 10
Slow EMA = 30
MinTrendGapDollars = 1.0
NoTradeDistanceDollars = 4
PullbackEntryDistanceDollars = 70
TakeProfitBufferDollars = 3
ATR_Stop_Multiplier = 3.0
M5_Entry_EMA_Period = 10

trades = 188
net_points = +226,914.7
max_drawdown = 22,847.1
profit_factor = 2.030
winrate = 38.3%
```

回测是历史结果，不代表未来保证盈利。

## 编译

代码修改后必须使用 MetaEditor 编译：

```powershell
"C:\Program Files\MetaTrader 5\MetaEditor64.exe" /compile:"C:\Users\c1985\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\TimeProfitEA\TimeProfitEA.mq5" /log:"C:\Users\c1985\Desktop\TimeProfitEA\compile.log"
```
