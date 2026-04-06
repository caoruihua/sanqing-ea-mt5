"""Poll-based tick ingress implementation."""

import time
from typing import Optional

from src.app.tick_ingress import TickIngress, TickWakeupPayload


class PollIngress(TickIngress):
    """Poll-based ingress that uses `time.sleep` for wake-ups."""

    def __init__(self, poll_interval_seconds: float = 2.0, symbol: str = "XAUUSD") -> None:
        self.poll_interval = max(poll_interval_seconds, 0.1)
        self.symbol = symbol
        self._running = False
        self._sequence = 0

    def start(self) -> None:
        self._running = True
        self._sequence = 0

    def wait(self) -> Optional[TickWakeupPayload]:
        if not self._running:
            return None
        time.sleep(self.poll_interval)
        if not self._running:
            return None

        self._sequence += 1
        current_time_ms = int(time.time() * 1000)
        return TickWakeupPayload(
            symbol=self.symbol,
            closed_bar_time=current_time_ms // 1000,
            time_msc=current_time_ms,
            bid=1950.0,
            ask=1950.1,
            sequence=self._sequence,
        )

    def stop(self) -> None:
        self._running = False
