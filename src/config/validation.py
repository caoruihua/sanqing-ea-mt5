"""
该文件负责交易系统参数的校验。

主要职责：
1. 根据 mt5-rewrite-requirements.md 第 5 节的要求校验配置参数；
2. 校验 EMA 周期顺序（快线 < 慢线）；
3. 校验手数合理性。

说明：
- 在系统启动时执行参数校验；
- 校验失败会抛出 ValidationError。
"""

import math
from typing import Any, Dict


class ValidationError(ValueError):
    """参数校验失败时抛出。"""

    pass


def validate_ema_ordering(ema_fast_period: int, ema_slow_period: int) -> None:
    """
    校验 EMA 周期顺序。

    要求：EMAFastPeriod > 0、EMASlowPeriod > 0，且 EMAFastPeriod < EMASlowPeriod。
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
    校验下单手数。

    要求：FixedLots > 0。
    """
    if lot_size <= 0:
        raise ValidationError(f"Lot size must be positive: {lot_size}")

    # 额外校验：手数需要处于合理范围内。
    if lot_size > 100:
        raise ValidationError(f"Lot size seems unreasonably large: {lot_size}")

    # 检查手数是否为有效数值（不能是 NaN 或 inf）。
    if not math.isfinite(lot_size):
        raise ValidationError(f"Lot size must be a finite number: {lot_size}")


def validate_threshold_non_negative(value: float, name: str) -> None:
    """
    校验阈值必须为非负数。

    要求：各类阈值参数都不能小于 0。
    """
    if value < 0:
        raise ValidationError(f"{name} must be non-negative: {value}")


def validate_strategy_parameters(params: Dict[str, Any]) -> None:
    """
    校验任务 2 需要的核心策略参数。

    这里只校验任务 2 需求中明确提到的参数。
    """
    # 检查必填参数。
    required_params = [
        "ema_fast_period",
        "ema_slow_period",
        "fixed_lots",
    ]

    missing_params = [p for p in required_params if p not in params]
    if missing_params:
        raise ValidationError(f"Missing required parameters: {missing_params}")

    # 执行任务 2 范围内的逐项校验。
    validate_ema_ordering(params["ema_fast_period"], params["ema_slow_period"])
    validate_lot_size(params["fixed_lots"])

    # 若存在可选阈值参数，则继续校验。
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
