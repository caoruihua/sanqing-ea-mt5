"""Runtime configuration for trigger modes and tick ingress."""

from dataclasses import dataclass
from enum import Enum


class TriggerMode(Enum):
    """Trigger mode for runtime operation."""

    POLL = "poll"
    TICK_HTTP = "tick_http"

    @classmethod
    def from_string(cls, value: str) -> "TriggerMode":
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(
                f"Invalid trigger mode: {value}. Must be one of: {[m.value for m in cls]}"
            ) from None


@dataclass
class TriggerConfig:
    """Configuration for runtime trigger mode."""

    trigger_mode: TriggerMode
    symbol: str
    host: str = "127.0.0.1"
    port: int = 8765
    queue_policy: str = "fifo"

    def __post_init__(self) -> None:
        if not self.symbol or not isinstance(self.symbol, str) or len(self.symbol.strip()) == 0:
            raise ValueError("Invalid symbol: must be a non-empty string")
        if not self.host or not isinstance(self.host, str) or len(self.host.strip()) == 0:
            raise ValueError("Invalid host: must be a non-empty string")
        if not isinstance(self.port, int) or self.port <= 0 or self.port > 65535:
            raise ValueError("Invalid port: must be an integer between 1 and 65535")
        if self.queue_policy not in {"fifo", "latest-only"}:
            raise ValueError(
                f"Invalid queue policy: {self.queue_policy}. Supported values: fifo, latest-only"
            )

    @classmethod
    def from_string(cls, trigger_mode_str: str, symbol: str, **kwargs) -> "TriggerConfig":
        return cls(trigger_mode=TriggerMode.from_string(trigger_mode_str), symbol=symbol, **kwargs)
