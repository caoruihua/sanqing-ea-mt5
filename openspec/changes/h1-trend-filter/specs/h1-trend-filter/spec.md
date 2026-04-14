# H1 趋势过滤器规格

## ADDED Requirements

### Requirement: H1 EMA50 趋势方向判断

系统 SHALL 使用 H1 周期的 EMA50 判断中期趋势方向。

#### Scenario: H1 上升趋势判断
- **WHEN** H1 Close 价格大于 H1 EMA50
- **THEN** 系统判定为中期上升趋势，只允许做多单

#### Scenario: H1 下降趋势判断
- **WHEN** H1 Close 价格小于 H1 EMA50
- **THEN** 系统判定为中期下降趋势，只允许做空单

#### Scenario: H1 趋势过滤可配置
- **WHEN** 用户设置 InpTrendTimeframe = 0
- **THEN** 系统禁用 H1 趋势过滤，允许双向交易

### Requirement: H1 趋势过滤应用于策略

系统 SHALL 将 H1 趋势过滤应用于所有趋势跟随策略。

#### Scenario: TrendContinuation 策略 H1 过滤
- **WHEN** TrendContinuation 策略产生做多信号
- **AND** H1 Close < EMA50（中期下降）
- **THEN** 信号被过滤，不执行交易

#### Scenario: Pullback 策略 H1 过滤
- **WHEN** Pullback 策略产生做空信号
- **AND** H1 Close > EMA50（中期上升）
- **THEN** 信号被过滤，不执行交易

#### Scenario: ExpansionFollow 策略 H1 过滤
- **WHEN** ExpansionFollow 策略产生做多信号
- **AND** H1 Close < EMA50（中期下降）
- **THEN** 信号被过滤，不执行交易

### Requirement: Reversal 策略可选 H1 过滤

系统 SHALL 允许 Reversal 策略独立配置是否应用 H1 趋势过滤。

#### Scenario: Reversal 策略禁用 H1 过滤
- **WHEN** 用户设置 Reversal 不应用 H1 过滤
- **AND** Reversal 策略产生信号
- **THEN** 信号不受 H1 方向限制，只受 ADX 过滤