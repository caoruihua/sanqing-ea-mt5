"""
该文件实现 ExpansionFollow（扩张跟随）策略。

主要职责：
1. 识别大实体、高量能、有效突破的扩张 K 线；
2. 在满足突破方向条件时生成买入/卖出信号；
3. 根据策略固定规则给出初始止损止盈。

说明：
- 该文件只负责信号判定；
- 不直接下单，也不负责账户状态管理。
"""

from typing import Optional

from src.domain.constants import (
    EXPANSION_FOLLOW_BODY_ATR_MIN,
    EXPANSION_FOLLOW_BODY_MEDIAN_RATIO_MIN,
    EXPANSION_FOLLOW_BODY_PREV3_MAX_RATIO_MIN,
    EXPANSION_FOLLOW_BODY_RANGE_RATIO_MIN,
    EXPANSION_FOLLOW_BREAKOUT_ATR_BUFFER,
    EXPANSION_FOLLOW_INITIAL_TP_ATR,
    EXPANSION_FOLLOW_STOP_LOSS_RANGE_RATIO,
    EXPANSION_FOLLOW_VOLUME_MA_RATIO_MIN,
)
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision
from src.strategies.base import BaseStrategy


class ExpansionFollowStrategy(BaseStrategy):
    """Enter after explosive closed bar confirms clean breakout direction."""

    def __init__(self, fixed_lots: float) -> None:
        self.fixed_lots = fixed_lots

    @property
    def name(self) -> str:
        return "ExpansionFollow"

    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        _ = state
        return (
            snapshot.atr14 > 0
            and snapshot.median_body_20 is not None
            and snapshot.prev3_body_max is not None
            and snapshot.volume_ma_20 is not None
            and snapshot.high_20 is not None
            and snapshot.low_20 is not None
        )

    def build_intent(
        self, snapshot: MarketSnapshot, state: RuntimeState
    ) -> Optional[SignalDecision]:
        _ = state
        if not self.can_trade(snapshot, state):
            return None

        median_body_20 = snapshot.median_body_20
        prev3_body_max = snapshot.prev3_body_max
        volume_ma_20 = snapshot.volume_ma_20
        high_20 = snapshot.high_20
        low_20 = snapshot.low_20
        if (
            median_body_20 is None
            or prev3_body_max is None
            or volume_ma_20 is None
            or high_20 is None
            or low_20 is None
        ):
            return None

        body = abs(snapshot.close - snapshot.open)
        range_ = snapshot.high - snapshot.low
        if body <= 0 or range_ <= 0:
            return None
        if median_body_20 <= 0 or prev3_body_max <= 0 or volume_ma_20 <= 0:
            return None

        if body / snapshot.atr14 < EXPANSION_FOLLOW_BODY_ATR_MIN:
            return None
        if body / median_body_20 < EXPANSION_FOLLOW_BODY_MEDIAN_RATIO_MIN:
            return None
        if body / prev3_body_max < EXPANSION_FOLLOW_BODY_PREV3_MAX_RATIO_MIN:
            return None
        if snapshot.volume / volume_ma_20 < EXPANSION_FOLLOW_VOLUME_MA_RATIO_MIN:
            return None
        if body / range_ < EXPANSION_FOLLOW_BODY_RANGE_RATIO_MIN:
            return None

        lower_shadow = min(snapshot.open, snapshot.close) - snapshot.low
        upper_shadow = snapshot.high - max(snapshot.open, snapshot.close)

        bullish = (
            snapshot.close > snapshot.open
            and lower_shadow / body <= 0.25
            and snapshot.close > high_20 + EXPANSION_FOLLOW_BREAKOUT_ATR_BUFFER * snapshot.atr14
        )
        if bullish:
            entry = snapshot.ask
            return SignalDecision(
                strategy_name=self.name,
                order_type=OrderType.BUY,
                entry_price=entry,
                stop_loss=snapshot.low + range_ * EXPANSION_FOLLOW_STOP_LOSS_RANGE_RATIO,
                take_profit=entry + EXPANSION_FOLLOW_INITIAL_TP_ATR * snapshot.atr14,
                atr_value=snapshot.atr14,
                lots=self.fixed_lots,
                conditions_met=["explosive_body", "volume_expansion", "breakout_up"],
            )

        bearish = (
            snapshot.close < snapshot.open
            and upper_shadow / body <= 0.25
            and snapshot.close < low_20 - EXPANSION_FOLLOW_BREAKOUT_ATR_BUFFER * snapshot.atr14
        )
        if bearish:
            entry = snapshot.bid
            return SignalDecision(
                strategy_name=self.name,
                order_type=OrderType.SELL,
                entry_price=entry,
                stop_loss=snapshot.high - range_ * EXPANSION_FOLLOW_STOP_LOSS_RANGE_RATIO,
                take_profit=entry - EXPANSION_FOLLOW_INITIAL_TP_ATR * snapshot.atr14,
                atr_value=snapshot.atr14,
                lots=self.fixed_lots,
                conditions_met=["explosive_body", "volume_expansion", "breakout_down"],
            )

        return None
