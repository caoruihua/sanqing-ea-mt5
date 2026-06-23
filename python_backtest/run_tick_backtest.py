#!/usr/bin/env python
"""Run a tick-level TimeProfitEA backtest on HistData bid/ask tick files."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.timeprofit_backtest.metrics import calculate_metrics
from src.timeprofit_backtest.report import write_html_report
from src.timeprofit_backtest.strategy import StrategyParams
from src.timeprofit_backtest.tick_backtester import TickBacktestConfig, run_tick_backtest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run tick-level TimeProfitEA validation using HistData tick CSV/ZIP files."
    )
    parser.add_argument(
        "--data",
        default=str(Path(__file__).parent / "data"),
        help="Tick CSV/ZIP file or directory. Defaults to python_backtest/data.",
    )
    parser.add_argument(
        "--report",
        default=str(Path(__file__).parent / "reports" / "tick_report.html"),
        help="HTML report path. Defaults to python_backtest/reports/tick_report.html.",
    )
    parser.add_argument("--fast", type=int, default=15)
    parser.add_argument("--slow", type=int, default=44)
    parser.add_argument("--time-check", type=int, default=None)
    parser.add_argument("--stop-loss", type=int, default=None)
    parser.add_argument("--cooldown", type=int, default=10)
    parser.add_argument("--day-time-check", type=int, default=None)
    parser.add_argument("--day-recheck", type=int, default=5)
    parser.add_argument("--day-stop-loss", type=int, default=None)
    parser.add_argument("--night-time-check", type=int, default=None)
    parser.add_argument("--night-recheck", type=int, default=5)
    parser.add_argument("--night-stop-loss", type=int, default=None)
    parser.add_argument("--disable-day-stop-loss", action="store_true")
    parser.add_argument("--disable-night-stop-loss", action="store_true")
    parser.add_argument("--disable-day-time-profit", action="store_true")
    parser.add_argument("--disable-night-time-profit", action="store_true")
    parser.add_argument("--disable-break-even", action="store_true")
    parser.add_argument("--break-even-start", type=int, default=500)
    parser.add_argument("--break-even-lock", type=int, default=30)
    parser.add_argument("--disable-giveback-close", action="store_true")
    parser.add_argument("--giveback-start", type=int, default=1500)
    parser.add_argument("--giveback-points", type=int, default=700)
    parser.add_argument("--giveback-percent", type=float, default=80.0)
    parser.add_argument("--point-size", type=float, default=0.01)
    parser.add_argument(
        "--exclude-dates",
        default="",
        help="Comma-separated dates to exclude, e.g. 2025-06-03,2026-01-01.",
    )
    parser.add_argument(
        "--time-profit-mode",
        choices=("tick", "bar"),
        default="bar",
        help="tick checks profit on every tick after the time threshold; bar checks only on new M5 bars.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    params = StrategyParams(
        ema_fast=args.fast,
        ema_slow=args.slow,
        cooldown_minutes=args.cooldown,
        day_stop_loss_points=args.day_stop_loss if args.day_stop_loss is not None else args.stop_loss,
        day_use_stop_loss=not args.disable_day_stop_loss,
        day_time_check_minutes=args.day_time_check if args.day_time_check is not None else args.time_check,
        day_time_profit_recheck_minutes=args.day_recheck,
        day_time_profit_close=not args.disable_day_time_profit,
        night_stop_loss_points=args.night_stop_loss if args.night_stop_loss is not None else args.stop_loss,
        night_use_stop_loss=not args.disable_night_stop_loss,
        night_time_check_minutes=args.night_time_check if args.night_time_check is not None else args.time_check,
        night_time_profit_recheck_minutes=args.night_recheck,
        night_time_profit_close=not args.disable_night_time_profit,
        use_break_even_stop=not args.disable_break_even,
        break_even_start_points=args.break_even_start,
        break_even_lock_points=args.break_even_lock,
        use_profit_giveback_close=not args.disable_giveback_close,
        giveback_start_points=args.giveback_start,
        giveback_close_points=args.giveback_points,
        giveback_close_percent=args.giveback_percent,
    )
    config = TickBacktestConfig(
        data_path=Path(args.data),
        params=params,
        point_size=args.point_size,
        excluded_dates=[value.strip() for value in args.exclude_dates.split(",") if value.strip()],
        time_profit_mode=args.time_profit_mode,
    )
    result = run_tick_backtest(config)
    metrics = calculate_metrics(result.trades, min_trades=0)
    summary = {
        "objective": "tick_validation",
        "lookback_days": 0,
        "bars_used": result.bar_count,
        "from": result.first_tick.isoformat(sep=" ") if result.first_tick else "",
        "to": result.last_tick.isoformat(sep=" ") if result.last_tick else "",
        "data_state": {
            "source": str(config.data_path),
            "tick_count": result.tick_count,
            "bar_count": result.bar_count,
        },
        "excluded_dates": config.excluded_dates,
        "best": {
            "ema_fast": params.ema_fast,
            "ema_slow": params.ema_slow,
            "time_check_minutes": params.time_check_for_session("DAY"),
            "stop_loss_points": params.stop_loss_for_session("DAY"),
            "day_time_check_minutes": params.time_check_for_session("DAY"),
            "day_time_profit_recheck_minutes": params.time_recheck_for_session("DAY"),
            "day_stop_loss_points": params.stop_loss_for_session("DAY"),
            "day_use_stop_loss": params.day_use_stop_loss,
            "day_time_profit_close": params.day_time_profit_close,
            "night_time_check_minutes": params.time_check_for_session("NIGHT"),
            "night_time_profit_recheck_minutes": params.time_recheck_for_session("NIGHT"),
            "night_stop_loss_points": params.stop_loss_for_session("NIGHT"),
            "night_use_stop_loss": params.night_use_stop_loss,
            "night_time_profit_close": params.night_time_profit_close,
            "use_break_even_stop": params.use_break_even_stop,
            "break_even_start_points": params.break_even_start_points,
            "break_even_lock_points": params.break_even_lock_points,
            "use_profit_giveback_close": params.use_profit_giveback_close,
            "giveback_start_points": params.giveback_start_points,
            "giveback_close_points": params.giveback_close_points,
            "giveback_close_percent": params.giveback_close_percent,
            "cooldown_minutes": params.cooldown_minutes,
            **metrics,
        },
        "top": [
            {
                "ema_fast": params.ema_fast,
                "ema_slow": params.ema_slow,
                "time_check_minutes": params.time_check_for_session("DAY"),
                "stop_loss_points": params.stop_loss_for_session("DAY"),
                "day_time_check_minutes": params.time_check_for_session("DAY"),
                "day_time_profit_recheck_minutes": params.time_recheck_for_session("DAY"),
                "day_stop_loss_points": params.stop_loss_for_session("DAY"),
                "day_use_stop_loss": params.day_use_stop_loss,
                "day_time_profit_close": params.day_time_profit_close,
                "night_time_check_minutes": params.time_check_for_session("NIGHT"),
                "night_time_profit_recheck_minutes": params.time_recheck_for_session("NIGHT"),
                "night_stop_loss_points": params.stop_loss_for_session("NIGHT"),
                "night_use_stop_loss": params.night_use_stop_loss,
                "night_time_profit_close": params.night_time_profit_close,
                "use_break_even_stop": params.use_break_even_stop,
                "break_even_start_points": params.break_even_start_points,
                "break_even_lock_points": params.break_even_lock_points,
                "use_profit_giveback_close": params.use_profit_giveback_close,
                "giveback_start_points": params.giveback_start_points,
                "giveback_close_points": params.giveback_close_points,
                "giveback_close_percent": params.giveback_close_percent,
                "cooldown_minutes": params.cooldown_minutes,
                **metrics,
            }
        ],
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_html_report(report_path, summary, result.trades)

    print("Tick backtest complete.")
    print(f"Ticks used: {result.tick_count}")
    print(f"M5 bars built for EMA: {result.bar_count}")
    print(f"Window: {summary['from']} to {summary['to']}")
    print(
        f"Trades={metrics['trade_count']}, net_points={metrics['net_points']:.2f}, "
        f"max_drawdown={metrics['max_drawdown_points']:.2f}, profit_factor={metrics['profit_factor']:.4f}"
    )
    print(f"Open visual report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
