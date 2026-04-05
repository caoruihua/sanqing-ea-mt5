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

from typing import Dict, Optional, Set

from src.adapters.broker_base import BrokerAdapter
from src.domain.constants import DEFAULT_MAX_RETRIES, DEFAULT_SLIPPAGE
from src.domain.models import RuntimeState, TradeIntent
from src.utils.logger import StructuredLogger


class DuplicateActionError(ValueError):
    """同一个 action_id 被重复提交时抛出。"""


class RetryExhaustedError(RuntimeError):
    """可重试的下单尝试耗尽时抛出。"""


class ExecutionEngine:
    """通过 Broker 提交 `TradeIntent`，并提供重试与幂等控制。"""

    def __init__(
        self,
        broker: BrokerAdapter,
        max_retries: int = DEFAULT_MAX_RETRIES,
        logger: Optional[StructuredLogger] = None,
    ) -> None:
        self.broker = broker
        self.max_retries = max_retries
        self.logger = logger
        self._submitted_action_ids: Set[str] = set()

    def _get_current_price(self, symbol: str, order_type: str) -> float:
        """获取当前市场价格用于重试下单。

        Args:
            symbol: 交易品种
            order_type: BUY 或 SELL

        Returns:
            当前市场价格（BUY用ask，SELL用bid）
        """
        import importlib

        try:
            mt5 = importlib.import_module("MetaTrader5")
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return 0.0
            return float(tick.ask) if order_type == "BUY" else float(tick.bid)
        except Exception:
            return 0.0

    def submit(self, intent: TradeIntent, state: RuntimeState) -> Dict[str, object]:
        if intent.action_id in self._submitted_action_ids:
            raise DuplicateActionError(f"action_id '{intent.action_id}' already submitted")

        snapshot = intent.market_snapshot
        existing_position = self.broker.get_position(snapshot.symbol, snapshot.magic_number)
        if existing_position is not None:
            return {"success": False, "reason": "EXISTING_POSITION"}

        last_error_reason = "UNKNOWN"
        for attempt in range(self.max_retries):
            # 重试时更新价格（第一次使用信号价格，后续获取最新价格）
            if attempt == 0:
                entry_price = intent.signal_decision.entry_price
            else:
                entry_price = self._get_current_price(
                    snapshot.symbol, intent.signal_decision.order_type.value
                )
                # 如果获取价格失败，使用原价格
                if entry_price <= 0:
                    entry_price = intent.signal_decision.entry_price

            result = self.broker.send_order(
                symbol=snapshot.symbol,
                magic=snapshot.magic_number,
                order_type=intent.signal_decision.order_type.value,
                volume=intent.signal_decision.lots,
                price=entry_price,
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
                # 保存策略名称到状态，用于后续保护日志
                state.position_strategy = intent.signal_decision.strategy_name
                # 记录开仓成功日志
                if self.logger is not None:
                    strategy_name = intent.signal_decision.strategy_name
                    event_name = f"{strategy_name}_order_filled"
                    self.logger.info(
                        event_name,
                        strategy_name=strategy_name,
                        symbol=snapshot.symbol,
                        order_type=intent.signal_decision.order_type.value,
                        entry_price=entry_price,
                        original_price=intent.signal_decision.entry_price,
                        lots=intent.signal_decision.lots,
                        stop_loss=intent.signal_decision.stop_loss,
                        take_profit=intent.signal_decision.take_profit,
                        ticket=ticket,
                        action_id=intent.action_id,
                        retry_count=attempt,
                    )
                return result

            last_error_reason = str(result.get("reason", "UNKNOWN"))
            if not bool(result.get("retryable", False)):
                # 记录开仓失败日志（不可重试错误）
                if self.logger is not None:
                    strategy_name = intent.signal_decision.strategy_name
                    self.logger.error(
                        "order_rejected",
                        strategy_name=strategy_name,
                        symbol=snapshot.symbol,
                        order_type=intent.signal_decision.order_type.value,
                        attempted_price=entry_price,
                        reason=last_error_reason,
                        retryable=False,
                        action_id=intent.action_id,
                    )
                return result

        # 记录重试耗尽日志
        if self.logger is not None:
            strategy_name = intent.signal_decision.strategy_name
            self.logger.error(
                "order_retry_exhausted",
                strategy_name=strategy_name,
                symbol=snapshot.symbol,
                order_type=intent.signal_decision.order_type.value,
                reason=last_error_reason,
                max_retries=self.max_retries,
                action_id=intent.action_id,
            )
        raise RetryExhaustedError(
            f"Order retry exhausted for action_id '{intent.action_id}': {last_error_reason}"
        )
