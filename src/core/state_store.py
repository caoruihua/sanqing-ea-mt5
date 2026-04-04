"""
该文件负责运行时状态的 JSON 持久化，使用原子写入保证数据完整性。

主要职责：
1. 将 RuntimeState 序列化为 JSON 并写入磁盘；
2. 使用临时文件+重命名的方式实现原子写入；
3. 支持加载持久化状态，处理文件不存在或损坏的情况。

说明：
- 状态文件路径由配置指定（默认 state/runtime_state.json）；
- 原子写入确保即使在写入过程中程序崩溃，也不会损坏已有状态文件。
"""

import json
import os
from pathlib import Path

from src.domain.models import RuntimeState


class StateStoreError(RuntimeError):
    """状态存储基础错误。"""


class StateStoreNotFoundError(StateStoreError):
    """状态文件不存在时抛出。"""


class StateStoreCorruptedError(StateStoreError):
    """状态文件损坏或无法解析时抛出。"""


class StateStore:
    """使用临时文件加替换语义将 `RuntimeState` 持久化到磁盘。"""

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
        except Exception as exc:  # noqa: BLE001 - 统一转换为领域层错误
            raise StateStoreCorruptedError(f"Corrupted state file: {self.file_path}") from exc

        try:
            return RuntimeState.from_dict(data)
        except Exception as exc:  # noqa: BLE001 - 统一转换为领域层错误
            raise StateStoreCorruptedError(f"Invalid state payload: {self.file_path}") from exc
