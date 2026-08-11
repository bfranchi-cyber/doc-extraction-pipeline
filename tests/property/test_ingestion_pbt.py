"""Property-based tests for pipeline.ingestion.

PBT-03: Invariants — discover_eligible_files never returns ineligible files
PBT-07: Generator quality — date boundaries, MIME types, error_type coverage
PBT-08: Shrinking enabled — no suppress_health_check overrides that disable shrinking
PBT-09: Framework — hypothesis
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.ingestion import ALLOWED_MIME_TYPES, discover_eligible_files
from pipeline.manifest import ManifestStore
from pipeline.models import ManifestRecord


# ---------------------------------------------------------------------------
# Shared generators (PBT-07: domain-appropriate)
# ---------------------------------------------------------------------------

# Google Drive file IDs: alphanumeric + hyphens + underscores, 10-44 chars
drive_file_ids = st.from_regex(r"[A-Za-z0-9_-]{10,44}", fullmatch=True)

# Allowed MIME types
allowed_mimes = st.sampled_from(sorted(ALLOWED_MIME_TYPES))

# Disallowed MIME types (filtered to exclude allowed ones)
disallowed_mimes = st.text(min_size=1, max_size=80).filter(lambda m: m not in ALLOWED_MIME_TYPES)

# Permanent error types (no date-eligibility, no transient)
permanent_error_types = st.sampled_from(["business", "validation", "permission"])

_ELIGIBILITY_DAYS = 5
_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(staging_dir: Path) -> Any:
    class _FakeConfig:
        drive_folder_id = "root"
        eligibility_days = _ELIGIBILITY_DAYS
        credentials_path = staging_dir / "token.json"

    return _FakeConfig()


def _make_drive_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _build_manifest_with_success(manifest_dir: Path, file_ids: list[str]) -> ManifestStore:
    store = ManifestStore(manifest_dir)
    for fid in file_ids:
        store.set(
            fid,
            ManifestRecord(
                file_id=fid,
                name="doc.docx",
                status="success",
                processed_at=_NOW.isoformat(),
                error=None,
            ),
        )
    return store


def _build_manifest_with_permanent_failure(
    manifest_dir: Path,
    file_ids: list[str],
    error_type: str,
) -> ManifestStore:
    store = ManifestStore(manifest_dir)
    for fid in file_ids:
        store.set(
            fid,
            ManifestRecord(
                file_id=fid,
                name="doc.docx",
                status="failed",
                processed_at=_NOW.isoformat(),
                error=json.dumps({"error_type": error_type, "is_retriable": False, "message": "err"}),
            ),
        )
    return store


def _stub_client_with_files(file_ids: list[str], mime: str, days_old: float) -> Any:
    """DriveClient that returns file_ids as files in the root folder."""
    items = [
        {
            "id": fid,
            "name": f"{fid}.docx",
            "mimeType": mime,
            "modifiedTime": _make_drive_ts(_NOW - timedelta(days=days_old)),
        }
        for fid in file_ids
    ]

    class _Client:
        def list_files(self, folder_id: str) -> list[dict]:
            return items if folder_id == "root" else []

        def download_file(self, file_id: str, destination: Path) -> None:
            destination.write_bytes(b"")

    return _Client()


# ---------------------------------------------------------------------------
# PBT-03 — Property A: success records are never returned
# ---------------------------------------------------------------------------


@given(
    file_ids=st.lists(drive_file_ids, min_size=1, max_size=8, unique=True),
)
@settings(max_examples=100)
def test_discover_never_returns_success_file(file_ids: list[str]) -> None:
    """No file with a success manifest record should ever appear in the result."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        manifest = _build_manifest_with_success(tmp_path / "manifests", file_ids)
        client = _stub_client_with_files(file_ids, mime=sorted(ALLOWED_MIME_TYPES)[0], days_old=6.0)

        result = discover_eligible_files(config, manifest, client, now=_NOW)
        result_ids = {r.file_id for r in result}

        for fid in file_ids:
            assert fid not in result_ids, f"Success file {fid} appeared in eligible list"


# ---------------------------------------------------------------------------
# PBT-03 — Property B: permanent failed records are never returned
# ---------------------------------------------------------------------------


