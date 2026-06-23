from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Trade:
    side: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    pnl_points: float
    exit_reason: str
    bars_held: int


def calculate_metrics(trades: list[Trade], min_trades: int) -> dict[str, float | int]:
    pnl = [trade.pnl_points for trade in trades]
    net = sum(pnl)
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    trade_count = len(trades)
    win_rate = len(wins) / trade_count if trade_count else 0.0
    low_trade_penalty = max(0, min_trades - trade_count) * 50.0
    score = net - (1.5 * max_drawdown) + (min(profit_factor, 5.0) * 100.0) - low_trade_penalty

    return {
        "trade_count": trade_count,
        "net_points": net,
        "gross_profit_points": gross_profit,
        "gross_loss_points": gross_loss,
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "max_drawdown_points": max_drawdown,
        "avg_trade_points": net / trade_count if trade_count else 0.0,
        "score": score,
    }
