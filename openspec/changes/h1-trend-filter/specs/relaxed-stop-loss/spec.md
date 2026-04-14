# 放宽止损距离规格

## ADDED Requirements

### Requirement: 初始止损距离调整

系统 SHALL 将初始止损距离从 1.2 × ATR 调整为 1.8 × ATR。

#### Scenario: 做多止损计算
- **WHEN** 策略产生做多信号
- **THEN** 初始止损 = 入场价 - 1.8 × ATR(14)

#### Scenario: 做空止损计算
- **WHEN** 策略产生做空信号
- **THEN** 初始止损 = 入场价 + 1.8 × ATR(14)

### Requirement: 止损倍数可配置

系统 SHALL 允许用户配置止损 ATR 倍数。

#### Scenario: 自定义止损倍数
- **WHEN** 用户设置 InpInitialSlAtrMultiplier = 2.0
- **THEN** 系统使用 2.0 × ATR 计算止损距离

### Requirement: 盈亏比保持

系统 SHALL 保持合理的盈亏比（止损:止盈 ≈ 1:1.4）。

#### Scenario: 做多止盈计算
- **WHEN** 策略产生做多信号
- **THEN** 初始止盈 = 入场价 + 2.5 × ATR(14)

#### Scenario: 做空止盈计算
- **WHEN** 策略产生做空信号
- **THEN** 初始止盈 = 入场价 - 2.5 × ATR(14)

### Requirement: 各策略统一止损参数

系统 SHALL 对所有策略应用统一的止损参数。

#### Scenario: TrendContinuation 止损更新
- **WHEN** TrendContinuation 策略产生信号
- **THEN** 使用 1.8 × ATR 计算止损

#### Scenario: Pullback 止损更新
- **WHEN** Pullback 策略产生信号
- **THEN** 使用 1.8 × ATR 计算止损

#### Scenario: ExpansionFollow 止损更新
- **WHEN** ExpansionFollow 策略产生信号
- **THEN** 使用 1.8 × ATR 计算止损

#### Scenario: Reversal 止损保持原有逻辑
- **WHEN** Reversal 策略产生信号
- **THEN** 使用 high24/low24 ± $6 计算止损（保持不变）