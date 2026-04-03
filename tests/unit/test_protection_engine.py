"""Unit tests for two-stage ATR protection engine."""

import importlib
from datetime import datetime

from src.domain.models import (
    MarketSnapshot,
    OrderType,
    ProtectionStage,
    ProtectionState,
    RuntimeState,
)

_protection_engine = importlib.import_module("src.core.protection_engine")
ProtectionEngine = _protection_engine.ProtectionEngine


def _snapshot(close_price: float) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=20260313,
        bid=close_price - 0.2,
        ask=close_price + 0.2,
        ema_fast=close_price - 1.0,
        ema_slow=close_price - 2.0,
        atr14=10.0,
        spread_points=20.0,
        last_closed_bar_time=datetime(2026, 4, 3, 10, 0, 0),
        close=close_price,
        open=close_price - 1.0,
        high=close_price + 1.5,
        low=close_price - 1.5,
        volume=1_000_000,
        ema_fast_prev3=close_price - 4.0,
        ema_slow_prev3=close_price - 5.0,
        high_prev2=close_price - 0.5,
        high_prev3=close_price - 1.0,
        low_prev2=close_price - 3.0,
        low_prev3=close_price - 3.5,
    )


def _state(entry_price: float = 100.0, entry_atr: float = 10.0) -> RuntimeState:
    return RuntimeState(
        day_key="2026.04.03",
        protection_state=ProtectionState(
            protection_stage=ProtectionStage.NONE,
            entry_price=entry_price,
            entry_atr=entry_atr,
            highest_close_since_entry=entry_price,
            lowest_close_since_entry=entry_price,
            trailing_active=False,
        ),
    )


def test_stage_progression() -> None:
    engine = ProtectionEngine()
    state = _state(entry_price=100.0, entry_atr=10.0)

    stage1_snapshot = _snapshot(111.0)  # +1.1 ATR
    decision1 = engine.evaluate(
        order_type=OrderType.BUY,
        snapshot=stage1_snapshot,
        state=state,
        current_sl=90.0,
        current_tp=120.0,
    )
    assert decision1.action == "modify"
    assert state.protection_state.protection_stage == ProtectionStage.STAGE1

    stage2_snapshot = _snapshot(116.0)  # +1.6 ATR
    decision2 = engine.evaluate(
        order_type=OrderType.BUY,
        snapshot=stage2_snapshot,
        state=state,
        current_sl=decision1.new_sl,
        current_tp=decision1.new_tp,
    )
    assert decision2.action == "modify"
    assert state.protection_state.protection_stage == ProtectionStage.STAGE2
    assert state.protection_state.trailing_active is True


def test_no_premature_modify() -> None:
    engine = ProtectionEngine()
    state = _state(entry_price=100.0, entry_atr=10.0)
    snapshot = _snapshot(104.0)  # +0.4 ATR

    decision = engine.evaluate(
        order_type=OrderType.BUY,
        snapshot=snapshot,
        state=state,
        current_sl=90.0,
        current_tp=120.0,
    )

    assert decision.action == "hold"
    assert state.protection_state.protection_stage == ProtectionStage.NONE


def test_no_stage_rollback() -> None:
    engine = ProtectionEngine()
    state = _state(entry_price=100.0, entry_atr=10.0)
    state.protection_state.protection_stage = ProtectionStage.STAGE1

    pullback_snapshot = _snapshot(103.0)  # falls back below stage threshold
    decision = engine.evaluate(
        order_type=OrderType.BUY,
        snapshot=pullback_snapshot,
        state=state,
        current_sl=101.0,
        current_tp=126.0,
    )

    assert decision.action == "hold"
    assert state.protection_state.protection_stage == ProtectionStage.STAGE1
