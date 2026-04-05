"""
该文件定义交易系统的领域模型。

主要职责：
1. 定义表示系统状态和决策的核心数据结构；
2. 提供 MarketSnapshot、SignalDecision、TradeIntent、RuntimeState 等核心模型；
3. 基于 mt5-rewrite-requirements.md 需求文档设计。

说明：
- 这些模型是系统各模块间传递数据的标准结构；
- 所有模型都支持序列化和反序列化，用于状态持久化。
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class OrderType(Enum):
    """订单类型枚举。"""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """订单状态枚举。"""

    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ProtectionStage(Enum):
    """保护阶段枚举。"""

    NONE = 0
    STAGE1 = 1  # 在 1.0 * ATR 位置启动保本保护
    STAGE2 = 2  # 在 1.5 * ATR 位置启动跟踪保护


@dataclass
class MarketSnapshot:
    """
    用于决策的市场快照，包含所需全部信息。

    基于需求文档第 6 节“市场快照与指标要求”设计。
    """

    symbol: str
    timeframe: int  # 单位为分钟，例如 M5 对应 5
    digits: int  # 价格小数位数
    magic_number: int
    bid: float
    ask: float
    ema_fast: float  # EMA 快线值
    ema_slow: float  # EMA 慢线值
    atr14: float  # ATR(14) 数值
    spread_points: float  # 点差，单位为 points
    last_closed_bar_time: datetime  # 最近已收盘 K 线的时间

    # 供策略计算使用的附加字段
    close: float  # 最近已收盘 K 线的收盘价
    open: float  # 最近已收盘 K 线的开盘价
    high: float  # 最近已收盘 K 线的最高价
    low: float  # 最近已收盘 K 线的最低价
    volume: float  # 最近已收盘 K 线的成交量

    # 趋势计算所需的历史数据
    ema_fast_prev3: Optional[float] = None  # 3 根前的 EMA 快线值
    ema_slow_prev3: Optional[float] = None  # 3 根前的 EMA 慢线值
    high_prev2: Optional[float] = None  # 2 根前的最高价
    high_prev3: Optional[float] = None  # 3 根前的最高价
    low_prev2: Optional[float] = None  # 2 根前的最低价
    low_prev3: Optional[float] = None  # 3 根前的最低价

    # 策略模块扩展指标（任务 4+）
    median_body_20: Optional[float] = None
    prev3_body_max: Optional[float] = None
    volume_ma_20: Optional[float] = None
    high_20: Optional[float] = None
    low_20: Optional[float] = None

    def __post_init__(self):
        """校验市场快照。"""
        if self.bid <= 0:
            raise ValueError(f"Bid price must be positive: {self.bid}")
        if self.ask <= 0:
            raise ValueError(f"Ask price must be positive: {self.ask}")
        if self.ask <= self.bid:
            raise ValueError(f"Ask price ({self.ask}) must be greater than bid ({self.bid})")
        if self.atr14 < 0:
            raise ValueError(f"ATR must be non-negative: {self.atr14}")
        if self.spread_points < 0:
            raise ValueError(f"Spread points must be non-negative: {self.spread_points}")


@dataclass
class SignalDecision:
    """
    策略生成的信号决策。

    表示某个策略模块产出的交易信号。
    """

    strategy_name: str
    order_type: OrderType
    entry_price: float  # 建议入场价
    stop_loss: float  # 初始止损
    take_profit: float  # 初始止盈
    atr_value: float  # 计算中使用的 ATR 值
    lots: float  # 手数（来自 FixedLots）

    # 供日志与调试使用的元数据
    confidence_score: float = 1.0  # 取值范围 0.0 到 1.0
    signal_strength: float = 1.0  # 相对强度指标
    conditions_met: List[str] = field(default_factory=list)  # 已满足的条件列表

    def __post_init__(self):
        """校验信号决策。"""
        if self.entry_price <= 0:
            raise ValueError(f"Entry price must be positive: {self.entry_price}")
        if self.lots <= 0:
            raise ValueError(f"Lot size must be positive: {self.lots}")
        if self.atr_value <= 0:
            raise ValueError(f"ATR value must be positive: {self.atr_value}")


@dataclass
class TradeIntent:
    """
    已准备进入执行阶段的交易意图。

    这是通过所有校验与门控之后，最终形成的交易执行决定。
    """

    signal_decision: SignalDecision
    market_snapshot: MarketSnapshot

    # 执行元数据
    action_id: str  # 当前交易尝试的唯一标识
    timestamp: datetime = field(default_factory=datetime.now)

    # 执行参数
    slippage: int = 30  # 默认允许滑点，单位为 points
    comment: str = ""  # 订单备注

    def __post_init__(self):
        """校验交易意图。"""
        if not self.action_id:
            raise ValueError("Action ID cannot be empty")


@dataclass
class ProtectionState:
    """
    活跃持仓的保护状态。

    基于需求文档第 13 节“运行时状态持久化要求”设计。
    """

    protection_stage: ProtectionStage = ProtectionStage.NONE
    entry_price: Optional[float] = None
    entry_atr: Optional[float] = None
    highest_close_since_entry: Optional[float] = None
    lowest_close_since_entry: Optional[float] = None
    trailing_active: bool = False

    # 分阶段专属数据
    stage1_activated_at: Optional[datetime] = None
    stage2_activated_at: Optional[datetime] = None

    def __post_init__(self):
        """校验保护状态。"""
        if self.entry_price is not None and self.entry_price <= 0:
            raise ValueError(f"Entry price must be positive: {self.entry_price}")
        if self.entry_atr is not None and self.entry_atr <= 0:
            raise ValueError(f"Entry ATR must be positive: {self.entry_atr}")


@dataclass
class RuntimeState:
    """
    为保证重启连续性而必须持久化的运行时状态。

    基于需求文档第 13 节“运行时状态持久化要求”设计。
    """

    day_key: str  # 服务器日标识，格式为 YYYY.MM.DD
    daily_locked: bool = False
    daily_closed_profit: float = 0.0  # 当日已实现盈亏
    trades_today: int = 0
    last_entry_bar_time: Optional[datetime] = None

    # 当前活跃持仓状态（如有）
    protection_state: ProtectionState = field(default_factory=ProtectionState)

    # 仓位管理的附加状态
    entry_price: Optional[float] = None
    entry_atr: Optional[float] = None
    highest_close_since_entry: Optional[float] = None
    lowest_close_since_entry: Optional[float] = None
    trailing_active: bool = False

    # 系统状态
    last_processed_bar_time: Optional[datetime] = None
    position_ticket: Optional[int] = None  # MT5 持仓 ticket
    last_position_ticket: Optional[int] = None  # 用于检测持仓消失的上一次持仓 ticket
    position_strategy: Optional[str] = None  # 当前持仓的策略名称

    def __post_init__(self):
        """校验运行时状态。"""
        if not self.day_key:
            raise ValueError("Day key cannot be empty")
        if self.daily_closed_profit < 0:
            # 如果当日有亏损交易，已实现盈亏为负是正常情况。
            pass  # 允许为负值
        if self.trades_today < 0:
            raise ValueError(f"Trades today cannot be negative: {self.trades_today}")

    def to_dict(self) -> Dict[str, Any]:
        """把运行时状态转换成可序列化的字典。"""
        data = asdict(self)

        # 将 datetime 对象转换为 ISO 格式字符串。
        def convert_value(value: Any) -> Any:
            if isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, ProtectionStage):
                return value.value
            elif isinstance(value, ProtectionState):
                return asdict(value)
            elif isinstance(value, Enum):
                return value.value
            else:
                return value

        # 递归应用转换规则。
        def convert_dict(d: Dict[str, Any]) -> Dict[str, Any]:
            result = {}
            for key, value in d.items():
                if isinstance(value, dict):
                    result[key] = convert_dict(value)
                elif isinstance(value, list):
                    result[key] = [convert_value(item) for item in value]
                else:
                    result[key] = convert_value(value)
            return result

        return convert_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeState":
        """根据字典创建运行时状态对象（反序列化）。"""

        # 将字符串日期恢复为 datetime 对象。
        def convert_value(key: str, value: Any) -> Any:
            if key in [
                "last_entry_bar_time",
                "last_processed_bar_time",
                "stage1_activated_at",
                "stage2_activated_at",
            ]:
                if value and isinstance(value, str):
                    try:
                        return datetime.fromisoformat(value)
                    except (ValueError, AttributeError):
                        return None
            elif key == "protection_stage" and value is not None:
                return ProtectionStage(value)
            elif key == "protection_state" and isinstance(value, dict):
                # 处理嵌套的 ProtectionState。
                protection_data = value.copy()
                if "protection_stage" in protection_data:
                    protection_data["protection_stage"] = ProtectionStage(
                        protection_data["protection_stage"]
                    )
                # 转换嵌套对象中的 datetime 字段。
                if "stage1_activated_at" in protection_data:
                    stage1_value = protection_data["stage1_activated_at"]
                    if stage1_value and isinstance(stage1_value, str):
                        try:
                            protection_data["stage1_activated_at"] = datetime.fromisoformat(
                                stage1_value
                            )
                        except (ValueError, AttributeError):
                            protection_data["stage1_activated_at"] = None
                if "stage2_activated_at" in protection_data:
                    stage2_value = protection_data["stage2_activated_at"]
                    if stage2_value and isinstance(stage2_value, str):
                        try:
                            protection_data["stage2_activated_at"] = datetime.fromisoformat(
                                stage2_value
                            )
                        except (ValueError, AttributeError):
                            protection_data["stage2_activated_at"] = None
                return ProtectionState(**protection_data)
            return value

        converted_data = {}
        for key, value in data.items():
            converted_data[key] = convert_value(key, value)

        return cls(**converted_data)

    def to_json(self) -> str:
        """将运行时状态序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "RuntimeState":
        """从 JSON 字符串反序列化运行时状态。"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def reset_for_new_day(self, new_day_key: str) -> None:
        """在新交易日开始时重置日内计数器。"""
        self.day_key = new_day_key
        self.daily_locked = False
        self.daily_closed_profit = 0.0
        self.trades_today = 0
        # 注意：last_entry_bar_time 不重置，它与 bar 相关，而不是与交易日相关。
