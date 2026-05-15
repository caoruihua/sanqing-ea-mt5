from datetime import datetime, timedelta

import pytest

from src.core.entry_gate import EntryGate
from src.domain.constants import RejectionReason
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision


def _make_signal() -> SignalDecision:
    return SignalDecision(
        strategy_name="BareK",
        order_type=OrderType.BUY,
        entry_price=1900.0,
        stop_loss=0.0,
        take_profit=0.0,
        atr_value=0.0,
        lots=0.01,
        profit_target_usd=10.0,
    )


def _make_snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=123,
        bid=1900.0,
        ask=1900.1,
        spread_points=10.0,
        last_closed_bar_time=datetime(2026, 1, 1, 12, 0),
        close=1900.0,
        open=1899.0,
        high=1901.0,
        low=1898.0,
        opens_history=[1899.0],
        closes_history=[1900.0],
        highs_history=[1901.0],
        lows_history=[1898.0],
    )


def test_cooldown_rejects_within_one_hour():
    gate = EntryGate(max_trades_per_day=30)
    state = RuntimeState(
        day_key="2026.01.01",
        last_trade_close_time=datetime(2026, 1, 1, 11, 30),
    )
    snapshot = _make_snapshot()
    snapshot.last_closed_bar_time = datetime(2026, 1, 1, 12, 0)

    result = gate.evaluate(
        signal=_make_signal(),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )
    assert result.intent is None
    assert result.reason_code == RejectionReason.COOLDOWN_ACTIVE


def test_cooldown_passes_after_one_hour():
    gate = EntryGate(max_trades_per_day=30)
    state = RuntimeState(
        day_key="2026.01.01",
        last_trade_close_time=datetime(2026, 1, 1, 10, 0),
    )
    snapshot = _make_snapshot()
    snapshot.last_closed_bar_time = datetime(2026, 1, 1, 12, 0)

    result = gate.evaluate(
        signal=_make_signal(),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )
    assert result.intent is not None
    assert result.reason_code is None


def test_no_cooldown_when_never_traded():
    gate = EntryGate(max_trades_per_day=30)
    state = RuntimeState(day_key="2026.01.01", last_trade_close_time=None)
    snapshot = _make_snapshot()

    result = gate.evaluate(
        signal=_make_signal(),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )
    assert result.intent is not None