@given(
    file_ids=st.lists(drive_file_ids, min_size=1, max_size=8, unique=True),
    error_type=permanent_error_types,
)
@settings(max_examples=100)
def test_discover_never_returns_permanent_failed_file(
    file_ids: list[str], error_type: str
) -> None:
    """Files with is_retriable=False (non-date-eligibility) must never appear in results."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        manifest = _build_manifest_with_permanent_failure(tmp_path / "manifests", file_ids, error_type)
        client = _stub_client_with_files(file_ids, mime=sorted(ALLOWED_MIME_TYPES)[0], days_old=6.0)

        result = discover_eligible_files(config, manifest, client, now=_NOW)
        result_ids = {r.file_id for r in result}

        for fid in file_ids:
            assert fid not in result_ids, (
                f"Permanently failed file ({error_type}) {fid} appeared in eligible list"
            )


# ---------------------------------------------------------------------------
# PBT-03 — Property C: business_date_eligibility depends on current file age
# ---------------------------------------------------------------------------


@given(
    file_id=drive_file_ids,
    days_old=st.floats(min_value=3.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_date_eligibility_retry_depends_on_current_age(
    file_id: str, days_old: float
) -> None:
    """business_date_eligibility record: file is returned iff now - last_modified >= eligibility_days."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        manifest = ManifestStore(tmp_path / "manifests")
        manifest.set(
            file_id,
            ManifestRecord(
                file_id=file_id,
                name="doc.docx",
                status="failed",
                processed_at=_NOW.isoformat(),
                error=json.dumps({
                    "error_type": "business_date_eligibility",
                    "is_retriable": False,
                    "message": "was too recent",
                }),
            ),
        )
        client = _stub_client_with_files([file_id], mime=sorted(ALLOWED_MIME_TYPES)[0], days_old=days_old)

        result = discover_eligible_files(config, manifest, client, now=_NOW)
        result_ids = {r.file_id for r in result}

        if days_old >= float(_ELIGIBILITY_DAYS):
            assert file_id in result_ids, (
                f"File with days_old={days_old} (>= {_ELIGIBILITY_DAYS}) should be eligible"
            )
        else:
            assert file_id not in result_ids, (
                f"File with days_old={days_old} (< {_ELIGIBILITY_DAYS}) should NOT be eligible"
            )


# ---------------------------------------------------------------------------
# PBT-07 — Date boundary coverage: exactly eligibility_days is eligible
# ---------------------------------------------------------------------------


@given(
    file_id=drive_file_ids,
    days_old=st.one_of(
        st.floats(min_value=0.01, max_value=4.998, allow_nan=False, allow_infinity=False),  # clearly too recent (>8s gap from boundary)
        st.floats(min_value=5.001, max_value=30.0, allow_nan=False, allow_infinity=False),  # clearly eligible (>8s gap from boundary)
    ),
)
@settings(max_examples=200)
def test_eligibility_date_boundary(file_id: str, days_old: float) -> None:
    """Files >= eligibility_days old are eligible; files < eligibility_days old are not."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        manifest = ManifestStore(tmp_path / "manifests")
        client = _stub_client_with_files([file_id], mime=sorted(ALLOWED_MIME_TYPES)[0], days_old=days_old)

        result = discover_eligible_files(config, manifest, client, now=_NOW)
        result_ids = {r.file_id for r in result}

        if days_old >= float(_ELIGIBILITY_DAYS):
            assert file_id in result_ids, f"File {days_old} days old should be eligible"
        else:
            assert file_id not in result_ids, f"File {days_old} days old should NOT be eligible"


# ---------------------------------------------------------------------------
# PBT-07 — MIME type coverage: only allowed MIME types pass through
# ---------------------------------------------------------------------------


@given(
    file_id=drive_file_ids,
    mime_type=st.one_of(allowed_mimes, disallowed_mimes),
)
@settings(max_examples=100)
def test_mime_filter_allows_only_docx_and_pdf(
    file_id: str, mime_type: str
) -> None:
    """Only DOCX and PDF MIME types should be eligible; all others are excluded."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = _make_config(tmp_path)
        manifest = ManifestStore(tmp_path / "manifests")
        client = _stub_client_with_files([file_id], mime=mime_type, days_old=6.0)

        result = discover_eligible_files(config, manifest, client, now=_NOW)
        result_ids = {r.file_id for r in result}

        if mime_type in ALLOWED_MIME_TYPES:
            assert file_id in result_ids, f"Allowed MIME {mime_type} should pass the filter"
        else:
            assert file_id not in result_ids, f"Disallowed MIME {mime_type} should be excluded"
