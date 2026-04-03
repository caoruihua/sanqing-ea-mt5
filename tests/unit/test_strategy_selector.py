"""Unit tests for strategy priority selector."""

from datetime import datetime

from src.core.strategy_selector import (
    NO_STRATEGY_SIGNAL,
    SUPPRESSED_BY_HIGHER_PRIORITY,
    StrategySelector,
)
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision
from src.strategies.base import BaseStrategy


def _build_snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=20260313,
        bid=2350.0,
        ask=2350.3,
        ema_fast=2349.5,
        ema_slow=2348.0,
        atr14=10.0,
        spread_points=15.0,
        last_closed_bar_time=datetime(2026, 4, 3, 10, 0, 0),
        close=2350.2,
        open=2346.0,
        high=2352.0,
        low=2345.0,
        volume=1_500_000,
        ema_fast_prev3=2345.0,
        ema_slow_prev3=2344.0,
        high_prev2=2349.0,
        high_prev3=2348.5,
        low_prev2=2339.0,
        low_prev3=2338.5,
    )


def _build_state() -> RuntimeState:
    return RuntimeState(day_key="2026.04.03")


class _SignalStrategy(BaseStrategy):
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        return True

    def build_intent(self, snapshot: MarketSnapshot, state: RuntimeState) -> SignalDecision:
        return SignalDecision(
            strategy_name=self.name,
            order_type=OrderType.BUY,
            entry_price=snapshot.ask,
            stop_loss=snapshot.ask - 1.2 * snapshot.atr14,
            take_profit=snapshot.ask + 2.0 * snapshot.atr14,
            atr_value=snapshot.atr14,
            lots=0.01,
        )


class _NoSignalStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "NoSignal"

    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        return True

    def build_intent(self, snapshot: MarketSnapshot, state: RuntimeState):
        return None


def test_priority_conflict_returns_only_highest_priority_signal() -> None:
    selector = StrategySelector(
        strategies=[
            _SignalStrategy("ExpansionFollow"),
            _SignalStrategy("Pullback"),
            _SignalStrategy("TrendContinuation"),
        ]
    )
    result = selector.select(snapshot=_build_snapshot(), state=_build_state())

    assert result.intent is not None
    assert result.intent.strategy_name == "ExpansionFollow"
    assert result.suppressed_reasons["Pullback"] == SUPPRESSED_BY_HIGHER_PRIORITY
    assert result.suppressed_reasons["TrendContinuation"] == SUPPRESSED_BY_HIGHER_PRIORITY


def test_no_signal_returns_reason_code() -> None:
    selector = StrategySelector(strategies=[_NoSignalStrategy()])
    result = selector.select(snapshot=_build_snapshot(), state=_build_state())

    assert result.intent is None
    assert result.rejection_reason == NO_STRATEGY_SIGNAL
