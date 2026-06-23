from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Literal

from .data import data_state, filter_date_range, filter_excluded_dates, filter_recent_days, load_bars
from .indicators import ema
from .metrics import calculate_metrics
from .report import write_html_report
from .strategy import CostParams, StrategyParams, backtest


Objective = Literal["score", "net_points"]


@dataclass(frozen=True)
class OptimizerConfig:
    data_path: Path
    report_dir: Path
    lookback_days: int
    ema_fast_values: list[int]
    ema_slow_values: list[int]
    time_check_values: list[int]
    stop_loss_values: list[int]
    cooldown_values: list[int]
    objective: Objective
    min_trades: int
    top_n: int
    point_size: float
    fallback_spread_points: float
    slippage_points: float
    commission_points: float
    excluded_dates: list[str]
    start_date: str | None = None   # YYYY-MM-DD，指定时替代 lookback_days
    end_date: str | None = None     # YYYY-MM-DD
    day_time_check_values: list[int] | None = None
    day_time_recheck_values: list[int] | None = None
    day_stop_loss_values: list[int] | None = None
    night_time_check_values: list[int] | None = None
    night_time_recheck_values: list[int] | None = None
    night_stop_loss_values: list[int] | None = None
    day_use_stop_loss: bool = True
    day_time_profit_close: bool = True
    night_use_stop_loss: bool = True
    night_time_profit_close: bool = True
    use_break_even_stop: bool = True
    break_even_start_points: int = 500
    break_even_lock_points: int = 30
    use_profit_giveback_close: bool = True
    giveback_start_points: int = 1500
    giveback_close_points: int = 700
    giveback_close_percent: float = 80.0


