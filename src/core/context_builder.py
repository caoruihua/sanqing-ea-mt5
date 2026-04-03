"""
该文件负责把 MT5 返回的原始 K 线数据加工成策略可直接使用的市场快照对象。

主要职责：
1. 基于一组“已经收盘”的 K 线数据，构建 `MarketSnapshot`；
2. 统一计算策略需要的 EMA / ATR 等指标；
3. 补齐趋势类、扩张类策略需要的历史高低点、实体统计、成交量统计字段；
4. 明确保证“只使用已收盘 K 线做决策”的语义。

说明：
- 该模块不负责向 MT5 发单；
- 该模块也不负责管理账户环境；
- 它只负责把原始市场数据变成后续策略、门控、执行层都能消费的标准快照。
"""

from datetime import datetime
from statistics import median
from typing import List, Optional, Sequence, Tuple

from src.domain.constants import (
    DEFAULT_ATR_PERIOD,
    DEFAULT_EMA_FAST_PERIOD,
    DEFAULT_EMA_SLOW_PERIOD,
    DEFAULT_MAGIC_NUMBER,
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
)
from src.domain.models import MarketSnapshot
from src.indicators.atr import calculate_atr
from src.indicators.ema import calculate_emas

# Type alias for bar data
# MT5 returns bars as tuples: (time, open, high, low, close, tick_volume, spread, real_volume)
BarData = Tuple[
    datetime,  # time
    float,  # open
    float,  # high
    float,  # low
    float,  # close
    int,  # tick_volume
    int,  # spread (in points)
    int,  # real_volume
]


class InsufficientBarsError(ValueError):
    """Raised when insufficient bars are available for indicator calculation."""

    def __init__(self, indicator: str, required: int, available: int):
        super().__init__(
            f"Insufficient bars for {indicator}: need at least {required} bars, got {available}"
        )
        self.indicator = indicator
        self.required = required
        self.available = available


