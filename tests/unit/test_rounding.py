"""
Unit tests for the rounding utilities.
"""

import math
from decimal import Decimal

import pytest

from src.utils.rounding import (
    RoundingError,
    calculate_atr_points,
    calculate_points_from_price,
    calculate_price_from_points,
    calculate_spread_points,
    normalize_price,
    normalize_volume,
)


class TestNormalizePrice:
    """Tests for price normalization."""

    def test_normalize_price_default_tick_size(self):
        """Test price normalization with default tick size."""
        # XAUUSD with 2 decimal places
        result = normalize_price(1800.505, digits=2)
        assert result == 1800.51  # Rounded up

        result = normalize_price(1800.504, digits=2)
        assert result == 1800.50  # Rounded down

    def test_normalize_price_custom_tick_size(self):
        """Test price normalization with custom tick size."""
        # Tick size of 0.25
        result = normalize_price(1800.30, digits=2, tick_size=0.25)
        assert result == 1800.25  # Rounded down to nearest 0.25

        result = normalize_price(1800.40, digits=2, tick_size=0.25)
        assert result == 1800.50  # Rounded up to nearest 0.25

    def test_normalize_price_rounding_methods(self):
        """Test different rounding methods."""
        price = 1800.505

        # Half up (default)
        result = normalize_price(price, digits=2, rounding_method="half_up")
        assert result == 1800.51

        # Round down
        result = normalize_price(price, digits=2, rounding_method="down")
        assert result == 1800.50

        # Round up
        result = normalize_price(price, digits=2, rounding_method="up")
        assert result == 1800.51

    def test_normalize_price_decimal_input(self):
        """Test price normalization with Decimal input."""
        result = normalize_price(Decimal("1800.505"), digits=2)
        assert result == 1800.51

    def test_normalize_price_negative_price(self):
        """Test negative price (should fail)."""
        with pytest.raises(RoundingError, match="Price must be positive"):
            normalize_price(-1800.50, digits=2)

    def test_normalize_price_zero_price(self):
        """Test zero price (should fail)."""
        with pytest.raises(RoundingError, match="Price must be positive"):
            normalize_price(0.0, digits=2)

    def test_normalize_price_negative_tick_size(self):
        """Test negative tick size (should fail)."""
        with pytest.raises(RoundingError, match="Tick size must be positive"):
            normalize_price(1800.50, digits=2, tick_size=-0.01)

    def test_normalize_price_zero_tick_size(self):
        """Test zero tick size (should fail)."""
        with pytest.raises(RoundingError, match="Tick size must be positive"):
            normalize_price(1800.50, digits=2, tick_size=0.0)

    def test_normalize_price_invalid_rounding_method(self):
        """Test invalid rounding method (should fail)."""
        with pytest.raises(RoundingError, match="Unknown rounding method"):
            normalize_price(1800.50, digits=2, rounding_method="invalid")


