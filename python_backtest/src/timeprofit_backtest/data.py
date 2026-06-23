from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import chain
from pathlib import Path
from typing import Iterable
from zipfile import BadZipFile, ZipFile


@dataclass(frozen=True)
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: float = 0.0
    spread_points: float = 0.0


def load_bars(
    data_path: Path,
    fallback_spread_points: float = 0.0,
    point_size: float = 0.01,
) -> list[Bar]:
    sources = _collect_data_sources(data_path)
    if not sources:
        raise FileNotFoundError(
            f"No CSV or ZIP files found at {data_path}. Put XAUUSD M5 CSV or HistData tick ZIP files in python_backtest/data."
        )

    bars: list[Bar] = []
    for source in sources:
        bars.extend(_read_source(source, fallback_spread_points, point_size))

    by_time: dict[datetime, Bar] = {}
    for bar in bars:
        by_time[bar.time] = bar

    ordered = [by_time[key] for key in sorted(by_time)]
    if not ordered:
        raise ValueError(f"No bars could be parsed from {data_path}.")
    return ordered


def filter_recent_days(bars: list[Bar], lookback_days: int) -> list[Bar]:
    if lookback_days <= 0:
        return bars
    end_time = bars[-1].time
    start_time = end_time - timedelta(days=lookback_days)
    filtered = [bar for bar in bars if bar.time >= start_time]
    if not filtered:
        raise ValueError(f"No bars remain after applying lookback_days={lookback_days}.")
    return filtered


def filter_date_range(bars: list[Bar], start_date: str | None, end_date: str | None) -> list[Bar]:
    """按起止日期筛选 K 线数据。日期格式 YYYY-MM-DD，start 含当天，end 含当天。

    用于 Walk-Forward 验证时按窗口截取训练/测试数据段。
    """
    if not start_date and not end_date:
        return bars
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    # end_date 当天最后一根 M5 K 线时间 = end_date 23:59:59，取到 end_date 当天所有数据
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59) if end_date else None
    filtered = [
        bar for bar in bars
        if (start_dt is None or bar.time >= start_dt) and (end_dt is None or bar.time <= end_dt)
    ]
    if not filtered:
        raise ValueError(f"No bars remain after applying date range {start_date}~{end_date}.")
    return filtered


def filter_excluded_dates(bars: list[Bar], excluded_dates: set[str]) -> list[Bar]:
    if not excluded_dates:
        return bars
    filtered = [bar for bar in bars if bar.time.date().isoformat() not in excluded_dates]
    if not filtered:
        raise ValueError(f"No bars remain after excluding dates: {', '.join(sorted(excluded_dates))}.")
    return filtered


def data_state(bars: list[Bar], source_path: Path) -> dict[str, object]:
    return {
        "source": str(source_path),
        "bar_count": len(bars),
        "first_bar": bars[0].time.isoformat(sep=" "),
        "last_bar": bars[-1].time.isoformat(sep=" "),
    }


def _collect_data_sources(data_path: Path) -> list[Path]:
    if data_path.is_file():
        return [data_path]
    if data_path.is_dir():
        return sorted(
            [
                path
                for path in data_path.iterdir()
                if path.is_file() and path.suffix.lower() in (".csv", ".txt", ".zip")
            ]
        )
    return []


def _read_source(file_path: Path, fallback_spread_points: float, point_size: float) -> list[Bar]:
    if file_path.suffix.lower() == ".zip":
        return _read_zip(file_path, fallback_spread_points, point_size)
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return _read_lines(file_path.name, handle, fallback_spread_points, point_size)


def _read_zip(file_path: Path, fallback_spread_points: float, point_size: float) -> list[Bar]:
    bars: list[Bar] = []
    try:
        archive = ZipFile(file_path)
    except BadZipFile as exc:
        print(f"Warning: skipping invalid ZIP file: {file_path}", file=sys.stderr)
        return []
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
                text = (line.decode("utf-8-sig").rstrip("\r\n") for line in binary)
                bars.extend(_read_lines(f"{file_path.name}:{entry.filename}", text, fallback_spread_points, point_size))
    return bars


def _read_lines(
    source_name: str,
    lines: Iterable[str],
    fallback_spread_points: float,
    point_size: float,
) -> list[Bar]:
    iterator = iter(lines)
    sample_lines: list[str] = []
    for line in iterator:
        if line.strip():
            sample_lines.append(line)
        if len(sample_lines) >= 5:
            break

    if not sample_lines:
        return []

    chained = chain(sample_lines, iterator)
    if _looks_like_histdata_tick(sample_lines[0]):
        return _read_histdata_ticks(chained, point_size)

    return _read_ohlc_csv(source_name, chained, fallback_spread_points, point_size)


