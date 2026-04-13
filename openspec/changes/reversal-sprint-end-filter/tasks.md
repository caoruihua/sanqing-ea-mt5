## 1. 数据结构扩展

- [x] 1.1 在 Common.mqh 中新增参数定义：REVERSAL_MOVE_ATR_MULTIPLIER = 2.8
- [x] 1.2 在 Common.mqh 中新增参数定义：REVERSAL_STOP_BUFFER_DOLLAR = 6.0
- [x] 1.3 在 Common.mqh 中新增参数定义：REVERSAL_TP_ATR_MULTIPLIER = 2.5
- [x] 1.4 在 SMarketSnapshot 中新增字段：close24Ago, priceMove24, high24, low24

## 2. 数据计算实现

- [x] 2.1 在 ContextBuilder.mqh 中实现 CalculateClose24Ago() 函数
- [x] 2.2 在 ContextBuilder.mqh 中实现 CalculatePriceMove24() 函数
- [x] 2.3 在 ContextBuilder.mqh 中实现 CalculateHigh24() 函数
- [x] 2.4 在 ContextBuilder.mqh 中实现 CalculateLow24() 函数
- [x] 2.5 在 BuildMarketSnapshot() 中调用新增的计算函数填充新字段

## 3. 策略逻辑修改

- [x] 3.1 在 ReversalStrategy.mqh 中新增 HasSignificantMove() 函数
- [x] 3.2 修改 BuildReversalSignal() 添加明显涨跌前置条件检查
- [x] 3.3 修改看跌信号止盈止损逻辑：SL = high24 + 6美元, TP = entry - ATR × 2.5
- [x] 3.4 修改看涨信号止盈止损逻辑：SL = low24 - 6美元, TP = entry + ATR × 2.5

## 4. 测试验证

- [ ] 4.1 编译验证无错误
- [ ] 4.2 日志验证新增字段计算正确
- [ ] 4.3 模拟运行验证入场条件过滤效果
