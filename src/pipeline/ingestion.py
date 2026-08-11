from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from pipeline.exceptions import (
    CredentialsMissingError,
    DownloadError,
    RateLimitError,
)
from pipeline.models import DriveFileMetadata, ManifestRecord
from pipeline.manifest import ManifestStore
from pipeline.config import Config

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials

# Re-exported so existing test imports (from pipeline.ingestion import DownloadError) keep working.
# New code should import directly from pipeline.exceptions.
__all__ = [
    "authenticate",
    "discover_eligible_files",
    "download_file",
    "build_failed_manifest_record",
    "build_escalation_context",
    "DriveClient",
    "GoogleDriveClient",
    "ALLOWED_MIME_TYPES",
    "CredentialsMissingError",
    "DownloadError",
    "RateLimitError",
]

# ---------------------------------------------------------------------------
# MIME type allowlist
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES: frozenset[str] = frozenset([
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/pdf",
])

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


# ---------------------------------------------------------------------------
# DriveClient protocol — injectable for testing
# ---------------------------------------------------------------------------


class DriveClient(Protocol):
    """Abstract interface over Google Drive operations.

    Raises RateLimitError on quota exhaustion.
    Raises any Exception on other failures.
    """

    def list_files(self, folder_id: str) -> list[dict]: ...

    def download_file(self, file_id: str, destination: Path) -> None: ...


# ---------------------------------------------------------------------------
# Real DriveClient backed by google-api-python-client
# ---------------------------------------------------------------------------


class GoogleDriveClient:
    """Production DriveClient backed by the Google Drive REST API."""

    def __init__(self, credentials: "Credentials") -> None:
        from googleapiclient.discovery import build  # type: ignore[import]
        self._service = build("drive", "v3", credentials=credentials)

    def list_files(self, folder_id: str) -> list[dict]:
        """List all children (files and folders) directly inside folder_id."""
        try:
            results = (
                self._service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="files(id, name, mimeType, modifiedTime)",
                    pageSize=1000,
                )
                .execute()
            )
            return results.get("files", [])
        except Exception as exc:
            _maybe_raise_rate_limit(exc)
            raise

    def download_file(self, file_id: str, destination: Path) -> None:
        """Download file_id binary content to destination path."""
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import]
        import io

        try:
            request = self._service.files().get_media(fileId=file_id)
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            destination.write_bytes(buf.getvalue())
        except Exception as exc:
            _maybe_raise_rate_limit(exc)
            raise


def _maybe_raise_rate_limit(exc: Exception) -> None:
    """Re-raise exc as RateLimitError when it signals quota exhaustion."""
    try:
        from googleapiclient.errors import HttpError  # type: ignore[import]
        if isinstance(exc, HttpError) and exc.resp.status == 429:
            retry_after = None
            try:
                retry_after = int(exc.resp.get("retry-after", 60))
            except (ValueError, TypeError):
                retry_after = 60
            raise RateLimitError(retry_after=retry_after) from exc
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# authenticate()
# ---------------------------------------------------------------------------


def authenticate(config: Config) -> "Credentials":
    """Return valid OAuth2 credentials for the Drive API.

    Raises CredentialsMissingError when running non-interactively without a valid token.
    Google Auth imports are deferred to this function so the module can be imported
    without google-auth installed (useful for unit tests that mock the DriveClient).
    """
    from google.auth.transport.requests import Request  # noqa: PLC0415
    from google.oauth2.credentials import Credentials  # noqa: PLC0415
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: PLC0415

    token_path = config.credentials_path
    app_creds_path = token_path.parent / "client_secrets.json"

    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _DRIVE_SCOPES)

    if creds is not None and creds.valid:
        return creds

    if creds is not None and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds, token_path)
        return creds

    # No valid token — need user interaction
    if not sys.stdin.isatty():
        raise CredentialsMissingError(
            credentials_path=token_path,
            message=(
                "No valid OAuth token found and the pipeline is running non-interactively. "
                f"Run the pipeline interactively once to generate a token at {token_path}, "
                "then retry from the scheduler."
            ),
        )

    if not app_creds_path.exists():
        raise CredentialsMissingError(
            credentials_path=app_creds_path,
            message=(
                f"OAuth client secrets file not found at {app_creds_path}. "
                "Download credentials.json from the Google Cloud Console and place it there."
            ),
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(app_creds_path), _DRIVE_SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds, token_path)
    return creds


