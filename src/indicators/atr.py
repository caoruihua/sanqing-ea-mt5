"""
该文件实现 ATR（平均真实波幅）指标计算。

主要职责：
1. 提供纯 Python 实现的 ATR 计算；
2. 仅使用标准库，无外部依赖；
3. 基于 mt5-rewrite-requirements.md 需求文档设计。

说明：
- ATR 用于衡量市场波动率；
- 计算结果用于止损、止盈、仓位保护等风控逻辑。
"""

from typing import List, Optional


def calculate_true_range(
    high: float,
    low: float,
    prev_close: Optional[float] = None,
) -> float:
    """
    计算单根 K 线的 True Range。

    True Range = max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close)
    )

    参数：
        high: 当前 K 线最高价
        low: 当前 K 线最低价
        prev_close: 前一根 K 线收盘价（可选）

    返回：
        True Range 数值
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
    计算给定价格序列的平均真实波幅 ATR。

    参数：
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        period: ATR 周期（默认 14，符合需求）

    返回：
        序列最后一根 K 线对应的 ATR 数值

    异常：
        ValueError: 当周期非法或数据不足时抛出
        ValueError: 当输入列表长度不一致时抛出
    """
    if period <= 0:
        raise ValueError(f"ATR period must be positive, got {period}")

    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError(
            f"Input lists must have same length: "
            f"highs={len(highs)}, lows={len(lows)}, closes={len(closes)}"
        )

    # 计算 ATR(period) 至少需要 `period + 1` 根 K 线，
    # 因为第一根 True Range 还需要前一根收盘价。
    if len(highs) < period + 1:
        raise ValueError(
            f"Insufficient data for ATR({period}): "
            f"need at least {period + 1} bars, got {len(highs)}"
        )

    # 计算每一根 K 线的 True Range（首根除外）。
    true_ranges: List[float] = []
    for i in range(1, len(highs)):
        tr = calculate_true_range(
            high=highs[i],
            low=lows[i],
            prev_close=closes[i - 1],
        )
        true_ranges.append(tr)

    # 将 True Range 序列按 EMA 方式平滑得到 ATR。
    # 第一笔 ATR 采用前 `period` 个 True Range 的简单平均值。
    initial_atr = sum(true_ranges[:period]) / period

    # 对剩余 True Range 继续执行 EMA 递推。
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
    计算整个序列每一根 K 线对应的 ATR。

    参数：
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        period: ATR 周期（默认 14）

    返回：
        ATR 数值列表。前 `period` 个位置为 `None`，之后为有效 ATR。

    异常：
        ValueError: 当周期非法或数据不足时抛出
        ValueError: 当输入列表长度不一致时抛出
    """
    if period <= 0:
        raise ValueError(f"ATR period must be positive, got {period}")

    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError(
            f"Input lists must have same length: "
            f"highs={len(highs)}, lows={len(lows)}, closes={len(closes)}"
        )

    n_bars = len(highs)

    # 计算 ATR(period) 至少需要 `period + 1` 根 K 线。
    if n_bars < period + 1:
        raise ValueError(
            f"Insufficient data for ATR({period}): need at least {period + 1} bars, got {n_bars}"
        )

    # 计算每一根 K 线的 True Range（首根除外）。
    true_ranges: List[float] = []
    for i in range(1, n_bars):
        tr = calculate_true_range(
            high=highs[i],
            low=lows[i],
            prev_close=closes[i - 1],
        )
        true_ranges.append(tr)

    # 初始化结果列表。
    atr_values: List[Optional[float]] = [None] * (period)  # 前 `period` 根 K 线没有 ATR

    # 第一笔 ATR 采用前 `period` 个 True Range 的简单平均值。
    initial_atr = sum(true_ranges[:period]) / period
    atr_values.append(initial_atr)

    # 对剩余 True Range 继续执行 EMA 递推。
    alpha = 2.0 / (period + 1.0)
    atr = initial_atr

    for tr in true_ranges[period:]:
        atr = tr * alpha + atr * (1.0 - alpha)
        atr_values.append(atr)

    return atr_values
