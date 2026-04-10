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

    def _validate_order_params(self, intent: TradeIntent) -> Optional[str]:
        """验证订单参数有效性。

        Returns:
            错误信息，如果验证通过返回 None
        """
        signal = intent.signal_decision

        # 价格检查
        if signal.entry_price <= 0:
            return f"Invalid entry_price: {signal.entry_price}"

        # 止损检查
        if signal.stop_loss <= 0:
            return f"Invalid stop_loss: {signal.stop_loss}"

        # 止盈检查
        if signal.take_profit <= 0:
            return f"Invalid take_profit: {signal.take_profit}"

        # 手数检查
        if signal.lots <= 0:
            return f"Invalid lots: {signal.lots}"

        # 多空方向与止损止盈逻辑检查
        if signal.order_type.value == "BUY":
            if signal.stop_loss >= signal.entry_price:
                return f"BUY stop_loss ({signal.stop_loss}) must be below entry ({signal.entry_price})"
            if signal.take_profit <= signal.entry_price:
                return f"BUY take_profit ({signal.take_profit}) must be above entry ({signal.entry_price})"
        else:  # SELL
            if signal.stop_loss <= signal.entry_price:
                return f"SELL stop_loss ({signal.stop_loss}) must be above entry ({signal.entry_price})"
            if signal.take_profit >= signal.entry_price:
                return f"SELL take_profit ({signal.take_profit}) must be below entry ({signal.entry_price})"

        return None

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
        snapshot = intent.market_snapshot
        strategy_name = intent.signal_decision.strategy_name
        order_type = intent.signal_decision.order_type.value

        # 1. 幂等检查
        if intent.action_id in self._submitted_action_ids:
            if self.logger is not None:
                self.logger.warning(
                    "order_duplicate_blocked",
                    策略名称=strategy_name,
                    动作ID=intent.action_id,
                )
            raise DuplicateActionError(f"action_id '{intent.action_id}' already submitted")

        # 2. 持仓检查
        existing_position = self.broker.get_position(snapshot.symbol, snapshot.magic_number)
        if existing_position is not None:
            if self.logger is not None:
                self.logger.warning(
                    "order_blocked_existing_position",
                    策略名称=strategy_name,
                    品种=snapshot.symbol,
                    现有持仓单号=int(existing_position.get("ticket", 0)),
                )
            return {"success": False, "reason": "EXISTING_POSITION"}

        # 3. 订单参数预检查
        validation_error = self._validate_order_params(intent)
        if validation_error:
            if self.logger is not None:
                self.logger.error(
                    "order_validation_failed",
                    策略名称=strategy_name,
                    品种=snapshot.symbol,
                    错误信息=validation_error,
                    入场价=intent.signal_decision.entry_price,
                    止损=intent.signal_decision.stop_loss,
                    止盈=intent.signal_decision.take_profit,
                )
            return {"success": False, "reason": f"VALIDATION_FAILED: {validation_error}"}

        # 4. 记录下单尝试开始
        if self.logger is not None:
            self.logger.info(
                "order_submit_started",
                策略名称=strategy_name,
                品种=snapshot.symbol,
                订单类型=order_type,
                入场价=intent.signal_decision.entry_price,
                手数=intent.signal_decision.lots,
                止损=intent.signal_decision.stop_loss,
                止盈=intent.signal_decision.take_profit,
                动作ID=intent.action_id,
                最大重试次数=self.max_retries,
            )

        last_error_reason = "UNKNOWN"
        for attempt in range(self.max_retries):
            # 重试时更新价格（第一次使用信号价格，后续获取最新价格）
            if attempt == 0:
                entry_price = intent.signal_decision.entry_price
            else:
                entry_price = self._get_current_price(
                    snapshot.symbol, order_type
                )
                # 如果获取价格失败，使用原价格
                if entry_price <= 0:
                    entry_price = intent.signal_decision.entry_price
                    if self.logger is not None:
                        self.logger.warning(
                            "order_price_refresh_failed",
                            策略名称=strategy_name,
                            尝试次数=attempt,
                            回退价格=entry_price,
                        )
                else:
                    if self.logger is not None:
                        self.logger.info(
                            "order_price_refreshed",
                            策略名称=strategy_name,
                            尝试次数=attempt,
                            新价格=entry_price,
                            原价格=intent.signal_decision.entry_price,
                        )

            # 记录每次尝试
            if self.logger is not None:
                self.logger.info(
                    "order_attempt",
                    策略名称=strategy_name,
                    尝试次数=attempt + 1,
                    最大重试次数=self.max_retries,
                    入场价=entry_price,
                    订单类型=order_type,
                )

            result = self.broker.send_order(
                symbol=snapshot.symbol,
                magic=snapshot.magic_number,
                order_type=order_type,
                volume=intent.signal_decision.lots,
                price=entry_price,
                sl=intent.signal_decision.stop_loss,
                tp=intent.signal_decision.take_profit,
                slippage=intent.slippage if intent.slippage is not None else DEFAULT_SLIPPAGE,
                comment=intent.comment or f"{strategy_name}|{intent.action_id[:8]}",
            )

            # 记录MT5返回结果
            if self.logger is not None:
                self.logger.info(
                    "order_attempt_result",
                    策略名称=strategy_name,
                    尝试次数=attempt + 1,
                    是否成功=result.get("success"),
                    返回码=result.get("retcode"),
                    原因=result.get("reason"),
                    可重试=result.get("retryable"),
                    订单号=result.get("ticket"),
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
                        策略名称=strategy_name,
                        品种=snapshot.symbol,
                        订单类型=intent.signal_decision.order_type.value,
                        入场价=entry_price,
                        原价格=intent.signal_decision.entry_price,
                        手数=intent.signal_decision.lots,
                        止损=intent.signal_decision.stop_loss,
                        止盈=intent.signal_decision.take_profit,
                        订单号=ticket,
                        动作ID=intent.action_id,
                        重试次数=attempt,
                    )
                return result

            last_error_reason = str(result.get("reason", "UNKNOWN"))
            if not bool(result.get("retryable", False)):
                # 记录开仓失败日志（不可重试错误）
                if self.logger is not None:
                    strategy_name = intent.signal_decision.strategy_name
                    self.logger.error(
                        "order_rejected",
                        策略名称=strategy_name,
                        品种=snapshot.symbol,
                        订单类型=intent.signal_decision.order_type.value,
                        尝试价格=entry_price,
                        原因=last_error_reason,
                        可重试=False,
                        动作ID=intent.action_id,
                    )
                return result

        # 记录重试耗尽日志
        if self.logger is not None:
            strategy_name = intent.signal_decision.strategy_name
            self.logger.error(
                "order_retry_exhausted",
                策略名称=strategy_name,
                品种=snapshot.symbol,
                订单类型=intent.signal_decision.order_type.value,
                原因=last_error_reason,
                最大重试次数=self.max_retries,
                动作ID=intent.action_id,
            )
        raise RetryExhaustedError(
            f"Order retry exhausted for action_id '{intent.action_id}': {last_error_reason}"
        )
