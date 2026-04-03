"""
Unit tests for the validation module.
"""


import pytest

from src.config.validation import (
    ValidationError,
    validate_ema_ordering,
    validate_lot_size,
    validate_strategy_parameters,
    validate_threshold_non_negative,
)


class TestEMAOrdering:
    """Tests for EMA ordering validation."""

    def test_valid_ema_ordering(self):
        """Test valid EMA ordering."""
        validate_ema_ordering(9, 21)  # Should not raise

    def test_invalid_fast_period_zero(self):
        """Test EMA fast period zero."""
        with pytest.raises(ValidationError, match="EMA fast period must be positive"):
            validate_ema_ordering(0, 21)

    def test_invalid_slow_period_zero(self):
        """Test EMA slow period zero."""
        with pytest.raises(ValidationError, match="EMA slow period must be positive"):
            validate_ema_ordering(9, 0)

    def test_invalid_fast_greater_than_slow(self):
        """Test EMA fast greater than slow."""
        with pytest.raises(ValidationError, match="EMA fast period.*must be less than"):
            validate_ema_ordering(21, 9)

    def test_invalid_fast_equal_to_slow(self):
        """Test EMA fast equal to slow."""
        with pytest.raises(ValidationError, match="EMA fast period.*must be less than"):
            validate_ema_ordering(9, 9)


class TestLotSizeValidation:
    """Tests for lot size validation."""

    def test_valid_lot_size(self):
        """Test valid lot sizes."""
        validate_lot_size(0.01)  # Minimum typical lot
        validate_lot_size(1.0)  # Standard lot
        validate_lot_size(0.1)  # Fractional lot

    def test_invalid_lot_size_zero(self):
        """Test lot size zero."""
        with pytest.raises(ValidationError, match="Lot size must be positive"):
            validate_lot_size(0.0)

    def test_invalid_lot_size_negative(self):
        """Test negative lot size."""
        with pytest.raises(ValidationError, match="Lot size must be positive"):
            validate_lot_size(-0.01)

    def test_invalid_lot_size_too_large(self):
        """Test unreasonably large lot size."""
        with pytest.raises(ValidationError, match="Lot size seems unreasonably large"):
            validate_lot_size(1000.0)

    def test_invalid_lot_size_nan(self):
        """Test NaN lot size."""
        with pytest.raises(ValidationError, match="Lot size must be a finite number"):
            validate_lot_size(float("nan"))


class TestThresholdValidation:
    """Tests for threshold validation."""

    def test_valid_thresholds(self):
        """Test valid thresholds."""
        validate_threshold_non_negative(0.0, "Test threshold")
        validate_threshold_non_negative(100.0, "Test threshold")
        validate_threshold_non_negative(0.001, "Test threshold")

    def test_invalid_threshold_negative(self):
        """Test negative threshold."""
        with pytest.raises(ValidationError, match="Test threshold must be non-negative"):
            validate_threshold_non_negative(-1.0, "Test threshold")


class TestStrategyParametersValidation:
    """Tests for strategy parameters validation."""

    def test_valid_strategy_parameters(self):
        """Test valid strategy parameters."""
        params = {
            "ema_fast_period": 9,
            "ema_slow_period": 21,
            "fixed_lots": 0.01,
        }
        validate_strategy_parameters(params)  # Should not raise

    def test_valid_strategy_parameters_with_thresholds(self):
        """Test valid strategy parameters including thresholds."""
        params = {
            "ema_fast_period": 9,
            "ema_slow_period": 21,
            "fixed_lots": 0.01,
            "low_vol_atr_points_floor": 300.0,
            "low_vol_atr_spread_ratio_floor": 3.0,
            "daily_profit_stop_usd": 50.0,
        }
        validate_strategy_parameters(params)  # Should not raise

    def test_invalid_missing_required_parameters(self):
        """Test missing required parameters."""
        params = {
            "ema_fast_period": 9,
            # Missing ema_slow_period
            # Missing fixed_lots
        }
        with pytest.raises(ValidationError, match="Missing required parameters"):
            validate_strategy_parameters(params)

    def test_invalid_ema_ordering_validation(self):
        """Test that EMA ordering validation is called."""
        params = {
            "ema_fast_period": 21,  # Fast > slow
            "ema_slow_period": 9,
            "fixed_lots": 0.01,
        }
        with pytest.raises(ValidationError, match="EMA fast period.*must be less than"):
            validate_strategy_parameters(params)

    def test_invalid_lot_size_validation(self):
        """Test that lot size validation is called."""
        params = {
            "ema_fast_period": 9,
            "ema_slow_period": 21,
            "fixed_lots": 0.0,  # Invalid lot size
        }
        with pytest.raises(ValidationError, match="Lot size must be positive"):
            validate_strategy_parameters(params)

    def test_invalid_negative_thresholds(self):
        """Test negative thresholds."""
        params = {
            "ema_fast_period": 9,
            "ema_slow_period": 21,
            "fixed_lots": 0.01,
            "low_vol_atr_points_floor": -1.0,  # Negative threshold
        }
        with pytest.raises(ValidationError, match="must be non-negative"):
            validate_strategy_parameters(params)


if __name__ == "__main__":
    pytest.main([__file__])
