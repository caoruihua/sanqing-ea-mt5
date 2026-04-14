# 统一 ADX 过滤器规格

## ADDED Requirements

### Requirement: 所有策略统一应用 ADX 过滤

系统 SHALL 对所有交易策略统一应用 ADX > 25 趋势强度过滤。

#### Scenario: ADX 过滤阈值
- **WHEN** ADX(14) 值小于 25
- **THEN** 系统判定为无趋势或震荡状态，禁止所有策略交易

#### Scenario: ADX 过滤通过
- **WHEN** ADX(14) 值大于等于 25
- **THEN** 系统判定为有趋势状态，允许策略交易

### Requirement: Pullback 策略新增 ADX 过滤

系统 SHALL 对 Pullback 策略应用 ADX 过滤。

#### Scenario: Pullback 策略 ADX 过滤生效
- **WHEN** Pullback 策略产生信号
- **AND** ADX(14) < 25
- **THEN** 信号被过滤，不执行交易

#### Scenario: Pullback 策略 ADX 过滤通过
- **WHEN** Pullback 策略产生信号
- **AND** ADX(14) >= 25
- **THEN** 信号通过 ADX 过滤，进入后续判断

### Requirement: Reversal 策略新增 ADX 过滤

系统 SHALL 对 Reversal 策略应用 ADX 过滤。

#### Scenario: Reversal 策略 ADX 过滤生效
- **WHEN** Reversal 策略产生信号
- **AND** ADX(14) < 25
- **THEN** 信号被过滤，不执行交易

#### Scenario: Reversal 策略 ADX 过滤通过
- **WHEN** Reversal 策略产生信号
- **AND** ADX(14) >= 25
- **THEN** 信号通过 ADX 过滤，进入后续判断

### Requirement: ADX 阈值可配置

系统 SHALL 允许用户配置 ADX 过滤阈值。

#### Scenario: 自定义 ADX 阈值
- **WHEN** 用户设置 InpAdxThreshold = 20
- **THEN** 系统使用 ADX > 20 作为趋势判断标准