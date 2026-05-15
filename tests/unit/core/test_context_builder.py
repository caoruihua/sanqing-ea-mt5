from datetime import datetime

import pytest

from src.core.context_builder import ContextBuilder


def test_build_snapshot_returns_candle_history():
    builder = ContextBuilder(symbol="XAUUSD", timeframe=5, digits=2, magic_number=123)
    bars = [
        (datetime(2026, 1, 1, 12, 0), 1900.0, 1901.0, 1899.0, 1900.5, 100, 10, 100),
        (datetime(2026, 1, 1, 12, 5), 1900.5, 1901.5, 1900.0, 1901.0, 100, 10, 100),
        (datetime(2026, 1, 1, 12, 10), 1901.0, 1902.0, 1900.5, 1901.5, 100, 10, 100),
        (datetime(2026, 1, 1, 12, 15), 1901.5, 1902.5, 1901.0, 1902.0, 100, 10, 100),
    ]
    snapshot = builder.build_snapshot(bars, bid=1901.9, ask=1902.0)

    assert snapshot.symbol == "XAUUSD"
    assert snapshot.close == 1902.0
    assert snapshot.open == 1901.5
    assert snapshot.closes_history == [1900.5, 1901.0, 1901.5, 1902.0]
    assert snapshot.opens_history == [1900.0, 1900.5, 1901.0, 1901.5]
    assert snapshot.highs_history == [1901.0, 1901.5, 1902.0, 1902.5]
    assert snapshot.lows_history == [1899.0, 1900.0, 1900.5, 1901.0]


def test_build_snapshot_rejects_empty_bars():
    builder = ContextBuilder()
    with pytest.raises(ValueError, match="No bars provided"):
        builder.build_snapshot([], bid=1900.0, ask=1900.1)
