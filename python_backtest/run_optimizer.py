#!/usr/bin/env python
"""CLI entry point for TimeProfitEA historical optimization."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.timeprofit_backtest.optimizer import OptimizerConfig, run_optimization
from src.timeprofit_backtest.ranges import parse_int_values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optimize TimeProfitEA parameters on XAUUSD M5 historical CSV data."
    )
    parser.add_argument(
        "--data",
        default=str(Path(__file__).parent / "data"),
        help="CSV file or directory containing CSV files. Defaults to python_backtest/data.",
    )
    parser.add_argument(
        "--reports",
        default=str(Path(__file__).parent / "reports"),
        help="Directory where optimization reports are written.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Use only the most recent N days of data. Default: 365.",
    )
    parser.add_argument(
        "--fast",
        default="5,8,10,12",
        help="Fast EMA values. Supports comma list or start:end:step, e.g. 3:21:2.",
    )
    parser.add_argument(
        "--slow",
        default="10,15,20,30,50",
        help="Slow EMA values. Supports comma list or start:end:step.",
    )
    parser.add_argument(
        "--time-check",
        default="15,30,60,120",
        help="Time-profit check minutes. Supports comma list or start:end:step.",
    )
    parser.add_argument(
        "--day-time-check",
        default=None,
        help="Day-session time-profit check minutes. Defaults to --time-check.",
    )
    parser.add_argument(
        "--night-time-check",
        default=None,
        help="Night-session time-profit check minutes. Defaults to --time-check.",
    )
    parser.add_argument(
        "--day-recheck",
        default=None,
        help="Day-session time-profit recheck minutes. Defaults to 5.",
    )
    parser.add_argument(
        "--night-recheck",
        default=None,
        help="Night-session time-profit recheck minutes. Defaults to 5.",
    )
    parser.add_argument(
        "--stop-loss",
        default="300,500,800,1200",
        help="Stop-loss points. Supports comma list or start:end:step.",
    )
    parser.add_argument(
        "--day-stop-loss",
        default=None,
        help="Day-session stop-loss points. Defaults to --stop-loss.",
    )
    parser.add_argument(
        "--night-stop-loss",
        default=None,
        help="Night-session stop-loss points. Defaults to --stop-loss.",
    )
    parser.add_argument(
        "--cooldown",
        default="15",
        help="Cooldown minutes after close. Supports comma list or start:end:step.",
    )
    parser.add_argument(
        "--objective",
        choices=("score", "net_points"),
        default="score",
        help="Optimization objective. score balances profit and drawdown; net_points maximizes raw profit.",
    )
    parser.add_argument(
        "--min-trades",
        type=int,
        default=30,
        help="Minimum trades before a parameter set avoids the low-trade penalty.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top rows to write to best_params.json.",
    )
    parser.add_argument(
        "--point-size",
        type=float,
        default=0.01,
        help="Symbol point size. XAUUSD commonly uses 0.01.",
    )
    parser.add_argument(
        "--spread-points",
        type=float,
        default=0.0,
        help="Fallback spread in points when CSV does not provide a spread column.",
    )
    parser.add_argument(
        "--slippage-points",
        type=float,
        default=0.0,
        help="Slippage cost in points per side.",
    )
    parser.add_argument(
        "--commission-points",
        type=float,
        default=0.0,
        help="Round-turn commission normalized to points per trade.",
    )
    parser.add_argument(
        "--exclude-dates",
        default="",
        help="Comma-separated dates to exclude from the backtest window, e.g. 2025-06-03,2026-01-01.",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Start date for data window (YYYY-MM-DD). When specified, overrides --days filtering.",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="End date for data window (YYYY-MM-DD). When specified, overrides --days filtering.",
    )
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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = OptimizerConfig(
        data_path=Path(args.data),
        report_dir=Path(args.reports),
        lookback_days=args.days,
        ema_fast_values=parse_int_values(args.fast),
        ema_slow_values=parse_int_values(args.slow),
        time_check_values=parse_int_values(args.time_check),
        stop_loss_values=parse_int_values(args.stop_loss),
        cooldown_values=parse_int_values(args.cooldown),
        objective=args.objective,
        min_trades=args.min_trades,
        top_n=args.top,
        point_size=args.point_size,
        fallback_spread_points=args.spread_points,
        slippage_points=args.slippage_points,
        commission_points=args.commission_points,
        excluded_dates=[value.strip() for value in args.exclude_dates.split(",") if value.strip()],
        start_date=args.start_date,
        end_date=args.end_date,
        day_time_check_values=parse_int_values(args.day_time_check) if args.day_time_check else None,
        night_time_check_values=parse_int_values(args.night_time_check) if args.night_time_check else None,
        day_time_recheck_values=parse_int_values(args.day_recheck) if args.day_recheck else None,
        night_time_recheck_values=parse_int_values(args.night_recheck) if args.night_recheck else None,
        day_stop_loss_values=parse_int_values(args.day_stop_loss) if args.day_stop_loss else None,
        night_stop_loss_values=parse_int_values(args.night_stop_loss) if args.night_stop_loss else None,
        day_use_stop_loss=not args.disable_day_stop_loss,
        night_use_stop_loss=not args.disable_night_stop_loss,
        day_time_profit_close=not args.disable_day_time_profit,
        night_time_profit_close=not args.disable_night_time_profit,
        use_break_even_stop=not args.disable_break_even,
        break_even_start_points=args.break_even_start,
        break_even_lock_points=args.break_even_lock,
        use_profit_giveback_close=not args.disable_giveback_close,
        giveback_start_points=args.giveback_start,
        giveback_close_points=args.giveback_points,
        giveback_close_percent=args.giveback_percent,
    )
    summary = run_optimization(config)
    best = summary["best"]
    print("Optimization complete.")
    print(f"Bars used: {summary['bars_used']} from {summary['from']} to {summary['to']}")
    print(
        "Best params: "
        f"fast={best['ema_fast']}, slow={best['ema_slow']}, "
        f"day_time_check={best['day_time_check_minutes']}, "
        f"day_recheck={best['day_time_profit_recheck_minutes']}, "
        f"day_stop_loss={best['day_stop_loss_points']}, "
        f"night_time_check={best['night_time_check_minutes']}, "
        f"night_recheck={best['night_time_profit_recheck_minutes']}, "
        f"night_stop_loss={best['night_stop_loss_points']}, "
        f"cooldown={best['cooldown_minutes']}, "
        f"break_even={best['use_break_even_stop']}, "
        f"giveback={best['use_profit_giveback_close']}"
    )
    print(
        f"Objective={args.objective}, net_points={best['net_points']:.2f}, "
        f"max_drawdown={best['max_drawdown_points']:.2f}, trades={best['trade_count']}"
    )
    print(f"Reports written to: {config.report_dir}")
    print(f"Open visual report: {config.report_dir / 'report.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
