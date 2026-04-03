"""
Price and volume rounding utilities.

This module provides functions for normalizing prices and volumes
according to symbol-specific precision requirements (digits, tick size,
volume step, min/max volume).

Based on MT5 market information constants and requirements for
proper price/volume normalization.
"""

import math
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from typing import Optional, Union


class RoundingError(ValueError):
    """Raised when rounding fails."""

    pass


def normalize_price(
    price: Union[float, Decimal],
    digits: int,
    tick_size: Optional[float] = None,
    rounding_method: str = "half_up",
) -> float:
    """
    Normalize price to the correct number of decimal places.

    Args:
        price: The price to normalize
        digits: Number of decimal places (e.g., 5 for XAUUSD, 2 for EURUSD)
        tick_size: Minimum price movement (if None, uses 10^(-digits))
        rounding_method: 'half_up', 'down', or 'up'

    Returns:
        Normalized price as float

    Raises:
        RoundingError: If price cannot be normalized
    """
    if price <= 0:
        raise RoundingError(f"Price must be positive: {price}")

    # Handle optional tick_size
    actual_tick_size: float
    if tick_size is None:
        actual_tick_size = 10**-digits
    else:
        actual_tick_size = tick_size

    if actual_tick_size <= 0:
        raise RoundingError(f"Tick size must be positive: {actual_tick_size}")

    # Convert to Decimal for precise arithmetic
    try:
        price_dec = Decimal(str(price))
        tick_dec = Decimal(str(actual_tick_size))
    except Exception as e:
        raise RoundingError(f"Failed to convert to Decimal: {e}") from e

    # Calculate number of ticks
    ticks = price_dec / tick_dec

    # Round to nearest tick based on method
    if rounding_method == "half_up":
        ticks_rounded = Decimal(ticks.to_integral_value(rounding=ROUND_HALF_UP))
    elif rounding_method == "down":
        ticks_rounded = Decimal(ticks.to_integral_value(rounding=ROUND_DOWN))
    elif rounding_method == "up":
        ticks_rounded = Decimal(ticks.to_integral_value(rounding=ROUND_UP))
    else:
        raise RoundingError(f"Unknown rounding method: {rounding_method}")

    # Convert back to price
    normalized_price = float(ticks_rounded * tick_dec)

    # Verify the result has correct precision
    normalized_str = str(normalized_price)
    if "." in normalized_str:
        decimal_places = len(normalized_str.split(".")[1])
        if decimal_places > digits:
            # This shouldn't happen, but check anyway
            normalized_price = round(normalized_price, digits)

    return normalized_price


def normalize_volume(
    volume: float,
    volume_step: float,
    min_volume: float,
    max_volume: float,
    rounding_method: str = "up",
) -> float:
    """
    Normalize volume to valid step size within min/max bounds.

    Args:
        volume: Desired volume (lots)
        volume_step: Minimum volume increment (e.g., 0.01 for micro lots)
        min_volume: Minimum allowed volume
        max_volume: Maximum allowed volume
        rounding_method: 'up', 'down', or 'nearest'

    Returns:
        Normalized volume as float

    Raises:
        RoundingError: If volume is out of bounds or cannot be normalized
    """
    if volume <= 0:
        raise RoundingError(f"Volume must be positive: {volume}")

    if volume_step <= 0:
        raise RoundingError(f"Volume step must be positive: {volume_step}")

    if min_volume <= 0:
        raise RoundingError(f"Minimum volume must be positive: {min_volume}")

    if max_volume <= min_volume:
        raise RoundingError(
            f"Maximum volume ({max_volume}) must be greater than minimum ({min_volume})"
        )

    # Check bounds first
    if volume < min_volume:
        raise RoundingError(f"Volume {volume} is below minimum {min_volume}")

    if volume > max_volume:
        raise RoundingError(f"Volume {volume} exceeds maximum {max_volume}")

    # Calculate number of steps
    steps = volume / volume_step

    # Round based on method
    if rounding_method == "up":
        steps_rounded = math.ceil(steps)
    elif rounding_method == "down":
        steps_rounded = math.floor(steps)
    elif rounding_method == "nearest":
        steps_rounded = round(steps)
    else:
        raise RoundingError(f"Unknown rounding method: {rounding_method}")

    normalized_volume = steps_rounded * volume_step

    # Ensure within bounds after rounding
    if normalized_volume < min_volume:
        normalized_volume = min_volume
    elif normalized_volume > max_volume:
        normalized_volume = max_volume

    # Verify step alignment
    remainder = normalized_volume % volume_step
    if abs(remainder) > 1e-10:  # Allow for floating point error
        # Force alignment
        normalized_volume = round(normalized_volume / volume_step) * volume_step

    return normalized_volume


def calculate_points_from_price(
    price1: float,
    price2: float,
    digits: int,
) -> float:
    """
    Calculate points difference between two prices.

    In Forex, 1 point = 0.00001 for 5-digit prices, 0.0001 for 4-digit.

    Args:
        price1: First price
        price2: Second price
        digits: Number of decimal places

    Returns:
        Points difference
    """
    point_size = 10**-digits
    points = abs(price1 - price2) / point_size
    return points


def calculate_price_from_points(
    base_price: float,
    points: float,
    digits: int,
) -> float:
    """
    Calculate price from points difference.

    Args:
        base_price: Base price
        points: Points to add/subtract
        digits: Number of decimal places

    Returns:
        Calculated price
    """
    point_size = 10**-digits
    price = base_price + (points * point_size)

    # Normalize to correct digits
    return normalize_price(price, digits)


def calculate_atr_points(
    atr_value: float,
    digits: int,
) -> float:
    """
    Calculate ATR in points.

    Args:
        atr_value: ATR value in price units
        digits: Number of decimal places

    Returns:
        ATR in points
    """
    point_size = 10**-digits
    atr_points = atr_value / point_size
    return atr_points


def calculate_spread_points(
    ask: float,
    bid: float,
    digits: int,
) -> float:
    """
    Calculate spread in points.

    Args:
        ask: Ask price
        bid: Bid price
        digits: Number of decimal places

    Returns:
        Spread in points
    """
    return calculate_points_from_price(ask, bid, digits)
