//+------------------------------------------------------------------+
//|                                                  README.md        |
//|              Sanqing EA MT5 - 黄金自动交易系统                    |
//+------------------------------------------------------------------+

# Sanqing EA MT5

基于 MT5 平台的黄金(XAUUSD)自动交易系统，MQL5 语言实现。

## 功能特性

### 三套策略（固定优先级）
1. **ExpansionFollow** (扩张跟随) - 最高优先级
   - 识别异常放大、放量、方向干净、并形成结构突破的爆发柱
   
2. **Pullback** (回撤确认) - 第二优先级
   - 在趋势方向中等待价格回踩快 EMA，并通过拒绝形态确认后入场
   
3. **TrendContinuation** (趋势延续) - 最低优先级
   - 在有效趋势中，跟随最近一根已收盘 K 线的结构突破继续入场

### 风险控制
- **日锁盈**: 基于服务器日，当日盈利达到阈值后禁止新开仓
- **两阶段ATR保护**:
  - Stage1: 盈利 >= 1.0x ATR 时，止损推进到保本附近
  - Stage2: 盈利 >= 1.5x ATR 时，启动追踪止损

### 核心约束
- 单一 symbol + magic 只允许一个持仓
- 所有交易决策基于已收盘 K 线
- 入场门控：重复bar过滤、日锁、交易次数、持仓检查、低波动过滤

## 项目结构

```
mt5-ea/
├── SanqingEA.mq5                    # 主EA入口
├── Include/
│   ├── Common.mqh                   # 公共定义、枚举、常量、结构体
│   ├── Indicators.mqh               # 技术指标计算（EMA/ATR）
│   ├── ContextBuilder.mqh           # 市场快照构建
│   ├── DailyRiskController.mqh      # 日风险控制
│   ├── ProtectionEngine.mqh         # 两阶段保护引擎
│   ├── StrategySelector.mqh         # 策略选择器
│   ├── EntryGate.mqh                # 入场门控
│   ├── ExecutionEngine.mqh          # 执行引擎
│   ├── StateStore.mqh               # 状态持久化（JSON）
│   └── Strategies/
│       ├── ExpansionFollowStrategy.mqh   # 扩张跟随策略
│       ├── PullbackStrategy.mqh          # 回撤策略
│       └── TrendContinuationStrategy.mqh # 趋势延续策略
└── README.md                        # 本文件
```

## 输入参数

### 交易参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| MagicNumber | 20260313 | 订单识别号 |
| FixedLots | 0.01 | 固定交易手数 |
| Slippage | 30 | 滑点（points） |
| MaxRetries | 6 | 下单最大重试次数 |

### 指标参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| EMA Fast Period | 9 | EMA 快线周期 |
| EMA Slow Period | 21 | EMA 慢线周期 |
| ATR Period | 14 | ATR 周期 |

### 风险控制
| 参数 | 默认值 | 说明 |
|------|--------|------|
| MaxTradesPerDay | 30 | 当日最大交易次数 |
| DailyProfitStopUsd | 50.0 | 日盈利锁定阈值（美元） |

### 波动率过滤
| 参数 | 默认值 | 说明 |
|------|--------|------|
| LowVolAtrPointsFloor | 300.0 | 低波动 ATR 点数下限 |
| LowVolAtrSpreadRatioFloor | 3.0 | 低波动 ATR/点差比率下限 |

## 安装与使用

1. 将 `mt5-ea` 文件夹复制到 MT5 的 MQL5 目录：
   - 实盘: `MT5/Data/MQL5/Experts/`
   - 测试: `MT5/Data/MQL5/Experts/`

2. 在 MetaEditor 中打开 `SanqingEA.mq5` 并编译

3. 在 MT5 终端中：
   - 将 EA 拖到 XAUUSD M5 图表上
   - 确保允许自动交易
   - 在 EA 属性中设置参数

## 主流程

```
OnTick() 触发
    ↓
构建市场快照 (MarketSnapshot)
    ↓
更新日风险状态
    ↓
检查持仓变化
    ↓
执行持仓保护（如有持仓）
    ↓
检查新收盘K线
    ↓
策略选择（ExpansionFollow → Pullback → TrendContinuation）
    ↓
入场门控检查
    ↓
执行下单
    ↓
更新状态并持久化
```

## 与 Python 项目的对应关系

| Python 模块 | MQL5 模块 |
|------------|-----------|
| src/core/context_builder.py | ContextBuilder.mqh |
| src/core/daily_risk_controller.py | DailyRiskController.mqh |
| src/core/protection_engine.py | ProtectionEngine.mqh |
| src/core/strategy_selector.py | StrategySelector.mqh |
| src/core/entry_gate.py | EntryGate.mqh |
| src/core/execution_engine.py | ExecutionEngine.mqh |
| src/core/state_store.py | StateStore.mqh |
| src/strategies/expansion_follow.py | Strategies/ExpansionFollowStrategy.mqh |
| src/strategies/pullback.py | Strategies/PullbackStrategy.mqh |
| src/strategies/trend_continuation.py | Strategies/TrendContinuationStrategy.mqh |

## 注意事项

- 本 EA 仅适用于 XAUUSD M5 周期
- 所有交易决策基于已收盘 K 线
- 状态持久化使用 JSON 格式，存储在 MQL5/Files 目录下
- 建议先在模拟账户测试

## 版本历史

- v1.0.0 (2026-04-09) - 初始版本
