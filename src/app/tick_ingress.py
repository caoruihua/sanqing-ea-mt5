"""Tick ingress abstraction for runtime driver."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TickWakeupPayload:
    """Lightweight wake-up payload for tick events."""

    symbol: str
    closed_bar_time: int
    time_msc: int
    bid: float
    ask: float
    sequence: int

    def __post_init__(self) -> None:
        if not self.symbol or not isinstance(self.symbol, str) or len(self.symbol.strip()) == 0:
            raise ValueError("Invalid symbol: must be a non-empty string")
        if not isinstance(self.closed_bar_time, int) or self.closed_bar_time <= 0:
            raise ValueError("Invalid closed_bar_time: must be a positive integer")
        if not isinstance(self.time_msc, int) or self.time_msc <= 0:
            raise ValueError("Invalid time_msc: must be a positive integer")
        if not isinstance(self.bid, (int, float)) or self.bid <= 0:
            raise ValueError("Invalid bid: must be a positive number")
        if not isinstance(self.ask, (int, float)) or self.ask <= 0:
            raise ValueError("Invalid ask: must be a positive number")
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("Invalid sequence: must be a non-negative integer")
        if self.ask <= self.bid:
            raise ValueError("Invalid prices: ask must be greater than bid")


class TickIngress(ABC):
    """Abstract base class for runtime wake-up sources."""

    @abstractmethod
    def start(self) -> None:
        """Start the ingress."""

    @abstractmethod
    def wait(self) -> Optional[TickWakeupPayload]:
        """Wait for the next wake-up payload, or `None` after stop."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the ingress."""
