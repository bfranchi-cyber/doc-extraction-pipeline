from __future__ import annotations

import os
from pathlib import Path

from pipeline.models import ManifestCorruptionError, ManifestRecord


class ManifestStore:
    """Per-document idempotency store.

    Each Drive document is tracked by a JSON file named {file_id}.json in manifest_dir.
    Writes are atomic: content is first written to a .tmp file then renamed to the final path,
    preventing partial writes from leaving a corrupted manifest on disk.
    """

    def __init__(self, manifest_dir: Path) -> None:
        self._dir = manifest_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def get(self, file_id: str) -> ManifestRecord | None:
        """Return the manifest record for file_id, or None if it does not exist.

        Raises ManifestCorruptionError if the file exists but contains malformed JSON.
        """
        path = self._path(file_id)
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        try:
            return ManifestRecord.from_json(raw)
        except Exception:
            raise ManifestCorruptionError(file_id)

    def set(self, file_id: str, record: ManifestRecord) -> None:
        """Write record to disk atomically (write-temp-rename pattern)."""
        final = self._path(file_id)
        tmp = self._dir / f"{file_id}.json.tmp"
        tmp.write_text(record.to_json(), encoding="utf-8")
        os.replace(tmp, final)

    def is_processed(self, file_id: str) -> bool:
        """Return True if and only if a 'success' manifest record exists for file_id.

        Propagates ManifestCorruptionError — callers must handle it explicitly.
        """
        record = self.get(file_id)
        if record is None:
            return False
        return record.status == "success"

    def list_failed(self) -> list[ManifestRecord]:
        """Return all manifest records with status == 'failed'."""
        failed = []
        for json_file in self._dir.glob("*.json"):
            file_id = json_file.stem
            record = self.get(file_id)
            if record is not None and record.status == "failed":
                failed.append(record)
        return failed

    def _path(self, file_id: str) -> Path:
        return self._dir / f"{file_id}.json"
