#!/usr/bin/env python
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from src.timeprofit_backtest.data import Bar, load_bars
from src.timeprofit_backtest.metrics import Trade, calculate_metrics


@dataclass(frozen=True)
class Params:
    mode: str
    donchian_entry: int
    donchian_exit: int
    ema_period: int
    atr_period: int
    atr_mult: float
    take_profit_mult: float
    min_deviation_atr: float
    rsi_period: int
    rsi_long_min: float
    rsi_short_max: float
    cooldown_bars: int


@dataclass
class Position:
    side: str
    entry_index: int
    entry_price: float
    stop_price: float
    take_profit: float
    highest: float
    lowest: float


def aggregate_bars(bars: list[Bar], minutes: int) -> list[Bar]:
    grouped: dict[object, Bar] = {}
    builders: dict[object, dict[str, float]] = {}
    for bar in bars:
        bucket = bar.time.replace(minute=bar.time.minute - bar.time.minute % minutes, second=0, microsecond=0)
        builder = builders.get(bucket)
        if builder is None:
            builders[bucket] = {
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "ticks": bar.tick_volume,
                "spread_sum": bar.spread_points,
                "spread_count": 1,
            }
        else:
            builder["high"] = max(builder["high"], bar.high)
            builder["low"] = min(builder["low"], bar.low)
            builder["close"] = bar.close
            builder["ticks"] += bar.tick_volume
            builder["spread_sum"] += bar.spread_points
            builder["spread_count"] += 1
    result: list[Bar] = []
    for bucket in sorted(builders):
        item = builders[bucket]
        result.append(
            Bar(
                time=bucket,
                open=item["open"],
                high=item["high"],
                low=item["low"],
                close=item["close"],
                tick_volume=item["ticks"],
                spread_points=item["spread_sum"] / item["spread_count"],
            )
        )
    return result


def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    avg = sum(values[:period]) / period
    out[period - 1] = avg
    alpha = 2.0 / (period + 1)
    prev = avg
    for i in range(period, len(values)):
        prev = values[i] * alpha + prev * (1.0 - alpha)
        out[i] = prev
    return out


