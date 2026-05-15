## 1. 参数与全局变量

- [x] 1.1 添加输入参数：SustainedTrendBars（持续趋势K线数，默认5）
- [x] 1.2 添加输入参数：SustainedTrendMinDeviation（持续趋势最小偏离，默认0.001即0.1%）
- [x] 1.3 添加全局变量：g_sustainedTrendBars（当前计数）
- [x] 1.4 添加全局变量：g_sustainedTrendDirection（当前方向）

## 2. 核心逻辑实现

- [x] 2.1 实现函数 CheckSustainedTrendEntry()：检查持续趋势入场条件
- [x] 2.2 实现K线同侧检测：获取最近N根K线收盘价与EMA比较
- [x] 2.3 实现计数逻辑：趋势方向变化时重置，同侧则+1，不同侧则重置

## 3. 集成与测试

- [x] 3.1 在OnTick中集成：在回调入场检查之后调用持续趋势检查
- [x] 3.2 更新版本号为v1.3
- [x] 3.3 更新版本历史注释
