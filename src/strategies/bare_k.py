"""
该文件实现 BareK（裸 K 线）策略。

主要职责：
1. 识别连续 N 根方向一致的 K 线；
2. 在连续同向 K 线形成时生成买入/卖出信号；
3. 提供固定利润目标。

说明：
- 该策略只分析 K 线实体方向，不依赖任何指标；
- 连续 N 根阳线 = 买入信号，连续 N 根阴线 = 卖出信号；
- 信号无止损止盈，仅设置固定利润目标。
"""

from typing import Optional

from src.domain.constants import DEFAULT_CONSECUTIVE_BARS, DEFAULT_FIXED_LOTS
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision
from src.strategies.base import BaseStrategy


class BareKStrategy(BaseStrategy):
    """Naked K-line strategy: trade in the direction of N consecutive candles."""

    def __init__(
        self,
        consecutive_bars: int = DEFAULT_CONSECUTIVE_BARS,
        fixed_lots: float = DEFAULT_FIXED_LOTS,
    ) -> None:
        self.consecutive_bars = consecutive_bars
        self.fixed_lots = fixed_lots

    @property
    def name(self) -> str:
        return "BareK"

    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        """返回当前策略是否满足评估前提（有足够的历史 K 线）。"""
        _ = state
        return len(snapshot.closes_history) >= self.consecutive_bars

    def build_intent(
        self, snapshot: MarketSnapshot, state: RuntimeState
    ) -> Optional[SignalDecision]:
        """在条件满足时返回信号决策。"""
        if not self.can_trade(snapshot, state):
            return None

        closes = snapshot.closes_history
        opens = snapshot.opens_history
        n = self.consecutive_bars

        # Check last N bars (current bar is the last element)
        last_closes = closes[-n:]
        last_opens = opens[-n:]

        bullish = all(c > o for c, o in zip(last_closes, last_opens))
        bearish = all(c < o for c, o in zip(last_closes, last_opens))

        if bullish:
            return SignalDecision(
                strategy_name=self.name,
                order_type=OrderType.BUY,
                entry_price=snapshot.ask,
                stop_loss=0.0,
                take_profit=None,
                atr_value=0.0,
                lots=self.fixed_lots,
                profit_target_usd=10.0,
                conditions_met=["consecutive_bullish"],
            )

        if bearish:
            return SignalDecision(
                strategy_name=self.name,
                order_type=OrderType.SELL,
                entry_price=snapshot.bid,
                stop_loss=0.0,
                take_profit=None,
                atr_value=0.0,
                lots=self.fixed_lots,
                profit_target_usd=10.0,
                conditions_met=["consecutive_bearish"],
            )

        return None
