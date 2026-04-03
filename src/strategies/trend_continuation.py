"""
该文件实现 TrendContinuation（趋势延续）策略。

主要职责：
1. 识别均线方向已经明确的趋势环境；
2. 判断最近收盘 K 线是否形成有效延续突破；
3. 在趋势延续成立时输出交易信号以及初始止损止盈。

说明：
- 该策略只负责分析，不直接发单；
- 实际发单由执行引擎统一处理。
"""

from typing import Optional

from src.domain.constants import (
    TREND_CONTINUATION_ATR_MULTIPLIER_BODY,
    TREND_CONTINUATION_ATR_MULTIPLIER_BREAKOUT,
    TREND_CONTINUATION_INITIAL_SL_ATR,
    TREND_CONTINUATION_INITIAL_TP_ATR,
)
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision
from src.strategies.base import BaseStrategy


class TrendContinuationStrategy(BaseStrategy):
    """Follow trend when closed bar confirms breakout continuation."""

    def __init__(self, fixed_lots: float) -> None:
        self.fixed_lots = fixed_lots

    @property
    def name(self) -> str:
        return "TrendContinuation"

    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        _ = state
        return (
            snapshot.atr14 > 0
            and snapshot.high_prev2 is not None
            and snapshot.high_prev3 is not None
            and snapshot.low_prev2 is not None
            and snapshot.low_prev3 is not None
        )

    def build_intent(
        self, snapshot: MarketSnapshot, state: RuntimeState
    ) -> Optional[SignalDecision]:
        _ = state
        if not self.can_trade(snapshot, state):
            return None

        high_prev2 = snapshot.high_prev2
        high_prev3 = snapshot.high_prev3
        low_prev2 = snapshot.low_prev2
        low_prev3 = snapshot.low_prev3
        if high_prev2 is None or high_prev3 is None or low_prev2 is None or low_prev3 is None:
            return None

        body = abs(snapshot.close - snapshot.open)
        if body < TREND_CONTINUATION_ATR_MULTIPLIER_BODY * snapshot.atr14:
            return None

        bullish_breakout = snapshot.close >= max(high_prev2, high_prev3) + (
            TREND_CONTINUATION_ATR_MULTIPLIER_BREAKOUT * snapshot.atr14
        )
        bearish_breakout = snapshot.close <= min(low_prev2, low_prev3) - (
            TREND_CONTINUATION_ATR_MULTIPLIER_BREAKOUT * snapshot.atr14
        )

        if snapshot.ema_fast > snapshot.ema_slow and bullish_breakout:
            entry = snapshot.ask
            return SignalDecision(
                strategy_name=self.name,
                order_type=OrderType.BUY,
                entry_price=entry,
                stop_loss=entry - TREND_CONTINUATION_INITIAL_SL_ATR * snapshot.atr14,
                take_profit=entry + TREND_CONTINUATION_INITIAL_TP_ATR * snapshot.atr14,
                atr_value=snapshot.atr14,
                lots=self.fixed_lots,
                conditions_met=["trend_up", "breakout_up", "body_strength_ok"],
            )

        if snapshot.ema_fast < snapshot.ema_slow and bearish_breakout:
            entry = snapshot.bid
            return SignalDecision(
                strategy_name=self.name,
                order_type=OrderType.SELL,
                entry_price=entry,
                stop_loss=entry + TREND_CONTINUATION_INITIAL_SL_ATR * snapshot.atr14,
                take_profit=entry - TREND_CONTINUATION_INITIAL_TP_ATR * snapshot.atr14,
                atr_value=snapshot.atr14,
                lots=self.fixed_lots,
                conditions_met=["trend_down", "breakout_down", "body_strength_ok"],
            )

        return None
