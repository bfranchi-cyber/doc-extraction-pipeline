"""Property-based tests for ManifestRecord serialization and ManifestStore invariants.

PBT-02: Round-trip — ManifestRecord.to_json() -> from_json() == original
PBT-03: Invariants — set()+get() returns matching record; is_processed() reflects status
PBT-07: Generator quality — file_id matches Google Drive ID format
PBT-08: Shrinking enabled — no suppress_health_check overrides that disable shrinking
PBT-09: Framework — hypothesis
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.models import ManifestRecord


# ---------------------------------------------------------------------------
# Generators (PBT-07: domain-appropriate, reusable)
# ---------------------------------------------------------------------------

# Google Drive file IDs: alphanumeric + hyphens + underscores, 10-44 chars
drive_file_ids = st.from_regex(r"[A-Za-z0-9_-]{10,44}", fullmatch=True)

manifest_statuses = st.sampled_from(["success", "failed"])

# error is None for success; a non-empty string for failed
error_strings = st.text(min_size=1, max_size=500)

processed_at_strings = st.just("2026-08-10T12:00:00+00:00")

document_names = st.text(min_size=1, max_size=200).map(lambda s: s.replace("\x00", ""))


def manifest_records(
    status_strategy=manifest_statuses,
) -> st.SearchStrategy[ManifestRecord]:
    """Reusable generator for ManifestRecord with realistic field values."""
    return st.builds(
        ManifestRecord,
        file_id=drive_file_ids,
        name=document_names,
        status=status_strategy,
        processed_at=processed_at_strings,
        error=st.none() | error_strings,
    )


# ---------------------------------------------------------------------------
# PBT-02: Round-trip property
# ---------------------------------------------------------------------------

@given(record=manifest_records())
@settings(max_examples=100)
def test_manifest_record_json_round_trip(record: ManifestRecord) -> None:
    """Serializing then deserializing a ManifestRecord yields the original value."""
    serialized = record.to_json()
    restored = ManifestRecord.from_json(serialized)
    assert restored == record


# ---------------------------------------------------------------------------
# PBT-03: ManifestStore invariants
# ---------------------------------------------------------------------------

@given(record=manifest_records())
@settings(max_examples=100)
def test_set_then_get_returns_matching_record(record: ManifestRecord) -> None:
    """After set(), get() returns a record with the same file_id and status."""
    from pipeline.manifest import ManifestStore
    with tempfile.TemporaryDirectory() as d:
        store = ManifestStore(Path(d) / "manifests")
        store.set(record.file_id, record)
        result = store.get(record.file_id)
    assert result is not None
    assert result.file_id == record.file_id
    assert result.status == record.status


@given(record=manifest_records(status_strategy=st.just("success")))
@settings(max_examples=100)
def test_is_processed_true_after_success_set(record: ManifestRecord) -> None:
    """is_processed() returns True after setting a success record."""
    from pipeline.manifest import ManifestStore
    with tempfile.TemporaryDirectory() as d:
        store = ManifestStore(Path(d) / "manifests")
        store.set(record.file_id, record)
        assert store.is_processed(record.file_id) is True


@given(record=manifest_records(status_strategy=st.just("failed")))
@settings(max_examples=100)
def test_is_processed_false_after_failed_set(record: ManifestRecord) -> None:
    """is_processed() returns False after setting a failed record."""
    from pipeline.manifest import ManifestStore
    with tempfile.TemporaryDirectory() as d:
        store = ManifestStore(Path(d) / "manifests")
        store.set(record.file_id, record)
        assert store.is_processed(record.file_id) is False
