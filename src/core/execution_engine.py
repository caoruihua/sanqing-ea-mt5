"""
该文件负责把已经通过门控的交易意图真正发送到 broker/MT5。

主要职责：
1. 在发单前做最终的单持仓检查；
2. 对同一个 action_id 做幂等保护，避免重复提交；
3. 对可重试错误执行有限次数重试；
4. 在成功下单后更新运行时状态（如 trades_today、position_ticket）。

说明：
- 本文件不负责产生策略信号；
- 不负责是否允许开仓；
- 只负责“已经决定要下”的那一步如何安全执行。
"""

from typing import Dict, Set

from src.adapters.broker_base import BrokerAdapter
from src.domain.constants import DEFAULT_MAX_RETRIES, DEFAULT_SLIPPAGE
from src.domain.models import RuntimeState, TradeIntent


class DuplicateActionError(ValueError):
    """同一个 action_id 被重复提交时抛出。"""


class RetryExhaustedError(RuntimeError):
    """可重试的下单尝试耗尽时抛出。"""


class ExecutionEngine:
    """通过 Broker 提交 `TradeIntent`，并提供重试与幂等控制。"""

    def __init__(self, broker: BrokerAdapter, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self.broker = broker
        self.max_retries = max_retries
        self._submitted_action_ids: Set[str] = set()

    def submit(self, intent: TradeIntent, state: RuntimeState) -> Dict[str, object]:
        if intent.action_id in self._submitted_action_ids:
            raise DuplicateActionError(f"action_id '{intent.action_id}' already submitted")

        snapshot = intent.market_snapshot
        existing_position = self.broker.get_position(snapshot.symbol, snapshot.magic_number)
        if existing_position is not None:
            return {"success": False, "reason": "EXISTING_POSITION"}

        last_error_reason = "UNKNOWN"
        for _ in range(self.max_retries):
            result = self.broker.send_order(
                symbol=snapshot.symbol,
                magic=snapshot.magic_number,
                order_type=intent.signal_decision.order_type.value,
                volume=intent.signal_decision.lots,
                price=intent.signal_decision.entry_price,
                sl=intent.signal_decision.stop_loss,
                tp=intent.signal_decision.take_profit,
                slippage=intent.slippage if intent.slippage is not None else DEFAULT_SLIPPAGE,
                comment=intent.comment,
            )

            if bool(result.get("success", False)):
                self._submitted_action_ids.add(intent.action_id)
                state.trades_today += 1
                ticket = int(result.get("ticket", 0))
                state.position_ticket = ticket if ticket > 0 else None
                return result

            last_error_reason = str(result.get("reason", "UNKNOWN"))
            if not bool(result.get("retryable", False)):
                return result

        raise RetryExhaustedError(
            f"Order retry exhausted for action_id '{intent.action_id}': {last_error_reason}"
        )