def run_optimization(config: OptimizerConfig) -> dict[str, object]:
    all_bars = load_bars(config.data_path, config.fallback_spread_points, config.point_size)
    # 日期范围优先：指定 start_date/end_date 时替代 lookback_days
    if config.start_date or config.end_date:
        bars = filter_date_range(all_bars, config.start_date, config.end_date)
    else:
        bars = filter_recent_days(all_bars, config.lookback_days)
    bars = filter_excluded_dates(bars, set(config.excluded_dates))
    closes = [bar.close for bar in bars]
    periods = sorted(set(config.ema_fast_values + config.ema_slow_values))
    ema_cache = {period: ema(closes, period) for period in periods}
    costs = CostParams(
        point_size=config.point_size,
        slippage_points=config.slippage_points,
        commission_points=config.commission_points,
    )

    rows: list[dict[str, object]] = []
    time_pairs = _paired_values(config.day_time_check_values, config.night_time_check_values, config.time_check_values)
    stop_pairs = _paired_values(config.day_stop_loss_values, config.night_stop_loss_values, config.stop_loss_values)
    recheck_pairs = _paired_values(config.day_time_recheck_values, config.night_time_recheck_values, [5])

    for fast, slow, time_pair, stop_pair, recheck_pair, cooldown in product(
        config.ema_fast_values,
        config.ema_slow_values,
        time_pairs,
        stop_pairs,
        recheck_pairs,
        config.cooldown_values,
    ):
        if fast >= slow:
            continue
        day_time_check, night_time_check = time_pair
        day_stop_loss, night_stop_loss = stop_pair
        day_recheck, night_recheck = recheck_pair
        params = StrategyParams(
            ema_fast=fast,
            ema_slow=slow,
            cooldown_minutes=cooldown,
            day_stop_loss_points=day_stop_loss,
            day_use_stop_loss=config.day_use_stop_loss,
            day_time_check_minutes=day_time_check,
            day_time_profit_recheck_minutes=day_recheck,
            day_time_profit_close=config.day_time_profit_close,
            night_stop_loss_points=night_stop_loss,
            night_use_stop_loss=config.night_use_stop_loss,
            night_time_check_minutes=night_time_check,
            night_time_profit_recheck_minutes=night_recheck,
            night_time_profit_close=config.night_time_profit_close,
            use_break_even_stop=config.use_break_even_stop,
            break_even_start_points=config.break_even_start_points,
            break_even_lock_points=config.break_even_lock_points,
            use_profit_giveback_close=config.use_profit_giveback_close,
            giveback_start_points=config.giveback_start_points,
            giveback_close_points=config.giveback_close_points,
            giveback_close_percent=config.giveback_close_percent,
        )
        trades = backtest(bars, ema_cache[fast], ema_cache[slow], params, costs)
        metrics = calculate_metrics(trades, config.min_trades)
        rows.append(
            {
                "ema_fast": fast,
                "ema_slow": slow,
                "time_check_minutes": day_time_check,
                "stop_loss_points": day_stop_loss,
                "day_time_check_minutes": day_time_check,
                "day_time_profit_recheck_minutes": day_recheck,
                "day_stop_loss_points": day_stop_loss,
                "day_use_stop_loss": config.day_use_stop_loss,
                "day_time_profit_close": config.day_time_profit_close,
                "night_time_check_minutes": night_time_check,
                "night_time_profit_recheck_minutes": night_recheck,
                "night_stop_loss_points": night_stop_loss,
                "night_use_stop_loss": config.night_use_stop_loss,
                "night_time_profit_close": config.night_time_profit_close,
                "use_break_even_stop": config.use_break_even_stop,
                "break_even_start_points": config.break_even_start_points,
                "break_even_lock_points": config.break_even_lock_points,
                "use_profit_giveback_close": config.use_profit_giveback_close,
                "giveback_start_points": config.giveback_start_points,
                "giveback_close_points": config.giveback_close_points,
                "giveback_close_percent": config.giveback_close_percent,
                "cooldown_minutes": cooldown,
                **metrics,
            }
        )

    if not rows:
        raise ValueError("No valid parameter combinations were evaluated.")

    rows.sort(key=lambda item: (float(item[config.objective]), float(item["net_points"])), reverse=True)
    config.report_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "objective": config.objective,
        "lookback_days": config.lookback_days,
        "bars_used": len(bars),
        "from": bars[0].time.isoformat(sep=" "),
        "to": bars[-1].time.isoformat(sep=" "),
        "data_state": data_state(all_bars, config.data_path),
        "excluded_dates": config.excluded_dates,
        "best": rows[0],
        "top": rows[: config.top_n],
    }

    best_params = StrategyParams(
        ema_fast=int(rows[0]["ema_fast"]),
        ema_slow=int(rows[0]["ema_slow"]),
        cooldown_minutes=int(rows[0]["cooldown_minutes"]),
        day_stop_loss_points=int(rows[0]["day_stop_loss_points"]),
        day_use_stop_loss=bool(rows[0]["day_use_stop_loss"]),
        day_time_check_minutes=int(rows[0]["day_time_check_minutes"]),
        day_time_profit_recheck_minutes=int(rows[0]["day_time_profit_recheck_minutes"]),
        day_time_profit_close=bool(rows[0]["day_time_profit_close"]),
        night_stop_loss_points=int(rows[0]["night_stop_loss_points"]),
        night_use_stop_loss=bool(rows[0]["night_use_stop_loss"]),
        night_time_check_minutes=int(rows[0]["night_time_check_minutes"]),
        night_time_profit_recheck_minutes=int(rows[0]["night_time_profit_recheck_minutes"]),
        night_time_profit_close=bool(rows[0]["night_time_profit_close"]),
        use_break_even_stop=bool(rows[0]["use_break_even_stop"]),
        break_even_start_points=int(rows[0]["break_even_start_points"]),
        break_even_lock_points=int(rows[0]["break_even_lock_points"]),
        use_profit_giveback_close=bool(rows[0]["use_profit_giveback_close"]),
        giveback_start_points=int(rows[0]["giveback_start_points"]),
        giveback_close_points=int(rows[0]["giveback_close_points"]),
        giveback_close_percent=float(rows[0]["giveback_close_percent"]),
    )
    best_trades = backtest(
        bars,
        ema_cache[best_params.ema_fast],
        ema_cache[best_params.ema_slow],
        best_params,
        costs,
    )
    write_html_report(config.report_dir / "report.html", summary, best_trades)
    return summary


def _paired_values(
    day_values: list[int] | None,
    night_values: list[int] | None,
    fallback_values: list[int],
) -> list[tuple[int, int]]:
    if day_values is None and night_values is None:
        return [(value, value) for value in fallback_values]
    resolved_day = day_values if day_values is not None else fallback_values
    resolved_night = night_values if night_values is not None else fallback_values
    return list(product(resolved_day, resolved_night))
