"""
该文件负责把“策略分析 -> 门控 -> 发单 -> 持久化”串成一条固定顺序的主流程。

主要职责：
1. 启动时连接 broker，并加载/恢复运行状态；
2. 对每一个市场快照按固定顺序执行：日风险更新、保护处理、策略选择、入场门控、执行下单；
3. 在关键节点写结构化日志，并把运行状态落盘；
4. 保证整条链路的执行顺序稳定、可追踪。

注意事项：
- 本文件不直接计算指标；
- 本文件不直接拼装 MT5 request；
- 它只负责把各个核心模块按既定顺序串起来。
"""

import importlib
from typing import Any, Dict

from src.adapters.broker_base import BrokerAdapter
from src.core.entry_gate import EntryGate
from src.core.strategy_selector import StrategySelector
from src.domain.constants import DEFAULT_MAGIC_NUMBER, DEFAULT_SYMBOL
from src.domain.models import OrderType, RuntimeState

_daily_risk_controller = importlib.import_module("src.core.daily_risk_controller")
_execution_engine = importlib.import_module("src.core.execution_engine")
_protection_engine = importlib.import_module("src.core.protection_engine")
_reconciliation = importlib.import_module("src.core.reconciliation")
_state_store = importlib.import_module("src.core.state_store")
_logger = importlib.import_module("src.utils.logger")

DailyRiskController = _daily_risk_controller.DailyRiskController
ExecutionEngine = _execution_engine.ExecutionEngine
ProtectionEngine = _protection_engine.ProtectionEngine
load_and_reconcile = _reconciliation.load_and_reconcile
StateStore = _state_store.StateStore
StateStoreCorruptedError = _state_store.StateStoreCorruptedError
StateStoreNotFoundError = _state_store.StateStoreNotFoundError
StructuredLogger = _logger.StructuredLogger


class ConnectFailedError(RuntimeError):
    """启动时 Broker 初始化失败时抛出。"""


