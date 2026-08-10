from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class Scratchpad:
    """Writes structured JSONL log entries to a local file.

    Each entry is a single JSON object on its own line:
        {"ts": "...", "level": "INFO"|"WARN"|"ERROR", "msg": "...", "context": {...}}

    The file is opened in append mode on every write — no persistent file handle.
    The file is not created until the first write.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def info(self, msg: str, context: dict | None = None) -> None:
        self._write("INFO", msg, context)

    def warn(self, msg: str, context: dict | None = None) -> None:
        self._write("WARN", msg, context)

    def error(self, msg: str, context: dict | None = None) -> None:
        self._write("ERROR", msg, context)

    def _write(self, level: str, msg: str, context: dict | None) -> None:
        entry: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "msg": msg,
        }
        if context is not None:
            entry["context"] = context
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
