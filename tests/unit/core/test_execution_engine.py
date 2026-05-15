from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.core.execution_engine import ExecutionEngine
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision, TradeIntent


def _make_intent(sl: float = 0.0, tp: float | None = None) -> TradeIntent:
    snapshot = MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=123,
        bid=1900.0,
        ask=1900.1,
        spread_points=10.0,
        last_closed_bar_time=datetime.now(),
        close=1900.0,
        open=1899.0,
        high=1901.0,
        low=1898.0,
        opens_history=[1899.0],
        closes_history=[1900.0],
        highs_history=[1901.0],
        lows_history=[1898.0],
    )
    signal = SignalDecision(
        strategy_name="BareK",
        order_type=OrderType.BUY,
        entry_price=1900.1,
        stop_loss=sl,
        take_profit=tp,
        atr_value=0.0,
        lots=0.01,
        profit_target_usd=10.0,
    )
    return TradeIntent(signal_decision=signal, market_snapshot=snapshot, action_id="test-001")


def test_validate_allows_zero_sl():
    broker = MagicMock()
    broker.get_position.return_value = None
    engine = ExecutionEngine(broker=broker)
    intent = _make_intent(sl=0.0)
    error = engine._validate_order_params(intent)
    assert error is None


def test_calculate_tp_price_for_buy():
    broker = MagicMock()
    engine = ExecutionEngine(broker=broker)

    mock_info = MagicMock()
    mock_info.trade_tick_value = 1.0
    mock_info.trade_tick_size = 0.01

    tp = engine._calculate_tp_price(
        symbol="XAUUSD",
        order_type="BUY",
        entry_price=1900.0,
        volume=0.01,
        profit_target_usd=10.0,
        symbol_info=mock_info,
    )
    assert tp == 1910.0


def test_calculate_tp_price_for_sell():
    broker = MagicMock()
    engine = ExecutionEngine(broker=broker)

    mock_info = MagicMock()
    mock_info.trade_tick_value = 1.0
    mock_info.trade_tick_size = 0.01

    tp = engine._calculate_tp_price(
        symbol="XAUUSD",
        order_type="SELL",
        entry_price=1900.0,
        volume=0.01,
        profit_target_usd=10.0,
        symbol_info=mock_info,
    )
    assert tp == 1890.0
