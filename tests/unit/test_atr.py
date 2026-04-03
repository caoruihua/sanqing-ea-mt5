"""
Unit tests for the ATR indicator module.
"""

import math

import pytest

from src.indicators.atr import (
    calculate_atr,
    calculate_atr_series,
    calculate_true_range,
)


class TestCalculateTrueRange:
    """Tests for calculate_true_range function."""

    def test_true_range_no_prev_close(self):
        """Test True Range without previous close."""
        tr = calculate_true_range(high=110.0, low=100.0)
        assert math.isclose(tr, 10.0, rel_tol=1e-9)  # high - low = 10

    def test_true_range_with_prev_close_high_gap(self):
        """Test True Range when high - prev_close is largest."""
        # high=110, low=100, prev_close=95
        # high-low=10, |high-prev_close|=15, |low-prev_close|=5
        tr = calculate_true_range(high=110.0, low=100.0, prev_close=95.0)
        assert math.isclose(tr, 15.0, rel_tol=1e-9)  # |high - prev_close| = 15

    def test_true_range_with_prev_close_low_gap(self):
        """Test True Range when low - prev_close is largest (negative)."""
        # high=110, low=100, prev_close=115
        # high-low=10, |high-prev_close|=5, |low-prev_close|=15
        tr = calculate_true_range(high=110.0, low=100.0, prev_close=115.0)
        assert math.isclose(tr, 15.0, rel_tol=1e-9)  # |low - prev_close| = 15

    def test_true_range_with_prev_close_equal(self):
        """Test True Range when all ranges are equal."""
        tr = calculate_true_range(high=110.0, low=100.0, prev_close=105.0)
        assert math.isclose(tr, 10.0, rel_tol=1e-9)  # high-low = 10

    def test_true_range_zero_range(self):
        """Test True Range with zero range."""
        tr = calculate_true_range(high=100.0, low=100.0, prev_close=100.0)
        assert math.isclose(tr, 0.0, rel_tol=1e-9)


class TestCalculateATR:
    """Tests for calculate_atr function."""

    def test_atr_constant_prices(self):
        """Test ATR with constant prices."""
        # 15 bars of constant prices
        highs = [100.0] * 15
        lows = [100.0] * 15
        closes = [100.0] * 15

        atr = calculate_atr(highs, lows, closes, period=14)

        # ATR should be 0 for constant prices
        assert math.isclose(atr, 0.0, abs_tol=1e-9)

    def test_atr_with_volatility(self):
        """Test ATR with volatile prices."""
        # Create simple pattern: price oscillates ±1 each bar
        highs = [
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
            101.0,
        ]
        lows = [
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
            99.0,
        ]
        closes = [
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
        ]

        atr = calculate_atr(highs, lows, closes, period=14)

        # True Range = high-low = 2.0 for each bar (except first)
        # Initial ATR = average of first 14 True Ranges = 2.0
        # EMA of constant 2.0 is 2.0
        assert math.isclose(atr, 2.0, rel_tol=1e-9)

    def test_atr_different_length_lists(self):
        """Test ATR with lists of different lengths."""
        highs = [100.0] * 15
        lows = [99.0] * 15
        closes = [99.5] * 10  # Shorter list

        with pytest.raises(ValueError, match="Input lists must have same length"):
            calculate_atr(highs, lows, closes, period=14)

    def test_atr_insufficient_data(self):
        """Test ATR with insufficient data."""
        # Need period+1 = 15 bars for ATR(14)
        highs = [100.0] * 10
        lows = [99.0] * 10
        closes = [99.5] * 10

        with pytest.raises(
            ValueError, match="Insufficient data for ATR\\(14\\): need at least 15 bars, got 10"
        ):
            calculate_atr(highs, lows, closes, period=14)

    def test_atr_minimum_data(self):
        """Test ATR with minimum required data."""
        # Exactly period+1 = 15 bars
        highs = [101.0] * 15
        lows = [99.0] * 15
        closes = [100.0] * 15

        atr = calculate_atr(highs, lows, closes, period=14)

        # Should calculate without error
        assert isinstance(atr, float)
        assert atr >= 0.0

    def test_atr_custom_period(self):
        """Test ATR with custom period."""
        # Use 5 bars for ATR(4) to simplify calculation
        highs = [101.0, 101.0, 101.0, 101.0, 101.0]
        lows = [99.0, 99.0, 99.0, 99.0, 99.0]
        closes = [100.0, 100.0, 100.0, 100.0, 100.0]

        atr = calculate_atr(highs, lows, closes, period=4)

        # True Range = 2.0 for each bar (except first)
        # Initial ATR = average of first 4 True Ranges = 2.0
        # EMA of constant 2.0 is 2.0
        assert math.isclose(atr, 2.0, rel_tol=1e-9)

    def test_atr_negative_period(self):
        """Test ATR with negative period."""
        highs = [100.0] * 15
        lows = [99.0] * 15
        closes = [99.5] * 15

        with pytest.raises(ValueError, match="ATR period must be positive"):
            calculate_atr(highs, lows, closes, period=-1)

    def test_atr_zero_period(self):
        """Test ATR with zero period."""
        highs = [100.0] * 15
        lows = [99.0] * 15
        closes = [99.5] * 15

        with pytest.raises(ValueError, match="ATR period must be positive"):
            calculate_atr(highs, lows, closes, period=0)


