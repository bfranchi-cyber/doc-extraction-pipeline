"""Unit tests for pipeline.ingestion — discover_eligible_files, download_file, error routing."""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from pipeline.config import Config
from pipeline.ingestion import (
    ALLOWED_MIME_TYPES,
    CredentialsMissingError,
    DownloadError,
    RateLimitError,
    _classify_exception,
    _resolve_local_name,
    build_escalation_context,
    build_failed_manifest_record,
    discover_eligible_files,
    download_file,
)
from pipeline.manifest import ManifestStore
from pipeline.models import DriveFileMetadata, ManifestRecord


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF = "application/pdf"
_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
_ELIGIBILITY_DAYS = 5


def _days_ago(days: float) -> datetime:
    return _NOW - timedelta(days=days)


def _drive_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _make_file_item(
    file_id: str = "file1",
    name: str = "doc.docx",
    mime: str = _DOCX,
    days_old: float = 6.0,
) -> dict:
    return {
        "id": file_id,
        "name": name,
        "mimeType": mime,
        "modifiedTime": _drive_ts(_days_ago(days_old)),
    }


def _make_folder_item(folder_id: str = "folder1", name: str = "SubFolder") -> dict:
    return {
        "id": folder_id,
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "modifiedTime": _drive_ts(_days_ago(30)),
    }


def _make_client(items_by_folder: dict[str, list[dict]]) -> Any:
    """Stub DriveClient returning items keyed by folder_id."""

    class _StubClient:
        def list_files(self, folder_id: str) -> list[dict]:
            return items_by_folder.get(folder_id, [])

        def download_file(self, file_id: str, destination: Path) -> None:
            destination.write_bytes(b"content")

    return _StubClient()


def _make_manifest(manifest_dir: Path) -> ManifestStore:
    return ManifestStore(manifest_dir)


def _write_failed_record(
    manifest: ManifestStore,
    file_id: str,
    error_type: str,
    is_retriable: bool,
    name: str = "doc.docx",
) -> None:
    error_payload = json.dumps({"error_type": error_type, "is_retriable": is_retriable, "message": "err"})
    manifest.set(
        file_id,
        ManifestRecord(
            file_id=file_id,
            name=name,
            status="failed",
            processed_at=_NOW.isoformat(),
            error=error_payload,
        ),
    )


def _make_config(tmp_path: Path) -> Config:
    """Return a minimal Config-like namespace for ingestion tests."""

    class _FakeConfig:
        drive_folder_id = "root"
        eligibility_days = _ELIGIBILITY_DAYS
        credentials_path = tmp_path / "token.json"
        staging_dir = tmp_path / "staging"

    cfg = _FakeConfig()
    cfg.staging_dir.mkdir(parents=True, exist_ok=True)
    return cfg  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# discover_eligible_files — eligibility filters
# ---------------------------------------------------------------------------


