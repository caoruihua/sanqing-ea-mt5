"""
该文件提供结构化的 JSON 行格式日志记录器。

主要职责：
1. 将运行时事件以结构化 JSON 格式写入日志文件；
2. 支持带字段的日志记录，方便后续分析；
3. 自动创建日志目录。

说明：
- 日志格式为 JSON Lines（每行一个 JSON 对象）；
- 包含时间戳、日志级别、事件类型和自定义字段。
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class StructuredLogger:
    """将结构化运行时事件写入日志文件。"""

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
