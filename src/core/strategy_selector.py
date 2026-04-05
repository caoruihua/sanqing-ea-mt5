"""
该文件负责在多个策略信号之间做固定优先级选择。

主要职责：
1. 按约定顺序依次执行策略；
2. 只返回优先级最高的那个有效信号；
3. 记录低优先级策略被高优先级策略抑制的原因，方便日志和测试断言。

说明：
- 该文件不负责下单；
- 也不负责行情采集；
- 它只解决“多个策略同时命中时，到底用哪个”的问题。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.domain.constants import DEFAULT_FIXED_LOTS
from src.domain.models import MarketSnapshot, RuntimeState, SignalDecision
from src.strategies.base import BaseStrategy
from src.strategies.expansion_follow import ExpansionFollowStrategy
from src.strategies.pullback import PullbackStrategy
from src.strategies.trend_continuation import TrendContinuationStrategy
from src.utils.logger import StructuredLogger

NO_STRATEGY_SIGNAL = "NO_STRATEGY_SIGNAL"
SUPPRESSED_BY_HIGHER_PRIORITY = "SUPPRESSED_BY_HIGHER_PRIORITY"


@dataclass
class StrategySelectionResult:
    """包含胜出策略及抑制元数据的选择结果。"""

    intent: Optional[SignalDecision]
    rejection_reason: Optional[str] = None
    suppressed_reasons: Dict[str, str] = field(default_factory=dict)


class StrategySelector:
    """按严格优先级顺序选择首个有效信号。"""

    def __init__(
        self,
        strategies: Optional[List[BaseStrategy]] = None,
        fixed_lots: float = DEFAULT_FIXED_LOTS,
        logger: Optional[StructuredLogger] = None,
    ) -> None:
        self.strategies = strategies or [
            ExpansionFollowStrategy(fixed_lots=fixed_lots),
            PullbackStrategy(fixed_lots=fixed_lots),
            TrendContinuationStrategy(fixed_lots=fixed_lots),
        ]
        self.logger = logger

    def select(self, snapshot: MarketSnapshot, state: RuntimeState) -> StrategySelectionResult:
        winner: Optional[SignalDecision] = None
        suppressed: Dict[str, str] = {}

        for strategy in self.strategies:
            if not strategy.can_trade(snapshot, state):
                continue
            candidate = strategy.build_intent(snapshot, state)
            if candidate is None:
                continue

            if winner is None:
                winner = candidate
                continue

            suppressed[strategy.name] = SUPPRESSED_BY_HIGHER_PRIORITY

        # 记录信号生成日志
        if self.logger is not None:
            if winner is not None:
                event_name = f"{winner.strategy_name}_signal_generated"
                self.logger.info(
                    event_name,
                    strategy_name=winner.strategy_name,
                    order_type=winner.order_type.value,
                    entry_price=winner.entry_price,
                    stop_loss=winner.stop_loss,
                    take_profit=winner.take_profit,
                    lots=winner.lots,
                    symbol=snapshot.symbol,
                )
                # 记录被抑制的策略
                for suppressed_strategy, reason in suppressed.items():
                    self.logger.warning(
                        "strategy_suppressed",
                        suppressed_strategy=suppressed_strategy,
                        winner_strategy=winner.strategy_name,
                        reason=reason,
                        symbol=snapshot.symbol,
                    )
            else:
                self.logger.info(
                    "no_signal",
                    reason=NO_STRATEGY_SIGNAL,
                    symbol=snapshot.symbol,
                )

        if winner is None:
            return StrategySelectionResult(intent=None, rejection_reason=NO_STRATEGY_SIGNAL)

        return StrategySelectionResult(intent=winner, suppressed_reasons=suppressed)
