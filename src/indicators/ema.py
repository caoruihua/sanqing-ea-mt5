"""
EMA indicator helpers.
"""

from typing import List, Tuple

import pandas as pd
import pandas_ta as ta


def calculate_ema(prices: List[float], period: int) -> float:
    """Return the EMA(period) value for the most recent price."""
    if period <= 0:
        raise ValueError(f"EMA period must be positive, got {period}")

    if len(prices) < period:
        raise ValueError(
            f"Insufficient data for EMA({period}): need at least {period} prices, got {len(prices)}"
        )

    series = pd.Series(prices)
    ema_series = ta.ema(series, length=period)
    result = ema_series.iloc[-1]
    if pd.isna(result):
        raise ValueError(f"EMA calculation resulted in NaN for period {period}")

    return float(result)


def calculate_emas(
    close_prices: List[float],
    fast_period: int,
    slow_period: int,
) -> Tuple[float, float]:
    """Return the fast and slow EMAs for the provided series."""
    ema_fast = calculate_ema(close_prices, fast_period)
    ema_slow = calculate_ema(close_prices, slow_period)
    return ema_fast, ema_slow
