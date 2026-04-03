"""Unit tests for server-day daily risk controller."""

import importlib
from datetime import datetime

from src.core.entry_gate import EntryGate
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision

_daily_risk_controller = importlib.import_module("src.core.daily_risk_controller")
DailyRiskController = _daily_risk_controller.DailyRiskController


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


def test_lock_on_profit() -> None:
    controller = DailyRiskController(daily_profit_stop_usd=50.0)
    state = RuntimeState(day_key="2026.04.03")

    controller.update(
        server_time=datetime(2026, 4, 3, 11, 0, 0),
        state=state,
        daily_closed_profit=50.0,
    )

    assert state.daily_locked is True
    assert state.daily_closed_profit == 50.0


def test_reset_on_new_day() -> None:
    controller = DailyRiskController(daily_profit_stop_usd=50.0)
    state = RuntimeState(
        day_key="2026.04.03",
        daily_locked=True,
        daily_closed_profit=80.0,
        trades_today=8,
    )

    controller.update(
        server_time=datetime(2026, 4, 4, 0, 1, 0),
        state=state,
        daily_closed_profit=0.0,
    )

    assert state.day_key == "2026.04.04"
    assert state.daily_locked is False
    assert state.daily_closed_profit == 0.0
    assert state.trades_today == 0


def test_entry_gate_blocked_when_daily_locked() -> None:
    controller = DailyRiskController(daily_profit_stop_usd=50.0)
    state = RuntimeState(day_key="2026.04.03")
    controller.update(
        server_time=datetime(2026, 4, 3, 11, 0, 0),
        state=state,
        daily_closed_profit=75.0,
    )

    snapshot = _snapshot()
    gate = EntryGate(max_trades_per_day=30)
    result = gate.evaluate(
        signal=_signal(snapshot),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )

    assert result.intent is None
    assert result.reason_code == "DAILY_LOCKED"
