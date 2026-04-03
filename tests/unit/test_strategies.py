"""Unit tests for three strategy modules."""

from datetime import datetime

from src.domain.models import MarketSnapshot, OrderType, RuntimeState
from src.strategies.expansion_follow import ExpansionFollowStrategy
from src.strategies.pullback import PullbackStrategy
from src.strategies.trend_continuation import TrendContinuationStrategy


def _state() -> RuntimeState:
    return RuntimeState(day_key="2026.04.03")


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=20260313,
        bid=2350.0,
        ask=2350.3,
        ema_fast=2350.0,
        ema_slow=2340.0,
        atr14=10.0,
        spread_points=15.0,
        last_closed_bar_time=datetime(2026, 4, 3, 10, 0, 0),
        close=2354.0,
        open=2348.0,
        high=2356.0,
        low=2345.5,
        volume=1_900_000,
        ema_fast_prev3=2344.0,
        ema_slow_prev3=2338.0,
        high_prev2=2350.5,
        high_prev3=2349.2,
        low_prev2=2338.0,
        low_prev3=2337.5,
    )


def test_trend_continuation_bullish_signal() -> None:
    strategy = TrendContinuationStrategy(fixed_lots=0.01)
    intent = strategy.build_intent(snapshot=_snapshot(), state=_state())

    assert intent is not None
    assert intent.order_type == OrderType.BUY
    assert intent.strategy_name == "TrendContinuation"


def test_pullback_bullish_rejection_signal() -> None:
    strategy = PullbackStrategy(fixed_lots=0.01)
    snapshot = _snapshot()
    snapshot.open = snapshot.ema_fast - 0.3
    snapshot.close = snapshot.ema_fast + 0.2
    snapshot.low = snapshot.open - 0.3
    snapshot.high = snapshot.close + 0.2
    intent = strategy.build_intent(snapshot=snapshot, state=_state())

    assert intent is not None
    assert intent.order_type == OrderType.BUY
    assert intent.strategy_name == "Pullback"


def test_expansion_follow_bullish_signal() -> None:
    strategy = ExpansionFollowStrategy(fixed_lots=0.01)
    snapshot = _snapshot()
    snapshot.open = 2320.0
    snapshot.close = 2365.0
    snapshot.high = 2366.0
    snapshot.low = 2318.0
    snapshot.volume = 2_500_000
    snapshot.high_prev2 = 2340.0
    snapshot.high_prev3 = 2342.0
    snapshot.low_prev2 = 2325.0
    snapshot.low_prev3 = 2328.0
    snapshot.median_body_20 = 12.0
    snapshot.prev3_body_max = 22.0
    snapshot.volume_ma_20 = 900_000.0
    snapshot.high_20 = 2342.0
    snapshot.low_20 = 2290.0
    intent = strategy.build_intent(snapshot=snapshot, state=_state())

    assert intent is not None
    assert intent.order_type == OrderType.BUY
    assert intent.strategy_name == "ExpansionFollow"
