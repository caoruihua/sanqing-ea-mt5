"""Startup reconciliation between persisted runtime state and broker reality."""

from typing import Any, Dict, Optional

from src.adapters.broker_base import BrokerAdapter
from src.domain.models import ProtectionState, RuntimeState


def reconcile_runtime_state(
    state: RuntimeState, broker_position: Optional[Dict[str, object]]
) -> RuntimeState:
    """Align persisted state with actual broker position snapshot."""
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
    """Load persisted state and reconcile position continuity at startup."""
    state = store.load()
    broker_position = broker.get_position(symbol=symbol, magic=magic)
    return reconcile_runtime_state(state=state, broker_position=broker_position)
