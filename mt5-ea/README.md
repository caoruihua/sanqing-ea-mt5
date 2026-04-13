# Sanqing EA MT5 - MQL5 交易策略

## 目录结构

```
mt5-ea/
├── cleanup.bat          # 清理编译产物脚本
├── Core/                # 核心模块
│   ├── ContextBuilder.mqh   # 市场数据构建器
│   └── Indicators.mqh       # 技术指标计算
├── Main/                # 主程序入口
│   ├── Common.mqh       # 公共定义和结构体
│   └── SanqingEA.mq5    # EA主程序（需创建）
└── Strategies/          # 策略模块
    ├── ReversalStrategy.mqh      # 反转策略
    └── TrendContinuationStrategy.mqh  # 趋势延续策略
```

## 编译方法

### 方法一：MetaEditor 编译（推荐）

1. 打开 MetaTrader 5 终端
2. 按 `F4` 打开 MetaEditor
3. 在 MetaEditor 中，选择 `文件` -> `打开数据文件夹`
4. 将 `mt5-ea` 目录下的所有文件复制到 `MQL5/Experts/` 目录
5. 在 MetaEditor 中打开 `Main/SanqingEA.mq5`
6. 按 `F7` 或点击 `编译` 按钮进行编译
7. 编译成功后，`SanqingEA.ex5` 文件会生成在 `Main/` 目录下

### 方法二：命令行编译

如果你知道 MT5 的安装路径，可以使用命令行编译：

```powershell
# 示例：使用 MT5 的编译器（路径根据实际安装位置调整）
& "C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile:"Main\SanqingEA.mq5" /log
```

### 方法三：使用清理脚本

编译前可以运行清理脚本清除旧的编译产物：

```powershell
.\cleanup.bat
```

## 文件说明

### Core/ 核心模块

| 文件 | 说明 |
|------|------|
| `ContextBuilder.mqh` | 构建市场快照数据，包含价格、指标、历史数据等 |
| `Indicators.mqh` | 技术指标计算函数（EMA、ATR、ADX等） |

### Main/ 主程序

| 文件 | 说明 |
|------|------|
| `Common.mqh` | 公共定义：参数常量、数据结构、工具函数 |
| `SanqingEA.mq5` | EA 入口程序（需要创建） |

### Strategies/ 策略模块

| 文件 | 说明 |
|------|------|
| `ReversalStrategy.mqh` | 反转策略：冲刺末端检测 + K线形态反转信号 |
| `TrendContinuationStrategy.mqh` | 趋势延续策略 |

## 策略参数

### 反转策略（ReversalStrategy）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `REVERSAL_MOVE_ATR_MULTIPLIER` | 2.8 | 明显涨跌检测：ATR倍数阈值 |
| `REVERSAL_STOP_BUFFER_DOLLAR` | 6.0 | 反转止损缓冲（美元） |
| `REVERSAL_TP_ATR_MULTIPLIER` | 2.5 | 反转止盈ATR倍数 |

## 注意事项

1. **编码格式**：所有 `.mqh` 和 `.mq5` 文件使用 UTF-8 编码
2. **换行符**：Windows 使用 CRLF，Git 会自动转换
3. **依赖关系**：
   - `SanqingEA.mq5` 依赖 `Common.mqh`
   - 策略文件依赖 `Common.mqh` 和 `Core/*.mqh`
4. **编译顺序**：无特定顺序要求，编译器会自动处理依赖

## 开发流程

1. 修改 `.mqh` 或 `.mq5` 源文件
2. 在 MetaEditor 中编译（F7）
3. 在 MT5 终端中测试 EA
4. 使用 `cleanup.bat` 清理编译产物（可选）