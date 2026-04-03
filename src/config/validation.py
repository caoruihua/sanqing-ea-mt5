"""
Parameter validation for the trading system.

This module validates configuration parameters according to the
requirements in `mt5-rewrite-requirements.md` section 5.
"""

import math
from typing import Any, Dict


class ValidationError(ValueError):
    """Raised when validation fails."""

    pass


def validate_ema_ordering(ema_fast_period: int, ema_slow_period: int) -> None:
    """
    Validate EMA period ordering.

    Requirements: EMAFastPeriod > 0, EMASlowPeriod > 0, EMAFastPeriod < EMASlowPeriod
    """
    if ema_fast_period <= 0:
        raise ValidationError(f"EMA fast period must be positive: {ema_fast_period}")
    if ema_slow_period <= 0:
        raise ValidationError(f"EMA slow period must be positive: {ema_slow_period}")
    if ema_fast_period >= ema_slow_period:
        raise ValidationError(
            f"EMA fast period ({ema_fast_period}) must be less than "
            f"EMA slow period ({ema_slow_period})"
        )


def validate_lot_size(lot_size: float) -> None:
    """
    Validate lot size.

    Requirements: FixedLots > 0
    """
    if lot_size <= 0:
        raise ValidationError(f"Lot size must be positive: {lot_size}")

    # Additional validation: lot size should be reasonable
    if lot_size > 100:
        raise ValidationError(f"Lot size seems unreasonably large: {lot_size}")

    # Check if lot size is a valid number (not NaN or inf)
    if not math.isfinite(lot_size):
        raise ValidationError(f"Lot size must be a finite number: {lot_size}")


def validate_threshold_non_negative(value: float, name: str) -> None:
    """
    Validate that a threshold value is non-negative.

    Requirements: Various thresholds must be non-negative.
    """
    if value < 0:
        raise ValidationError(f"{name} must be non-negative: {value}")


def validate_strategy_parameters(params: Dict[str, Any]) -> None:
    """
    Validate core strategy parameters required by Task 2.

    Validates only the parameters explicitly mentioned in Task 2 requirements.
    """
    # Check for required parameters
    required_params = [
        "ema_fast_period",
        "ema_slow_period",
        "fixed_lots",
    ]

    missing_params = [p for p in required_params if p not in params]
    if missing_params:
        raise ValidationError(f"Missing required parameters: {missing_params}")

    # Individual validations for Task 2 scope
    validate_ema_ordering(params["ema_fast_period"], params["ema_slow_period"])
    validate_lot_size(params["fixed_lots"])

    # Check optional threshold parameters if present
    threshold_params = [
        "low_vol_atr_points_floor",
        "low_vol_atr_spread_ratio_floor",
        "daily_profit_stop_usd",
    ]

    for param_name in threshold_params:
        if param_name in params:
            validate_threshold_non_negative(
                params[param_name], param_name.replace("_", " ").title()
            )