def atr(bars: list[Bar], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(bars)
    trs: list[float] = []
    for i, bar in enumerate(bars):
        if i == 0:
            tr = bar.high - bar.low
        else:
            prev_close = bars[i - 1].close
            tr = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
        trs.append(tr)
    if len(trs) < period:
        return out
    value = sum(trs[:period]) / period
    out[period - 1] = value
    for i in range(period, len(trs)):
        value = (value * (period - 1) + trs[i]) / period
        out[i] = value
    return out


def rsi(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = []
    losses = []
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def backtest(bars: list[Bar], params: Params, point_size: float) -> list[Trade]:
    closes = [bar.close for bar in bars]
    ema_values = ema(closes, params.ema_period)
    atr_values = atr(bars, params.atr_period)
    rsi_values = rsi(closes, params.rsi_period)
    trades: list[Trade] = []
    position: Position | None = None
    cooldown_until = -1

    warmup = max(params.donchian_entry, params.donchian_exit, params.ema_period, params.atr_period, params.rsi_period) + 2
    for i in range(warmup, len(bars)):
        bar = bars[i]
        prev = bars[i - 1]
        atr_prev = atr_values[i - 1]
        ema_prev = ema_values[i - 1]
        rsi_prev = rsi_values[i - 1]
        if atr_prev is None or ema_prev is None or rsi_prev is None:
            continue

        if position is not None:
            if position.side == "BUY":
                if bar.high >= position.take_profit:
                    trades.append(make_trade(position, bars, i, position.take_profit, "take_profit", point_size))
                    position = None
                    cooldown_until = i + params.cooldown_bars
                    continue
                position.highest = max(position.highest, bar.high)
                trail = position.highest - atr_prev * params.atr_mult
                if params.mode == "trend":
                    position.stop_price = max(position.stop_price, trail)
                exit_channel = min(item.low for item in bars[i - params.donchian_exit - 1 : i - 1])
                if bar.low <= position.stop_price:
                    trades.append(make_trade(position, bars, i, position.stop_price, "stop_loss", point_size))
                    position = None
                    cooldown_until = i + params.cooldown_bars
                    continue
                if params.mode == "trend" and bar.close < exit_channel:
                    trades.append(make_trade(position, bars, i, bar.close, "donchian_exit", point_size))
                    position = None
                    cooldown_until = i + params.cooldown_bars
                    continue
            else:
                if bar.low <= position.take_profit:
                    trades.append(make_trade(position, bars, i, position.take_profit, "take_profit", point_size))
                    position = None
                    cooldown_until = i + params.cooldown_bars
                    continue
                position.lowest = min(position.lowest, bar.low)
                trail = position.lowest + atr_prev * params.atr_mult
                if params.mode == "trend":
                    position.stop_price = min(position.stop_price, trail)
                exit_channel = max(item.high for item in bars[i - params.donchian_exit - 1 : i - 1])
                if bar.high >= position.stop_price:
                    trades.append(make_trade(position, bars, i, position.stop_price, "stop_loss", point_size))
                    position = None
                    cooldown_until = i + params.cooldown_bars
                    continue
                if params.mode == "trend" and bar.close > exit_channel:
                    trades.append(make_trade(position, bars, i, bar.close, "donchian_exit", point_size))
                    position = None
                    cooldown_until = i + params.cooldown_bars
                    continue

        if position is not None or i < cooldown_until:
            continue

        entry_high = max(item.high for item in bars[i - params.donchian_entry - 1 : i - 1])
        entry_low = min(item.low for item in bars[i - params.donchian_entry - 1 : i - 1])
        deviation_atr = abs(prev.close - ema_prev) / atr_prev if atr_prev > 0 else 0.0
        if params.mode == "trend":
            if prev.close > entry_high and prev.close > ema_prev and rsi_prev >= params.rsi_long_min:
                entry = bar.open
                stop = entry - atr_prev * params.atr_mult
                target = entry + atr_prev * params.take_profit_mult
                position = Position("BUY", i, entry, stop, target, entry, entry)
            elif prev.close < entry_low and prev.close < ema_prev and rsi_prev <= params.rsi_short_max:
                entry = bar.open
                stop = entry + atr_prev * params.atr_mult
                target = entry - atr_prev * params.take_profit_mult
                position = Position("SELL", i, entry, stop, target, entry, entry)
        else:
            if prev.close < entry_low and prev.close < ema_prev and rsi_prev <= params.rsi_long_min and deviation_atr >= params.min_deviation_atr:
                entry = bar.open
                stop = entry - atr_prev * params.atr_mult
                target = entry + atr_prev * params.take_profit_mult
                position = Position("BUY", i, entry, stop, target, entry, entry)
            elif prev.close > entry_high and prev.close > ema_prev and rsi_prev >= params.rsi_short_max and deviation_atr >= params.min_deviation_atr:
                entry = bar.open
                stop = entry + atr_prev * params.atr_mult
                target = entry - atr_prev * params.take_profit_mult
                position = Position("SELL", i, entry, stop, target, entry, entry)

    if position is not None:
        trades.append(make_trade(position, bars, len(bars) - 1, bars[-1].close, "end_of_data", point_size))
    return trades


def make_trade(position: Position, bars: list[Bar], exit_index: int, exit_price: float, reason: str, point_size: float) -> Trade:
    if position.side == "BUY":
        pnl = (exit_price - position.entry_price) / point_size
    else:
        pnl = (position.entry_price - exit_price) / point_size
    return Trade(
        side=position.side,
        entry_time=bars[position.entry_index].time.isoformat(sep=" "),
        exit_time=bars[exit_index].time.isoformat(sep=" "),
        entry_price=position.entry_price,
        exit_price=exit_price,
        pnl_points=pnl,
        exit_reason=reason,
        bars_held=exit_index - position.entry_index,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=r"C:\tmp\histdata_xauusd_tick_zips")
    parser.add_argument("--point-size", type=float, default=0.01)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    print("Loading data...")
    m5 = load_bars(Path(args.data), point_size=args.point_size)
    bars = aggregate_bars(m5, 15)
    print(f"M15 bars: {len(bars)} from {bars[0].time} to {bars[-1].time}")

    rows: list[dict[str, object]] = []
    for mode in ("trend", "reversion"):
      for entry in (12, 20, 40, 60, 80, 100, 120):
        for exit_period in (8, 10, 20, 30, 40):
            if exit_period >= entry:
                continue
            for ema_period in (50, 100, 200, 300, 400):
                for atr_mult in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
                  for tp_mult in (0.8, 1.0, 1.2, 1.5, 2.0, 3.0):
                   for min_dev in (0.0, 0.5, 1.0, 1.5, 2.0):
                    for long_min, short_max in ((30, 70), (35, 65), (40, 60), (45, 55), (52, 48), (55, 50), (58, 45), (60, 40)):
                        params = Params(
                            mode=mode,
                            donchian_entry=entry,
                            donchian_exit=exit_period,
                            ema_period=ema_period,
                            atr_period=14,
                            atr_mult=atr_mult,
                            take_profit_mult=tp_mult,
                            min_deviation_atr=min_dev,
                            rsi_period=14,
                            rsi_long_min=long_min,
                            rsi_short_max=short_max,
                            cooldown_bars=1,
                        )
                        trades = backtest(bars, params, args.point_size)
                        metrics = calculate_metrics(trades, min_trades=20)
                        if metrics["trade_count"] < 15:
                            continue
                        score = float(metrics["net_points"]) - 1.2 * float(metrics["max_drawdown_points"])
                        rows.append({"params": params, "score": score, **metrics})

    rows.sort(key=lambda item: (float(item["score"]), float(item["net_points"])), reverse=True)
    for row in rows[: args.top]:
        params = row["params"]
        print(
            f"score={row['score']:.1f} net={row['net_points']:.1f} dd={row['max_drawdown_points']:.1f} "
            f"pf={row['profit_factor']:.2f} trades={row['trade_count']} wr={row['win_rate']:.1%} "
            f"mode={params.mode} entry={params.donchian_entry} exit={params.donchian_exit} ema={params.ema_period} "
            f"sl_atr={params.atr_mult} tp_atr={params.take_profit_mult} dev={params.min_deviation_atr} "
            f"rsi=({params.rsi_long_min},{params.rsi_short_max})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
