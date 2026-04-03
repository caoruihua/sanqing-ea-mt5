"""
该文件实现 Pullback（回撤确认）策略。

主要职责：
1. 在趋势方向明确时，识别价格回踩 EMA 后的拒绝形态；
2. 根据回撤后重新站回 EMA 的行为生成顺势信号；
3. 输出该策略对应的初始止损止盈。

说明：
- 该文件只输出信号；
- 不负责直接调用 MT5 下单。
"""

from typing import Optional

from src.domain.constants import (
    PULLBACK_EMA_TOLERANCE_ATR,
    PULLBACK_INITIAL_SL_ATR,
    PULLBACK_INITIAL_TP_ATR,
)
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision
from src.strategies.base import BaseStrategy


class PullbackStrategy(BaseStrategy):
    """Wait for EMA pullback rejection and rejoin trend direction."""

    def __init__(self, fixed_lots: float) -> None:
        self.fixed_lots = fixed_lots

    @property
    def name(self) -> str:
        return "Pullback"

    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        _ = state
        return snapshot.atr14 > 0

    def build_intent(
        self, snapshot: MarketSnapshot, state: RuntimeState
    ) -> Optional[SignalDecision]:
        _ = state
        if not self.can_trade(snapshot, state):
            return None

        body = abs(snapshot.close - snapshot.open)
        if body <= 0:
            return None

        tolerance = PULLBACK_EMA_TOLERANCE_ATR * snapshot.atr14

        lower_shadow = min(snapshot.open, snapshot.close) - snapshot.low
        upper_shadow = snapshot.high - max(snapshot.open, snapshot.close)

        bullish = (
            snapshot.ema_fast > snapshot.ema_slow
            and snapshot.low <= snapshot.ema_fast + tolerance
            and snapshot.close > snapshot.ema_fast
            and snapshot.close > snapshot.open
            and lower_shadow >= 0.5 * body
        )
        if bullish:
            entry = snapshot.ask
            return SignalDecision(
                strategy_name=self.name,
                order_type=OrderType.BUY,
                entry_price=entry,
                stop_loss=entry - PULLBACK_INITIAL_SL_ATR * snapshot.atr14,
                take_profit=entry + PULLBACK_INITIAL_TP_ATR * snapshot.atr14,
                atr_value=snapshot.atr14,
                lots=self.fixed_lots,
                conditions_met=["trend_up", "ema_reclaim", "bullish_rejection"],
            )

        bearish = (
            snapshot.ema_fast < snapshot.ema_slow
            and snapshot.high >= snapshot.ema_fast - tolerance
            and snapshot.close < snapshot.ema_fast
            and snapshot.close < snapshot.open
            and upper_shadow >= 0.5 * body
        )
        if bearish:
            entry = snapshot.bid
            return SignalDecision(
                strategy_name=self.name,
                order_type=OrderType.SELL,
                entry_price=entry,
                stop_loss=entry + PULLBACK_INITIAL_SL_ATR * snapshot.atr14,
                take_profit=entry - PULLBACK_INITIAL_TP_ATR * snapshot.atr14,
                atr_value=snapshot.atr14,
                lots=self.fixed_lots,
                conditions_met=["trend_down", "ema_reject", "bearish_rejection"],
            )

        return None
