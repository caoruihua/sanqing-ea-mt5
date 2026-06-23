from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import chain
from pathlib import Path
from typing import Iterable, Iterator, Literal
from zipfile import BadZipFile, ZipFile

from .data import Bar
from .indicators import ema
from .metrics import Trade
from .strategy import Session, StrategyParams


TimeProfitMode = Literal["tick", "bar"]


@dataclass(frozen=True)
class Tick:
    time: datetime
    bid: float
    ask: float


@dataclass(frozen=True)
class TickBacktestConfig:
    data_path: Path
    params: StrategyParams
    point_size: float = 0.01
    excluded_dates: list[str] | None = None
    time_profit_mode: TimeProfitMode = "bar"
    start_date: str | None = None   # YYYY-MM-DD，Walk-Forward 验证时截取数据段起点
    end_date: str | None = None     # YYYY-MM-DD，Walk-Forward 验证时截取数据段终点


@dataclass(frozen=True)
class TickBacktestResult:
    trades: list[Trade]
    tick_count: int
    bar_count: int
    first_tick: datetime | None
    last_tick: datetime | None


@dataclass
class _BarBuilder:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    ticks: int = 0

    def update(self, price: float) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.ticks += 1

    def to_bar(self) -> Bar:
        return Bar(
            time=self.time,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            tick_volume=float(self.ticks),
            spread_points=0.0,
        )


@dataclass
class _Position:
    side: str
    entry_time: datetime
    entry_bar: datetime
    entry_price: float
    stop_price: float | None
    session: Session
    last_time_profit_check_time: datetime | None = None
    max_floating_profit_points: float = 0.0


def run_tick_backtest(config: TickBacktestConfig) -> TickBacktestResult:
    excluded_dates = set(config.excluded_dates or [])
    bars, tick_count, first_tick, last_tick = _build_m5_bars_from_ticks(config, excluded_dates)
    signal_by_bar = _build_signal_map(bars, config.params)
    trades = _execute_tick_strategy(config, excluded_dates, signal_by_bar)
    return TickBacktestResult(
        trades=trades,
        tick_count=tick_count,
        bar_count=len(bars),
        first_tick=first_tick,
        last_tick=last_tick,
    )


def _build_m5_bars_from_ticks(
    config: TickBacktestConfig,
    excluded_dates: set[str],
) -> tuple[list[Bar], int, datetime | None, datetime | None]:
    # 日期范围过滤：解析 start_date/end_date 为 date 对象
    start_date_obj = datetime.strptime(config.start_date, "%Y-%m-%d").date() if config.start_date else None
    end_date_obj = datetime.strptime(config.end_date, "%Y-%m-%d").date() if config.end_date else None

    builders: dict[datetime, _BarBuilder] = {}
    tick_count = 0
    first_tick: datetime | None = None
    last_tick: datetime | None = None

    for tick in iter_ticks(config.data_path):
        if tick.time.date().isoformat() in excluded_dates:
            continue
        if start_date_obj and tick.time.date() < start_date_obj:
            continue
        if end_date_obj and tick.time.date() > end_date_obj:
            continue
        tick_count += 1
        first_tick = first_tick or tick.time
        last_tick = tick.time
        bar_time = floor_m5(tick.time)
        price = (tick.bid + tick.ask) / 2.0
        builder = builders.get(bar_time)
        if builder is None:
            builders[bar_time] = _BarBuilder(
                time=bar_time,
                open=price,
                high=price,
                low=price,
                close=price,
                ticks=1,
            )
        else:
            builder.update(price)

    bars = [builders[key].to_bar() for key in sorted(builders)]
    if not bars:
        raise ValueError("No M5 bars could be built from tick data.")
    return bars, tick_count, first_tick, last_tick


def _build_signal_map(bars: list[Bar], params: StrategyParams) -> dict[datetime, int]:
    closes = [bar.close for bar in bars]
    fast = ema(closes, params.ema_fast)
    slow = ema(closes, params.ema_slow)
    signals: dict[datetime, int] = {}
    for index in range(1, len(bars)):
        fast_prev = fast[index - 1]
        slow_prev = slow[index - 1]
        if fast_prev is None or slow_prev is None:
            continue
        if fast_prev > slow_prev:
            signals[bars[index].time] = 1
        elif fast_prev < slow_prev:
            signals[bars[index].time] = -1
    return signals


