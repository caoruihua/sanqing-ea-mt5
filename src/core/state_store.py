"""JSON runtime state persistence with atomic writes."""

import json
import os
from pathlib import Path

from src.domain.models import RuntimeState


class StateStoreError(RuntimeError):
    """Base state store error."""


class StateStoreNotFoundError(StateStoreError):
    """Raised when state file does not exist yet."""


class StateStoreCorruptedError(StateStoreError):
    """Raised when persisted state file is unreadable or invalid."""


class StateStore:
    """Persist RuntimeState to disk with temp-file + replace semantics."""

    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)

    def save(self, state: RuntimeState) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = state.to_json()

        tmp_path = self.file_path.with_suffix(f"{self.file_path.suffix}.tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, self.file_path)

    def load(self) -> RuntimeState:
        if not self.file_path.exists():
            raise StateStoreNotFoundError(f"State file not found: {self.file_path}")

        try:
            text = self.file_path.read_text(encoding="utf-8")
            data = json.loads(text)
        except Exception as exc:  # noqa: BLE001 - normalize into domain-specific error
            raise StateStoreCorruptedError(f"Corrupted state file: {self.file_path}") from exc

        try:
            return RuntimeState.from_dict(data)
        except Exception as exc:  # noqa: BLE001 - normalize into domain-specific error
            raise StateStoreCorruptedError(f"Invalid state payload: {self.file_path}") from exc