class Orchestrator:
    """协调快照处理、风险控制、保护、信号、门控、执行与持久化流程。"""

    def __init__(
        self,
        broker: BrokerAdapter,
        strategy_selector: StrategySelector,
        entry_gate: EntryGate,
        execution_engine: ExecutionEngine,
        protection_engine: ProtectionEngine,
        daily_risk_controller: DailyRiskController,
        state_store: StateStore,
        logger: StructuredLogger,
        state: RuntimeState,
        symbol: str = DEFAULT_SYMBOL,
        magic: int = DEFAULT_MAGIC_NUMBER,
    ) -> None:
        self.broker = broker
        self.strategy_selector = strategy_selector
        self.entry_gate = entry_gate
        self.execution_engine = execution_engine
        self.protection_engine = protection_engine
        self.daily_risk_controller = daily_risk_controller
        self.state_store = state_store
        self.logger = logger
        self.state = state
        self.symbol = symbol
        self.magic = magic

    def start(self) -> None:
        connected = self.broker.connect()
        if not connected:
            detail = getattr(self.broker, "last_connect_error", None) or "CONNECT_FAILED"
            self.logger.info("connect_failed", 原因="CONNECT_FAILED", 详情=detail)
            raise ConnectFailedError(f"CONNECT_FAILED: {detail}")

        try:
            self.state = load_and_reconcile(
                store=self.state_store,
                broker=self.broker,
                symbol=self.symbol,
                magic=self.magic,
            )
            self.logger.info("state_loaded", 日期=self.state.day_key)
        except StateStoreNotFoundError:
            # 当状态文件不存在时，允许系统首次启动。
            self.logger.info("state_missing", 日期=self.state.day_key)
        except StateStoreCorruptedError as exc:
            self.logger.info("state_corrupted", 原因=str(exc))
            raise

    def process_snapshot(self, snapshot) -> Dict[str, Any]:
        trace = []

        trace.append("build_snapshot")
        day_key = snapshot.last_closed_bar_time.strftime("%Y.%m.%d")
        profit = self.broker.get_closed_profit(day_key)

        trace.append("update_daily_risk")
        self.daily_risk_controller.update(snapshot.last_closed_bar_time, self.state, profit)

        position = self.broker.get_position(snapshot.symbol, snapshot.magic_number)

        # 检测持仓消失（平仓）
        self._detect_position_close(position, snapshot)

        trace.append("protection")
        self._process_protection(position=position, snapshot=snapshot)

        trace.append("new_bar_check")
        if self.state.last_processed_bar_time == snapshot.last_closed_bar_time:
            self.state_store.save(self.state)
            return {"success": False, "reason": "NOT_NEW_CLOSED_BAR", "trace": trace}
        self.state.last_processed_bar_time = snapshot.last_closed_bar_time

        trace.append("strategy_select")
        selection = self.strategy_selector.select(snapshot, self.state)
        if selection.intent is None:
            self.state_store.save(self.state)
            return {
                "success": False,
                "reason": selection.rejection_reason,
                "trace": trace,
            }

        trace.append("gate_check")
        gate_result = self.entry_gate.evaluate(
            signal=selection.intent,
            snapshot=snapshot,
            state=self.state,
            has_existing_position=position is not None,
            strategy_can_trade=True,
        )
        if gate_result.intent is None:
            self.state_store.save(self.state)
            return {"success": False, "reason": gate_result.reason_code, "trace": trace}

        trace.append("execute")
        exec_result = self.execution_engine.submit(gate_result.intent, self.state)

        trace.append("persist")
        self.state_store.save(self.state)
        self.logger.info(
            "tick_processed", 是否成功=bool(exec_result.get("success", False)), 追踪=trace
        )

        return {
            "success": bool(exec_result.get("success", False)),
            "result": exec_result,
            "trace": trace,
        }

    def _process_protection(self, position, snapshot) -> None:
        if position is None:
            return

        ps = self.state.protection_state
        if ps.entry_price is None or ps.entry_atr is None:
            return

        order_type = self._resolve_position_order_type(position)
        decision = self.protection_engine.evaluate(
            order_type=order_type,
            snapshot=snapshot,
            state=self.state,
            current_sl=float(position.get("sl", 0.0)),
            current_tp=float(position.get("tp", 0.0)),
        )
        if (
            decision.action == "modify"
            and decision.new_sl is not None
            and decision.new_tp is not None
        ):
            current_sl = float(position.get("sl", 0.0))
            current_tp = float(position.get("tp", 0.0))
            if not self._protection_levels_changed(
                current_sl=current_sl,
                current_tp=current_tp,
                new_sl=decision.new_sl,
                new_tp=decision.new_tp,
            ):
                # 保护未变更，使用策略名前缀
                strategy = self.state.position_strategy or "unknown"
                self.logger.info(
                    f"{strategy}_protection_unchanged",
                    订单号=int(position["ticket"]),
                    策略=strategy,
                )
                return
            self.broker.modify_position(
                ticket=int(position["ticket"]), sl=decision.new_sl, tp=decision.new_tp
            )
            # 保护已修改，使用策略名前缀
            strategy = self.state.position_strategy or "unknown"
            ps = self.state.protection_state
            stage = ps.protection_stage.value if ps.protection_stage else 0
            self.logger.info(
                f"{strategy}_protection_modified",
                订单号=int(position["ticket"]),
                策略=strategy,
                阶段=stage,
                原止损=current_sl,
                新止损=decision.new_sl,
                原止盈=current_tp,
                新止盈=decision.new_tp,
            )

    @staticmethod
    def _protection_levels_changed(
        *, current_sl: float, current_tp: float, new_sl: float, new_tp: float
    ) -> bool:
        return abs(current_sl - new_sl) > 1e-9 or abs(current_tp - new_tp) > 1e-9

    @staticmethod
    def _resolve_position_order_type(position: Dict[str, Any]) -> OrderType:
        order_type = position.get("order_type")
        if order_type == "BUY":
            return OrderType.BUY
        if order_type == "SELL":
            return OrderType.SELL
        if int(position.get("type", 1)) == 0:
            return OrderType.BUY
        return OrderType.SELL

    def _detect_position_close(self, position, snapshot) -> None:
        """检测持仓是否消失（被平仓），并记录平仓日志。"""
        last_ticket = self.state.last_position_ticket
        current_ticket = self.state.position_ticket

        # 如果有历史持仓记录但当前无持仓，说明持仓被平仓了
        if last_ticket is not None and position is None:
            # 查询最近平仓成交记录
            from datetime import datetime, timedelta

            since = datetime.now() - timedelta(minutes=5)  # 查询最近5分钟

            if hasattr(self.broker, "get_last_closed_deal"):
                deal = self.broker.get_last_closed_deal(last_ticket, since)
                if deal is not None:
                    close_price = deal.get("price", 0.0)
                    pnl = deal.get("profit", 0.0)

                    # 判断平仓原因（需要根据之前持仓的SL/TP判断）
                    # 这里简化处理，实际应该传入之前持仓的SL/TP
                    close_reason = self._determine_close_reason(close_price)

                    self.logger.info(
                        f"{close_reason}_position_closed",
                        订单号=last_ticket,
                        平仓价=close_price,
                        平仓原因=close_reason,
                        盈亏=pnl,
                        品种=snapshot.symbol,
                    )

            # 清除历史持仓记录
            self.state.last_position_ticket = None

        # 更新历史持仓记录
        if current_ticket is not None:
            self.state.last_position_ticket = current_ticket

    def _determine_close_reason(self, close_price: float) -> str:
        """根据平仓价格判断平仓原因。

        注意：这是一个简化版本，实际应该根据持仓的SL/TP价格精确判断。
        """
        # 由于当前上下文没有持仓的SL/TP信息，返回UNKNOWN
        # 实际使用时可以通过其他方式传入
        return "UNKNOWN"
