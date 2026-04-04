"""
该文件提供价格和手数的归一化/舍入工具函数。

主要职责：
1. 根据品种精度要求（小数位、tick size）归一化价格；
2. 根据手数步长归一化交易量；
3. 支持多种舍入模式（四舍五入、向上取整、向下取整）。

说明：
- 基于 MT5 市场信息常量设计；
- 确保下单价格和手数符合 Broker 要求。
"""

import math
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from typing import Optional, Union


class RoundingError(ValueError):
    """归一化或舍入失败时抛出。"""

    pass


def normalize_price(
    price: Union[float, Decimal],
    digits: int,
    tick_size: Optional[float] = None,
    rounding_method: str = "half_up",
) -> float:
    """
    将价格归一化到正确的小数位数。

    参数：
        price: 待归一化的价格
        digits: 小数位数（例如 XAUUSD 常用 5，EURUSD 常用 2）
        tick_size: 最小价格跳动（若为 `None`，则使用 `10^(-digits)`）
        rounding_method: 舍入方式，可选 `'half_up'`、`'down'` 或 `'up'`

    返回：
        归一化后的浮点价格

    异常：
        RoundingError: 当价格无法正确归一化时抛出
    """
    if price <= 0:
        raise RoundingError(f"Price must be positive: {price}")

    # 处理可选的 tick_size 参数。
    actual_tick_size: float
    if tick_size is None:
        actual_tick_size = 10**-digits
    else:
        actual_tick_size = tick_size

    if actual_tick_size <= 0:
        raise RoundingError(f"Tick size must be positive: {actual_tick_size}")

    # 转成 Decimal，避免浮点误差。
    try:
        price_dec = Decimal(str(price))
        tick_dec = Decimal(str(actual_tick_size))
    except Exception as e:
        raise RoundingError(f"Failed to convert to Decimal: {e}") from e

    # 计算当前价格对应多少个最小跳动单位。
    ticks = price_dec / tick_dec

    # 按指定方式舍入到最近的跳动单位。
    if rounding_method == "half_up":
        ticks_rounded = Decimal(ticks.to_integral_value(rounding=ROUND_HALF_UP))
    elif rounding_method == "down":
        ticks_rounded = Decimal(ticks.to_integral_value(rounding=ROUND_DOWN))
    elif rounding_method == "up":
        ticks_rounded = Decimal(ticks.to_integral_value(rounding=ROUND_UP))
    else:
        raise RoundingError(f"Unknown rounding method: {rounding_method}")

    # 转回价格数值。
    normalized_price = float(ticks_rounded * tick_dec)

    # 校验结果的小数精度是否符合要求。
    normalized_str = str(normalized_price)
    if "." in normalized_str:
        decimal_places = len(normalized_str.split(".")[1])
        if decimal_places > digits:
            # 理论上不应发生，但仍做兜底校验。
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
    将手数归一化到合法步长，并限制在最小/最大范围内。

    参数：
        volume: 目标手数（lots）
        volume_step: 最小手数步长（例如 0.01）
        min_volume: 允许的最小手数
        max_volume: 允许的最大手数
        rounding_method: 舍入方式，可选 `'up'`、`'down'` 或 `'nearest'`

    返回：
        归一化后的浮点手数

    异常：
        RoundingError: 当手数越界或无法归一化时抛出
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

    # 先检查上下界。
    if volume < min_volume:
        raise RoundingError(f"Volume {volume} is below minimum {min_volume}")

    if volume > max_volume:
        raise RoundingError(f"Volume {volume} exceeds maximum {max_volume}")

    # 计算对应多少个步长单位。
    steps = volume / volume_step

    # 按指定方式舍入步长数。
    if rounding_method == "up":
        steps_rounded = math.ceil(steps)
    elif rounding_method == "down":
        steps_rounded = math.floor(steps)
    elif rounding_method == "nearest":
        steps_rounded = round(steps)
    else:
        raise RoundingError(f"Unknown rounding method: {rounding_method}")

    normalized_volume = steps_rounded * volume_step

    # 舍入后再次确保仍在合法范围内。
    if normalized_volume < min_volume:
        normalized_volume = min_volume
    elif normalized_volume > max_volume:
        normalized_volume = max_volume

    # 校验是否与步长对齐。
    remainder = normalized_volume % volume_step
    if abs(remainder) > 1e-10:  # 允许存在极小的浮点误差
        # 强制对齐到合法步长。
        normalized_volume = round(normalized_volume / volume_step) * volume_step

    return normalized_volume


def calculate_points_from_price(
    price1: float,
    price2: float,
    digits: int,
) -> float:
    """
    计算两个价格之间相差多少个 points。

    在外汇里，5 位小数价格通常 1 point = 0.00001，4 位小数通常为 0.0001。

    参数：
        price1: 第一个价格
        price2: 第二个价格
        digits: 小数位数

    返回：
        价格差对应的 points 数值
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
    根据 points 差值推算目标价格。

    参数：
        base_price: 基准价格
        points: 需要加减的 points 数
        digits: 小数位数

    返回：
        计算后的价格
    """
    point_size = 10**-digits
    price = base_price + (points * point_size)

    # 再按品种精度做一次归一化。
    return normalize_price(price, digits)


def calculate_atr_points(
    atr_value: float,
    digits: int,
) -> float:
    """
    将 ATR 的价格单位数值换算成 points。

    参数：
        atr_value: 价格单位下的 ATR 数值
        digits: 小数位数

    返回：
        points 单位下的 ATR 数值
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
    计算点差对应的 points 数值。

    参数：
        ask: 卖价
        bid: 买价
        digits: 小数位数

    返回：
        points 单位下的点差
    """
    return calculate_points_from_price(ask, bid, digits)
