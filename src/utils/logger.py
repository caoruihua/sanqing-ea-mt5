"""Structured JSON-lines logger for runtime events."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class StructuredLogger:
    """Write structured runtime events to a log file."""

    def __init__(self, log_path: str) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def info(self, event: str, **fields: Any) -> None:
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "event": event,
        }
        payload.update(fields)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
