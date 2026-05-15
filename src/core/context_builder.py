"""
Build a minimal MarketSnapshot from raw MT5 bar data.
No indicators — only raw candle history for naked-K strategies.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from src.domain.constants import DEFAULT_MAGIC_NUMBER, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from src.domain.models import MarketSnapshot

BarData = Tuple[
    datetime, float, float, float, float, int, int, int
]


class ContextBuilder:
    def __init__(
        self,
        symbol: str = DEFAULT_SYMBOL,
        timeframe: int = DEFAULT_TIMEFRAME,
        digits: int = 2,
        magic_number: int = DEFAULT_MAGIC_NUMBER,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.digits = digits
        self.magic_number = magic_number

    def build_snapshot(self, bars: List[BarData], bid: float, ask: float) -> MarketSnapshot:
        if not bars:
            raise ValueError("No bars provided")
        if bid <= 0 or ask <= 0:
            raise ValueError(f"Bid/ask prices must be positive: bid={bid}, ask={ask}")
        if ask <= bid:
            raise ValueError(f"Ask price ({ask}) must be greater than bid ({bid})")

        times = [b[0] for b in bars]
        opens = [b[1] for b in bars]
        highs = [b[2] for b in bars]
        lows = [b[3] for b in bars]
        closes = [b[4] for b in bars]
        spreads = [b[6] for b in bars]

        last = len(bars) - 1
        return MarketSnapshot(
            symbol=self.symbol,
            timeframe=self.timeframe,
            digits=self.digits,
            magic_number=self.magic_number,
            bid=bid,
            ask=ask,
            spread_points=float(spreads[last]),
            last_closed_bar_time=times[last],
            close=closes[last],
            open=opens[last],
            high=highs[last],
            low=lows[last],
            opens_history=opens,
            closes_history=closes,
            highs_history=highs,
            lows_history=lows,
        )


def create_market_snapshot(
    bars: List[BarData],
    bid: float,
    ask: float,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: int = DEFAULT_TIMEFRAME,
    digits: int = 2,
    magic_number: int = DEFAULT_MAGIC_NUMBER,
) -> MarketSnapshot:
    builder = ContextBuilder(symbol=symbol, timeframe=timeframe, digits=digits, magic_number=magic_number)
    return builder.build_snapshot(bars, bid, ask)
