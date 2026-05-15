from datetime import datetime

import pytest

from src.domain.models import MarketSnapshot, OrderType, RuntimeState
from src.strategies.bare_k import BareKStrategy


def _make_snapshot(closes, opens) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=123,
        bid=closes[-1] - 0.1,
        ask=closes[-1] + 0.1,
        spread_points=10.0,
        last_closed_bar_time=datetime.now(),
        close=closes[-1],
        open=opens[-1],
        high=max(closes[-1], opens[-1]) + 0.5,
        low=min(closes[-1], opens[-1]) - 0.5,
        opens_history=opens,
        closes_history=closes,
        highs_history=[max(c, o) + 0.5 for c, o in zip(closes, opens)],
        lows_history=[min(c, o) - 0.5 for c, o in zip(closes, opens)],
    )


def test_three_bullish_bars_generates_buy():
    opens = [1900.0, 1901.0, 1902.0]
    closes = [1901.0, 1902.0, 1903.0]
    snapshot = _make_snapshot(closes, opens)
    state = RuntimeState(day_key="2026.05.15")
    strategy = BareKStrategy(consecutive_bars=3, fixed_lots=0.01)

    assert strategy.can_trade(snapshot, state) is True
    intent = strategy.build_intent(snapshot, state)
    assert intent is not None
    assert intent.order_type == OrderType.BUY
    assert intent.profit_target_usd == 10.0


def test_three_bearish_bars_generates_sell():
    opens = [1903.0, 1902.0, 1901.0]
    closes = [1902.0, 1901.0, 1900.0]
    snapshot = _make_snapshot(closes, opens)
    state = RuntimeState(day_key="2026.05.15")
    strategy = BareKStrategy(consecutive_bars=3, fixed_lots=0.01)

    intent = strategy.build_intent(snapshot, state)
    assert intent is not None
    assert intent.order_type == OrderType.SELL


def test_mixed_direction_returns_none():
    opens = [1900.0, 1901.0, 1902.0]
    closes = [1901.0, 1900.0, 1903.0]
    snapshot = _make_snapshot(closes, opens)
    state = RuntimeState(day_key="2026.05.15")
    strategy = BareKStrategy(consecutive_bars=3, fixed_lots=0.01)

    assert strategy.build_intent(snapshot, state) is None


def test_insufficient_history_returns_none():
    opens = [1900.0, 1901.0]
    closes = [1901.0, 1902.0]
    snapshot = _make_snapshot(closes, opens)
    state = RuntimeState(day_key="2026.05.15")
    strategy = BareKStrategy(consecutive_bars=3, fixed_lots=0.01)

    assert strategy.can_trade(snapshot, state) is False
    assert strategy.build_intent(snapshot, state) is None