def _execute_tick_strategy(
    config: TickBacktestConfig,
    excluded_dates: set[str],
    signal_by_bar: dict[datetime, int],
) -> list[Trade]:
    # 日期范围过滤：解析 start_date/end_date 为 date 对象
    start_date_obj = datetime.strptime(config.start_date, "%Y-%m-%d").date() if config.start_date else None
    end_date_obj = datetime.strptime(config.end_date, "%Y-%m-%d").date() if config.end_date else None

    trades: list[Trade] = []
    position: _Position | None = None
    last_close_time: datetime | None = None
    last_bar_time: datetime | None = None
    last_tick: Tick | None = None

    for tick in iter_ticks(config.data_path):
        if tick.time.date().isoformat() in excluded_dates:
            continue
        if start_date_obj and tick.time.date() < start_date_obj:
            continue
        if end_date_obj and tick.time.date() > end_date_obj:
            continue
        last_tick = tick
        bar_time = floor_m5(tick.time)
        is_new_bar = bar_time != last_bar_time
        if is_new_bar:
            last_bar_time = bar_time

        if position is not None:
            closed = _try_close_position(position, tick, bar_time, is_new_bar, config, trades)
            if closed:
                last_close_time = tick.time
                position = None
                continue

        if position is not None or not is_new_bar:
            continue

        if last_close_time is not None:
            elapsed = tick.time - last_close_time
            if elapsed < timedelta(minutes=config.params.cooldown_minutes):
                continue

        signal = signal_by_bar.get(bar_time, 0)
        if signal == 1:
            entry = tick.ask
            session = config.params.session_at(tick.time)
            stop_price = (
                entry - config.params.stop_loss_for_session(session) * config.point_size
                if config.params.use_stop_loss(session)
                else None
            )
            position = _Position(
                side="BUY",
                entry_time=tick.time,
                entry_bar=bar_time,
                entry_price=entry,
                stop_price=stop_price,
                session=session,
            )
        elif signal == -1:
            entry = tick.bid
            session = config.params.session_at(tick.time)
            stop_price = (
                entry + config.params.stop_loss_for_session(session) * config.point_size
                if config.params.use_stop_loss(session)
                else None
            )
            position = _Position(
                side="SELL",
                entry_time=tick.time,
                entry_bar=bar_time,
                entry_price=entry,
                stop_price=stop_price,
                session=session,
            )

    if position is not None and last_tick is not None:
        close_price = last_tick.bid if position.side == "BUY" else last_tick.ask
        trades.append(_make_trade(position, last_tick.time, floor_m5(last_tick.time), close_price, "end_of_data", config))
    return trades


def _try_close_position(
    position: _Position,
    tick: Tick,
    bar_time: datetime,
    is_new_bar: bool,
    config: TickBacktestConfig,
    trades: list[Trade],
) -> bool:
    if position.stop_price is not None and position.side == "BUY" and tick.bid <= position.stop_price:
        trades.append(_make_trade(position, tick.time, bar_time, position.stop_price, "stop_loss", config))
        return True
    if position.stop_price is not None and position.side == "SELL" and tick.ask >= position.stop_price:
        trades.append(_make_trade(position, tick.time, bar_time, position.stop_price, "stop_loss", config))
        return True

    if _try_profit_protection(position, tick, bar_time, config, trades):
        return True

    if config.time_profit_mode == "bar" and not is_new_bar:
        return False

    if not config.params.time_profit_enabled(position.session):
        return False

    check_interval = timedelta(minutes=config.params.time_check_for_session(position.session))
    if tick.time - position.entry_time < check_interval:
        return False

    recheck_interval = timedelta(minutes=config.params.time_recheck_for_session(position.session))
    if (
        position.last_time_profit_check_time is not None
        and tick.time - position.last_time_profit_check_time < recheck_interval
    ):
        return False

    position.last_time_profit_check_time = tick.time
    close_price = tick.bid if position.side == "BUY" else tick.ask
    pnl = _pnl_points(position.side, position.entry_price, close_price, config.point_size)
    if pnl > 0:
        trades.append(_make_trade(position, tick.time, bar_time, close_price, "time_profit", config))
        return True
    return False


def _try_profit_protection(
    position: _Position,
    tick: Tick,
    bar_time: datetime,
    config: TickBacktestConfig,
    trades: list[Trade],
) -> bool:
    close_price = tick.bid if position.side == "BUY" else tick.ask
    floating_points = _pnl_points(position.side, position.entry_price, close_price, config.point_size)
    position.max_floating_profit_points = max(position.max_floating_profit_points, max(0.0, floating_points))

    params = config.params
    if params.use_break_even_stop and floating_points >= params.break_even_start_points:
        if position.side == "BUY":
            new_stop = position.entry_price + params.break_even_lock_points * config.point_size
            if position.stop_price is None or new_stop > position.stop_price:
                position.stop_price = new_stop
        else:
            new_stop = position.entry_price - params.break_even_lock_points * config.point_size
            if position.stop_price is None or new_stop < position.stop_price:
                position.stop_price = new_stop

    if not params.use_profit_giveback_close:
        return False
    if position.max_floating_profit_points < params.giveback_start_points:
        return False

    giveback_points = position.max_floating_profit_points - floating_points
    points_triggered = params.giveback_close_points > 0 and giveback_points >= params.giveback_close_points
    percent_triggered = False
    if params.giveback_close_percent > 0.0:
        min_keep_points = position.max_floating_profit_points * (1.0 - params.giveback_close_percent / 100.0)
        percent_triggered = floating_points <= min_keep_points

    if points_triggered or percent_triggered:
        trades.append(_make_trade(position, tick.time, bar_time, close_price, "profit_giveback", config))
        return True
    return False


