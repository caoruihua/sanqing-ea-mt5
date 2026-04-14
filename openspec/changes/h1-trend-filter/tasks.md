# H1 趋势过滤器 - 实施任务

## 1. 参数和数据结构

- [x] 1.1 在 Common.mqh 中添加 H1 趋势过滤参数定义
  - DEFAULT_TREND_TIMEFRAME = PERIOD_H1
  - DEFAULT_EMA_TREND_PERIOD = 50
  - DEFAULT_ADX_THRESHOLD = 25.0
  - DEFAULT_INITIAL_SL_ATR = 1.8
  - DEFAULT_INITIAL_TP_ATR = 2.5

- [x] 1.2 在 Common.mqh 中添加输入参数
  - InpTrendTimeframe (趋势周期)
  - InpEmaTrendPeriod (趋势 EMA 周期)
  - InpAdxThreshold (ADX 阈值)
  - InpInitialSlAtrMultiplier (止损 ATR 倍数)

- [x] 1.3 在 SMarketSnapshot 结构中添加新字段
  - emaTrend_H1 (H1 EMA50 值)
  - close_H1 (H1 收盘价)

- [x] 1.4 更新止损相关常量
  - TREND_CONTINUATION_INITIAL_SL_ATR = 1.8
  - PULLBACK_INITIAL_SL_ATR = 1.8

## 2. 数据获取和计算

- [x] 2.1 在 ContextBuilder.mqh 中添加 H1 数据获取函数
  - GetH1Close() 获取 H1 收盘价
  - GetH1EmaTrend() 获取 H1 EMA50

- [x] 2.2 在 BuildMarketSnapshot() 中添加 H1 数据计算
  - 计算 emaTrend_H1
  - 计算 close_H1

- [x] 2.3 在 ContextBuilder.mqh 中添加趋势判断辅助函数
  - IsH1Uptrend() 判断 H1 上升趋势
  - IsH1Downtrend() 判断 H1 下降趋势

## 3. 策略修改 - TrendContinuation

- [x] 3.1 在 TrendContinuationStrategy.mqh 中添加 H1 趋势过滤
  - 做多条件增加: IsH1Uptrend(snapshot)
  - 做空条件增加: IsH1Downtrend(snapshot)

- [x] 3.2 更新 TrendContinuation 止损计算
  - 使用 1.8 × ATR 计算止损

## 4. 策略修改 - Pullback

- [x] 4.1 在 PullbackStrategy.mqh 中添加 ADX 过滤
  - TrendContinuationCanTrade() 中增加 ADX > 25 检查

- [x] 4.2 在 PullbackStrategy.mqh 中添加 H1 趋势过滤
  - 做多条件增加: IsH1Uptrend(snapshot)
  - 做空条件增加: IsH1Downtrend(snapshot)

- [x] 4.3 更新 Pullback 止损计算
  - 使用 1.8 × ATR 计算止损

## 5. 策略修改 - ExpansionFollow

- [x] 5.1 在 ExpansionFollowStrategy.mqh 中添加 H1 趋势过滤
  - 做多条件增加: IsH1Uptrend(snapshot)
  - 做空条件增加: IsH1Downtrend(snapshot)

- [x] 5.2 更新 ExpansionFollow 止损计算
  - 使用 1.8 × ATR 计算止损

## 6. 策略修改 - Reversal

- [x] 6.1 在 ReversalStrategy.mqh 中添加 ADX 过滤
  - ReversalCanTrade() 中增加 ADX > 25 检查

- [x] 6.2 添加 Reversal 策略 H1 过滤可选参数
  - InpReversalUseH1Filter (是否使用 H1 过滤) - 未实现，保持 Reversal 双向交易

## 7. 测试和验证

- [ ] 7.1 编译 EA 确保无语法错误

- [ ] 7.2 在 MT5 策略测试器中进行回测验证
  - 对比修改前后的交易次数
  - 对比修改前后的盈亏比

- [ ] 7.3 模拟盘测试
  - 观察信号过滤效果
  - 验证止损距离是否正确

- [ ] 7.4 实盘小仓位测试
  - 验证实际交易效果
  - 收集数据评估改进效果