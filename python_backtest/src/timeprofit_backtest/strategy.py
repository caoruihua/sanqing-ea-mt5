from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from .data import Bar
from .metrics import Trade


Session = Literal["DAY", "NIGHT"]


@dataclass(frozen=True)
class StrategyParams:
    ema_fast: int = 15
    ema_slow: int = 44
    cooldown_minutes: int = 10
    night_session_start_hour: int = 21
    night_session_start_minute: int = 30
    night_session_end_hour: int = 3
    night_session_end_minute: int = 0
    day_stop_loss_points: int | None = None
    day_use_stop_loss: bool = True
    day_time_check_minutes: int | None = None
    day_time_profit_recheck_minutes: int = 5
    day_time_profit_close: bool = True
    night_stop_loss_points: int | None = None
    night_use_stop_loss: bool = True
    night_time_check_minutes: int | None = None
    night_time_profit_recheck_minutes: int = 5
    night_time_profit_close: bool = True
    use_break_even_stop: bool = True
    break_even_start_points: int = 500
    break_even_lock_points: int = 30
    use_profit_giveback_close: bool = True
    giveback_start_points: int = 1500
    giveback_close_points: int = 700
    giveback_close_percent: float = 80.0
    # Backward-compatible aliases used by older scripts. When day/night values
    # are not provided, these apply to both sessions.
    time_check_minutes: int | None = None
    stop_loss_points: int | None = None

    def session_at(self, value: datetime) -> Session:
        beijing_time = value + timedelta(hours=8)
        current_minutes = beijing_time.hour * 60 + beijing_time.minute
        start_minutes = self.night_session_start_hour * 60 + self.night_session_start_minute
        end_minutes = self.night_session_end_hour * 60 + self.night_session_end_minute

        if start_minutes > end_minutes:
            if current_minutes >= start_minutes or current_minutes < end_minutes:
                return "NIGHT"
        elif start_minutes <= current_minutes < end_minutes:
            return "NIGHT"
        return "DAY"

    def use_stop_loss(self, session: Session) -> bool:
        return self.night_use_stop_loss if session == "NIGHT" else self.day_use_stop_loss

    def stop_loss_for_session(self, session: Session) -> int:
        value = self.night_stop_loss_points if session == "NIGHT" else self.day_stop_loss_points
        if value is not None:
            return value
        if self.stop_loss_points is not None:
            return self.stop_loss_points
        return 2000 if session == "NIGHT" else 1000

    def time_profit_enabled(self, session: Session) -> bool:
        return self.night_time_profit_close if session == "NIGHT" else self.day_time_profit_close

    def time_check_for_session(self, session: Session) -> int:
        value = self.night_time_check_minutes if session == "NIGHT" else self.day_time_check_minutes
        if value is not None:
            return value
        if self.time_check_minutes is not None:
            return self.time_check_minutes
        return 15 if session == "NIGHT" else 10

    def time_recheck_for_session(self, session: Session) -> int:
        if session == "NIGHT":
            return self.night_time_profit_recheck_minutes
        return self.day_time_profit_recheck_minutes


@dataclass(frozen=True)
class CostParams:
    point_size: float = 0.01
    slippage_points: float = 0.0
    commission_points: float = 0.0


@dataclass
class Position:
    side: str
    entry_index: int
    entry_time: datetime
    entry_price: float
    stop_price: float | None
    session: Session
    last_time_profit_check_time: datetime | None = None
    max_floating_profit_points: float = 0.0


def backtest(
    bars: list[Bar],
    ema_fast: list[float | None],
    ema_slow: list[float | None],
    params: StrategyParams,
    costs: CostParams,
) -> list[Trade]:
    if params.ema_fast >= params.ema_slow:
        return []

    trades: list[Trade] = []
    position: Position | None = None
    last_close_time: datetime | None = None

    for index in range(1, len(bars)):
        bar = bars[index]

        if position is not None:
            closed = _try_close_position(position, bar, index, params, costs)
            if closed is not None:
                trades.append(closed)
                last_close_time = bar.time
                position = None
                continue

        if position is not None:
            continue

        if last_close_time is not None and bar.time - last_close_time < timedelta(minutes=params.cooldown_minutes):
            continue

        previous = index - 1
        fast_value = ema_fast[previous]
        slow_value = ema_slow[previous]
        if fast_value is None or slow_value is None:
            continue

        if fast_value > slow_value:
            position = _open_position("BUY", index, bar, params, costs)
        elif fast_value < slow_value:
            position = _open_position("SELL", index, bar, params, costs)

    if position is not None:
        final_bar = bars[-1]
        trades.append(_close_at_price(position, final_bar, len(bars) - 1, final_bar.close, "end_of_data", costs))

    return trades


