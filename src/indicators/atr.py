"""
Average True Range (ATR) indicator implementation.

This module provides pure Python implementations of ATR calculation
using only the standard library, following the requirements from
`mt5-rewrite-requirements.md`.
"""

from typing import List, Optional


def calculate_true_range(
    high: float,
    low: float,
    prev_close: Optional[float] = None,
) -> float:
    """
    Calculate True Range for a single bar.

    True Range = max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close)
    )

    Args:
        high: High price of current bar
        low: Low price of current bar
        prev_close: Close price of previous bar (optional)

    Returns:
        True Range value
    """
    hl_range = high - low

    if prev_close is None:
        return hl_range

    hc_range = abs(high - prev_close)
    lc_range = abs(low - prev_close)

    return max(hl_range, hc_range, lc_range)


def calculate_atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> float:
    """
    Calculate Average True Range (ATR) for the given price series.

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of close prices
        period: ATR period (default 14 as per requirements)

    Returns:
        ATR value for the last bar in the series

    Raises:
        ValueError: If period is not positive or insufficient data
        ValueError: If input lists have different lengths
    """
    if period <= 0:
        raise ValueError(f"ATR period must be positive, got {period}")

    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError(
            f"Input lists must have same length: "
            f"highs={len(highs)}, lows={len(lows)}, closes={len(closes)}"
        )

    # Need at least period+1 bars to calculate ATR(period)
    # because first True Range needs previous close
    if len(highs) < period + 1:
        raise ValueError(
            f"Insufficient data for ATR({period}): "
            f"need at least {period + 1} bars, got {len(highs)}"
        )

    # Calculate True Range for each bar (except first)
    true_ranges: List[float] = []
    for i in range(1, len(highs)):
        tr = calculate_true_range(
            high=highs[i],
            low=lows[i],
            prev_close=closes[i - 1],
        )
        true_ranges.append(tr)

    # Calculate ATR as EMA of True Ranges
    # First ATR is simple average of first period True Ranges
    initial_atr = sum(true_ranges[:period]) / period

    # Calculate EMA for remaining True Ranges
    alpha = 2.0 / (period + 1.0)
    atr = initial_atr

    for tr in true_ranges[period:]:
        atr = tr * alpha + atr * (1.0 - alpha)

    return atr


def calculate_atr_series(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> List[Optional[float]]:
    """
    Calculate ATR for each bar in the series.

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of close prices
        period: ATR period (default 14)

    Returns:
        List of ATR values. First period values will be None, then ATR values.

    Raises:
        ValueError: If period is not positive or insufficient data
        ValueError: If input lists have different lengths
    """
    if period <= 0:
        raise ValueError(f"ATR period must be positive, got {period}")

    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError(
            f"Input lists must have same length: "
            f"highs={len(highs)}, lows={len(lows)}, closes={len(closes)}"
        )

    n_bars = len(highs)

    # Need at least period+1 bars to calculate ATR(period)
    if n_bars < period + 1:
        raise ValueError(
            f"Insufficient data for ATR({period}): need at least {period + 1} bars, got {n_bars}"
        )

    # Calculate True Range for each bar (except first)
    true_ranges: List[float] = []
    for i in range(1, n_bars):
        tr = calculate_true_range(
            high=highs[i],
            low=lows[i],
            prev_close=closes[i - 1],
        )
        true_ranges.append(tr)

    # Initialize result list
    atr_values: List[Optional[float]] = [None] * (period)  # First period bars have no ATR

    # First ATR is simple average of first period True Ranges
    initial_atr = sum(true_ranges[:period]) / period
    atr_values.append(initial_atr)

    # Calculate EMA for remaining True Ranges
    alpha = 2.0 / (period + 1.0)
    atr = initial_atr

    for tr in true_ranges[period:]:
        atr = tr * alpha + atr * (1.0 - alpha)
        atr_values.append(atr)

    return atr_values