class ContextBuilder:
    """根据已收盘 K 线构建标准市场快照。"""

    def __init__(
        self,
        symbol: str = DEFAULT_SYMBOL,
        timeframe: int = DEFAULT_TIMEFRAME,
        digits: int = 2,  # XAUUSD typically has 2 decimal places
        magic_number: int = DEFAULT_MAGIC_NUMBER,
        ema_fast_period: int = DEFAULT_EMA_FAST_PERIOD,
        ema_slow_period: int = DEFAULT_EMA_SLOW_PERIOD,
        atr_period: int = DEFAULT_ATR_PERIOD,
    ):
        """
        Initialize the context builder.

        Args:
            symbol: Trading symbol (e.g., "XAUUSD")
            timeframe: Timeframe in minutes (e.g., 5 for M5)
            digits: Price decimal places
            magic_number: Magic number for order identification
            ema_fast_period: Fast EMA period (default 9)
            ema_slow_period: Slow EMA period (default 21)
            atr_period: ATR period (default 14)
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.digits = digits
        self.magic_number = magic_number
        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period
        self.atr_period = atr_period

        # Validate periods
        if ema_fast_period <= 0 or ema_slow_period <= 0:
            raise ValueError("EMA periods must be positive")
        if ema_fast_period >= ema_slow_period:
            raise ValueError(
                f"EMA fast period ({ema_fast_period}) must be less than slow period ({ema_slow_period})"
            )
        if atr_period <= 0:
            raise ValueError("ATR period must be positive")

    def build_snapshot(
        self,
        bars: List[BarData],
        bid: float,
        ask: float,
    ) -> MarketSnapshot:
        """
        Build a market snapshot from bar data and current prices.

        Args:
            bars: List of bar data, most recent last. Each bar is a tuple:
                  (time, open, high, low, close, tick_volume, spread, real_volume)
            bid: Current bid price
            ask: Current ask price

        Returns:
            MarketSnapshot with all required fields

        Raises:
            InsufficientBarsError: If insufficient bars for indicator calculation
            ValueError: If bid/ask prices are invalid or bars list is empty
        """
        if not bars:
            raise ValueError("No bars provided")

        if bid <= 0 or ask <= 0:
            raise ValueError(f"Bid/ask prices must be positive: bid={bid}, ask={ask}")
        if ask <= bid:
            raise ValueError(f"Ask price ({ask}) must be greater than bid ({bid})")

        # Extract data from bars
        times = [bar[0] for bar in bars]
        opens = [bar[1] for bar in bars]
        highs = [bar[2] for bar in bars]
        lows = [bar[3] for bar in bars]
        closes = [bar[4] for bar in bars]
        volumes = [bar[7] for bar in bars]  # real_volume
        spreads = [bar[6] for bar in bars]  # spread in points

        # Last closed bar is the last bar in the list
        last_bar_idx = len(bars) - 1
        last_closed_bar_time = times[last_bar_idx]

        # Calculate indicators
        ema_fast, ema_slow = self._calculate_emas(closes)
        atr14 = self._calculate_atr(highs, lows, closes)

        # Calculate spread in points (use spread from last bar)
        spread_points = float(spreads[last_bar_idx])

        # Get historical data for trend calculations
        ema_fast_prev3 = self._get_ema_prev_value(closes, self.ema_fast_period, 3)
        ema_slow_prev3 = self._get_ema_prev_value(closes, self.ema_slow_period, 3)

        # Get high/low for previous bars (for TrendContinuation strategy)
        high_prev2 = self._get_prev_value(highs, 2)
        high_prev3 = self._get_prev_value(highs, 3)
        low_prev2 = self._get_prev_value(lows, 2)
        low_prev3 = self._get_prev_value(lows, 3)

        # 为 ExpansionFollow 等策略补充扩展统计字段。
        median_body_20 = self._calculate_median_body_20(opens, closes)
        prev3_body_max = self._calculate_prev3_body_max(opens, closes)
        volume_ma_20 = self._calculate_volume_ma_20(volumes)
        high_20 = self._calculate_high_20(highs)
        low_20 = self._calculate_low_20(lows)

        # Create market snapshot
        snapshot = MarketSnapshot(
            symbol=self.symbol,
            timeframe=self.timeframe,
            digits=self.digits,
            magic_number=self.magic_number,
            bid=bid,
            ask=ask,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            atr14=atr14,
            spread_points=spread_points,
            last_closed_bar_time=last_closed_bar_time,
            close=closes[last_bar_idx],
            open=opens[last_bar_idx],
            high=highs[last_bar_idx],
            low=lows[last_bar_idx],
            volume=volumes[last_bar_idx],
            ema_fast_prev3=ema_fast_prev3,
            ema_slow_prev3=ema_slow_prev3,
            high_prev2=high_prev2,
            high_prev3=high_prev3,
            low_prev2=low_prev2,
            low_prev3=low_prev3,
            median_body_20=median_body_20,
            prev3_body_max=prev3_body_max,
            volume_ma_20=volume_ma_20,
            high_20=high_20,
            low_20=low_20,
        )

        return snapshot

    def _calculate_emas(self, closes: List[float]) -> Tuple[float, float]:
        """Calculate fast and slow EMAs."""
        try:
            ema_fast, ema_slow = calculate_emas(
                close_prices=closes,
                fast_period=self.ema_fast_period,
                slow_period=self.ema_slow_period,
            )
        except ValueError as e:
            if "Insufficient data" in str(e):
                raise InsufficientBarsError(
                    indicator=f"EMA({self.ema_fast_period}/{self.ema_slow_period})",
                    required=max(self.ema_fast_period, self.ema_slow_period),
                    available=len(closes),
                ) from e
            raise
        return ema_fast, ema_slow

    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float]) -> float:
        """Calculate ATR(14)."""
        try:
            atr = calculate_atr(
                highs=highs,
                lows=lows,
                closes=closes,
                period=self.atr_period,
            )
        except ValueError as e:
            if "Insufficient data" in str(e):
                raise InsufficientBarsError(
                    indicator=f"ATR({self.atr_period})",
                    required=self.atr_period + 1,
                    available=len(highs),
                ) from e
            raise
        return atr

    def _get_ema_prev_value(
        self, closes: List[float], period: int, bars_back: int
    ) -> Optional[float]:
        """
        Get EMA value from bars_back bars ago.

        Returns None if insufficient data.
        """
        # Need at least period + bars_back bars to calculate EMA bars_back bars ago
        if len(closes) < period + bars_back:
            return None

        # Calculate EMA for the subset ending bars_back bars ago
        subset_closes = closes[: -(bars_back - 1)] if bars_back > 1 else closes
        from src.indicators.ema import calculate_ema

        try:
            ema = calculate_ema(subset_closes, period)
        except ValueError:
            return None
        return ema

    def _get_prev_value(self, values: List[float], bars_back: int) -> Optional[float]:
        """
        Get value from bars_back bars ago.

        Returns None if insufficient data.
        """
        if len(values) < bars_back:
            return None
        return values[-(bars_back + 1)]  # -1 for last bar, -bars_back for offset

    def _calculate_median_body_20(self, opens: List[float], closes: List[float]) -> Optional[float]:
        """计算当前 bar 之前 20 根 K 线的实体中位数。"""
        if len(opens) < 21:
            return None
        body_values = [abs(c - o) for o, c in zip(opens[-21:-1], closes[-21:-1])]
        return float(median(body_values))

    def _calculate_prev3_body_max(self, opens: List[float], closes: List[float]) -> Optional[float]:
        """计算当前 bar 之前 3 根 K 线实体长度的最大值。"""
        if len(opens) < 4:
            return None
        body_values = [abs(c - o) for o, c in zip(opens[-4:-1], closes[-4:-1])]
        return max(body_values) if body_values else None

    def _calculate_volume_ma_20(self, volumes: Sequence[float]) -> Optional[float]:
        """计算当前 bar 之前 20 根 K 线成交量均值。"""
        if len(volumes) < 21:
            return None
        previous_volumes = volumes[-21:-1]
        return float(sum(previous_volumes) / len(previous_volumes))

    def _calculate_high_20(self, highs: List[float]) -> Optional[float]:
        """计算当前 bar 之前 20 根 K 线的最高点。"""
        if len(highs) < 21:
            return None
        return max(highs[-21:-1])

    def _calculate_low_20(self, lows: List[float]) -> Optional[float]:
        """计算当前 bar 之前 20 根 K 线的最低点。"""
        if len(lows) < 21:
            return None
        return min(lows[-21:-1])


def create_market_snapshot(
    bars: List[BarData],
    bid: float,
    ask: float,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: int = DEFAULT_TIMEFRAME,
    digits: int = 2,
    magic_number: int = DEFAULT_MAGIC_NUMBER,
) -> MarketSnapshot:
    """
    Convenience function to create a market snapshot with default parameters.

    Args:
        bars: List of bar data
        bid: Current bid price
        ask: Current ask price
        symbol: Trading symbol
        timeframe: Timeframe in minutes
        digits: Price decimal places
        magic_number: Magic number for order identification

    Returns:
        MarketSnapshot
    """
    builder = ContextBuilder(
        symbol=symbol,
        timeframe=timeframe,
        digits=digits,
        magic_number=magic_number,
    )
    return builder.build_snapshot(bars, bid, ask)
