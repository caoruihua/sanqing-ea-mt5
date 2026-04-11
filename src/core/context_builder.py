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
from src.indicators.adx import calculate_adx
from src.indicators.atr import calculate_atr
from src.indicators.ema import calculate_emas

# K 线数据的类型别名。
# MT5 返回的 bar 元组字段依次为：
# （时间、开盘价、最高价、最低价、收盘价、tick_volume、spread、real_volume）
BarData = Tuple[
    datetime,  # 时间
    float,  # 开盘价
    float,  # 最高价
    float,  # 最低价
    float,  # 收盘价
    int,  # tick_volume 成交量字段
    int,  # 点差字段，单位为 points
    int,  # real_volume 成交量字段
]


class InsufficientBarsError(ValueError):
    """当可用 K 线不足以完成指标计算时抛出。"""

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
        digits: int = 2,  # XAUUSD 通常保留 2 位小数
        magic_number: int = DEFAULT_MAGIC_NUMBER,
        ema_fast_period: int = DEFAULT_EMA_FAST_PERIOD,
        ema_slow_period: int = DEFAULT_EMA_SLOW_PERIOD,
        atr_period: int = DEFAULT_ATR_PERIOD,
    ):
        """
        初始化上下文构建器。

        参数：
            symbol: 交易品种（如 `"XAUUSD"`）
            timeframe: 时间框，单位为分钟（如 M5 对应 5）
            digits: 价格小数位数
            magic_number: 订单识别用 magic number
            ema_fast_period: 快线 EMA 周期（默认 9）
            ema_slow_period: 慢线 EMA 周期（默认 21）
            atr_period: ATR 周期（默认 14）
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.digits = digits
        self.magic_number = magic_number
        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period
        self.atr_period = atr_period

        # 校验周期参数。
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
        根据 K 线数据和当前报价构建市场快照。

        参数：
            bars: K 线数据列表，最新一根放在最后；单根 K 线格式为
                `(time, open, high, low, close, tick_volume, spread, real_volume)`
            bid: 当前买价
            ask: 当前卖价

        返回：
            包含全部必需字段的 `MarketSnapshot`

        异常：
            InsufficientBarsError: 当指标计算所需 K 线不足时抛出
            ValueError: 当 bid/ask 非法或 bars 为空时抛出
        """
        if not bars:
            raise ValueError("No bars provided")

        if bid <= 0 or ask <= 0:
            raise ValueError(f"Bid/ask prices must be positive: bid={bid}, ask={ask}")
        if ask <= bid:
            raise ValueError(f"Ask price ({ask}) must be greater than bid ({bid})")

        # 从 K 线序列中拆出各个字段。
        times = [bar[0] for bar in bars]
        opens = [bar[1] for bar in bars]
        highs = [bar[2] for bar in bars]
        lows = [bar[3] for bar in bars]
        closes = [bar[4] for bar in bars]
        volumes = [bar[7] for bar in bars]  # 成交量 real_volume
        spreads = [bar[6] for bar in bars]  # 点差，单位为 points

        # 列表中的最后一根就是最近已收盘 K 线。
        last_bar_idx = len(bars) - 1
        last_closed_bar_time = times[last_bar_idx]

        # 计算指标。
        ema_fast, ema_slow = self._calculate_emas(closes)
        atr14 = self._calculate_atr(highs, lows, closes)

        # 计算点差（直接使用最后一根 K 线自带的 spread 字段）。
        spread_points = float(spreads[last_bar_idx])

        # 取趋势计算所需的历史指标值。
        ema_fast_prev3 = self._get_ema_prev_value(closes, self.ema_fast_period, 3)
        ema_slow_prev3 = self._get_ema_prev_value(closes, self.ema_slow_period, 3)

        # 取前几根 K 线的高低点，供 TrendContinuation 策略使用。
        high_prev2 = self._get_prev_value(highs, 2)
        high_prev3 = self._get_prev_value(highs, 3)
        low_prev2 = self._get_prev_value(lows, 2)
        low_prev3 = self._get_prev_value(lows, 3)

        # 为反转策略补充历史K线数据
        prev_open = self._get_prev_value(opens, 1)
        prev_close = self._get_prev_value(closes, 1)
        prev_high = self._get_prev_value(highs, 1)
        prev_low = self._get_prev_value(lows, 1)
        high_3 = self._calculate_high_3(highs)
        low_3 = self._calculate_low_3(lows)

        # 为 ExpansionFollow 等策略补充扩展统计字段。
        median_body_20 = self._calculate_median_body_20(opens, closes)
        prev3_body_max = self._calculate_prev3_body_max(opens, closes)
        volume_ma_20 = self._calculate_volume_ma_20(volumes)
        high_20 = self._calculate_high_20(highs)
        low_20 = self._calculate_low_20(lows)

        # 计算趋势/震荡过滤指标。
        adx14 = self._calculate_adx_safe(highs, lows, closes)
        channel_width_ratio = self._calculate_channel_width_ratio(high_20, low_20, atr14)

        # 组装市场快照对象。
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
            prev_open=prev_open,
            prev_close=prev_close,
            prev_high=prev_high,
            prev_low=prev_low,
            high_3=high_3,
            low_3=low_3,
            median_body_20=median_body_20,
            prev3_body_max=prev3_body_max,
            volume_ma_20=volume_ma_20,
            high_20=high_20,
            low_20=low_20,
            adx14=adx14,
            channel_width_ratio=channel_width_ratio,
        )

        return snapshot

    def _calculate_emas(self, closes: List[float]) -> Tuple[float, float]:
        """计算快线与慢线 EMA。"""
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
        """计算 ATR(14)。"""
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

    def _calculate_adx_safe(
        self, highs: List[float], lows: List[float], closes: List[float]
    ) -> Optional[float]:
        """计算ADX(14)，数据不足时返回None而非抛异常。"""
        try:
            return calculate_adx(highs=highs, lows=lows, closes=closes, period=14)
        except ValueError:
            return None

    def _calculate_channel_width_ratio(
        self, high_20: Optional[float], low_20: Optional[float], atr14: float
    ) -> Optional[float]:
        """计算20日通道宽度相对于ATR的倍数。

        公式: (high_20 - low_20) / atr14
        返回值:
            - < 3: 窄幅整理
            - 3-5: 正常趋势波动
            - > 5: 宽幅震荡（假突破风险高）
        """
        if high_20 is None or low_20 is None or atr14 <= 0:
            return None
        channel_width = high_20 - low_20
        if channel_width <= 0:
            return None
        return channel_width / atr14

    def _get_ema_prev_value(
        self, closes: List[float], period: int, bars_back: int
    ) -> Optional[float]:
        """
        获取若干根 K 线之前的 EMA 值。

        如果历史数据不足，则返回 `None`。
        """
        # 至少要有 `period + bars_back` 根 K 线，才能计算出对应历史位置的 EMA。
        if len(closes) < period + bars_back:
            return None

        # 取出终止于 `bars_back` 根之前的子序列来计算 EMA。
        subset_closes = closes[: -(bars_back - 1)] if bars_back > 1 else closes
        from src.indicators.ema import calculate_ema

        try:
            ema = calculate_ema(subset_closes, period)
        except ValueError:
            return None
        return ema

    def _get_prev_value(self, values: List[float], bars_back: int) -> Optional[float]:
        """
        获取若干根 K 线之前的数值。

        如果历史数据不足，则返回 `None`。
        """
        if len(values) <= bars_back:
            return None
        return values[-(bars_back + 1)]  # -1 表示最后一根，额外偏移 `bars_back`

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

    def _calculate_high_3(self, highs: List[float]) -> Optional[float]:
        """计算当前 bar 之前 3 根 K 线的最高点。"""
        if len(highs) < 4:
            return None
        return max(highs[-4:-1])  # 获取索引 -4, -3, -2 的最高值（排除当前 bar -1）

    def _calculate_low_3(self, lows: List[float]) -> Optional[float]:
        """计算当前 bar 之前 3 根 K 线的最低点。"""
        if len(lows) < 4:
            return None
        return min(lows[-4:-1])  # 获取索引 -4, -3, -2 的最低值（排除当前 bar -1）


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
    使用默认参数创建市场快照的便捷函数。

    参数：
        bars: K 线数据列表
        bid: 当前买价
        ask: 当前卖价
        symbol: 交易品种
        timeframe: 时间框，单位为分钟
        digits: 价格小数位数
        magic_number: 订单识别用 magic number

    返回：
        `MarketSnapshot`
    """
    builder = ContextBuilder(
        symbol=symbol,
        timeframe=timeframe,
        digits=digits,
        magic_number=magic_number,
    )
    return builder.build_snapshot(bars, bid, ask)
