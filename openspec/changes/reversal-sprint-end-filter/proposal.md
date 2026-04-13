## Why

当前 ReversalStrategy 反转策略的入场时机不够精准，往往在行情还在中途就入场，导致被止损。需要增加"明显涨跌"作为硬性前置条件，确保只在行情冲刺末端（2小时内有明显涨跌）才触发反转信号，提高胜率和盈亏比。

## What Changes

- 新增"明显涨跌"检测作为入场硬性前置条件
  - 2小时（24根M5 K线）内涨跌幅必须达到 ATR × 2.8 以上
- 修改止盈止损逻辑
  - 止损：当前最高/最低价 ± 6美元（固定缓冲）
  - 止盈：ATR × 2.5（动态计算）
- 新增数据字段支持涨跌检测
  - close24Ago：24根K线前的收盘价
  - priceMove24：2小时涨跌幅
  - high24/low24：2小时内最高/最低价

## Capabilities

### New Capabilities

- `sprint-detection`: 检测2小时内是否有明显涨跌（冲刺行情），作为反转策略的前置条件

### Modified Capabilities

- `reversal-strategy`: 修改入场逻辑，增加明显涨跌前置条件；修改止盈止损计算方式

## Impact

- 受影响文件：
  - `mt5-ea/Main/Common.mqh` - 新增参数定义和数据字段
  - `mt5-ea/Core/ContextBuilder.mqh` - 新增 close24Ago、priceMove24、high24、low24 计算
  - `mt5-ea/Strategies/ReversalStrategy.mqh` - 新增明显涨跌检测函数、修改入场逻辑、修改止盈止损
- 无API变更
- 无外部依赖变更