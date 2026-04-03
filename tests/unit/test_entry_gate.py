"""Unit tests for the entry gate pipeline."""

import importlib
from datetime import datetime

from src.domain.constants import RejectionReason
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision

EntryGate = importlib.import_module("src.core.entry_gate").EntryGate


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=20260313,
        bid=2350.0,
        ask=2350.3,
        ema_fast=2349.5,
        ema_slow=2348.0,
        atr14=5.0,
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


def _state() -> RuntimeState:
    return RuntimeState(day_key="2026.04.03")


def _signal(snapshot: MarketSnapshot) -> SignalDecision:
    return SignalDecision(
        strategy_name="ExpansionFollow",
        order_type=OrderType.BUY,
        entry_price=snapshot.ask,
        stop_loss=snapshot.ask - 8.0,
        take_profit=snapshot.ask + 15.0,
        atr_value=snapshot.atr14,
        lots=0.01,
    )


def test_pass_all_returns_trade_intent() -> None:
    gate = EntryGate(max_trades_per_day=30)
    snapshot = _snapshot()
    state = _state()

    result = gate.evaluate(
        signal=_signal(snapshot),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
        action_id="bar-20260403-1000",
    )

    assert result.reason_code is None
    assert result.intent is not None
    assert result.intent.signal_decision.strategy_name == "ExpansionFollow"
    assert state.last_entry_bar_time == snapshot.last_closed_bar_time


def test_blocks_when_same_closed_bar_already_attempted() -> None:
    gate = EntryGate(max_trades_per_day=30)
    snapshot = _snapshot()
    state = _state()
    state.last_entry_bar_time = snapshot.last_closed_bar_time

    result = gate.evaluate(
        signal=_signal(snapshot),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )

    assert result.intent is None
    assert result.reason_code == RejectionReason.NOT_NEW_CLOSED_BAR


def test_blocks_when_daily_locked() -> None:
    gate = EntryGate(max_trades_per_day=30)
    snapshot = _snapshot()
    state = _state()
    state.daily_locked = True

    result = gate.evaluate(
        signal=_signal(snapshot),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )

    assert result.intent is None
    assert result.reason_code == RejectionReason.DAILY_LOCKED


def test_blocks_when_max_trades_reached() -> None:
    gate = EntryGate(max_trades_per_day=2)
    snapshot = _snapshot()
    state = _state()
    state.trades_today = 2

    result = gate.evaluate(
        signal=_signal(snapshot),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )

    assert result.intent is None
    assert result.reason_code == RejectionReason.MAX_TRADES_EXCEEDED


def test_blocks_when_existing_position() -> None:
    gate = EntryGate(max_trades_per_day=30)
    snapshot = _snapshot()
    state = _state()

    result = gate.evaluate(
        signal=_signal(snapshot),
        snapshot=snapshot,
        state=state,
        has_existing_position=True,
        strategy_can_trade=True,
    )

    assert result.intent is None
    assert result.reason_code == RejectionReason.EXISTING_POSITION


def test_low_volatility_block_by_atr_points() -> None:
    gate = EntryGate(max_trades_per_day=30)
    snapshot = _snapshot()
    snapshot.atr14 = 1.5  # 150 points with digits=2
    state = _state()

    result = gate.evaluate(
        signal=_signal(snapshot),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )

    assert result.intent is None
    assert result.reason_code == RejectionReason.LOW_VOLATILITY


def test_low_volatility_block_by_atr_spread_ratio() -> None:
    gate = EntryGate(max_trades_per_day=30)
    snapshot = _snapshot()
    snapshot.atr14 = 4.5  # 450 points
    snapshot.spread_points = 200.0  # ratio 2.25 < 3.0
    state = _state()

    result = gate.evaluate(
        signal=_signal(snapshot),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )

    assert result.intent is None
    assert result.reason_code == RejectionReason.LOW_VOLATILITY


def test_blocks_when_strategy_cannot_trade() -> None:
    gate = EntryGate(max_trades_per_day=30)
    snapshot = _snapshot()
    state = _state()

    result = gate.evaluate(
        signal=_signal(snapshot),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=False,
    )

    assert result.intent is None
    assert result.reason_code == RejectionReason.STRATEGY_CANNOT_TRADE
