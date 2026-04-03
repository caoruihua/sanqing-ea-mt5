"""
Unit tests for the EMA indicator module.
"""

import math

import pytest

from src.indicators.ema import (
    calculate_ema,
    calculate_ema_series,
    calculate_emas,
)


class TestCalculateEMA:
    """Tests for calculate_ema function."""

    def test_valid_ema_calculation(self):
        """Test EMA calculation with valid data."""
        # Test data: 10 constant prices
        prices = [100.0] * 10
        ema = calculate_ema(prices, period=9)

        # EMA of constant prices should be the constant value
        assert math.isclose(ema, 100.0, rel_tol=1e-9)

    def test_ema_with_ascending_prices(self):
        """Test EMA calculation with ascending prices."""
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0]
        ema = calculate_ema(prices, period=5)

        # EMA should be between the values
        assert 100.0 < ema < 109.0

        # Verify with manual calculation
        # SMA of first 5 prices: (100+101+102+103+104)/5 = 102.0
        # alpha = 2/(5+1) = 2/6 = 1/3
        # EMA6 = 105 * 1/3 + 102 * 2/3 = 103.0
        # EMA7 = 106 * 1/3 + 103 * 2/3 = 104.0
        # EMA8 = 107 * 1/3 + 104 * 2/3 = 105.0
        # EMA9 = 108 * 1/3 + 105 * 2/3 = 106.0
        # EMA10 = 109 * 1/3 + 106 * 2/3 = 107.0
        expected_ema = 107.0
        assert math.isclose(ema, expected_ema, rel_tol=1e-9)

    def test_ema_with_prev_ema(self):
        """Test incremental EMA calculation with previous EMA."""
        # First calculate EMA for first 9 prices
        prices1 = [float(i) for i in range(100, 109)]  # 100.0, 101.0, ..., 108.0
        prev_ema = calculate_ema(prices1, period=9)

        # Then increment with new price
        new_price = 109.0
        ema = calculate_ema([new_price], period=9, prev_ema=prev_ema)

        # Should match calculating from scratch
        all_prices = prices1 + [new_price]
        expected_ema = calculate_ema(all_prices, period=9)

        assert math.isclose(ema, expected_ema, rel_tol=1e-9)

    def test_negative_period(self):
        """Test EMA calculation with negative period."""
        with pytest.raises(ValueError, match="EMA period must be positive"):
            calculate_ema([100.0, 101.0], period=-1)

    def test_zero_period(self):
        """Test EMA calculation with zero period."""
        with pytest.raises(ValueError, match="EMA period must be positive"):
            calculate_ema([100.0, 101.0], period=0)

    def test_insufficient_data(self):
        """Test EMA calculation with insufficient data."""
        prices = [100.0, 101.0, 102.0]

        with pytest.raises(
            ValueError, match="Insufficient data for EMA\\(9\\): need at least 9 prices, got 3"
        ):
            calculate_ema(prices, period=9)

    def test_single_price_with_prev_ema(self):
        """Test EMA calculation with single price and previous EMA."""
        ema = calculate_ema([110.0], period=9, prev_ema=100.0)

        # EMA formula: price * alpha + prev_ema * (1 - alpha)
        alpha = 2.0 / (9 + 1.0)
        expected = 110.0 * alpha + 100.0 * (1.0 - alpha)

        assert math.isclose(ema, expected, rel_tol=1e-9)


class TestCalculateEMASeries:
    """Tests for calculate_ema_series function."""

    def test_ema_series_valid(self):
        """Test EMA series calculation."""
        prices = [float(i) for i in range(100, 115)]  # 100.0, 101.0, ..., 114.0 (15 prices)
        period = 9

        ema_values = calculate_ema_series(prices, period)

        # Should have same length as input
        assert len(ema_values) == len(prices)

        # First (period-1) values should be None
        for i in range(period - 1):
            assert ema_values[i] is None

        # Remaining values should be EMA calculations
        for i in range(period - 1, len(prices)):
            assert ema_values[i] is not None

        # Last value should match calculate_ema
        expected_last = calculate_ema(prices, period)
        assert math.isclose(ema_values[-1], expected_last, rel_tol=1e-9)

    def test_ema_series_insufficient_data(self):
        """Test EMA series with insufficient data."""
        prices = [100.0, 101.0, 102.0]

        with pytest.raises(
            ValueError, match="Insufficient data for EMA\\(9\\): need at least 9 prices, got 3"
        ):
            calculate_ema_series(prices, period=9)

    def test_ema_series_exact_period(self):
        """Test EMA series with exactly period prices."""
        prices = [float(i) for i in range(100, 109)]  # 9 prices for period=9
        ema_values = calculate_ema_series(prices, period=9)

        # Should have 9 values
        assert len(ema_values) == 9

        # First 8 should be None
        for i in range(8):
            assert ema_values[i] is None

        # Last should be SMA of all prices
        assert math.isclose(ema_values[-1], sum(prices) / 9, rel_tol=1e-9)


class TestCalculateEMAs:
    """Tests for calculate_emas function."""

    def test_calculate_emas_valid(self):
        """Test calculating both fast and slow EMAs."""
        prices = [float(i) for i in range(100, 125)]  # 25 prices

        ema_fast, ema_slow = calculate_emas(prices, fast_period=9, slow_period=21)

        # Both should be valid floats
        assert isinstance(ema_fast, float)
        assert isinstance(ema_slow, float)

        # Calculate independently to verify
        expected_fast = calculate_ema(prices, period=9)
        expected_slow = calculate_ema(prices, period=21)

        assert math.isclose(ema_fast, expected_fast, rel_tol=1e-9)
        assert math.isclose(ema_slow, expected_slow, rel_tol=1e-9)

    def test_calculate_emas_insufficient_for_slow(self):
        """Test when insufficient data for slow EMA."""
        prices = [float(i) for i in range(100, 115)]  # 15 prices

        with pytest.raises(
            ValueError, match="Insufficient data for EMA\\(21\\): need at least 21 prices, got 15"
        ):
            calculate_emas(prices, fast_period=9, slow_period=21)

    def test_calculate_emas_insufficient_for_fast(self):
        """Test when insufficient data for fast EMA."""
        prices = [100.0, 101.0, 102.0]

        with pytest.raises(
            ValueError, match="Insufficient data for EMA\\(9\\): need at least 9 prices, got 3"
        ):
            calculate_emas(prices, fast_period=9, slow_period=21)

    def test_calculate_emas_edge_case(self):
        """Test edge case with minimal data."""
        prices = [float(i) for i in range(100, 122)]  # Exactly 22 prices (min for EMA21)

        ema_fast, ema_slow = calculate_emas(prices, fast_period=9, slow_period=21)

        # Both should be calculated
        assert isinstance(ema_fast, float)
        assert isinstance(ema_slow, float)

        # With exactly period+1 prices, slow EMA should be:
        # SMA of first 21 prices = (100+120)*21/2/21 = 110.0
        # Then EMA for 22nd price: 121 * alpha + 110 * (1-alpha) where alpha = 2/22 = 1/11
        # So EMA = 121/11 + 110*10/11 = 11 + 100 = 111.0
        expected_slow = 111.0
        assert math.isclose(ema_slow, expected_slow, rel_tol=1e-9)
