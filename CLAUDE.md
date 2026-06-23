# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ 强制要求：必须编译通过才能交付

**所有代码修改完成后，必须使用 MetaEditor 编译通过，才能交付给用户。**
**这是最高优先级的硬性要求，不可跳过。**

如果编译失败，必须自行修复所有错误，直到编译零错误通过。

编译命令：

```
"C:\Program Files\MetaTrader 5\MetaEditor64.exe" /compile:"C:\Users\c1985\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\TimeProfitEA\TimeProfitEA.mq5" /log:"C:\Users\c1985\Desktop\TimeProfitEA\compile.log"
```

`/log` 参数将编译日志输出到文件，方便排查错误。编译后检查该日志确认是否通过。

## ⚠️ 强制要求：代码修改后必须同步更新 README

**所有功能逻辑相关的代码修改，在编译通过后，必须同步更新 `README.md` 文件。**
**将修改的功能部分同步写入 README，确保文档与代码保持一致。**

## 项目概述

**TimeProfitEA** — MQL5 智能交易系统（EA），用于 XAUUSD。策略：双 EMA 交叉判断趋势入场 + 时间止盈出场。

- **交易品种**：仅 XAUUSD（启动时校验）
- **时间周期**：仅 M5（启动时校验）
- **入场**：EMA 快慢线相对位置判断方向（非交叉检测，仅判断快线在慢线上方或下方）
- **出场**：时间止盈 — 每隔 N 分钟检查，若持仓盈利则平仓（支持白天/晚上独立参数）
- **止损**：固定点数止损，下单时附带（支持白天/晚上独立参数）
- **双时段**：以北京时间（UTC+8）为界，白天和晚上使用各自独立的止损和时间止盈参数

## 文件结构

| 文件 | 用途 |
|------|------|
| `TimeProfitEA.mq5` | 主文件 — 包含所有逻辑、输入参数和生命周期函数 |
| `TimeProfitEA.mqh` | 头文件 — 常量（`EA_NAME`）、枚举（`ENUM_SIGNAL`、`ENUM_SESSION`）、全局变量、函数声明 |

## 架构

### 生命周期
1. **`OnInit()`** — 校验品种/周期/参数，创建 EMA 指标句柄
2. **`OnDeinit()`** — 释放指标句柄
3. **`OnTick()`** — 每个 tick 调用，但仅在新 K 线形成时执行操作（`IsNewBar()`）

### OnTick 流程
```
新K线？→ 否 → 返回
       → 是 → SyncPositionSession()
              → 有持仓？
                  → 有 → CheckTimeProfit()（使用开仓时段参数）→ 触发 → ClosePosition()
                  → 无 → CheckEMASignal() → 做多/做空 → OpenPosition()（使用当前时段止损参数）
```

### 核心函数
- **`IsNewBar()`** — 比较当前 K 线时间与 `g_lastBarTime`，每根 K 线仅触发一次
- **`CheckEMASignal()`** — 读取 EMA[1]（上一根已收盘 K 线），快线 > 慢线返回 BUY，快线 < 慢线返回 SELL
- **`HasOpenPosition()`** — 遍历持仓，匹配 MagicNumber + 品种
- **`OpenPosition(signal)`** — 发送 `TRADE_ACTION_DEAL` 订单（IOC 成交），使用当前时段的止损参数
- **`ClosePosition()`** — 找到匹配持仓，发送反向订单平仓，清除持仓时段标记
- **`CheckTimeProfit()`** — 使用持仓开仓时段的参数，持仓时间 >= checkMinutes 且盈利 > 0 时，触发平仓信号

### 时段辅助函数
- **`GetCurrentSession()`** — 根据 `TimeGMT() + 8小时` 计算北京时间，判断当前属于白天/晚上时段
- **`IsNightSession()`** — 便捷判断当前是否为晚盘
- **`GetPositionSession()`** — 返回持仓开仓时所属时段（无持仓时返回当前时段）
- **`SyncPositionSession()`** — 持仓时首次记录所属时段，无持仓时清除记录

### 全局状态
- `g_emaFastHandle`、`g_emaSlowHandle` — 指标句柄（OnInit 创建，OnDeinit 释放）
- `g_lastBarTime` — 记录最后一根处理的 K 线时间，用于新K线判断
- `g_positionSession` / `g_hasPositionSession` — 记录当前持仓所属时段，开仓时写入，平仓时清除

## 双时段策略架构

EA 以北京时间（UTC+8）为界，将交易日分为白天和晚上两个时段，各自拥有独立的止损和时间止盈参数组。

- **时段判断**：`GetCurrentSession()` 使用 `TimeGMT() + 8小时` 计算北京时间，与经纪商服务器时区无关
- **跨午夜处理**：晚盘默认 21:30 ~ 03:00，`nightStartMinutes > nightEndMinutes` 时自动按跨午夜逻辑判断
- **参数锁定**：开仓时使用当前时段止损参数，时间止盈检查时沿用开仓时段参数，不随时间变化
- **时段追踪**：通过 `g_positionSession` / `g_hasPositionSession` 全局变量追踪，EA 重启后 `SyncPositionSession()` 会在首次检测到持仓时自动记录

## MQL5 注意事项

- `input` 变量**必须**放在主 `.mq5` 文件中（不能放在 `.mqh`），否则 MetaEditor 不会显示在参数界面
- K 线索引：`ArraySetAsSeries(arr, true)` 使索引 0 = 最新的 K 线
- 信号判断仅使用已收盘 K 线（索引 1+），索引 0 的 K 线仍在形成中
- 交易请求使用 `MqlTradeRequest`/`MqlTradeResult` 结构体，通过 `OrderSend()` 发送
