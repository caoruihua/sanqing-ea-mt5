## ADDED Requirements

### Requirement: 检测2小时明显涨跌

系统必须能够检测2小时（24根M5 K线）内是否有明显涨跌，作为反转策略的前置条件。

#### Scenario: 检测明显上涨
- **WHEN** 2小时内涨幅 >= ATR × 2.8
- **THEN** 系统标记为"明显上涨"，允许看跌反转信号

#### Scenario: 检测明显下跌
- **WHEN** 2小时内跌幅 >= ATR × 2.8
- **THEN** 系统标记为"明显下跌"，允许看涨反转信号

#### Scenario: 无明显涨跌
- **WHEN** 2小时内涨跌幅 < ATR × 2.8
- **THEN** 系统不触发反转信号

### Requirement: 计算2小时价格数据

系统必须计算并存储以下2小时价格数据：
- close24Ago: 24根K线前的收盘价
- priceMove24: 2小时涨跌幅（带符号）
- high24: 2小时内最高价
- low24: 2小时内最低价

#### Scenario: 计算涨跌幅
- **WHEN** BuildMarketSnapshot 被调用
- **THEN** priceMove24 = close[1] - close[25]

#### Scenario: 计算2小时高低点
- **WHEN** BuildMarketSnapshot 被调用
- **THEN** high24 = max(highs[1..24]), low24 = min(lows[1..24])