# sanqing-ea-mt5

这是一个 **只负责策略分析与向本机 MT5 终端发送指令** 的 Python 项目。

你自己在电脑上把 MT5 终端打开并登录好即可；本项目**不负责管理你本机 MT5 是模拟盘还是实盘**，也不负责自动登录账户。项目的职责只有：

1. 从本机 MT5 读取行情/K线；
2. 计算指标并分析策略；
3. 按规则生成交易信号；
4. 把下单指令发送给本机 MT5 终端。

## 1. 项目框架（架构）

```
sanqing-ea-mt5/
├── src/                         # 核心源代码
│   ├── app/                     # 运行入口与主编排
│   │   ├── orchestrator.py      # 主编排器
│   │   ├── run.py               # 入口模块
│   │   ├── poll_ingress.py      # 轮询入口
│   │   ├── tick_http_ingress.py # HTTP Tick入口
│   │   └── tick_ingress.py      # Tick入口基类
│   ├── core/                    # 核心流程
│   │   ├── context_builder.py   # 快照构建
│   │   ├── strategy_selector.py # 策略选择
│   │   ├── entry_gate.py        # 开仓门控
│   │   ├── execution_engine.py  # 执行引擎
│   │   ├── protection_engine.py # 保护引擎
│   │   ├── daily_risk_controller.py  # 日风险控制
│   │   ├── state_store.py       # 状态持久化
│   │   └── reconciliation.py    # 对账
│   ├── strategies/              # 三策略信号模块
│   │   ├── expansion_follow.py  # 扩张跟随策略
│   │   ├── pullback.py          # 回撤策略
│   │   └── trend_continuation.py # 趋势延续策略
│   ├── adapters/                # 交易适配层
│   │   ├── mt5_broker.py        # MT5券商适配器
│   │   └── sim_broker.py        # 模拟券商适配器
│   ├── indicators/              # 技术指标（使用 pandas-ta）
│   │   ├── ema.py               # EMA计算（pandas-ta）
│   │   └── atr.py               # ATR计算（pandas-ta）
│   ├── domain/                  # 领域模型
│   │   ├── models.py            # 数据模型
│   │   └── constants.py         # 常量定义
│   └── utils/                   # 工具模块
│       ├── logger.py            # 结构化日志
│       └── rounding.py          # 精度处理
├── tests/                       # 测试目录
│   ├── unit/                    # 单元测试（20个）
│   ├── integration/             # 集成测试（9个）
│   └── e2e/                     # 语义回归测试
├── config/                      # 配置文件
│   ├── runtime.ini              # 本地运行配置
│   └── runtime.ini.example      # 配置模板
├── mt5/                         # MT5集成
│   └── TickRelay.mq5            # Tick事件接收EA
├── scripts/                     # 脚本工具
│   └── run_semantic_suite.py    # 语义回归套件
├── run.py                       # 根目录主入口（推荐）
├── pyproject.toml               # 项目配置与依赖
└── README.md                    # 本文件
```

## 2. 运行时依赖

**运行时依赖**：
- `MetaTrader5` - 官方 MT5 Python API
- `pandas` >= 2.0.0 - 数据处理
- `pandas-ta` >= 0.3.14 - 技术指标计算

**开发依赖**：
- `pytest`, `pytest-cov`, `ruff`

**注意**：`MetaTrader5` 包会传递性安装 `numpy` 作为依赖。

## 3. 快速开始

### 3.1 创建虚拟环境并安装依赖

