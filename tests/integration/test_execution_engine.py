"""Integration tests for execution engine behavior."""

import importlib
from datetime import datetime

import pytest

from src.adapters.broker_base import BrokerAdapter
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision, TradeIntent

_execution_engine = importlib.import_module("src.core.execution_engine")
DuplicateActionError = _execution_engine.DuplicateActionError
ExecutionEngine = _execution_engine.ExecutionEngine
RetryExhaustedError = _execution_engine.RetryExhaustedError


class _FakeBroker(BrokerAdapter):
    def __init__(self, send_results):
        self.send_results = list(send_results)
        self.send_calls = 0
        self._position = None

    def connect(self) -> bool:
        return True

    def get_rates(self, symbol: str, timeframe: int, count: int):
        return []

    def get_position(self, symbol: str, magic: int):
        _ = symbol, magic
        return self._position

    def send_order(
        self,
        symbol: str,
        magic: int,
        order_type: str,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        slippage: int,
        comment: str,
    ):
        _ = symbol, magic, order_type, volume, price, sl, tp, slippage, comment
        self.send_calls += 1
        if not self.send_results:
            return {"success": False, "retryable": False, "reason": "NO_RESULT"}
        result = self.send_results.pop(0)
        if result.get("success"):
            self._position = {"ticket": result.get("ticket", 1)}
        return result

    def modify_position(self, ticket: int, sl: float, tp: float):
        return {"success": True}

    def close_position(self, ticket: int, close_price: float, closed_at: datetime):
        return {"success": True}

    def get_closed_profit(self, day_key: str) -> float:
        return 0.0


def _intent(action_id: str) -> TradeIntent:
    snapshot = MarketSnapshot(
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
    signal = SignalDecision(
        strategy_name="ExpansionFollow",
        order_type=OrderType.BUY,
        entry_price=snapshot.ask,
        stop_loss=snapshot.ask - 8.0,
        take_profit=snapshot.ask + 15.0,
        atr_value=snapshot.atr14,
        lots=0.01,
    )
    return TradeIntent(signal_decision=signal, market_snapshot=snapshot, action_id=action_id)


def test_submit_success() -> None:
    broker = _FakeBroker(send_results=[{"success": True, "ticket": 1001, "retcode": 10009}])
    engine = ExecutionEngine(broker=broker, max_retries=3)
    state = RuntimeState(day_key="2026.04.03")

    result = engine.submit(_intent("a-1"), state=state)

    assert result["success"] is True
    assert broker.send_calls == 1
    assert state.trades_today == 1


def test_retry_exhausted() -> None:
    broker = _FakeBroker(
        send_results=[
            {"success": False, "retryable": True, "reason": "REQUOTE"},
            {"success": False, "retryable": True, "reason": "PRICE_OFF"},
            {"success": False, "retryable": True, "reason": "TIMEOUT"},
        ]
    )
    engine = ExecutionEngine(broker=broker, max_retries=3)
    state = RuntimeState(day_key="2026.04.03")

    with pytest.raises(RetryExhaustedError, match="exhausted"):
        engine.submit(_intent("a-2"), state=state)

    assert broker.send_calls == 3


def test_duplicate_action_id_blocked() -> None:
    broker = _FakeBroker(send_results=[{"success": True, "ticket": 1001, "retcode": 10009}])
    engine = ExecutionEngine(broker=broker, max_retries=2)
    state = RuntimeState(day_key="2026.04.03")

    engine.submit(_intent("dup-1"), state=state)
    with pytest.raises(DuplicateActionError, match="already submitted"):
        engine.submit(_intent("dup-1"), state=state)
