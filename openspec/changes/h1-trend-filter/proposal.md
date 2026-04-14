# H1 趋势过滤器

## Why

当前策略使用 M5 周期的 EMA 9/21 判断方向，但这只是短期均线，无法代表中长期趋势方向。在震荡行情中 EMA 9/21 频繁交叉导致假信号，入场后行情反转被止损。需要增加 H1 周期的趋势过滤，确保只做顺势交易，同时放宽止损距离以容纳正常波动。

## What Changes

- 新增 H1 周期 EMA50 作为中期趋势方向过滤器
- H1 Close > EMA50 时只允许做多，H1 Close < EMA50 时只允许做空
- 统一所有策略应用 ADX > 25 趋势强度过滤（当前只有部分策略有）
- 放宽初始止损距离：1.2 × ATR → 1.8 × ATR
- 新增可配置参数：趋势周期、趋势 EMA 周期

## Capabilities

### New Capabilities

- `h1-trend-filter`: H1 周期趋势方向过滤功能，使用 EMA50 判断中期趋势方向
- `unified-adx-filter`: 统一的 ADX 趋势强度过滤，所有策略共享
- `relaxed-stop-loss`: 放宽止损距离参数配置

### Modified Capabilities

- `trend-continuation-strategy`: 增加 H1 趋势方向过滤条件
- `pullback-strategy`: 增加 H1 趋势方向过滤条件和 ADX 过滤
- `expansion-follow-strategy`: 增加 H1 趋势方向过滤条件
- `reversal-strategy`: 增加 ADX 过滤（可选是否应用 H1 过滤）

## Impact

### 受影响的文件

- `mt5-ea/Main/Common.mqh`: 新增参数定义和数据结构字段
- `mt5-ea/Core/ContextBuilder.mqh`: 新增 H1 EMA 和 Close 数据获取
- `mt5-ea/Core/Indicators.mqh`: 新增多周期指标计算函数
- `mt5-ea/Strategies/TrendContinuationStrategy.mqh`: 增加 H1 趋势过滤
- `mt5-ea/Strategies/PullbackStrategy.mqh`: 增加 H1 趋势过滤和 ADX 过滤
- `mt5-ea/Strategies/ExpansionFollowStrategy.mqh`: 增加 H1 趋势过滤
- `mt5-ea/Strategies/ReversalStrategy.mqh`: 增加 ADX 过滤

### 参数变更

| 参数 | 当前值 | 新值 | 说明 |
|------|--------|------|------|
| INITIAL_SL_ATR | 1.2 | 1.8 | 放宽止损距离 |
| ADX_THRESHOLD | 各策略不同 | 统一 25 | ADX 阈值统一 |
| 新增 InpTrendTimeframe | - | PERIOD_H1 | 趋势判断周期 |
| 新增 InpEmaTrendPeriod | - | 50 | 趋势 EMA 周期 |

### 向后兼容性

- 新增参数有默认值，不影响现有配置
- 可通过参数关闭 H1 趋势过滤（设置 InpTrendTimeframe = 0）