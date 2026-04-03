"""
Unit tests for the context builder module.
"""

import math
from datetime import datetime, timedelta

import pytest

from src.core.context_builder import (
    ContextBuilder,
    InsufficientBarsError,
    create_market_snapshot,
)
from src.domain.models import MarketSnapshot


def create_test_bars(
    n_bars: int,
    start_time: datetime,
    interval_minutes: int = 5,
    base_price: float = 1800.0,
    volatility: float = 10.0,
) -> list:
    """
    Create test bar data for testing.

    Returns list of tuples: (time, open, high, low, close, tick_volume, spread, real_volume)
    """
    bars = []
    for i in range(n_bars):
        time = start_time + timedelta(minutes=interval_minutes * i)
        open_price = base_price + (i * volatility * 0.1)
        close_price = open_price + volatility * 0.5
        high_price = max(open_price, close_price) + volatility * 0.3
        low_price = min(open_price, close_price) - volatility * 0.3

        bars.append(
            (
                time,
                open_price,
                high_price,
                low_price,
                close_price,
                1000,  # tick_volume
                15,  # spread in points
                1_000_000,  # real_volume
            )
        )

    return bars


class TestContextBuilder:
    """Tests for ContextBuilder class."""

    def test_build_snapshot_valid(self):
        """Test building a valid market snapshot."""
        # Create 30 bars (enough for EMA21 and ATR14)
        start_time = datetime(2024, 1, 1, 0, 0)
        bars = create_test_bars(30, start_time)

        builder = ContextBuilder()
        snapshot = builder.build_snapshot(bars, bid=1800.0, ask=1800.5)

        # Verify required fields are present
        assert isinstance(snapshot, MarketSnapshot)
        assert snapshot.symbol == "XAUUSD"
        assert snapshot.timeframe == 5
        assert snapshot.digits == 2
        assert snapshot.magic_number == 20260313
        assert snapshot.bid == 1800.0
        assert snapshot.ask == 1800.5
        assert snapshot.spread_points == 15.0  # From last bar

        # Verify indicators are calculated
        assert isinstance(snapshot.ema_fast, float)
        assert isinstance(snapshot.ema_slow, float)
        assert isinstance(snapshot.atr14, float)
        assert snapshot.atr14 >= 0.0

        # Verify last closed bar data
        assert snapshot.last_closed_bar_time == bars[-1][0]
        assert snapshot.close == bars[-1][4]
        assert snapshot.open == bars[-1][1]
        assert snapshot.high == bars[-1][2]
        assert snapshot.low == bars[-1][3]
        assert snapshot.volume == bars[-1][7]

        # Verify historical data (should be available with 30 bars)
        assert snapshot.ema_fast_prev3 is not None
        assert snapshot.ema_slow_prev3 is not None
        assert snapshot.high_prev2 is not None
        assert snapshot.high_prev3 is not None
        assert snapshot.low_prev2 is not None
        assert snapshot.low_prev3 is not None
        assert snapshot.median_body_20 is not None
        assert snapshot.prev3_body_max is not None
        assert snapshot.volume_ma_20 is not None
        assert snapshot.high_20 is not None
        assert snapshot.low_20 is not None

    def test_build_snapshot_insufficient_bars_for_ema(self):
        """Test building snapshot with insufficient bars for EMA."""
        # Create only 5 bars (need at least 21 for slow EMA)
        start_time = datetime(2024, 1, 1, 0, 0)
        bars = create_test_bars(5, start_time)

        builder = ContextBuilder()

        with pytest.raises(
            InsufficientBarsError,
            match="Insufficient bars for EMA\\(9/21\\): need at least 21 bars, got 5",
        ):
            builder.build_snapshot(bars, bid=1800.0, ask=1800.5)

    def test_build_snapshot_insufficient_bars_for_atr(self):
        """Test building snapshot with insufficient bars for ATR."""
        # Create 10 bars (need at least 11 for ATR10: period+1)
        # But using smaller EMA periods (5 and 10) so EMA needs only 10 bars
        start_time = datetime(2024, 1, 1, 0, 0)
        bars = create_test_bars(10, start_time)

        builder = ContextBuilder(
            ema_fast_period=5,
            ema_slow_period=10,
            atr_period=10,  # Needs 11 bars
        )

        # Should fail because ATR10 needs 11 bars
        with pytest.raises(
            InsufficientBarsError,
            match="Insufficient bars for ATR\\(10\\): need at least 11 bars, got 10",
        ):
            builder.build_snapshot(bars, bid=1800.0, ask=1800.5)

    def test_build_snapshot_minimum_bars(self):
        """Test building snapshot with minimum required bars."""
        # Need at least max(21, 15) = 21 bars for EMA21
        # ATR14 needs 15 bars, so 21 is enough
        start_time = datetime(2024, 1, 1, 0, 0)
        bars = create_test_bars(21, start_time)

        builder = ContextBuilder()
        snapshot = builder.build_snapshot(bars, bid=1800.0, ask=1800.5)

        # Should succeed
        assert isinstance(snapshot, MarketSnapshot)

        # Historical data may be None for some fields with minimal bars
        # ema_fast_prev3 and ema_slow_prev3 need period+3 bars
        # So with 21 bars: EMA21 needs 21 bars, EMA21 3 bars ago needs 24 bars
        # So ema_slow_prev3 should be None
        assert snapshot.ema_slow_prev3 is None

        # But high/low prev2/prev3 should be available
        assert snapshot.high_prev2 is not None
        assert snapshot.high_prev3 is not None
        assert snapshot.low_prev2 is not None
        assert snapshot.low_prev3 is not None

    def test_build_snapshot_invalid_bid_ask(self):
        """Test building snapshot with invalid bid/ask prices."""
        start_time = datetime(2024, 1, 1, 0, 0)
        bars = create_test_bars(30, start_time)

        builder = ContextBuilder()

        # Bid <= 0
        with pytest.raises(ValueError, match="Bid/ask prices must be positive"):
            builder.build_snapshot(bars, bid=0.0, ask=1800.5)

        # Ask <= 0
        with pytest.raises(ValueError, match="Bid/ask prices must be positive"):
            builder.build_snapshot(bars, bid=1800.0, ask=0.0)

        # Ask <= Bid
        with pytest.raises(ValueError, match="Ask price.*must be greater than bid"):
            builder.build_snapshot(bars, bid=1800.5, ask=1800.0)

    def test_build_snapshot_empty_bars(self):
        """Test building snapshot with empty bars list."""
        builder = ContextBuilder()

        with pytest.raises(ValueError, match="No bars provided"):
            builder.build_snapshot([], bid=1800.0, ask=1800.5)

    def test_build_snapshot_custom_parameters(self):
        """Test building snapshot with custom parameters."""
        start_time = datetime(2024, 1, 1, 0, 0)
        bars = create_test_bars(30, start_time)

        builder = ContextBuilder(
            symbol="TEST",
            timeframe=15,
            digits=3,
            magic_number=999,
            ema_fast_period=5,
            ema_slow_period=10,
            atr_period=10,
        )

        snapshot = builder.build_snapshot(bars, bid=1800.0, ask=1800.5)

        # Verify custom parameters
        assert snapshot.symbol == "TEST"
        assert snapshot.timeframe == 15
        assert snapshot.digits == 3
        assert snapshot.magic_number == 999

        # Indicators should still be calculated (with custom periods)
        assert isinstance(snapshot.ema_fast, float)
        assert isinstance(snapshot.ema_slow, float)
        assert isinstance(snapshot.atr14, float)

    def test_build_snapshot_invalid_periods(self):
        """Test ContextBuilder with invalid periods."""
        # Fast period >= slow period
        with pytest.raises(ValueError, match="EMA fast period.*must be less than"):
            ContextBuilder(ema_fast_period=21, ema_slow_period=9)

        # Zero or negative periods
        with pytest.raises(ValueError, match="EMA periods must be positive"):
            ContextBuilder(ema_fast_period=0, ema_slow_period=21)

        with pytest.raises(ValueError, match="ATR period must be positive"):
            ContextBuilder(atr_period=0)

    def test_build_snapshot_historical_data_calculation(self):
        """Test that historical data is calculated correctly."""
        # Create bars with known pattern to verify calculations
        start_time = datetime(2024, 1, 1, 0, 0)

        # Simple ascending prices for predictable EMA
        bars = []
        for i in range(30):
            time = start_time + timedelta(minutes=5 * i)
            price = 1800.0 + i * 1.0  # Increase by 1 each bar
            bars.append(
                (
                    time,
                    price,  # open
                    price + 2,  # high
                    price - 2,  # low
                    price + 1,  # close
                    1000,
                    15,
                    1_000_000,
                )
            )

        builder = ContextBuilder()
        snapshot = builder.build_snapshot(bars, bid=1829.0, ask=1829.5)

        # Verify last closed bar is last bar
        assert snapshot.last_closed_bar_time == bars[-1][0]
        assert math.isclose(snapshot.close, 1829.0 + 1.0, rel_tol=1e-9)  # 1830.0

        # Verify high_prev2 is high of bar at position -3 (0-indexed)
        # bars[-3] is 3rd from last: 1800 + 27 = 1827 open, high = 1829
        assert snapshot.high_prev2 is not None
        assert math.isclose(snapshot.high_prev2, 1829.0, rel_tol=1e-9)

        # Verify high_prev3 is high of bar at position -4
        assert snapshot.high_prev3 is not None
        assert math.isclose(snapshot.high_prev3, 1828.0, rel_tol=1e-9)

        # Verify low_prev2 is low of bar at position -3
        assert snapshot.low_prev2 is not None
        assert math.isclose(snapshot.low_prev2, 1825.0, rel_tol=1e-9)

        # Verify low_prev3 is low of bar at position -4
        assert snapshot.low_prev3 is not None
        assert math.isclose(snapshot.low_prev3, 1824.0, rel_tol=1e-9)


