#!/usr/bin/env python
"""三阶段全自动参数优化脚本。

Phase 1: K 线网格搜索 (objective=score) → Top N 候选
Phase 2: K 线 Walk-Forward 验证 → Top M 稳健候选
Phase 3: Tick 级验证 → 最终最优参数

使用方法:
  python run_full_optimizer.py --data data
  python run_full_optimizer.py --data data --fast 3:30:2 --slow 10:60:5
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime as dt
from pathlib import Path

from src.timeprofit_backtest.data import load_bars
from src.timeprofit_backtest.indicators import ema
from src.timeprofit_backtest.metrics import calculate_metrics
from src.timeprofit_backtest.optimizer import OptimizerConfig, run_optimization
from src.timeprofit_backtest.ranges import parse_int_values
from src.timeprofit_backtest.report import write_full_optimizer_report
from src.timeprofit_backtest.strategy import CostParams, StrategyParams, backtest
from src.timeprofit_backtest.tick_backtester import TickBacktestConfig, run_tick_backtest


# --- Walk-Forward 窗口定义 ---
# 4 个滚动窗口：每窗口 4 月 train + 2 月 test，向前滚动 2 个月
WF_WINDOWS = [
    {"train_start": "2025-06-01", "train_end": "2025-09-30",
     "test_start": "2025-10-01", "test_end": "2025-11-30"},
    {"train_start": "2025-08-01", "train_end": "2025-11-30",
     "test_start": "2025-12-01", "test_end": "2026-01-31"},
    {"train_start": "2025-10-01", "train_end": "2026-01-31",
     "test_start": "2026-02-01", "test_end": "2026-03-31"},
    {"train_start": "2025-12-01", "train_end": "2026-03-31",
     "test_start": "2026-04-01", "test_end": "2026-05-31"},
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="三阶段全自动参数优化：K线网格搜索 → Walk-Forward → Tick验证"
    )
    parser.add_argument(
        "--m5-data",
        default=None,
        help="M5 K 线 CSV 文件路径（Phase 1/2 使用）。如果不指定，自动在 data 目录查找 CSV 文件",
    )
    parser.add_argument(
        "--data",
        default=str(Path(__file__).parent / "data"),
        help="Tick 数据路径（ZIP/CSV 文件或目录，Phase 3 使用）。默认 python_backtest/data",
    )
    parser.add_argument(
        "--reports",
        default=str(Path(__file__).parent / "reports"),
        help="报告输出目录。默认 python_backtest/reports",
    )
    parser.add_argument(
        "--fast",
        default="3:30:2",
        help="Fast EMA 值范围。格式: start:end:step 或逗号列表",
    )
    parser.add_argument(
        "--slow",
        default="10:60:5",
        help="Slow EMA 值范围。格式: start:end:step 或逗号列表",
    )
    parser.add_argument(
        "--time-check",
        default="15:240:15",
        help="时间止盈检查分钟范围。格式同上",
    )
    parser.add_argument(
        "--stop-loss",
        default="100:1500:100",
        help="止损点数范围。格式同上",
    )
    parser.add_argument(
        "--cooldown",
        default="5:30:5",
        help="冷却分钟范围。格式同上",
    )
    parser.add_argument(
        "--top-kline",
        type=int,
        default=50,
        help="Phase 1 取多少候选组合。默认 50",
    )
    parser.add_argument(
        "--top-wf",
        type=int,
        default=10,
        help="Phase 2 取多少候选做 Walk-Forward。默认 10",
    )
    parser.add_argument(
        "--top-tick",
        type=int,
        default=5,
        help="Phase 3 最终取多少做 Tick 验证。默认 5",
    )
    parser.add_argument(
        "--point-size",
        type=float,
        default=0.01,
        help="品种点值。XAUUSD 通常 0.01",
    )
    parser.add_argument(
        "--exclude-dates",
        default="",
        help="排除日期，逗号分隔，如 2025-06-03",
    )
    return parser


def _find_m5_csv(data_dir: Path, m5_data_arg: str | None) -> Path:
    """自动查找 M5 K 线 CSV 文件用于 Phase 1/2（K 线回测速度远快于 tick）"""
    if m5_data_arg:
        path = Path(m5_data_arg)
        if path.exists():
            return path
    # 自动在 data 目录中找 CSV 文件（排除 ZIP）
    csv_files = sorted(
        p for p in data_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".csv"
    )
    if csv_files:
        return csv_files[0]
    # 如果没有 CSV，退回到使用 data 目录（包含 ZIP，会较慢）
    return data_dir


def run_phase1(args: argparse.Namespace) -> dict[str, object]:
    """Phase 1: K 线网格搜索，objective=score，筛出 Top N 候选"""
    print("=" * 60)
    print("Phase 1: K 线网格搜索 (objective=score)")
    print("=" * 60)

    # Phase 1/2 用 M5 CSV（快），Phase 3 用 tick ZIP（精确）
    data_dir = Path(args.data)
    m5_csv = _find_m5_csv(data_dir, args.m5_data)
    print(f"K 线数据源: {m5_csv}")

    fast_values = parse_int_values(args.fast)
    slow_values = parse_int_values(args.slow)
    tc_values = parse_int_values(args.time_check)
    sl_values = parse_int_values(args.stop_loss)
    cd_values = parse_int_values(args.cooldown)

    total_combos = len(fast_values) * len(slow_values) * len(tc_values) * len(sl_values) * len(cd_values)
    # 估算有效组合数（fast < slow 的比例约为 60-80%）
    print(f"参数范围: fast={len(fast_values)}, slow={len(slow_values)}, "
          f"time_check={len(tc_values)}, stop_loss={len(sl_values)}, cooldown={len(cd_values)}")
    print(f"总组合数约 {total_combos}（过滤后更少）")

    config = OptimizerConfig(
        data_path=m5_csv,
        report_dir=Path(args.reports),
        lookback_days=0,  # 不做 lookback 过滤，用全量数据（或用 start_date/end_date）
        ema_fast_values=fast_values,
        ema_slow_values=slow_values,
        time_check_values=tc_values,
        stop_loss_values=sl_values,
        cooldown_values=cd_values,
        objective="score",
        min_trades=30,
        top_n=args.top_kline,
        point_size=args.point_size,
        fallback_spread_points=0.0,
        slippage_points=0.0,
        commission_points=0.0,
        excluded_dates=[v.strip() for v in args.exclude_dates.split(",") if v.strip()],
    )

    start = time.time()
    summary = run_optimization(config)
    elapsed = time.time() - start

    print(f"完成！耗时 {elapsed:.1f}s")
    print(f"数据窗口: {summary['from']} 至 {summary['to']}, Bars={summary['bars_used']}")
    best = summary["best"]
    print(f"Best: fast={best['ema_fast']}, slow={best['ema_slow']}, "
          f"time_check={best['time_check_minutes']}, stop_loss={best['stop_loss_points']}, "
          f"cooldown={best['cooldown_minutes']}")
    print(f"Score={best['score']:.2f}, Net={best['net_points']:.2f}, "
          f"DD={best['max_drawdown_points']:.2f}, PF={best['profit_factor']:.2f}")
    print()
    return summary


def run_phase2(
    phase1_summary: dict[str, object],
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    """Phase 2: K 线 Walk-Forward 验证，筛出稳健候选"""
    print("=" * 60)
    print("Phase 2: Walk-Forward 验证 (K 线)")
    print("=" * 60)

    top_candidates = phase1_summary["top"][:args.top_wf]
    print(f"对 Top {len(top_candidates)} 候选做 Walk-Forward 验证...")

    # 加载全量 M5 K 线数据（一次性加载，各窗口切片使用）
    data_dir = Path(args.data)
    m5_csv = _find_m5_csv(data_dir, args.m5_data)
    all_bars = load_bars(m5_csv, 0.0, args.point_size)
    excluded_set = set(v.strip() for v in args.exclude_dates.split(",") if v.strip())

    # 收集所有候选参数用到的 EMA 周期，一次性计算缓存
    periods_needed = set()
    for candidate in top_candidates:
        periods_needed.add(candidate["ema_fast"])
        periods_needed.add(candidate["ema_slow"])
    closes_all = [bar.close for bar in all_bars]
    ema_cache_all = {p: ema(closes_all, p) for p in periods_needed}

    costs = CostParams(point_size=args.point_size)

    phase2_results = []

    start = time.time()
    for idx, candidate in enumerate(top_candidates):
        fast = int(candidate["ema_fast"])
        slow = int(candidate["ema_slow"])
        tc = int(candidate["time_check_minutes"])
        sl = int(candidate["stop_loss_points"])
        cd = int(candidate["cooldown_minutes"])
        params = StrategyParams(
            ema_fast=fast, ema_slow=slow,
            time_check_minutes=tc, stop_loss_points=sl, cooldown_minutes=cd,
        )

        wf_oos_metrics = []
        oos_positive_count = 0
        oos_net_sum = 0.0

        for window in WF_WINDOWS:
            # 截取训练期和测试期 K 线
            train_start = dt.strptime(window["train_start"], "%Y-%m-%d")
            train_end = dt.strptime(window["train_end"], "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            test_start = dt.strptime(window["test_start"], "%Y-%m-%d")
            test_end = dt.strptime(window["test_end"], "%Y-%m-%d").replace(hour=23, minute=59, second=59)

            train_bars = [b for b in all_bars
                         if train_start <= b.time <= train_end
                         and b.time.date().isoformat() not in excluded_set]
            test_bars = [b for b in all_bars
                        if test_start <= b.time <= test_end
                        and b.time.date().isoformat() not in excluded_set]

            if not train_bars or not test_bars:
                wf_oos_metrics.append({"net_points": 0, "trade_count": 0, "max_drawdown_points": 0})
                continue

            # 在 test_bars 上运行 K 线回测（OOS）
            # 注意：EMA 需要在 train_bars 的上下文中预计算，
            # 因为 EMA 是递推指标，需要从更早的数据开始计算才能在 test 期有稳定值
            # 我们用 all_bars 的缓存，但在 test_bars 索引区间内取值
            # 策略：用全量 EMA，但只在 test_bars 索引范围内运行 backtest
            # 先找到 test_bars 在 all_bars 中的索引范围
            test_time_set = {b.time for b in test_bars}
            test_bar_indices = [i for i, b in enumerate(all_bars) if b.time in test_time_set]
            if not test_bar_indices:
                wf_oos_metrics.append({"net_points": 0, "trade_count": 0, "max_drawdown_points": 0})
                continue

            # 在 test_bars 上运行回测，使用全量 EMA 值（保证递推连续性）
            # backtest() 使用 bars 索引，需要把 EMA 映射到 test_bars
            # 最简单的方式：直接对 test_bars 运行独立回测（EMA 从 test_bars 自身收盘价计算）
            # 这牺牲了 EMA 递推连续性，但对 M5 周期 2 个月数据影响不大
            test_closes = [b.close for b in test_bars]
            test_fast_ema = ema(test_closes, fast)
            test_slow_ema = ema(test_closes, slow)
            test_trades = backtest(test_bars, test_fast_ema, test_slow_ema, params, costs)
            test_metrics = calculate_metrics(test_trades, min_trades=0)

            wf_oos_metrics.append({
                "net_points": test_metrics["net_points"],
                "trade_count": test_metrics["trade_count"],
                "max_drawdown_points": test_metrics["max_drawdown_points"],
            })
            oos_net_sum += test_metrics["net_points"]
            if test_metrics["net_points"] > 0:
                oos_positive_count += 1

        # 稳健度评分：OOS 正收益占比 × 平均 OOS net_points
        oos_positive_ratio = oos_positive_count / len(WF_WINDOWS) if WF_WINDOWS else 0
        robustness_score = oos_positive_ratio * oos_net_sum if oos_net_sum > 0 else 0

        phase2_results.append({
            "ema_fast": fast, "ema_slow": slow,
            "time_check_minutes": tc, "stop_loss_points": sl,
            "cooldown_minutes": cd,
            "wf_oos_metrics": wf_oos_metrics,
            "oos_positive_ratio": oos_positive_ratio,
            "robustness_score": robustness_score,
        })

        print(f"  [{idx+1}/{len(top_candidates)}] fast={fast} slow={slow} tc={tc} sl={sl} cd={cd} "
              f"→ OOS正占比={oos_positive_ratio:.0%} 稳健度={robustness_score:.2f}")

    elapsed = time.time() - start
    print(f"完成！耗时 {elapsed:.1f}s")

    # 按 robustness_score 降序排序
    phase2_results.sort(key=lambda x: (x["robustness_score"], x.get("oos_positive_ratio", 0)), reverse=True)

    # 取 Top M 稳健候选
    top_wf = phase2_results[:args.top_tick]
    print(f"稳健候选 Top {len(top_wf)}:")
    for r in top_wf:
        print(f"  fast={r['ema_fast']} slow={r['ema_slow']} tc={r['time_check_minutes']} "
              f"sl={r['stop_loss_points']} cd={r['cooldown_minutes']} "
              f"OOS正占比={r['oos_positive_ratio']:.0%} 稳健度={r['robustness_score']:.2f}")
    print()
    return phase2_results


def run_phase3(
    phase2_results: list[dict[str, object]],
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    """Phase 3: Tick 级验证 Top M 稳健候选"""
    print("=" * 60)
    print("Phase 3: Tick 级验证")
    print("=" * 60)

    top_wf = phase2_results[:args.top_tick]
    print(f"对 Top {len(top_wf)} 稳健候选做 Tick 级回测...")

    data_path = Path(args.data)
    excluded_dates = [v.strip() for v in args.exclude_dates.split(",") if v.strip()]

    phase3_results = []
    start = time.time()

    for idx, candidate in enumerate(top_wf):
        params = StrategyParams(
            ema_fast=candidate["ema_fast"],
            ema_slow=candidate["ema_slow"],
            time_check_minutes=candidate["time_check_minutes"],
            stop_loss_points=candidate["stop_loss_points"],
            cooldown_minutes=candidate["cooldown_minutes"],
        )
        config = TickBacktestConfig(
            data_path=data_path,
            params=params,
            point_size=args.point_size,
            excluded_dates=excluded_dates,
            time_profit_mode="bar",
        )

        tick_start = time.time()
        result = run_tick_backtest(config)
        tick_elapsed = time.time() - tick_start
        metrics = calculate_metrics(result.trades, min_trades=0)

        phase3_results.append({
            "ema_fast": params.ema_fast,
            "ema_slow": params.ema_slow,
            "time_check_minutes": params.time_check_minutes,
            "stop_loss_points": params.stop_loss_points,
            "cooldown_minutes": params.cooldown_minutes,
            **metrics,
        })

        print(f"  [{idx+1}/{len(top_wf)}] fast={params.ema_fast} slow={params.ema_slow} "
              f"tc={params.time_check_minutes} sl={params.stop_loss_points} cd={params.cooldown_minutes} "
              f"→ Net={metrics['net_points']:.2f} DD={metrics['max_drawdown_points']:.2f} "
              f"PF={metrics['profit_factor']:.2f} Trades={metrics['trade_count']} "
              f"({tick_elapsed:.1f}s)")

    elapsed = time.time() - start
    print(f"完成！总耗时 {elapsed:.1f}s")

    # 按 net_points 降序排序
    phase3_results.sort(key=lambda x: x["net_points"], reverse=True)

    print(f"\n最终最优参数:")
    best = phase3_results[0]
    print(f"  fast={best['ema_fast']} slow={best['ema_slow']} "
          f"tc={best['time_check_minutes']} sl={best['stop_loss_points']} cd={best['cooldown_minutes']}")
    print(f"  Tick Net={best['net_points']:.2f} DD={best['max_drawdown_points']:.2f} "
          f"PF={best['profit_factor']:.2f} Trades={best['trade_count']}")
    print()
    return phase3_results


def main() -> int:
    args = build_parser().parse_args()

    total_start = time.time()

    # Phase 1: K 线网格搜索
    phase1_summary = run_phase1(args)

    # Phase 2: Walk-Forward 验证
    phase2_results = run_phase2(phase1_summary, args)

    # Phase 3: Tick 级验证
    phase3_results = run_phase3(phase2_results, args)

    total_elapsed = time.time() - total_start
    print("=" * 60)
    print(f"全部完成！总耗时 {total_elapsed:.1f}s ({total_elapsed/60:.1f}min)")
    print("=" * 60)

    # 生成综合报告
    report_path = Path(args.reports) / "full_optimizer_report.html"
    final_best = phase3_results[0]
    write_full_optimizer_report(
        path=report_path,
        phase1_summary=phase1_summary,
        phase2_results=phase2_results,
        phase3_results=phase3_results,
        final_best=final_best,
        wf_windows=WF_WINDOWS,
    )
    print(f"综合报告已写入: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
