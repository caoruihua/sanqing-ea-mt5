"""ADX (Average Directional Index) 指标计算。

用于衡量趋势强度，不区分方向：
- ADX < 20: 弱趋势/震荡市
- ADX 20-25: 趋势萌芽
- ADX > 25: 强趋势
- ADX > 40: 极强趋势
"""

from typing import List

import pandas as pd
import pandas_ta as ta


def calculate_adx(
    highs: List[float], lows: List[float], closes: List[float], period: int = 14
) -> float:
    """计算ADX值。

    Args:
        highs: 最高价列表
        lows: 最低价列表
        closes: 收盘价列表
        period: ADX周期，默认14

    Returns:
        ADX值 (0-100)

    Raises:
        ValueError: 数据不足时抛出
    """
    if len(highs) < period + 1:
        raise ValueError(
            f"Insufficient data for ADX({period}): "
            f"need at least {period + 1} bars, got {len(highs)}"
        )

    df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
    adx_result = df.ta.adx(length=period)

    # pandas-ta返回的列名格式: ADX_14
    adx_column = f"ADX_{period}"
    if adx_column not in adx_result.columns:
        raise ValueError(f"ADX calculation failed: {adx_column} not in result")

    result = adx_result[adx_column].iloc[-1]
    if pd.isna(result):
        raise ValueError(f"ADX calculation resulted in NaN for period {period}")

    return float(result)
