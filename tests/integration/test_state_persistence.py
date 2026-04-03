"""Integration tests for runtime state persistence and startup reconciliation."""

import importlib
from datetime import datetime

import pytest

from src.adapters.sim_broker import SimBrokerAdapter
from src.core.entry_gate import EntryGate
from src.domain.models import (
    MarketSnapshot,
    OrderType,
    ProtectionStage,
    ProtectionState,
    RuntimeState,
    SignalDecision,
)

_state_store = importlib.import_module("src.core.state_store")
_reconciliation = importlib.import_module("src.core.reconciliation")

StateStore = _state_store.StateStore
StateStoreCorruptedError = _state_store.StateStoreCorruptedError
load_and_reconcile = _reconciliation.load_and_reconcile


def _snapshot(bar_time: datetime) -> MarketSnapshot:
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
        last_closed_bar_time=bar_time,
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


def test_restart_continuity(tmp_path) -> None:
    store_path = tmp_path / "runtime_state.json"
    store = StateStore(str(store_path))

    bar_time = datetime(2026, 4, 3, 10, 0, 0)
    original = RuntimeState(
        day_key="2026.04.03",
        daily_locked=False,
        daily_closed_profit=12.5,
        trades_today=2,
        last_entry_bar_time=bar_time,
        protection_state=ProtectionState(
            protection_stage=ProtectionStage.STAGE1,
            entry_price=2350.0,
            entry_atr=5.0,
            trailing_active=False,
        ),
        position_ticket=1001,
    )
    store.save(original)

    broker = SimBrokerAdapter()
    broker.connect()
    reconciled = load_and_reconcile(store=store, broker=broker, symbol="XAUUSD", magic=20260313)

    assert reconciled.last_entry_bar_time == bar_time
    gate = EntryGate(max_trades_per_day=30)
    result = gate.evaluate(
        signal=_signal(_snapshot(bar_time)),
        snapshot=_snapshot(bar_time),
        state=reconciled,
        has_existing_position=False,
        strategy_can_trade=True,
    )
    assert result.intent is None
    assert result.reason_code == "NOT_NEW_CLOSED_BAR"


def test_corrupted_state(tmp_path) -> None:
    store_path = tmp_path / "runtime_state_corrupted.json"
    store_path.write_text("{invalid-json", encoding="utf-8")
    store = StateStore(str(store_path))

    with pytest.raises(StateStoreCorruptedError):
        store.load()
