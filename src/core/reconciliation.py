"""
该文件负责启动时对账：对比持久化的运行时状态与 Broker 实际持仓。

主要职责：
1. 加载持久化状态后，与 MT5 实际持仓进行对账；
2. 处理持仓连续性（如持仓已平仓则清除状态）；
3. 确保系统重启后状态一致性。

说明：
- 对账在 Orchestrator 启动时执行；
- 若发现持仓已不存在，会重置相关保护状态。
"""

from typing import Any, Dict, Optional

from src.adapters.broker_base import BrokerAdapter
from src.domain.models import ProtectionState, RuntimeState


def reconcile_runtime_state(
    state: RuntimeState, broker_position: Optional[Dict[str, object]]
) -> RuntimeState:
    """将持久化状态与 Broker 实际持仓快照对齐。"""
    if broker_position is None:
        state.position_ticket = None
        state.protection_state = ProtectionState()
        return state

    ticket = broker_position.get("ticket")
    if isinstance(ticket, int):
        state.position_ticket = ticket
    return state


def load_and_reconcile(
    store: Any,
    broker: BrokerAdapter,
    symbol: str,
    magic: int,
) -> RuntimeState:
    """加载持久化状态，并在启动时对齐持仓连续性。"""
    state = store.load()
    broker_position = broker.get_position(symbol=symbol, magic=magic)
    return reconcile_runtime_state(state=state, broker_position=broker_position)