class TestCreateMarketSnapshot:
    """Tests for create_market_snapshot convenience function."""

    def test_create_market_snapshot_valid(self):
        """Test creating market snapshot with convenience function."""
        start_time = datetime(2024, 1, 1, 0, 0)
        bars = create_test_bars(30, start_time)

        snapshot = create_market_snapshot(
            bars=bars,
            bid=1800.0,
            ask=1800.5,
            symbol="TEST",
            timeframe=15,
            digits=3,
            magic_number=999,
        )

        # Verify parameters
        assert snapshot.symbol == "TEST"
        assert snapshot.timeframe == 15
        assert snapshot.digits == 3
        assert snapshot.magic_number == 999

        # Verify indicators calculated
        assert isinstance(snapshot.ema_fast, float)
        assert isinstance(snapshot.ema_slow, float)
        assert isinstance(snapshot.atr14, float)

    def test_create_market_snapshot_defaults(self):
        """Test creating market snapshot with default parameters."""
        start_time = datetime(2024, 1, 1, 0, 0)
        bars = create_test_bars(30, start_time)

        snapshot = create_market_snapshot(bars=bars, bid=1800.0, ask=1800.5)

        # Verify default parameters
        assert snapshot.symbol == "XAUUSD"
        assert snapshot.timeframe == 5
        assert snapshot.digits == 2
        assert snapshot.magic_number == 20260313


class TestInsufficientBarsError:
    """Tests for InsufficientBarsError exception."""

    def test_insufficient_bars_error_creation(self):
        """Test creating InsufficientBarsError."""
        error = InsufficientBarsError(
            indicator="EMA(9/21)",
            required=21,
            available=5,
        )

        assert error.indicator == "EMA(9/21)"
        assert error.required == 21
        assert error.available == 5
        assert str(error) == "Insufficient bars for EMA(9/21): need at least 21 bars, got 5"