def test_file_6_days_old_is_eligible(tmp_path):
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    client = _make_client({"root": [_make_file_item(days_old=6.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert len(result) == 1
    assert result[0].file_id == "file1"


def test_file_exactly_5_days_old_is_eligible(tmp_path):
    """AC-01.3 — boundary: exactly eligibility_days is eligible."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    client = _make_client({"root": [_make_file_item(days_old=5.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert len(result) == 1


def test_file_3_days_old_is_excluded(tmp_path):
    """AC-01.2 — recently modified files are excluded."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    client = _make_client({"root": [_make_file_item(days_old=3.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert result == []


def test_unsupported_mime_type_excluded(tmp_path):
    """AC-01.5 — non-docx/pdf files are silently skipped."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    client = _make_client({"root": [_make_file_item(mime="image/png", days_old=10.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert result == []


def test_pdf_mime_type_included(tmp_path):
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    client = _make_client({"root": [_make_file_item(mime=_PDF, days_old=7.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert len(result) == 1


def test_success_manifest_excludes_file(tmp_path):
    """AC-01.4 — already-processed files are excluded."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    manifest.set(
        "file1",
        ManifestRecord(file_id="file1", name="doc.docx", status="success", processed_at=_NOW.isoformat(), error=None),
    )
    client = _make_client({"root": [_make_file_item(days_old=6.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert result == []


def test_retriable_failed_manifest_includes_file(tmp_path):
    """Failed + is_retriable=True (transient) → included for retry."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    _write_failed_record(manifest, "file1", error_type="transient", is_retriable=True)
    client = _make_client({"root": [_make_file_item(days_old=6.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert len(result) == 1


def test_business_date_eligibility_included_when_old_enough(tmp_path):
    """BR-I-03 — business_date_eligibility record included when file now >= 5 days old."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    _write_failed_record(manifest, "file1", error_type="business_date_eligibility", is_retriable=False)
    client = _make_client({"root": [_make_file_item(days_old=6.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert len(result) == 1


def test_business_date_eligibility_excluded_when_still_recent(tmp_path):
    """BR-I-03 — business_date_eligibility record excluded when file still < 5 days old (date filter runs first)."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    _write_failed_record(manifest, "file1", error_type="business_date_eligibility", is_retriable=False)
    client = _make_client({"root": [_make_file_item(days_old=3.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert result == []


def test_permanent_business_failure_excluded(tmp_path):
    """BR-I-03 — permanent business failure is never retried."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    _write_failed_record(manifest, "file1", error_type="business", is_retriable=False)
    client = _make_client({"root": [_make_file_item(days_old=6.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert result == []


def test_validation_failure_excluded(tmp_path):
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    _write_failed_record(manifest, "file1", error_type="validation", is_retriable=False)
    client = _make_client({"root": [_make_file_item(days_old=6.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert result == []


def test_permission_failure_excluded(tmp_path):
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    _write_failed_record(manifest, "file1", error_type="permission", is_retriable=False)
    client = _make_client({"root": [_make_file_item(days_old=6.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert result == []


def test_empty_folder_returns_empty_list(tmp_path):
    """AC-03.4 — empty eligible list handled cleanly."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    client = _make_client({"root": []})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert result == []


def test_subfolder_recursion_includes_nested_files(tmp_path):
    """BR-I-05 — files in subfolders are discovered via depth-first recursion."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    client = _make_client({
        "root": [_make_folder_item(folder_id="sub1")],
        "sub1": [_make_file_item(file_id="file_in_sub", days_old=6.0)],
    })

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert len(result) == 1
    assert result[0].file_id == "file_in_sub"


def test_mime_filter_short_circuits_before_date_check(tmp_path):
    """BR-I-04 — wrong MIME type prevents date/manifest checks from running."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")
    # If date were checked, file would be eligible (old enough). But MIME filter fires first.
    client = _make_client({"root": [_make_file_item(mime="text/plain", days_old=100.0)]})

    result = discover_eligible_files(config, manifest, client, now=_NOW)

    assert result == []


def test_rate_limit_on_list_files_waits_and_retries(tmp_path):
    """BR-I-09 — rate-limit error triggers wait + one retry."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")

    call_count = 0

    class _RateLimitThenSuccessClient:
        def list_files(self, folder_id: str) -> list[dict]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(retry_after=0)
            return [_make_file_item(days_old=6.0)]

        def download_file(self, file_id: str, destination: Path) -> None:
            destination.write_bytes(b"")

    with patch("pipeline.ingestion.time.sleep") as mock_sleep:
        result = discover_eligible_files(config, manifest, _RateLimitThenSuccessClient(), now=_NOW)

    mock_sleep.assert_called_once_with(0)
    assert len(result) == 1


def test_non_rate_limit_error_on_list_files_propagates(tmp_path):
    """Non-rate-limit errors from list_files are re-raised as-is."""
    config = _make_config(tmp_path)
    manifest = _make_manifest(tmp_path / "manifests")

    class _ErrorClient:
        def list_files(self, folder_id: str) -> list[dict]:
            raise ConnectionError("Drive unreachable")

        def download_file(self, file_id: str, destination: Path) -> None:
            pass

    with pytest.raises(ConnectionError):
        discover_eligible_files(config, manifest, _ErrorClient(), now=_NOW)


# ---------------------------------------------------------------------------
# download_file
# ---------------------------------------------------------------------------


def _make_metadata(
    file_id: str = "file1",
    name: str = "report.docx",
) -> DriveFileMetadata:
    return DriveFileMetadata(
        file_id=file_id,
        name=name,
        mime_type=_DOCX,
        last_modified=_days_ago(6.0),
        download_url="",
    )


def test_successful_download_returns_path(tmp_path):
    """AC-03.1 — successful download returns correct local path."""
    staging = tmp_path / "staging"
    staging.mkdir()
    metadata = _make_metadata()

    class _OkClient:
        def list_files(self, folder_id: str) -> list[dict]:
            return []

        def download_file(self, file_id: str, destination: Path) -> None:
            destination.write_bytes(b"data")

    result = download_file(metadata, staging, _OkClient())

    assert result == staging / "report.docx"
    assert result.read_bytes() == b"data"


def test_collision_suffix_appended(tmp_path):
    """BR-I-06 — filename collision results in suffix (2), (3), etc."""
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "report.docx").write_bytes(b"existing")

    class _OkClient:
        def list_files(self, folder_id: str) -> list[dict]:
            return []

        def download_file(self, file_id: str, destination: Path) -> None:
            destination.write_bytes(b"new")

    result = download_file(_make_metadata(), staging, _OkClient())

    assert result.name == "report (2).docx"


def test_rate_limit_retry_succeeds(tmp_path):
    """AC-03.2 — rate-limit error triggers wait + retry; retry succeeds."""
    staging = tmp_path / "staging"
    staging.mkdir()
    call_count = 0

    class _RateLimitThenOkClient:
        def list_files(self, folder_id: str) -> list[dict]:
            return []

        def download_file(self, file_id: str, destination: Path) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(retry_after=0)
            destination.write_bytes(b"ok")

    with patch("pipeline.ingestion.time.sleep") as mock_sleep:
        result = download_file(_make_metadata(), staging, _RateLimitThenOkClient())

    mock_sleep.assert_called_once_with(0)
    assert result.exists()


def test_rate_limit_retry_also_fails_raises_download_error(tmp_path):
    """Rate-limit retry that also fails raises DownloadError."""
    staging = tmp_path / "staging"
    staging.mkdir()

    class _AlwaysRateLimitClient:
        def list_files(self, folder_id: str) -> list[dict]:
            return []

        def download_file(self, file_id: str, destination: Path) -> None:
            raise RateLimitError(retry_after=0)

    with patch("pipeline.ingestion.time.sleep"):
        with pytest.raises(DownloadError) as exc_info:
            download_file(_make_metadata(), staging, _AlwaysRateLimitClient())

    assert exc_info.value.file_id == "file1"


def test_network_timeout_raises_transient_download_error(tmp_path):
    """AC-03.3 — network timeout → DownloadError with error_type=transient, is_retriable=True."""
    staging = tmp_path / "staging"
    staging.mkdir()

    class _TimeoutClient:
        def list_files(self, folder_id: str) -> list[dict]:
            return []

        def download_file(self, file_id: str, destination: Path) -> None:
            raise TimeoutError("connection timed out")

    with pytest.raises(DownloadError) as exc_info:
        download_file(_make_metadata(), staging, _TimeoutClient())

    err = exc_info.value
    assert err.error_type == "transient"
    assert err.is_retriable is True


def test_permission_error_raises_permission_download_error(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()

    class _PermissionClient:
        def list_files(self, folder_id: str) -> list[dict]:
            return []

        def download_file(self, file_id: str, destination: Path) -> None:
            raise PermissionError("403 Forbidden")

    with pytest.raises(DownloadError) as exc_info:
        download_file(_make_metadata(), staging, _PermissionClient())

    assert exc_info.value.error_type == "permission"
    assert exc_info.value.is_retriable is False


def test_value_error_raises_validation_download_error(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()

    class _MalformedClient:
        def list_files(self, folder_id: str) -> list[dict]:
            return []

        def download_file(self, file_id: str, destination: Path) -> None:
            raise ValueError("malformed response")

    with pytest.raises(DownloadError) as exc_info:
        download_file(_make_metadata(), staging, _MalformedClient())

    assert exc_info.value.error_type == "validation"
    assert exc_info.value.is_retriable is False


def test_download_error_does_not_write_manifest(tmp_path):
    """DownloadError does NOT write to the manifest — that is the Coordinator's job."""
    staging = tmp_path / "staging"
    staging.mkdir()
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()

    class _FailClient:
        def list_files(self, folder_id: str) -> list[dict]:
            return []

        def download_file(self, file_id: str, destination: Path) -> None:
            raise ConnectionError("fail")

    with pytest.raises(DownloadError):
        download_file(_make_metadata(), staging, _FailClient())

    assert not list(manifest_dir.glob("*.json"))


# ---------------------------------------------------------------------------
# _resolve_local_name
# ---------------------------------------------------------------------------


def test_resolve_local_name_no_collision(tmp_path):
    assert _resolve_local_name(tmp_path, "report.docx") == "report.docx"


def test_resolve_local_name_one_collision(tmp_path):
    (tmp_path / "report.docx").write_bytes(b"")
    assert _resolve_local_name(tmp_path, "report.docx") == "report (2).docx"


def test_resolve_local_name_two_collisions(tmp_path):
    (tmp_path / "report.docx").write_bytes(b"")
    (tmp_path / "report (2).docx").write_bytes(b"")
    assert _resolve_local_name(tmp_path, "report.docx") == "report (3).docx"


# ---------------------------------------------------------------------------
# Coordinator error-routing helpers (BR-I-10, BR-I-13, BR-I-14)
# ---------------------------------------------------------------------------


def _make_download_error(
    error_type: str = "transient",
    file_id: str = "file1",
    name: str = "doc.docx",
) -> DownloadError:
    return DownloadError(file_id=file_id, name=name, error_type=error_type, message="test error")


def test_build_failed_manifest_record_transient(tmp_path):
    """Transient error → failed manifest with is_retriable=True."""
    metadata = _make_metadata()
    error = _make_download_error(error_type="transient")

    record = build_failed_manifest_record(metadata, error)

    assert record.status == "failed"
    payload = json.loads(record.error)
    assert payload["is_retriable"] is True
    assert payload["error_type"] == "transient"


def test_build_failed_manifest_record_business_not_retriable(tmp_path):
    metadata = _make_metadata()
    error = _make_download_error(error_type="business")

    record = build_failed_manifest_record(metadata, error)

    payload = json.loads(record.error)
    assert payload["is_retriable"] is False


def test_build_failed_manifest_record_date_eligibility(tmp_path):
    metadata = _make_metadata()
    error = _make_download_error(error_type="business_date_eligibility")

    record = build_failed_manifest_record(metadata, error)

    payload = json.loads(record.error)
    assert payload["error_type"] == "business_date_eligibility"
    assert payload["is_retriable"] is False


def test_build_escalation_context_permission(tmp_path):
    """BR-I-14 — permission escalation includes all required fields."""
    metadata = _make_metadata()
    error = _make_download_error(error_type="permission")

    ctx = build_escalation_context(metadata, error, traceback_str="Traceback...")

    assert ctx["file_id"] == "file1"
    assert ctx["file_name"] == "report.docx"
    assert ctx["error_type"] == "permission"
    assert "Traceback..." in ctx["error_logs"]
    assert ctx["summary"] == "test error"
    assert len(ctx["fix_suggestion"]) > 0


def test_build_escalation_context_validation(tmp_path):
    metadata = _make_metadata()
    error = _make_download_error(error_type="validation")

    ctx = build_escalation_context(metadata, error, traceback_str="err")

    assert ctx["error_type"] == "validation"
    assert len(ctx["fix_suggestion"]) > 0


# ---------------------------------------------------------------------------
# _classify_exception
# ---------------------------------------------------------------------------


def test_classify_connection_error_is_transient():
    err_type, is_retriable = _classify_exception(ConnectionError("reset"))
    assert err_type == "transient"
    assert is_retriable is True


def test_classify_timeout_error_is_transient():
    err_type, _ = _classify_exception(TimeoutError())
    assert err_type == "transient"


def test_classify_permission_error():
    err_type, is_retriable = _classify_exception(PermissionError())
    assert err_type == "permission"
    assert is_retriable is False


def test_classify_value_error_is_validation():
    err_type, is_retriable = _classify_exception(ValueError("bad shape"))
    assert err_type == "validation"
    assert is_retriable is False
