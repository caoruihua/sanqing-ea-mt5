"""
该文件实现 EMA（指数移动平均线）指标计算。

主要职责：
1. 提供纯 Python 实现的 EMA 计算；
2. 支持增量计算和完整计算两种模式；
3. 仅使用标准库，无外部依赖。

说明：
- EMA 用于判断趋势方向；
- 快线（默认 9 周期）和慢线（默认 21 周期）的交叉是策略信号的重要输入。
"""

from typing import List, Optional


def calculate_ema(
    prices: List[float],
    period: int,
    prev_ema: Optional[float] = None,
) -> float:
    """
    计算给定价格序列的指数移动平均线 EMA。

    参数：
        prices: 价格序列（通常为收盘价）
        period: EMA 周期（例如快线 9、慢线 21）
        prev_ema: 若已知上一期 EMA，则可用于增量计算

    返回：
        序列最后一个价格对应的 EMA 数值

    异常：
        ValueError: 当周期非法或数据不足时抛出
    """
    if period <= 0:
        raise ValueError(f"EMA period must be positive, got {period}")

    # 如果提供了上一期 EMA，则走增量计算。
    if prev_ema is not None:
        # 使用最后一个价格做一次递推更新。
        if not prices:
            raise ValueError("No prices provided for EMA calculation")
        price = prices[-1]
        alpha = 2.0 / (period + 1.0)
        ema = price * alpha + prev_ema * (1.0 - alpha)
        return ema

    # 否则从头开始完整计算。
    if len(prices) < period:
        raise ValueError(
            f"Insufficient data for EMA({period}): need at least {period} prices, got {len(prices)}"
        )

    # 先计算首个周期的 SMA。
    sma = sum(prices[:period]) / period

    # 用 SMA 作为 EMA 初始值。
    ema = sma

    # 对剩余价格继续执行 EMA 递推。
    alpha = 2.0 / (period + 1.0)

    for price in prices[period:]:
        ema = price * alpha + ema * (1.0 - alpha)

    return ema


def calculate_ema_series(
    prices: List[float],
    period: int,
) -> List[float]:
    """
    计算序列中每个价格点对应的 EMA。

    参数：
        prices: 价格序列（通常为收盘价）
        period: EMA 周期

    返回：
        与价格点一一对应的 EMA 列表。
        前 `period - 1` 个位置为 `None`，之后为有效 EMA。

    异常：
        ValueError: 当周期非法或数据不足时抛出
    """
    if period <= 0:
        raise ValueError(f"EMA period must be positive, got {period}")

    if len(prices) < period:
        raise ValueError(
            f"Insufficient data for EMA({period}): need at least {period} prices, got {len(prices)}"
        )

    ema_values: List[Optional[float]] = [None] * (period - 1)

    # 先计算首个周期的 SMA。
    sma = sum(prices[:period]) / period
    ema_values.append(sma)

    # 对剩余价格继续执行 EMA 递推。
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
    基于收盘价同时计算快线与慢线 EMA。

    参数：
        close_prices: 收盘价序列
        fast_period: 快线 EMA 周期（例如 9）
        slow_period: 慢线 EMA 周期（例如 21）

    返回：
        `(ema_fast, ema_slow)` 元组

    异常：
        ValueError: 当任一 EMA 所需数据不足时抛出
    """
    ema_fast = calculate_ema(close_prices, fast_period)
    ema_slow = calculate_ema(close_prices, slow_period)

    return ema_fast, ema_slow
