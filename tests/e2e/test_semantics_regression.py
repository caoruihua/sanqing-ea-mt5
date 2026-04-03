"""Semantic regression suite for core strategy/risk/runtime invariants."""

import importlib
from datetime import datetime

from src.adapters.sim_broker import SimBrokerAdapter
from src.core.entry_gate import EntryGate
from src.core.strategy_selector import StrategySelector
from src.domain.models import (
    MarketSnapshot,
    OrderType,
    ProtectionState,
    RuntimeState,
    SignalDecision,
)
from src.strategies.base import BaseStrategy

DailyRiskController = importlib.import_module("src.core.daily_risk_controller").DailyRiskController
ProtectionEngine = importlib.import_module("src.core.protection_engine").ProtectionEngine
StateStore = importlib.import_module("src.core.state_store").StateStore
load_and_reconcile = importlib.import_module("src.core.reconciliation").load_and_reconcile


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
        atr14=10.0,
        spread_points=20.0,
        last_closed_bar_time=bar_time,
        close=2355.0,
        open=2345.0,
        high=2358.0,
        low=2342.0,
        volume=1_500_000,
        ema_fast_prev3=2344.0,
        ema_slow_prev3=2343.0,
        high_prev2=2350.0,
        high_prev3=2348.0,
        low_prev2=2338.0,
        low_prev3=2337.0,
    )


def _signal(snapshot: MarketSnapshot, strategy_name: str = "ExpansionFollow") -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        order_type=OrderType.BUY,
        entry_price=snapshot.ask,
        stop_loss=snapshot.ask - 12.0,
        take_profit=snapshot.ask + 20.0,
        atr_value=snapshot.atr14,
        lots=0.01,
    )


class _StaticSignal(BaseStrategy):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        return True

    def build_intent(self, snapshot: MarketSnapshot, state: RuntimeState):
        return _signal(snapshot, strategy_name=self._name)


def test_priority_conflict_semantic() -> None:
    selector = StrategySelector(
        strategies=[
            _StaticSignal("ExpansionFollow"),
            _StaticSignal("Pullback"),
            _StaticSignal("TrendContinuation"),
        ]
    )
    result = selector.select(
        _snapshot(datetime(2026, 4, 3, 10, 0, 0)), RuntimeState(day_key="2026.04.03")
    )
    assert result.intent is not None
    assert result.intent.strategy_name == "ExpansionFollow"


def test_closed_bar_dedupe_semantic() -> None:
    bar_time = datetime(2026, 4, 3, 10, 0, 0)
    snap = _snapshot(bar_time)
    state = RuntimeState(day_key="2026.04.03", last_entry_bar_time=bar_time)
    gate = EntryGate(max_trades_per_day=30)

    result = gate.evaluate(
        signal=_signal(snap),
        snapshot=snap,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )
    assert result.reason_code == "NOT_NEW_CLOSED_BAR"


def test_daily_lock_semantic() -> None:
    bar_time = datetime(2026, 4, 3, 10, 0, 0)
    snap = _snapshot(bar_time)
    state = RuntimeState(day_key="2026.04.03")
    DailyRiskController(daily_profit_stop_usd=50.0).update(
        bar_time, state, daily_closed_profit=80.0
    )
    gate = EntryGate(max_trades_per_day=30)
    result = gate.evaluate(
        signal=_signal(snap),
        snapshot=snap,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )
    assert result.reason_code == "DAILY_LOCKED"


def test_protection_stage_semantic() -> None:
    engine = ProtectionEngine()
    state = RuntimeState(
        day_key="2026.04.03",
        protection_state=ProtectionState(entry_price=100.0, entry_atr=10.0),
    )
    d1 = engine.evaluate(
        OrderType.BUY, _snapshot(datetime(2026, 4, 3, 10, 0, 0)), state, 90.0, 110.0
    )
    assert d1.action == "modify"
    d2 = engine.evaluate(
        OrderType.BUY,
        _snapshot(datetime(2026, 4, 3, 10, 5, 0)),
        state,
        d1.new_sl or 0.0,
        d1.new_tp or 0.0,
    )
    assert d2.action == "modify"


def test_restart_recovery_semantic(tmp_path) -> None:
    path = tmp_path / "state.json"
    store = StateStore(str(path))
    bar_time = datetime(2026, 4, 3, 10, 0, 0)
    state = RuntimeState(day_key="2026.04.03", last_entry_bar_time=bar_time)
    store.save(state)

    broker = SimBrokerAdapter()
    broker.connect()
    loaded = load_and_reconcile(store, broker, symbol="XAUUSD", magic=20260313)
    assert loaded.last_entry_bar_time == bar_time
