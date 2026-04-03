"""Broker adapter contract for MT5 and simulation backends."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class BrokerAdapter(ABC):
    """Unified interface used by core execution/orchestration modules."""

    @abstractmethod
    def connect(self) -> bool:
        """Initialize broker connection."""

    @abstractmethod
    def get_rates(self, symbol: str, timeframe: int, count: int) -> List[Dict[str, Any]]:
        """Fetch recent rates, newest last."""

    @abstractmethod
    def get_position(self, symbol: str, magic: int) -> Optional[Dict[str, Any]]:
        """Get current position for symbol+magic if present."""

    @abstractmethod
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
    ) -> Dict[str, Any]:
        """Submit a market order request."""

    @abstractmethod
    def modify_position(self, ticket: int, sl: float, tp: float) -> Dict[str, Any]:
        """Modify stop-loss / take-profit for active position."""

    @abstractmethod
    def close_position(
        self, ticket: int, close_price: float, closed_at: datetime
    ) -> Dict[str, Any]:
        """Close position and return close result."""

    @abstractmethod
    def get_closed_profit(self, day_key: str) -> float:
        """Get realized closed profit for a server-day key."""
