#!/usr/bin/env python
"""Compare the custom TimeProfit backtester with a Backtrader implementation."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import backtrader as bt

from timeprofit_backtest.data import filter_recent_days, load_bars
from timeprofit_backtest.indicators import ema
from timeprofit_backtest.metrics import Trade, calculate_metrics
from timeprofit_backtest.strategy import CostParams, StrategyParams, backtest


class XauM5Csv(bt.feeds.GenericCSVData):
    lines = ("spread",)
    params = (
        ("dtformat", "%Y-%m-%d %H:%M:%S%z"),
        ("datetime", 0),
        ("open", 1),
        ("high", 2),
        ("low", 3),
        ("close", 4),
        ("volume", 5),
        ("spread", 6),
        ("openinterest", -1),
        ("timeframe", bt.TimeFrame.Minutes),
        ("compression", 5),
        ("headers", True),
        ("separator", ","),
    )


class TimeProfitBtStrategy(bt.Strategy):
    params = (
        ("ema_fast", 15),
        ("ema_slow", 44),
        ("time_check_minutes", 105),
        ("stop_loss_points", 200),
        ("cooldown_minutes", 10),
        ("point_size", 0.01),
    )

    def __init__(self) -> None:
        self.ema_fast = bt.ind.EMA(self.data.close, period=self.p.ema_fast)
        self.ema_slow = bt.ind.EMA(self.data.close, period=self.p.ema_slow)
        self.position_state: dict[str, object] | None = None
        self.last_close_dt = None
        self.trades: list[Trade] = []

    def next(self) -> None:
        dt = self.data.datetime.datetime(0)

        if self.position_state is not None:
            closed = self._try_close(dt)
            if closed:
                return

        if self.position_state is not None:
            return

        if self.last_close_dt is not None:
            elapsed_minutes = (dt - self.last_close_dt).total_seconds() / 60.0
            if elapsed_minutes < self.p.cooldown_minutes:
                return

        if len(self.data) < max(self.p.ema_fast, self.p.ema_slow) + 1:
            return

        fast_prev = float(self.ema_fast[-1])
        slow_prev = float(self.ema_slow[-1])
        if fast_prev > slow_prev:
            self._open("BUY", dt)
        elif fast_prev < slow_prev:
            self._open("SELL", dt)

    def stop(self) -> None:
        if self.position_state is None:
            return
        dt = self.data.datetime.datetime(0)
        close_price = float(self.data.close[0])
        self._close(dt, close_price, "end_of_data")

    def _spread_points(self) -> float:
        raw_spread = float(self.data.spread[0])
        if 0 < raw_spread < 10:
            return raw_spread / self.p.point_size
        return raw_spread

    def _open(self, side: str, dt) -> None:
        spread_points = self._spread_points()
        half_spread = (spread_points * self.p.point_size) / 2.0
        open_price = float(self.data.open[0])
        if side == "BUY":
            entry_price = open_price + half_spread
            stop_price = entry_price - self.p.stop_loss_points * self.p.point_size
        else:
            entry_price = open_price - half_spread
            stop_price = entry_price + self.p.stop_loss_points * self.p.point_size
        self.position_state = {
            "side": side,
            "entry_dt": dt,
            "entry_bar": len(self.data) - 1,
            "entry_price": entry_price,
            "stop_price": stop_price,
        }

    def _try_close(self, dt) -> bool:
        assert self.position_state is not None
        side = str(self.position_state["side"])
        stop_price = float(self.position_state["stop_price"])
        if side == "BUY" and float(self.data.low[0]) <= stop_price:
            self._close(dt, stop_price, "stop_loss")
            return True
        if side == "SELL" and float(self.data.high[0]) >= stop_price:
            self._close(dt, stop_price, "stop_loss")
            return True

        elapsed_minutes = (dt - self.position_state["entry_dt"]).total_seconds() / 60.0
        if elapsed_minutes >= self.p.time_check_minutes:
            close_price = self._tradable_close_price(side)
            pnl = self._pnl_points(side, float(self.position_state["entry_price"]), close_price)
            if pnl > 0:
                self._close(dt, close_price, "time_profit")
                return True
        return False

    def _tradable_close_price(self, side: str) -> float:
        spread_points = self._spread_points()
        half_spread = (spread_points * self.p.point_size) / 2.0
        close_price = float(self.data.close[0])
        if side == "BUY":
            return close_price - half_spread
        return close_price + half_spread

    def _close(self, dt, close_price: float, reason: str) -> None:
        assert self.position_state is not None
        side = str(self.position_state["side"])
        entry_price = float(self.position_state["entry_price"])
        pnl = self._pnl_points(side, entry_price, close_price)
        self.trades.append(
            Trade(
                side=side,
                entry_time=self.position_state["entry_dt"].isoformat(sep=" "),
                exit_time=dt.isoformat(sep=" "),
                entry_price=entry_price,
                exit_price=close_price,
                pnl_points=pnl,
                exit_reason=reason,
                bars_held=(len(self.data) - 1) - int(self.position_state["entry_bar"]),
            )
        )
        self.position_state = None
        self.last_close_dt = dt

    def _pnl_points(self, side: str, entry_price: float, close_price: float) -> float:
        if side == "BUY":
            return (close_price - entry_price) / self.p.point_size
        return (entry_price - close_price) / self.p.point_size


def run_backtrader(data_path: Path, params: StrategyParams, point_size: float) -> list[Trade]:
    cerebro = bt.Cerebro(stdstats=False, exactbars=False, runonce=False)
    data = XauM5Csv(dataname=str(data_path))
    cerebro.adddata(data)
    cerebro.addstrategy(
        TimeProfitBtStrategy,
        ema_fast=params.ema_fast,
        ema_slow=params.ema_slow,
        time_check_minutes=params.time_check_minutes,
        stop_loss_points=params.stop_loss_points,
        cooldown_minutes=params.cooldown_minutes,
        point_size=point_size,
    )
    strategies = cerebro.run()
    return strategies[0].trades


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare custom backtest results with Backtrader.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--fast", type=int, default=15)
    parser.add_argument("--slow", type=int, default=44)
    parser.add_argument("--time-check", type=int, default=105)
    parser.add_argument("--stop-loss", type=int, default=200)
    parser.add_argument("--cooldown", type=int, default=10)
    parser.add_argument("--point-size", type=float, default=0.01)
    parser.add_argument("--show", type=int, default=5)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    data_path = Path(args.data)
    params = StrategyParams(
        ema_fast=args.fast,
        ema_slow=args.slow,
        time_check_minutes=args.time_check,
        stop_loss_points=args.stop_loss,
        cooldown_minutes=args.cooldown,
    )
    bars = filter_recent_days(load_bars(data_path, point_size=args.point_size), args.days)
    closes = [bar.close for bar in bars]
    custom_trades = backtest(
        bars,
        ema(closes, params.ema_fast),
        ema(closes, params.ema_slow),
        params,
        CostParams(point_size=args.point_size),
    )
    bt_trades = run_backtrader(data_path, params, args.point_size)

    custom_metrics = calculate_metrics(custom_trades, min_trades=0)
    bt_metrics = calculate_metrics(bt_trades, min_trades=0)
    print(f"params={asdict(params)}")
    print(f"bars={len(bars)} from={bars[0].time} to={bars[-1].time}")
    _print_metrics("custom", custom_metrics)
    _print_metrics("backtrader", bt_metrics)
    print(f"trade_count_diff={len(bt_trades) - len(custom_trades)}")
    print(f"net_points_diff={bt_metrics['net_points'] - custom_metrics['net_points']:.6f}")
    print(f"max_drawdown_diff={bt_metrics['max_drawdown_points'] - custom_metrics['max_drawdown_points']:.6f}")
    _print_trade_compare("first", custom_trades[: args.show], bt_trades[: args.show])
    _print_trade_compare("last", custom_trades[-args.show :], bt_trades[-args.show :])
    return 0


def _print_metrics(label: str, metrics: dict[str, float | int]) -> None:
    print(
        f"{label}: trades={metrics['trade_count']} "
        f"net={metrics['net_points']:.6f} "
        f"dd={metrics['max_drawdown_points']:.6f} "
        f"pf={metrics['profit_factor']:.6f} "
        f"win_rate={metrics['win_rate']:.6f}"
    )


def _print_trade_compare(label: str, custom: list[Trade], bt_trades: list[Trade]) -> None:
    print(f"{label}_trades:")
    for index, (left, right) in enumerate(zip(custom, bt_trades), 1):
        print(
            f"  {index}: custom=({left.side},{left.entry_time},{left.exit_time},{left.pnl_points:.2f},{left.exit_reason},{left.bars_held}) "
            f"backtrader=({right.side},{right.entry_time},{right.exit_time},{right.pnl_points:.2f},{right.exit_reason},{right.bars_held})"
        )


if __name__ == "__main__":
    raise SystemExit(main())
