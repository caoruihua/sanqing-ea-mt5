"""Integration tests for orchestrator fixed execution flow."""

import importlib
from datetime import datetime

import pytest

from src.adapters.broker_base import BrokerAdapter
from src.core.entry_gate import EntryGate
from src.core.strategy_selector import StrategySelector
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision
from src.strategies.base import BaseStrategy

_orchestrator = importlib.import_module("src.app.orchestrator")
_daily_risk_controller = importlib.import_module("src.core.daily_risk_controller")
_execution_engine = importlib.import_module("src.core.execution_engine")
_protection_engine = importlib.import_module("src.core.protection_engine")
_state_store = importlib.import_module("src.core.state_store")
_logger = importlib.import_module("src.utils.logger")

Orchestrator = _orchestrator.Orchestrator
ConnectFailedError = _orchestrator.ConnectFailedError
DailyRiskController = _daily_risk_controller.DailyRiskController
ExecutionEngine = _execution_engine.ExecutionEngine
ProtectionEngine = _protection_engine.ProtectionEngine
StateStore = _state_store.StateStore
StateStoreCorruptedError = _state_store.StateStoreCorruptedError
StructuredLogger = _logger.StructuredLogger


class _SignalStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "ExpansionFollow"

    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        return True

    def build_intent(self, snapshot: MarketSnapshot, state: RuntimeState):
        return SignalDecision(
            strategy_name=self.name,
            order_type=OrderType.BUY,
            entry_price=snapshot.ask,
            stop_loss=snapshot.ask - 8.0,
            take_profit=snapshot.ask + 15.0,
            atr_value=snapshot.atr14,
            lots=0.01,
        )


class _Broker(BrokerAdapter):
    def __init__(self, connect_ok: bool = True):
        self.connect_ok = connect_ok
        self.events = []
        self.position = None

    def connect(self) -> bool:
        self.events.append("connect")
        return self.connect_ok

    def get_rates(self, symbol: str, timeframe: int, count: int):
        return []

    def get_position(self, symbol: str, magic: int):
        self.events.append("get_position")
        return self.position

    def send_order(
        self,
        symbol: str,
        magic: int,
        order_type: str,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        slippage: int,
        comment: str,
    ):
        self.events.append("send_order")
        self.position = {
            "ticket": 1001,
            "symbol": symbol,
            "magic": magic,
            "order_type": order_type,
            "sl": sl,
            "tp": tp,
        }
        return {"success": True, "ticket": 1001, "retcode": 10009}

    def modify_position(self, ticket: int, sl: float, tp: float):
        self.events.append("modify_position")
        return {"success": True}

    def close_position(self, ticket: int, close_price: float, closed_at: datetime):
        self.events.append("close_position")
        return {"success": True}

    def get_closed_profit(self, day_key: str) -> float:
        self.events.append("get_closed_profit")
        return 0.0


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=20260313,
        bid=2350.0,
        ask=2350.3,
        ema_fast=2349.5,
        ema_slow=2348.0,
        atr14=5.0,
        spread_points=15.0,
        last_closed_bar_time=datetime(2026, 4, 3, 10, 0, 0),
        close=2350.2,
        open=2346.0,
        high=2352.0,
        low=2345.0,
        volume=1_500_000,
        ema_fast_prev3=2345.0,
        ema_slow_prev3=2344.0,
        high_prev2=2349.0,
        high_prev3=2348.5,
        low_prev2=2339.0,
        low_prev3=2338.5,
    )


def test_full_flow(tmp_path) -> None:
    broker = _Broker(connect_ok=True)
    logger = StructuredLogger(log_path=str(tmp_path / "runtime.log"))
    store = StateStore(str(tmp_path / "runtime_state.json"))
    state = RuntimeState(day_key="2026.04.03")

    orchestrator = Orchestrator(
        broker=broker,
        strategy_selector=StrategySelector(strategies=[_SignalStrategy()]),
        entry_gate=EntryGate(max_trades_per_day=30),
        execution_engine=ExecutionEngine(broker=broker, max_retries=2),
        protection_engine=ProtectionEngine(),
        daily_risk_controller=DailyRiskController(),
        state_store=store,
        logger=logger,
        state=state,
    )
    orchestrator.start()

    result = orchestrator.process_snapshot(_snapshot())

    assert result["success"] is True
    assert "send_order" in broker.events
    assert (tmp_path / "runtime_state.json").exists()


def test_broker_connect_fail(tmp_path) -> None:
    broker = _Broker(connect_ok=False)
    logger = StructuredLogger(log_path=str(tmp_path / "runtime.log"))
    orchestrator = Orchestrator(
        broker=broker,
        strategy_selector=StrategySelector(strategies=[_SignalStrategy()]),
        entry_gate=EntryGate(max_trades_per_day=30),
        execution_engine=ExecutionEngine(broker=broker, max_retries=2),
        protection_engine=ProtectionEngine(),
        daily_risk_controller=DailyRiskController(),
        state_store=StateStore(str(tmp_path / "runtime_state.json")),
        logger=logger,
        state=RuntimeState(day_key="2026.04.03"),
    )

    with pytest.raises(ConnectFailedError, match="CONNECT_FAILED"):
        orchestrator.start()


def test_start_fails_on_corrupted_state(tmp_path) -> None:
    state_path = tmp_path / "runtime_state.json"
    state_path.write_text("{invalid", encoding="utf-8")

    broker = _Broker(connect_ok=True)
    logger = StructuredLogger(log_path=str(tmp_path / "runtime.log"))
    orchestrator = Orchestrator(
        broker=broker,
        strategy_selector=StrategySelector(strategies=[_SignalStrategy()]),
        entry_gate=EntryGate(max_trades_per_day=30),
        execution_engine=ExecutionEngine(broker=broker, max_retries=2),
        protection_engine=ProtectionEngine(),
        daily_risk_controller=DailyRiskController(),
        state_store=StateStore(str(state_path)),
        logger=logger,
        state=RuntimeState(day_key="2026.04.03"),
    )

    with pytest.raises(StateStoreCorruptedError):
        orchestrator.start()
