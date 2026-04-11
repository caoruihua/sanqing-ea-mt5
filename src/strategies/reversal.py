"""
该文件实现 Reversal（反转）策略。

主要职责：
1. 识别价格反转形态；
2. 判断反转信号是否有效；
3. 在反转形态成立时输出交易信号以及初始止损止盈。

说明：
- 该策略只负责分析，不直接发单；
- 实际发单由执行引擎统一处理。
"""

from typing import Optional

from src.domain.constants import (
    REVERSAL_DARKCLOUD_COVERAGE_MIN,
    REVERSAL_EMA_TOLERANCE_ATR,
    REVERSAL_INITIAL_TP_ATR,
    REVERSAL_SHADOW_BODY_RATIO_MIN,
    REVERSAL_STOP_BUFFER_POINTS,
)
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision
from src.strategies.base import BaseStrategy


class ReversalStrategy(BaseStrategy):
    """当收盘 K 线确认价格反转形态时入场。"""

    def __init__(self, fixed_lots: float) -> None:
        self.fixed_lots = fixed_lots

    @property
    def name(self) -> str:
        return "Reversal"

    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        """返回当前策略是否满足评估前提。"""
        _ = state
        # 基础数据检查
        if not (
            snapshot.atr14 > 0
            and snapshot.prev_open is not None
            and snapshot.prev_close is not None
            and snapshot.high_3 is not None
            and snapshot.low_3 is not None
            and snapshot.ema_fast is not None
            and snapshot.ema_slow is not None
            and snapshot.ema_fast_prev3 is not None
            and snapshot.ema_slow_prev3 is not None
        ):
            return False

        return True

    def _is_uptrend(self, snapshot: MarketSnapshot) -> bool:
        """判断是否为上涨趋势。

        上涨趋势定义：
        1. 价格在EMA之上（close > ema_fast）
        2. EMA向上（当前EMA > 3根前EMA）
        """
        return (
            snapshot.close > snapshot.ema_fast
            and snapshot.ema_fast > snapshot.ema_fast_prev3
        )

    def _is_downtrend(self, snapshot: MarketSnapshot) -> bool:
        """判断是否为下跌趋势。

        下跌趋势定义：
        1. 价格在EMA之下（close < ema_fast）
        2. EMA向下（当前EMA < 3根前EMA）
        """
        return (
            snapshot.close < snapshot.ema_fast
            and snapshot.ema_fast < snapshot.ema_fast_prev3
        )

    def build_intent(
        self, snapshot: MarketSnapshot, state: RuntimeState
    ) -> Optional[SignalDecision]:
        """在条件满足时返回信号决策。"""
        if not self.can_trade(snapshot, state):
            return None

        # 确保所需的历史数据存在
        if (
            snapshot.prev_open is None
            or snapshot.prev_close is None
            or snapshot.high_3 is None
            or snapshot.low_3 is None
        ):
            return None

        # 检测反转形态
        conditions_met = []
        order_type = None
        entry_price = None

        # 检测乌云压顶形态（看跌反转，只在上涨趋势中有效）
        if self._is_uptrend(snapshot) and self._detect_dark_cloud_cover(
            snapshot.prev_open, snapshot.prev_close, snapshot.prev_high, snapshot.open, snapshot.close
        ):
            conditions_met.append("dark_cloud_cover")
            order_type = OrderType.SELL
            entry_price = snapshot.bid  # 卖出用bid价

        # 检测长上影线形态（看跌反转，只在上涨趋势中有效）
        elif self._is_uptrend(snapshot) and self._detect_long_upper_shadow(snapshot.open, snapshot.close, snapshot.high, snapshot.low):
            conditions_met.append("long_upper_shadow")
            order_type = OrderType.SELL
            entry_price = snapshot.bid  # 卖出用bid价

        # 检测长下影线形态（看涨反转，只在下跌趋势中有效）
        elif self._is_downtrend(snapshot) and self._detect_long_lower_shadow(snapshot.open, snapshot.close, snapshot.low, snapshot.high):
            conditions_met.append("long_lower_shadow")
            order_type = OrderType.BUY
            entry_price = snapshot.ask  # 买入用ask价

        # 如果没有检测到任何形态，返回None
        if not conditions_met or order_type is None or entry_price is None:
            return None

        # 检查是否需要的高低点数据存在
        if snapshot.high_20 is None or snapshot.low_20 is None:
            return None

        # 计算止损止盈
        stop_loss = None
        take_profit = None

        # 计算20根K线区间范围的60%位置
        range_20 = snapshot.high_20 - snapshot.low_20

        if order_type == OrderType.BUY:
            # 做多止损：最近3根K线最低价 - 3美元
            stop_loss = snapshot.low_3 - REVERSAL_STOP_BUFFER_POINTS
            # 做多止盈：前20根K线最低点 + 60%区间范围
            take_profit = snapshot.low_20 + range_20 * 0.6
        else:  # OrderType.SELL
            # 做空止损：最近3根K线最高价 + 3美元
            stop_loss = snapshot.high_3 + REVERSAL_STOP_BUFFER_POINTS
            # 做空止盈：前20根K线最高点 - 60%区间范围
            take_profit = snapshot.high_20 - range_20 * 0.6

        # 创建信号决策
        return SignalDecision(
            strategy_name=self.name,
            order_type=order_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            atr_value=snapshot.atr14,
            lots=self.fixed_lots,
            conditions_met=conditions_met,
        )

    def _detect_dark_cloud_cover(
        self, prev_open: float, prev_close: float, prev_high: float, current_open: float, current_close: float
    ) -> bool:
        """检测乌云压顶形态。

        乌云压顶定义：
        1. 前一根K线为阳线（close > open）
        2. 当前K线跳空高开（open > prev_high）
        3. 当前K线为阴线（close < open）
        4. 当前阴线实体深入前一根阳线实体50%以上

        Args:
            prev_open: 前一根K线的开盘价
            prev_close: 前一根K线的收盘价
            prev_high: 前一根K线的最高价
            current_open: 当前K线的开盘价
            current_close: 当前K线的收盘价

        Returns:
            bool: 如果检测到乌云压顶返回True，否则返回False
        """
        # 前一根K线必须是阳线
        if prev_close <= prev_open:
            return False

        # 当前K线必须跳空高开（开盘价高于前一根最高价）
        if current_open <= prev_high:
            return False

        # 当前K线必须是阴线
        if current_close >= current_open:
            return False

        # 计算前一根阳线的实体长度
        prev_body = prev_close - prev_open
        if prev_body <= 0:
            return False

        # 计算当前阴线深入前一根阳线实体的比例
        # 公式: (prev_close - current_close) / (prev_close - prev_open)
        penetration = (prev_close - current_close) / prev_body

        # 需要深入50%以上
        return penetration >= REVERSAL_DARKCLOUD_COVERAGE_MIN

    def _detect_long_upper_shadow(self, open_price: float, close_price: float, high: float, low: float) -> bool:
        """检测长上影线形态。

        长上影线定义：
        - 上影线长度 >= 实体长度的2.0倍
        - 上影线 = high - max(open, close)
        - 实体 = abs(close - open)
        - 上影线必须明显长于下影线（排除十字星）

        Args:
            open_price: K线的开盘价
            close_price: K线的收盘价
            high: K线的最高价
            low: K线的最低价

        Returns:
            bool: 如果检测到长上影线返回True，否则返回False
        """
        # 计算实体长度
        body = abs(close_price - open_price)
        if body <= 0:
            return False

        # 计算上影线长度
        upper_shadow = high - max(open_price, close_price)

        # 计算下影线长度
        lower_shadow = min(open_price, close_price) - low

        # 检查上影线长度是否达到实体长度的2倍
        if upper_shadow < body * REVERSAL_SHADOW_BODY_RATIO_MIN:
            return False

        # 关键：上影线必须明显长于下影线（3倍以上），排除十字星
        if lower_shadow > 0 and upper_shadow < lower_shadow * 3:
            return False

        return True

    def _detect_long_lower_shadow(self, open_price: float, close_price: float, low: float, high: float) -> bool:
        """检测长下影线形态。

        长下影线定义：
        - 下影线长度 >= 实体长度的2.0倍
        - 下影线 = min(open, close) - low
        - 实体 = abs(close - open)
        - 下影线必须明显长于上影线（排除十字星）

        Args:
            open_price: K线的开盘价
            close_price: K线的收盘价
            low: K线的最低价
            high: K线的最高价

        Returns:
            bool: 如果检测到长下影线返回True，否则返回False
        """
        # 计算实体长度
        body = abs(close_price - open_price)
        if body <= 0:
            return False

        # 计算下影线长度
        lower_shadow = min(open_price, close_price) - low

        # 计算上影线长度
        upper_shadow = high - max(open_price, close_price)

        # 检查下影线长度是否达到实体长度的2倍
        if lower_shadow < body * REVERSAL_SHADOW_BODY_RATIO_MIN:
            return False

        # 关键：下影线必须明显长于上影线（3倍以上），排除十字星
        if upper_shadow > 0 and lower_shadow < upper_shadow * 3:
            return False

        return True