def _make_trade(
    position: _Position,
    exit_time: datetime,
    exit_bar: datetime,
    exit_price: float,
    reason: str,
    config: TickBacktestConfig,
) -> Trade:
    return Trade(
        side=position.side,
        entry_time=position.entry_time.isoformat(sep=" "),
        exit_time=exit_time.isoformat(sep=" "),
        entry_price=position.entry_price,
        exit_price=exit_price,
        pnl_points=_pnl_points(position.side, position.entry_price, exit_price, config.point_size),
        exit_reason=reason,
        bars_held=max(0, int((exit_bar - position.entry_bar).total_seconds() // 300)),
    )


def _pnl_points(side: str, entry_price: float, exit_price: float, point_size: float) -> float:
    if side == "BUY":
        return (exit_price - entry_price) / point_size
    return (entry_price - exit_price) / point_size


def iter_ticks(data_path: Path) -> Iterator[Tick]:
    for source in _collect_sources(data_path):
        if source.suffix.lower() == ".zip":
            yield from _iter_zip_ticks(source)
        elif source.suffix.lower() in (".csv", ".txt"):
            yield from _iter_text_ticks(source)


def _collect_sources(data_path: Path) -> list[Path]:
    if data_path.is_file():
        return [data_path]
    if data_path.is_dir():
        return sorted(
            path
            for path in data_path.iterdir()
            if path.is_file() and path.suffix.lower() in (".zip", ".csv", ".txt")
        )
    return []


def _iter_zip_ticks(path: Path) -> Iterator[Tick]:
    try:
        archive = ZipFile(path)
    except BadZipFile:
        print(f"Warning: skipping invalid ZIP file: {path}", file=sys.stderr)
        return

    with archive:
        entries = sorted(
            (
                entry
                for entry in archive.infolist()
                if not entry.is_dir() and Path(entry.filename).suffix.lower() in (".csv", ".txt")
            ),
            key=lambda entry: entry.filename,
        )
        for entry in entries:
            if entry.file_size < 2048 and Path(entry.filename).suffix.lower() == ".txt":
                continue
            with archive.open(entry) as binary:
                lines = (line.decode("utf-8-sig").rstrip("\r\n") for line in binary)
                yield from _parse_tick_lines(lines)


def _iter_text_ticks(path: Path) -> Iterator[Tick]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from _parse_tick_lines(handle)


def _parse_tick_lines(lines: Iterable[str]) -> Iterator[Tick]:
    iterator = iter(lines)
    sample: list[str] = []
    for line in iterator:
        if line.strip():
            sample.append(line)
        if len(sample) >= 5:
            break
    if not sample:
        return
    if not _looks_like_histdata_tick(sample[0]):
        return
    for line in chain(sample, iterator):
        tick = _parse_histdata_tick(line)
        if tick is not None:
            yield tick


def _looks_like_histdata_tick(line: str) -> bool:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 3:
        return False
    datetime_parts = parts[0].split()
    return (
        len(datetime_parts) == 2
        and len(datetime_parts[0]) == 8
        and datetime_parts[0].isdigit()
        and len(datetime_parts[1]) >= 6
        and datetime_parts[1].isdigit()
    )


def _parse_histdata_tick(line: str) -> Tick | None:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 3:
        return None
    datetime_parts = parts[0].split()
    if len(datetime_parts) != 2:
        return None
    date_raw, time_raw = datetime_parts
    if len(time_raw) < 6:
        return None
    millis = int(time_raw[6:9] or "0")
    time = datetime(
        int(date_raw[0:4]),
        int(date_raw[4:6]),
        int(date_raw[6:8]),
        int(time_raw[0:2]),
        int(time_raw[2:4]),
        int(time_raw[4:6]),
        millis * 1000,
    )
    return Tick(time=time, bid=float(parts[1]), ask=float(parts[2]))


def floor_m5(value: datetime) -> datetime:
    return value.replace(minute=value.minute - value.minute % 5, second=0, microsecond=0)
