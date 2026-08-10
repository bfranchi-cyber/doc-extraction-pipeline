"""Unit tests for pipeline.scratchpad.Scratchpad."""
from __future__ import annotations

import json
from pathlib import Path


def _read_entries(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").strip().splitlines()]


def test_info_writes_valid_jsonl_entry(tmp_path):
    from pipeline.scratchpad import Scratchpad
    log = tmp_path / "scratchpad.log"
    sp = Scratchpad(log)
    sp.info("pipeline started")
    entries = _read_entries(log)
    assert len(entries) == 1
    assert entries[0]["level"] == "INFO"
    assert entries[0]["msg"] == "pipeline started"
    assert "ts" in entries[0]


def test_warn_writes_warn_level(tmp_path):
    from pipeline.scratchpad import Scratchpad
    log = tmp_path / "scratchpad.log"
    Scratchpad(log).warn("category mismatch")
    entry = _read_entries(log)[0]
    assert entry["level"] == "WARN"


def test_error_writes_error_level(tmp_path):
    from pipeline.scratchpad import Scratchpad
    log = tmp_path / "scratchpad.log"
    Scratchpad(log).error("something failed")
    entry = _read_entries(log)[0]
    assert entry["level"] == "ERROR"


def test_context_included_when_provided(tmp_path):
    from pipeline.scratchpad import Scratchpad
    log = tmp_path / "scratchpad.log"
    Scratchpad(log).info("processing file", context={"file_id": "abc123"})
    entry = _read_entries(log)[0]
    assert entry["context"] == {"file_id": "abc123"}


def test_context_omitted_when_none(tmp_path):
    from pipeline.scratchpad import Scratchpad
    log = tmp_path / "scratchpad.log"
    Scratchpad(log).info("no context here")
    entry = _read_entries(log)[0]
    assert "context" not in entry


def test_multiple_writes_append_not_overwrite(tmp_path):
    from pipeline.scratchpad import Scratchpad
    log = tmp_path / "scratchpad.log"
    sp = Scratchpad(log)
    sp.info("first")
    sp.warn("second")
    sp.error("third")
    entries = _read_entries(log)
    assert len(entries) == 3
    assert entries[0]["msg"] == "first"
    assert entries[1]["msg"] == "second"
    assert entries[2]["msg"] == "third"


def test_each_entry_is_valid_json(tmp_path):
    from pipeline.scratchpad import Scratchpad
    log = tmp_path / "scratchpad.log"
    sp = Scratchpad(log)
    sp.info("a")
    sp.warn("b", context={"key": "value"})
    for line in log.read_text(encoding="utf-8").strip().splitlines():
        parsed = json.loads(line)
        assert "ts" in parsed
        assert "level" in parsed
        assert "msg" in parsed
