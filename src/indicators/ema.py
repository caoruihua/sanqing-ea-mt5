"""
Exponential Moving Average (EMA) indicator implementation.

This module provides pure Python implementations of EMA calculation
using only the standard library, following the requirements from
`mt5-rewrite-requirements.md`.
"""

from typing import List, Optional


def calculate_ema(
    prices: List[float],
    period: int,
    prev_ema: Optional[float] = None,
) -> float:
    """
    Calculate Exponential Moving Average for the given prices.

    Args:
        prices: List of price values (typically close prices)
        period: EMA period (e.g., 9 for fast EMA, 21 for slow EMA)
        prev_ema: Previous EMA value if available (for incremental calculation)

    Returns:
        EMA value for the last price in the list

    Raises:
        ValueError: If period is not positive or insufficient data
    """
    if period <= 0:
        raise ValueError(f"EMA period must be positive, got {period}")

    # If previous EMA is provided, use incremental calculation
    if prev_ema is not None:
        # Use the last price for incremental update
        if not prices:
            raise ValueError("No prices provided for EMA calculation")
        price = prices[-1]
        alpha = 2.0 / (period + 1.0)
        ema = price * alpha + prev_ema * (1.0 - alpha)
        return ema

    # Otherwise calculate from scratch
    if len(prices) < period:
        raise ValueError(
            f"Insufficient data for EMA({period}): need at least {period} prices, got {len(prices)}"
        )

    # Calculate SMA for first period values
    sma = sum(prices[:period]) / period

    # Initialize EMA with SMA
    ema = sma

    # Calculate EMA for remaining values
    alpha = 2.0 / (period + 1.0)

    for price in prices[period:]:
        ema = price * alpha + ema * (1.0 - alpha)

    return ema


def calculate_ema_series(
    prices: List[float],
    period: int,
) -> List[float]:
    """
    Calculate EMA for each price point in the series.

    Args:
        prices: List of price values (typically close prices)
        period: EMA period

    Returns:
        List of EMA values corresponding to each price point.
        The first (period-1) values will be None, then EMA values.

    Raises:
        ValueError: If period is not positive or insufficient data
    """
    if period <= 0:
        raise ValueError(f"EMA period must be positive, got {period}")

    if len(prices) < period:
        raise ValueError(
            f"Insufficient data for EMA({period}): need at least {period} prices, got {len(prices)}"
        )

    ema_values: List[Optional[float]] = [None] * (period - 1)

    # Calculate SMA for first period values
    sma = sum(prices[:period]) / period
    ema_values.append(sma)

    # Calculate EMA for remaining values
    alpha = 2.0 / (period + 1.0)
    ema = sma

    for price in prices[period:]:
        ema = price * alpha + ema * (1.0 - alpha)
        ema_values.append(ema)

    return ema_values  # type: ignore


def calculate_emas(
    close_prices: List[float],
    fast_period: int,
    slow_period: int,
) -> tuple[float, float]:
    """
    Calculate both fast and slow EMAs from close prices.

    Args:
        close_prices: List of close price values
        fast_period: Fast EMA period (e.g., 9)
        slow_period: Slow EMA period (e.g., 21)

    Returns:
        Tuple of (ema_fast, ema_slow)

    Raises:
        ValueError: If insufficient data for either EMA
    """
    ema_fast = calculate_ema(close_prices, fast_period)
    ema_slow = calculate_ema(close_prices, slow_period)

    return ema_fast, ema_slow