> 严格使用项目内 `.venv`，不要用全局 Python。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
uv pip install -e .[dev]
```

### 3.2 准备配置

项目已包含 `config/runtime.ini`。你也可以基于模板重建：

```powershell
copy config\runtime.ini.example config\runtime.ini
```

其中 `runtime` 段用于控制运行输出路径：

```ini
[runtime]
log_path = logs/runtime.log
state_path = state/runtime_state.json
trigger_mode = poll
tick_host = 127.0.0.1
tick_port = 8765
queue_policy = fifo
```

## 4. 怎么使用

### 4.1 启动前准备

在运行 Python 项目前，请先手动完成：

1. 打开你电脑上的 **MetaTrader 5**；
2. 用你自己的账户手动登录；
3. 确认目标交易品种在终端里可见；
4. 确认终端允许 Python 连接。

> 项目不会帮你区分模拟盘/实盘，也不会帮你登录。

### 4.2 从根目录主入口运行（推荐）

执行一次分析/决策：

```powershell
uv run python run.py --config config/runtime.ini --once
```

持续轮询运行：

```powershell
uv run python run.py --config config/runtime.ini --poll-sec 2
```

按真实 tick 事件触发运行：

```powershell
uv run python run.py --config config/runtime.ini --trigger-mode tick_http
```

> `tick_http` 模式下，Python 运行时会等待本机 `TickRelay.mq5` 推送 tick 唤醒事件；入场策略仍然只对**已收盘 K 线**做决策。

### 4.3 旧入口仍可用

```powershell
uv run python -m app.run --config config/runtime.ini --once
```

## 5. 主运行链路说明

当前主链路如下：

```text
本机 MT5 K线/报价
    -> ContextBuilder 构建 MarketSnapshot
    -> StrategySelector 选择最高优先级策略
    -> EntryGate 做开仓门控
    -> ExecutionEngine 调用 MT5BrokerAdapter.send_order
    -> MT5 官方库 order_send
```

也就是说，项目本质上是一个：

> **本机 MT5 指令发送型策略客户端**

## 6. 配置重点

你主要会关心这些配置：

```ini
[runtime]
log_path = logs/runtime.log
state_path = state/runtime_state.json
trigger_mode = poll
tick_host = 127.0.0.1
tick_port = 8765
queue_policy = fifo

[symbol]
symbol = XAUUSD

[timeframe]
timeframe = 5

[magic]
magic = 20260313

[trading]
fixed_lots = 0.01
slippage = 30
max_retries = 6
```

## 7. 开发与验证命令

```powershell
# 全量测试
uv run python -m pytest -q

# 代码规范检查
uv run python -m ruff check src tests app scripts

# 语义回归报告
uv run python scripts/run_semantic_suite.py --out .sisyphus/evidence/task-12-semantic-suite.json
```

## 8. TickRelay 与回滚

启用 `tick_http` 前，请在 MT5 里：

1. 把 `mt5/TickRelay.mq5` 挂到目标品种图表；
2. 在 **Tools -> Options -> Expert Advisors** 中把 `http://127.0.0.1:8765` 加入 `WebRequest` 白名单；
3. 保持 Python 运行时与 TickRelay 使用同一个 symbol。

如果要快速回滚到旧模式：

1. 停止/移除 `TickRelay.mq5`；
2. 用 `uv run python run.py --config config/runtime.ini --trigger-mode poll --poll-sec 2` 重启；
3. 确认日志中不再出现 `收到 tick 事件` 字样。

## 9. 关键行为说明

- 策略优先级固定：`ExpansionFollow -> Pullback -> TrendContinuation`
- 仅对已收盘 K 线决策
- `symbol + magic` 单持仓约束
- 日锁盈按服务器日生效，跨日重置
- 两阶段 ATR 保护（1.0x / 1.5x）
- 运行状态持久化（JSON 原子写）并支持重启恢复

## 10. 三套策略说明

### 10.1 ExpansionFollow（扩张跟随）
识别"异常放大、放量、方向干净、并形成结构突破"的爆发柱，然后顺势入场。

### 10.2 Pullback（回撤）
在趋势方向中等待价格回踩快 EMA，并通过拒绝形态确认后入场。

### 10.3 TrendContinuation（趋势延续）
在有效趋势中，跟随最近一根已收盘 K 线的结构突破继续入场。

## 11. 参考

- 需求文档：`mt5-rewrite-requirements.md`
- 运维说明：`README-ops.md`
