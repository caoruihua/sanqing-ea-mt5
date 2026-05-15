## Why

当前剥头皮策略在单边行情中容易踏空。当价格偏离EMA在0.1%-0.4%区间时，既不满足强趋势直接入场（需>=0.4%），也不满足回调入场（需回到EMA距离30%以内），导致一路等待回调却始终等不到，错过整波行情。

## What Changes

- 新增"持续趋势入场"条件：当价格连续5根K线在EMA同侧且偏离>0.1%时，允许入场
- 该条件独立于现有回调逻辑，作为第三种入场方式
- 做多做空均适用

## Capabilities

### New Capabilities

- `sustained-trend-entry`: 持续趋势入场检测，当价格在EMA同侧持续运行时触发入场信号

### Modified Capabilities

无

## Impact

- 影响文件：`mt5/剥头皮脚本.mq5`
- 新增全局变量：持续趋势计数器
- 修改 `CheckPullbackEntry` 函数或新增独立检查函数
- 不影响现有回调入场逻辑
