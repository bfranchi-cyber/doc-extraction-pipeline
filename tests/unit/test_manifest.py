"""Unit tests for pipeline.manifest.ManifestStore."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.models import ManifestCorruptionError, ManifestRecord


def _record(file_id: str = "abc123", status: str = "success", error: str | None = None) -> ManifestRecord:
    return ManifestRecord(
        file_id=file_id,
        name="test_doc.docx",
        status=status,
        processed_at="2026-08-10T12:00:00+00:00",
        error=error,
    )


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

def test_get_returns_none_for_missing_file(tmp_path):
    from pipeline.manifest import ManifestStore
    store = ManifestStore(tmp_path / "manifests")
    assert store.get("nonexistent") is None


def test_get_raises_corruption_error_on_malformed_json(tmp_path):
    from pipeline.manifest import ManifestStore
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "badfile.json").write_text("NOT JSON", encoding="utf-8")
    store = ManifestStore(manifest_dir)
    with pytest.raises(ManifestCorruptionError):
        store.get("badfile")


# ---------------------------------------------------------------------------
# set() + get() round-trip (example-based)
# ---------------------------------------------------------------------------

def test_set_then_get_returns_equal_record(tmp_path):
    from pipeline.manifest import ManifestStore
    store = ManifestStore(tmp_path / "manifests")
    rec = _record("file001", "success")
    store.set("file001", rec)
    result = store.get("file001")
    assert result == rec


def test_set_overwrites_existing_record(tmp_path):
    from pipeline.manifest import ManifestStore
    store = ManifestStore(tmp_path / "manifests")
    store.set("file001", _record("file001", "success"))
    updated = _record("file001", "failed", error='{"error_type":"business","text":"bad","is_retriable":false,"suggestion":"fix it"}')
    store.set("file001", updated)
    result = store.get("file001")
    assert result is not None
    assert result.status == "failed"


def test_atomic_write_leaves_no_tmp_file(tmp_path):
    from pipeline.manifest import ManifestStore
    manifest_dir = tmp_path / "manifests"
    store = ManifestStore(manifest_dir)
    store.set("file001", _record())
    tmp_files = list(manifest_dir.glob("*.tmp"))
    assert tmp_files == []


# ---------------------------------------------------------------------------
# is_processed()
# ---------------------------------------------------------------------------

def test_is_processed_true_for_success(tmp_path):
    from pipeline.manifest import ManifestStore
    store = ManifestStore(tmp_path / "manifests")
    store.set("file001", _record("file001", "success"))
    assert store.is_processed("file001") is True


def test_is_processed_false_for_failed(tmp_path):
    from pipeline.manifest import ManifestStore
    store = ManifestStore(tmp_path / "manifests")
    store.set("file001", _record("file001", "failed", error="something went wrong"))
    assert store.is_processed("file001") is False


def test_is_processed_false_for_missing(tmp_path):
    from pipeline.manifest import ManifestStore
    store = ManifestStore(tmp_path / "manifests")
    assert store.is_processed("no_such_file") is False


def test_is_processed_propagates_corruption_error(tmp_path):
    from pipeline.manifest import ManifestStore
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "corrupt.json").write_text("{bad json", encoding="utf-8")
    store = ManifestStore(manifest_dir)
    with pytest.raises(ManifestCorruptionError):
        store.is_processed("corrupt")


# ---------------------------------------------------------------------------
# list_failed()
# ---------------------------------------------------------------------------

def test_list_failed_returns_only_failed_records(tmp_path):
    from pipeline.manifest import ManifestStore
    store = ManifestStore(tmp_path / "manifests")
    store.set("ok1",   _record("ok1",   "success"))
    store.set("ok2",   _record("ok2",   "success"))
    store.set("bad1",  _record("bad1",  "failed", error="err"))
    store.set("bad2",  _record("bad2",  "failed", error="err"))
    failed = store.list_failed()
    ids = {r.file_id for r in failed}
    assert ids == {"bad1", "bad2"}


def test_list_failed_returns_empty_when_no_failures(tmp_path):
    from pipeline.manifest import ManifestStore
    store = ManifestStore(tmp_path / "manifests")
    store.set("ok1", _record("ok1", "success"))
    assert store.list_failed() == []