class TestNormalizeVolume:
    """Tests for volume normalization."""

    def test_normalize_volume_standard_lots(self):
        """Test volume normalization for standard lots."""
        # Standard lot with 0.01 step
        result = normalize_volume(
            volume=1.0,
            volume_step=0.01,
            min_volume=0.01,
            max_volume=100.0,
            rounding_method="nearest",
        )
        assert result == 1.0

    def test_normalize_volume_fractional_lots(self):
        """Test volume normalization for fractional lots."""
        # Round up
        result = normalize_volume(
            volume=0.015, volume_step=0.01, min_volume=0.01, max_volume=100.0, rounding_method="up"
        )
        assert result == 0.02

        # Round down
        result = normalize_volume(
            volume=0.015,
            volume_step=0.01,
            min_volume=0.01,
            max_volume=100.0,
            rounding_method="down",
        )
        assert result == 0.01

        # Round nearest
        result = normalize_volume(
            volume=0.015,
            volume_step=0.01,
            min_volume=0.01,
            max_volume=100.0,
            rounding_method="nearest",
        )
        # Python's round() uses banker's rounding, so 1.5 rounds to 2
        assert result == 0.02

    def test_normalize_volume_at_minimum(self):
        """Test volume at minimum bound."""
        result = normalize_volume(volume=0.01, volume_step=0.01, min_volume=0.01, max_volume=100.0)
        assert result == 0.01

    def test_normalize_volume_at_maximum(self):
        """Test volume at maximum bound."""
        result = normalize_volume(volume=100.0, volume_step=0.01, min_volume=0.01, max_volume=100.0)
        assert result == 100.0

    def test_normalize_volume_below_minimum(self):
        """Test volume below minimum (should fail)."""
        with pytest.raises(RoundingError, match="Volume.*is below minimum"):
            normalize_volume(volume=0.005, volume_step=0.01, min_volume=0.01, max_volume=100.0)

    def test_normalize_volume_above_maximum(self):
        """Test volume above maximum (should fail)."""
        with pytest.raises(RoundingError, match="Volume.*exceeds maximum"):
            normalize_volume(volume=200.0, volume_step=0.01, min_volume=0.01, max_volume=100.0)

    def test_normalize_volume_negative_volume(self):
        """Test negative volume (should fail)."""
        with pytest.raises(RoundingError, match="Volume must be positive"):
            normalize_volume(volume=-1.0, volume_step=0.01, min_volume=0.01, max_volume=100.0)

    def test_normalize_volume_invalid_step(self):
        """Test invalid volume step (should fail)."""
        with pytest.raises(RoundingError, match="Volume step must be positive"):
            normalize_volume(volume=1.0, volume_step=0.0, min_volume=0.01, max_volume=100.0)

    def test_normalize_volume_invalid_bounds(self):
        """Test invalid min/max bounds (should fail)."""
        with pytest.raises(RoundingError, match="Maximum volume.*must be greater than minimum"):
            normalize_volume(volume=1.0, volume_step=0.01, min_volume=10.0, max_volume=1.0)


class TestPointsCalculations:
    """Tests for points-based calculations."""

    def test_calculate_points_from_price(self):
        """Test points calculation from prices."""
        # XAUUSD with 2 digits (1 point = 0.01)
        result = calculate_points_from_price(1800.50, 1800.00, digits=2)
        assert math.isclose(result, 50.0, rel_tol=1e-9)  # (1800.50 - 1800.00) / 0.01

        # EURUSD with 5 digits (1 point = 0.00001)
        result = calculate_points_from_price(1.08500, 1.08490, digits=5)
        assert math.isclose(result, 10.0, rel_tol=1e-9)  # (1.08500 - 1.08490) / 0.00001

    def test_calculate_price_from_points(self):
        """Test price calculation from points."""
        # XAUUSD with 2 digits
        result = calculate_price_from_points(1800.00, 50.0, digits=2)
        assert math.isclose(result, 1800.50, rel_tol=1e-9)

        # EURUSD with 5 digits
        result = calculate_price_from_points(1.08490, 10.0, digits=5)
        assert math.isclose(result, 1.08500, rel_tol=1e-9)

    def test_calculate_atr_points(self):
        """Test ATR points calculation."""
        # XAUUSD: ATR of 18.0 with 2 digits
        result = calculate_atr_points(18.0, digits=2)
        assert math.isclose(result, 1800.0, rel_tol=1e-9)  # 18.0 / 0.01

        # EURUSD: ATR of 0.0010 with 5 digits
        result = calculate_atr_points(0.0010, digits=5)
        assert math.isclose(result, 100.0, rel_tol=1e-9)  # 0.0010 / 0.00001

    def test_calculate_spread_points(self):
        """Test spread points calculation."""
        # XAUUSD: spread of 0.05 with 2 digits
        result = calculate_spread_points(1800.55, 1800.50, digits=2)
        assert math.isclose(result, 5.0, rel_tol=1e-9)  # (1800.55 - 1800.50) / 0.01

        # EURUSD: spread of 0.00010 with 5 digits
        result = calculate_spread_points(1.08500, 1.08490, digits=5)
        assert math.isclose(result, 10.0, rel_tol=1e-9)  # (1.08500 - 1.08490) / 0.00001


if __name__ == "__main__":
    pytest.main([__file__])
