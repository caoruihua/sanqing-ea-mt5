"""
该文件定义所有策略模块必须遵守的统一接口。

主要职责：
1. 约束每个策略都必须暴露名称；
2. 约束每个策略都必须实现“是否允许评估”和“生成信号”两个核心动作；
3. 让策略选择器可以用统一方式调用不同策略。

说明：
- 该文件不包含具体交易规则；
- 具体规则由各个策略文件自行实现。
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models import MarketSnapshot, RuntimeState, SignalDecision


class BaseStrategy(ABC):
    """Strategy interface used by priority selector."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""

    @abstractmethod
    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        """Return whether this strategy is eligible to evaluate."""

    @abstractmethod
    def build_intent(
        self, snapshot: MarketSnapshot, state: RuntimeState
    ) -> Optional[SignalDecision]:
        """Return a signal decision when conditions are satisfied."""
