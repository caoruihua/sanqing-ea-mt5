"""
Average True Range indicator helpers.
"""

from typing import List

import pandas as pd
import pandas_ta as ta


def calculate_atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> float:
    """Return ATR(period) value for the most recent bar."""
    if period <= 0:
        raise ValueError(f"ATR period must be positive, got {period}")

    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError(
            f"Input lists must have same length: "
            f"highs={len(highs)}, lows={len(lows)}, closes={len(closes)}"
        )

    if len(highs) < period + 1:
        raise ValueError(
            f"Insufficient data for ATR({period}): "
            f"need at least {period + 1} bars, got {len(highs)}"
        )

    df = pd.DataFrame(
        {
            "high": highs,
            "low": lows,
            "close": closes,
        }
    )

    atr_series = ta.atr(df["high"], df["low"], df["close"], length=period)
    result = atr_series.iloc[-1]
    if pd.isna(result):
        raise ValueError(f"ATR calculation resulted in NaN for period {period}")

    return float(result)