def _save_token(creds: Credentials, path: Path) -> None:
    path.write_text(creds.to_json(), encoding="utf-8")


# ---------------------------------------------------------------------------
# discover_eligible_files()
# ---------------------------------------------------------------------------


def discover_eligible_files(
    config: Config,
    manifest: ManifestStore,
    drive_client: DriveClient,
    now: datetime | None = None,
) -> list[DriveFileMetadata]:
    """Scan Drive recursively from config.drive_folder_id and return eligible files.

    now is injectable for testing; defaults to datetime.now(timezone.utc).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    eligible: list[DriveFileMetadata] = []
    _scan_folder(config.drive_folder_id, config, manifest, drive_client, now, eligible)
    return eligible


def _scan_folder(
    folder_id: str,
    config: Config,
    manifest: ManifestStore,
    drive_client: DriveClient,
    now: datetime,
    accumulator: list[DriveFileMetadata],
) -> None:
    # list_files with rate-limit retry (BR-I-09, BR-I-12)
    try:
        items = drive_client.list_files(folder_id)
    except RateLimitError as exc:
        _wait_rate_limit(exc)
        items = drive_client.list_files(folder_id)  # retry once; any error propagates

    for item in items:
        item_mime = item.get("mimeType", "")

        if item_mime == "application/vnd.google-apps.folder":
            _scan_folder(item["id"], config, manifest, drive_client, now, accumulator)
            continue

        # BR-I-04: MIME type → date → manifest (short-circuit on first exclusion)

        # Step i: MIME type filter (BR-I-02)
        if item_mime not in ALLOWED_MIME_TYPES:
            continue

        # Step ii: date filter (BR-I-01)
        last_modified = _parse_drive_datetime(item.get("modifiedTime", ""))
        if now - last_modified < timedelta(days=config.eligibility_days):
            continue

        # Step iii: manifest retry-eligibility (BR-I-03)
        file_id = item["id"]
        record = manifest.get(file_id)
        if record is not None:
            if record.status == "success":
                continue
            if record.status == "failed" and record.error:
                try:
                    err = json.loads(record.error)
                except (json.JSONDecodeError, TypeError):
                    err = {}
                is_retriable = err.get("is_retriable", False)
                error_type = err.get("error_type", "")
                if is_retriable:
                    pass  # eligible — transient errors
                elif error_type == "business_date_eligibility":
                    pass  # eligible — file already passed date filter above
                else:
                    continue  # permanent failure — skip

        accumulator.append(
            DriveFileMetadata(
                file_id=file_id,
                name=item["name"],
                mime_type=item_mime,
                last_modified=last_modified,
                download_url="",
            )
        )


def _parse_drive_datetime(value: str) -> datetime:
    """Parse Google Drive RFC 3339 datetime string to an aware UTC datetime."""
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    # Drive returns e.g. "2024-03-01T12:00:00.000Z"
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# download_file()
# ---------------------------------------------------------------------------


def download_file(
    file_metadata: DriveFileMetadata,
    staging_dir: Path,
    drive_client: DriveClient,
) -> Path:
    """Download one Drive file to staging_dir.

    Returns the local Path. Raises DownloadError on non-rate-limit failures.
    Rate-limit errors trigger one retry (BR-I-09, BR-I-12).
    Does NOT write to the manifest — that is the Coordinator's responsibility.
    """
    local_name = _resolve_local_name(staging_dir, file_metadata.name)
    destination = staging_dir / local_name

    try:
        drive_client.download_file(file_metadata.file_id, destination)
    except RateLimitError as exc:
        _wait_rate_limit(exc)
        try:
            drive_client.download_file(file_metadata.file_id, destination)
        except Exception as retry_exc:
            raise DownloadError(
                file_id=file_metadata.file_id,
                name=file_metadata.name,
                error_type=_classify_exception(retry_exc)[0],
                message=str(retry_exc),
                cause=retry_exc,
            ) from retry_exc
    except Exception as exc:
        error_type, _ = _classify_exception(exc)
        raise DownloadError(
            file_id=file_metadata.file_id,
            name=file_metadata.name,
            error_type=error_type,
            message=str(exc),
            cause=exc,
        ) from exc

    return destination


def _resolve_local_name(staging_dir: Path, original_name: str) -> str:
    """Return a collision-safe filename for staging_dir (BR-I-06)."""
    candidate = Path(original_name)
    stem, suffix = candidate.stem, candidate.suffix

    if not (staging_dir / original_name).exists():
        return original_name

    counter = 2
    while (staging_dir / f"{stem} ({counter}){suffix}").exists():
        counter += 1
    return f"{stem} ({counter}){suffix}"


def _classify_exception(exc: Exception) -> tuple[str, bool]:
    """Map a raw exception to (error_type, is_retriable).

    "transient"  — network / server-side transient failure; is_retriable=True
    "permission" — auth / access denied; is_retriable=False
    "validation" — malformed response / data shape; is_retriable=False
    "business"   — known permanent failure (e.g. unsupported file); is_retriable=False
    """
    exc_name = type(exc).__name__
    exc_str = str(exc).lower()

    if isinstance(exc, (ConnectionError, TimeoutError)):
        return "transient", True
    if isinstance(exc, PermissionError):
        return "permission", False
    if isinstance(exc, ValueError):
        return "validation", False

    try:
        from googleapiclient.errors import HttpError  # type: ignore[import]
        if isinstance(exc, HttpError):
            status = exc.resp.status
            if status == 403:
                return "permission", False
            if status in (500, 502, 503, 504):
                return "transient", True
            if status == 404:
                return "business", False
            return "business", False
    except ImportError:
        pass

    if "timeout" in exc_str or "connection" in exc_str or "reset" in exc_str:
        return "transient", True
    if "permission" in exc_str or "forbidden" in exc_str or "403" in exc_str:
        return "permission", False
    if "malformed" in exc_str or "unexpected" in exc_str or "parse" in exc_str:
        return "validation", False

    return "business", False


# ---------------------------------------------------------------------------
# Rate-limit wait helper (BR-I-09)
# ---------------------------------------------------------------------------


def _wait_rate_limit(exc: RateLimitError) -> None:
    delay = exc.retry_after if exc.retry_after is not None else 60
    time.sleep(delay)


# ---------------------------------------------------------------------------
# Coordinator error-routing helpers (BR-I-10, BR-I-13, BR-I-14)
# ---------------------------------------------------------------------------


def build_failed_manifest_record(
    file_metadata: DriveFileMetadata,
    error: DownloadError,
) -> ManifestRecord:
    """Build a failed ManifestRecord from a DownloadError (used by Coordinator)."""
    from datetime import datetime, timezone

    error_payload = json.dumps({
        "error_type": error.error_type,
        "is_retriable": error.is_retriable,
        "message": error.message,
    })
    return ManifestRecord(
        file_id=file_metadata.file_id,
        name=file_metadata.name,
        status="failed",
        processed_at=datetime.now(timezone.utc).isoformat(),
        error=error_payload,
    )


def build_escalation_context(
    file_metadata: DriveFileMetadata,
    error: DownloadError,
    traceback_str: str,
) -> dict:
    """Build the EscalationHandoff dict for BR-I-14 scratchpad logging."""
    error_type = error.error_type
    if error_type == "permission":
        fix = (
            "Check that the Google Drive OAuth scopes include 'drive.readonly'. "
            "Re-run the pipeline interactively to refresh credentials. "
            "If the error persists, verify the file is shared with the service account."
        )
    else:
        fix = (
            "Inspect the error logs for a malformed Drive API response. "
            "Verify the Drive API quota and that the file still exists. "
            "Contact the API administrator if the error recurs."
        )
    return {
        "file_id": file_metadata.file_id,
        "file_name": file_metadata.name,
        "error_type": error_type,
        "error_logs": traceback_str,
        "summary": error.message,
        "fix_suggestion": fix,
    }