def _open_position(
    side: str,
    index: int,
    bar: Bar,
    params: StrategyParams,
    costs: CostParams,
) -> Position:
    session = params.session_at(bar.time)
    use_stop_loss = params.use_stop_loss(session)
    stop_loss_points = params.stop_loss_for_session(session)
    half_spread = (bar.spread_points * costs.point_size) / 2.0
    if side == "BUY":
        entry_price = bar.open + half_spread + costs.slippage_points * costs.point_size
        stop_price = entry_price - stop_loss_points * costs.point_size if use_stop_loss else None
    else:
        entry_price = bar.open - half_spread - costs.slippage_points * costs.point_size
        stop_price = entry_price + stop_loss_points * costs.point_size if use_stop_loss else None
    return Position(side, index, bar.time, entry_price, stop_price, session)


def _try_close_position(
    position: Position,
    bar: Bar,
    index: int,
    params: StrategyParams,
    costs: CostParams,
) -> Trade | None:
    if position.stop_price is not None and position.side == "BUY" and bar.low <= position.stop_price:
        return _close_at_price(position, bar, index, position.stop_price, "stop_loss", costs)
    if position.stop_price is not None and position.side == "SELL" and bar.high >= position.stop_price:
        return _close_at_price(position, bar, index, position.stop_price, "stop_loss", costs)

    protection_close = _try_profit_protection(position, bar, index, params, costs)
    if protection_close is not None:
        return protection_close

    if not params.time_profit_enabled(position.session):
        return None

    held_time = bar.time - position.entry_time
    check_interval = timedelta(minutes=params.time_check_for_session(position.session))
    if held_time < check_interval:
        return None

    recheck_interval = timedelta(minutes=params.time_recheck_for_session(position.session))
    if (
        position.last_time_profit_check_time is not None
        and bar.time - position.last_time_profit_check_time < recheck_interval
    ):
        return None

    position.last_time_profit_check_time = bar.time
    close_price = _tradable_close_price(position.side, bar, costs)
    pnl_points = _pnl_points(position.side, position.entry_price, close_price, costs)
    if pnl_points > 0:
        return _close_at_price(position, bar, index, close_price, "time_profit", costs)
    return None


def _try_profit_protection(
    position: Position,
    bar: Bar,
    index: int,
    params: StrategyParams,
    costs: CostParams,
) -> Trade | None:
    if position.side == "BUY":
        favorable_price = bar.high
    else:
        favorable_price = bar.low
    max_points_this_bar = max(0.0, _pnl_points(position.side, position.entry_price, favorable_price, costs))
    position.max_floating_profit_points = max(position.max_floating_profit_points, max_points_this_bar)

    if params.use_break_even_stop and position.max_floating_profit_points >= params.break_even_start_points:
        if position.side == "BUY":
            new_stop = position.entry_price + params.break_even_lock_points * costs.point_size
            if position.stop_price is None or new_stop > position.stop_price:
                position.stop_price = new_stop
        else:
            new_stop = position.entry_price - params.break_even_lock_points * costs.point_size
            if position.stop_price is None or new_stop < position.stop_price:
                position.stop_price = new_stop

    if not params.use_profit_giveback_close:
        return None
    if position.max_floating_profit_points < params.giveback_start_points:
        return None

    close_price = _tradable_close_price(position.side, bar, costs)
    current_points = _pnl_points(position.side, position.entry_price, close_price, costs)
    giveback_points = position.max_floating_profit_points - current_points
    points_triggered = params.giveback_close_points > 0 and giveback_points >= params.giveback_close_points
    percent_triggered = False
    if params.giveback_close_percent > 0.0:
        min_keep_points = position.max_floating_profit_points * (1.0 - params.giveback_close_percent / 100.0)
        percent_triggered = current_points <= min_keep_points

    if points_triggered or percent_triggered:
        return _close_at_price(position, bar, index, close_price, "profit_giveback", costs)
    return None


def _tradable_close_price(side: str, bar: Bar, costs: CostParams) -> float:
    half_spread = (bar.spread_points * costs.point_size) / 2.0
    if side == "BUY":
        return bar.close - half_spread - costs.slippage_points * costs.point_size
    return bar.close + half_spread + costs.slippage_points * costs.point_size


def _close_at_price(
    position: Position,
    bar: Bar,
    index: int,
    close_price: float,
    reason: str,
    costs: CostParams,
) -> Trade:
    pnl = _pnl_points(position.side, position.entry_price, close_price, costs)
    return Trade(
        side=position.side,
        entry_time=position.entry_time.isoformat(sep=" "),
        exit_time=bar.time.isoformat(sep=" "),
        entry_price=position.entry_price,
        exit_price=close_price,
        pnl_points=pnl,
        exit_reason=reason,
        bars_held=index - position.entry_index,
    )


def _pnl_points(side: str, entry_price: float, close_price: float, costs: CostParams) -> float:
    if side == "BUY":
        raw = (close_price - entry_price) / costs.point_size
    else:
        raw = (entry_price - close_price) / costs.point_size
    return raw - costs.commission_points