def _read_ohlc_csv(
    source_name: str,
    lines: Iterable[str],
    fallback_spread_points: float,
    point_size: float,
) -> list[Bar]:
    raw = list(lines)
    if not raw:
        return []

    sample = "\n".join(raw[:5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(raw, dialect=dialect)
    if reader.fieldnames is None:
        raise ValueError(f"CSV file has no header: {file_path}")

    normalized = {_normalize_name(name): name for name in reader.fieldnames}
    required = ("open", "high", "low", "close")
    missing = [name for name in required if name not in normalized]
    if missing:
        raise ValueError(f"{source_name} is missing columns: {', '.join(missing)}")

    bars = []
    for row in reader:
        if not any(row.values()):
            continue
        bars.append(
            Bar(
                time=_parse_time(row, normalized),
                open=_to_float(row[normalized["open"]]),
                high=_to_float(row[normalized["high"]]),
                low=_to_float(row[normalized["low"]]),
                close=_to_float(row[normalized["close"]]),
                tick_volume=_optional_float(row, normalized, ("tick_volume", "tickvol", "volume")),
                spread_points=_optional_spread_points(row, normalized, fallback_spread_points, point_size),
            )
        )
    return bars


@dataclass
class _BarBuilder:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    spread_sum: float = 0.0
    ticks: int = 0

    def update(self, price: float, spread_points: float) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.spread_sum += spread_points
        self.ticks += 1

    def to_bar(self) -> Bar:
        return Bar(
            time=self.time,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            tick_volume=float(self.ticks),
            spread_points=self.spread_sum / self.ticks if self.ticks else 0.0,
        )


def _read_histdata_ticks(lines: Iterable[str], point_size: float) -> list[Bar]:
    builders: dict[datetime, _BarBuilder] = {}
    for line in lines:
        parsed = _parse_histdata_tick(line, point_size)
        if parsed is None:
            continue
        tick_time, bid, ask, spread_points = parsed
        bar_time = tick_time.replace(
            minute=tick_time.minute - (tick_time.minute % 5),
            second=0,
            microsecond=0,
        )
        price = (bid + ask) / 2.0
        builder = builders.get(bar_time)
        if builder is None:
            builders[bar_time] = _BarBuilder(
                time=bar_time,
                open=price,
                high=price,
                low=price,
                close=price,
                spread_sum=spread_points,
                ticks=1,
            )
        else:
            builder.update(price, spread_points)
    return [builders[key].to_bar() for key in sorted(builders)]


def _looks_like_histdata_tick(line: str) -> bool:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 3:
        return False
    datetime_parts = parts[0].split()
    if len(datetime_parts) != 2:
        return False
    return (
        len(datetime_parts[0]) == 8
        and datetime_parts[0].isdigit()
        and len(datetime_parts[1]) >= 6
        and datetime_parts[1].isdigit()
    )


def _parse_histdata_tick(line: str, point_size: float) -> tuple[datetime, float, float, float] | None:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 3:
        return None
    date_time = parts[0].split()
    if len(date_time) != 2:
        return None
    date_raw, time_raw = date_time
    if len(time_raw) < 6:
        return None
    millis = int(time_raw[6:9] or "0")
    tick_time = datetime(
        int(date_raw[0:4]),
        int(date_raw[4:6]),
        int(date_raw[6:8]),
        int(time_raw[0:2]),
        int(time_raw[2:4]),
        int(time_raw[4:6]),
        millis * 1000,
    )
    bid = _to_float(parts[1])
    ask = _to_float(parts[2])
    spread_points = max(0.0, (ask - bid) / point_size)
    return tick_time, bid, ask, spread_points


def _normalize_name(name: str) -> str:
    normalized = name.strip().strip("<>").lower()
    normalized = normalized.replace(" ", "_").replace("-", "_")
    aliases = {
        "date": "date",
        "time": "time",
        "datetime": "time",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "tickvol": "tickvol",
        "tick_volume": "tick_volume",
        "vol": "volume",
        "volume": "volume",
        "spread": "spread",
    }
    return aliases.get(normalized, normalized)


def _parse_time(row: dict[str, str], names: dict[str, str]) -> datetime:
    if "date" in names and "time" in names:
        return _parse_datetime_value(f"{row[names['date']]} {row[names['time']]}")
    if "time" in names:
        return _parse_datetime_value(row[names["time"]])
    raise ValueError("CSV must contain either time or date + time columns.")


def _parse_datetime_value(value: str) -> datetime:
    value = value.strip().replace("/", ".")
    formats = (
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    # fromisoformat 在 Python 3.11+ 可能解析出带时区的 datetime，
    # 统一转换为无时区 datetime，避免与 HistData tick 产生的不带时区 datetime 比较时冲突
    result = datetime.fromisoformat(value)
    if result.tzinfo is not None:
        result = result.replace(tzinfo=None)
    return result


def _to_float(value: str) -> float:
    return float(value.strip().replace(",", "."))


def _optional_float(
    row: dict[str, str],
    names: dict[str, str],
    keys: Iterable[str],
    default: float = 0.0,
) -> float:
    for key in keys:
        if key in names:
            value = row.get(names[key], "")
            if value == "":
                return default
            return _to_float(value)
    return default


def _optional_spread_points(
    row: dict[str, str],
    names: dict[str, str],
    default: float,
    point_size: float,
) -> float:
    if "spread" not in names:
        return default
    raw_value = row.get(names["spread"], "").strip()
    if raw_value == "":
        return default
    spread = _to_float(raw_value)

    # MT5 CSV usually stores spread as integer points, while converted HistData
    # M5 files often store ask-bid as a price difference such as 1.071303.
    if "." in raw_value and 0 < spread < 10:
        return spread / point_size
    return spread