class TestCalculateATRSeries:
    """Tests for calculate_atr_series function."""

    def test_atr_series_valid(self):
        """Test ATR series calculation."""
        # 20 bars
        highs = [101.0] * 20
        lows = [99.0] * 20
        closes = [100.0] * 20

        atr_values = calculate_atr_series(highs, lows, closes, period=14)

        # Should have same length as input
        assert len(atr_values) == len(highs)

        # First 14 values should be None (need period bars for first ATR)
        for i in range(14):
            assert atr_values[i] is None

        # Remaining values should be ATR calculations
        for i in range(14, len(atr_values)):
            assert atr_values[i] is not None

        # Last value should match calculate_atr
        expected_last = calculate_atr(highs, lows, closes, period=14)
        assert atr_values[-1] is not None
        assert math.isclose(atr_values[-1], expected_last, rel_tol=1e-9)

    def test_atr_series_insufficient_data(self):
        """Test ATR series with insufficient data."""
        highs = [100.0] * 10
        lows = [99.0] * 10
        closes = [99.5] * 10

        with pytest.raises(
            ValueError, match="Insufficient data for ATR\\(14\\): need at least 15 bars, got 10"
        ):
            calculate_atr_series(highs, lows, closes, period=14)

    def test_atr_series_exact_minimum(self):
        """Test ATR series with exactly minimum data."""
        # Exactly period+1 = 15 bars
        highs = [101.0] * 15
        lows = [99.0] * 15
        closes = [100.0] * 15

        atr_values = calculate_atr_series(highs, lows, closes, period=14)

        # Should have 15 values
        assert len(atr_values) == 15

        # First 14 should be None
        for i in range(14):
            assert atr_values[i] is None

        # Last should be SMA of first 14 True Ranges
        # True Range = 2.0 for each bar (except first)
        # 14 True Ranges average = 2.0
        assert atr_values[-1] is not None
        assert math.isclose(atr_values[-1], 2.0, rel_tol=1e-9)

    def test_atr_series_different_length_lists(self):
        """Test ATR series with lists of different lengths."""
        highs = [100.0] * 15
        lows = [99.0] * 15
        closes = [99.5] * 10  # Shorter list

        with pytest.raises(ValueError, match="Input lists must have same length"):
            calculate_atr_series(highs, lows, closes, period=14)

    def test_atr_series_custom_period(self):
        """Test ATR series with custom period."""
        # 10 bars for ATR(5)
        highs = [101.0] * 10
        lows = [99.0] * 10
        closes = [100.0] * 10

        atr_values = calculate_atr_series(highs, lows, closes, period=5)

        # First 5 values should be None
        for i in range(5):
            assert atr_values[i] is None

        # Remaining should be ATR values
        for i in range(5, len(atr_values)):
            assert atr_values[i] is not None
