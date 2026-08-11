# Code Generation Plan — Unit 2: Ingestion

## Unit Context

**Unit**: Unit 2 — Ingestion
**Stories**: US-01 (AC-01.1–01.5), US-02 (AC-02.1–02.4), US-03 (AC-03.1–03.4)
**Depends on**: Unit 1 (Foundation) — uses `Config`, `DriveFileMetadata`, `ManifestStore`, `Scratchpad`
**Other units depend on this**: Unit 5 (Coordinator invokes ingestion functions)

**Source root**: `src/pipeline/` (src/ layout, greenfield)
**Test root**: `tests/`
**Workspace root**: `c:\Users\bfranchi\Desktop\projetos\docs-extraction`

**Key design decisions carried forward**:
- Google Drive access via **MCP tool calls** (Q1=B) — not the Python SDK
- **Recursive folder scan** (Q2=B) — depth-first, no depth limit, root = `config.drive_folder_id`
- **Original Drive filename** for downloads (Q3=A) — collision suffix if duplicate (BR-I-06)
- **DownloadError raised by `download_file()`** (Q4=B) — Coordinator catches and writes manifest
- **Inline retry logic** per function (Q5=B) — no shared retry helper
- Filter order: MIME type → date → manifest (BR-I-04)
- OAuth: `CredentialsMissingError` on non-interactive missing credentials (BR-I-07)
- Rate limit: read `retry-after`, default 60s, retry once (BR-I-09)
- Python 3.11+, `hypothesis` for PBT (PBT-03, 07, 08, 09 applicable)

---

## PBT Compliance Check (Partial enforcement: PBT-02, 03, 07, 08, 09)

| Rule | Applicability | Plan coverage |
|---|---|---|
| PBT-02 (round-trip) | NO — no serialization round-trips in this unit | N/A |
| PBT-03 (invariants) | YES — `discover_eligible_files` must never return a file with `is_processed(file_id) == True` | Step 4: `test_ingestion_pbt.py` |
| PBT-07 (generator quality) | YES — date generators must cover exactly-5-day boundary; MIME type generators must cover allowed/disallowed types | Step 4: custom generators |
| PBT-08 (shrinking) | YES — no `suppress_health_check` to disable shrinking; `@settings(max_examples=100)` | Step 4: enforced in test structure |
| PBT-09 (framework) | YES — `hypothesis` already declared in `pyproject.toml` dev deps | Already satisfied by Unit 1 Step 2 |

---

## Generation Steps

- [x] Step 1: Create `src/pipeline/ingestion.py`
- [x] Step 2: Create `tests/unit/test_ingestion.py`
- [x] Step 3: Create `tests/integration/test_ingestion_drive.md` (stub + documentation only — Drive MCP not mockable in unit tests)
- [x] Step 4: Create `tests/property/test_ingestion_pbt.py`

---

## Step Details

### Step 1 — `src/pipeline/ingestion.py`

**Purpose**: Implement the three public functions (`authenticate`, `discover_eligible_files`, `download_file`) and the `DownloadError` / `CredentialsMissingError` exceptions.

**Note on MCP integration**: Because access to Google Drive is via MCP tool calls (not the Python SDK), `ingestion.py` must be written so that the MCP interaction is **injectable / mockable** — callers pass in a `drive_client` protocol/callable that wraps the MCP calls. This lets unit tests pass a mock client without needing a live MCP server. The real `drive_client` is constructed by the Coordinator using the MCP SDK.

**Exceptions** (defined in this module — they live here, not in `models.py`):
```python
class DownloadError(ExtractionPipelineError):
    def __init__(
        self,
        file_id: str,
        name: str,
        error_type: str,   # "transient" | "business" | "validation" | "permission"
        message: str,
        cause: Exception | None = None,
    ) -> None: ...

class CredentialsMissingError(ExtractionPipelineError):
    def __init__(self, credentials_path: Path, message: str) -> None: ...
```

**Public interface**:

```python
def authenticate(config: Config) -> Any:
    """Return OAuth credentials. Raises CredentialsMissingError on non-interactive failure."""

def discover_eligible_files(
    config: Config,
    manifest: ManifestStore,
    drive_client: DriveClient,
) -> list[DriveFileMetadata]:
    """Scan Drive recursively from config.drive_folder_id, return eligible files."""

def download_file(
    file_metadata: DriveFileMetadata,
    staging_dir: Path,
    drive_client: DriveClient,
) -> Path:
    """Download one file to staging_dir. Raises DownloadError on non-rate-limit failure."""
```

**`DriveClient` protocol** (defined in this module):
```python
from typing import Protocol, Any

class DriveClient(Protocol):
    def list_files(self, folder_id: str) -> list[dict]: ...
    def download_file(self, file_id: str, destination: Path) -> None: ...
```
Each method raises a `RateLimitError` (also defined here, subclass of `ExtractionPipelineError`) when quota is exceeded, and any other `Exception` for other errors.

```python
class RateLimitError(ExtractionPipelineError):
    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
```

**`authenticate()` logic** (from business-logic-model.md — Workflow 1):
1. Check `config.credentials_path` exists → raise `CredentialsMissingError` if not
2. Load token file from `config.credentials_path`
   - No token file: run first-time OAuth flow (interactive only — check `sys.stdin.isatty()`)
   - Valid token: return credentials
   - Expired + refresh token present: refresh, save, return
   - Expired + no refresh, interactive: run browser OAuth flow
   - Expired + no refresh, non-interactive: raise `CredentialsMissingError`

**Note**: For now, `authenticate()` uses `google-auth-oauthlib` for the OAuth flow (stored in credentials file). The `DriveClient` passed to `discover_eligible_files` and `download_file` is constructed by the Coordinator using the authenticated credentials. `authenticate()` returns a `google.oauth2.credentials.Credentials` object.

**`_scan_folder()` private helper** (from business-logic-model.md — Workflow 2):
- `list_files()` on folder_id
- Rate-limit: read `retry_after`, wait, retry once; other errors re-raised
- For each item: if FOLDER → recurse; if FILE → apply filters (BR-I-04: MIME → date → manifest retry-eligibility)
- Manifest retry-eligibility logic (BR-I-03):
  - No record → eligible
  - `status="success"` → skip
  - `status="failed"`: deserialize `error` JSON, read `is_retriable` and `error_type`:
    - `is_retriable=True` → eligible (transient errors)
    - `is_retriable=False`, `error_type="business_date_eligibility"` → eligible
      (file already passed the date filter in step ii, so the condition is now met)
    - `is_retriable=False`, all other `error_type` → skip
- Append passing files to accumulator

**`_classify_exception()` private helper**:
Map raw exceptions to `(error_type, is_retriable)` for populating `DownloadError`:
```python
def _classify_exception(exc: Exception) -> tuple[str, bool]:
    # ConnectionError, TimeoutError, Drive 5xx → ("transient", True)
    # PermissionError, HTTP 403              → ("permission", False)
    # ValueError, malformed response         → ("validation", False)
    # Known-unrecoverable Drive errors       → ("business", False)
```

Note: `"business_date_eligibility"` is never produced by `_classify_exception` — it is raised explicitly by `_scan_folder` at the point of the BR-I-01 date check, before a download is even attempted. If `_scan_folder` finds a file in Drive, checks `now - last_modified < eligibility_days`, and fails (should not happen in normal flow since step ii already ran, but guards against clock skew or reordered results), it raises `DownloadError(error_type="business_date_eligibility", is_retriable=False, ...)`. The `False` is accurate: at this exact moment the file is still too recent. On the next run, step ii will re-evaluate the date and either filter the file out again or pass it through to step iii, which will include it because `error_type="business_date_eligibility"` is the marker for dynamic re-evaluation.

**MIME type constants**:
```python
ALLOWED_MIME_TYPES = frozenset([
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/pdf",
])
```

**`download_file()` logic** (from business-logic-model.md — Workflow 3):
1. Determine `local_name` from `file_metadata.name` with collision suffix if needed (BR-I-06)
2. Call `drive_client.download_file(file_metadata.file_id, destination=staging_dir / local_name)`
   - `RateLimitError`: wait (BR-I-09), retry once
   - Other exception: classify via `_error_type_from_exception(exc)`, raise `DownloadError(file_id, name, error_type, message, cause=exc)`
3. Return `Path(staging_dir / local_name)`

Note: `DownloadError` is raised with an `error_type` so the Coordinator can apply BR-I-10 routing without inspecting raw exceptions.

**Imports** (top of file):
```python
from __future__ import annotations
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from pipeline.models import Config, DriveFileMetadata, ManifestStore, ExtractionPipelineError
```

---

### Step 2 — `tests/unit/test_ingestion.py`

**Purpose**: Unit tests for `discover_eligible_files` and `download_file` using a mock `DriveClient`. No live Drive calls.

**Test cases for `discover_eligible_files`**:
- File too recent (< 5 days) → excluded
- File exactly 5 days old → included (AC-01.1, AC-01.3)
- File 3 days old → excluded (AC-01.2)
- File with unsupported MIME type → excluded (AC-01.5)
- File in manifest with `status=success` → excluded (AC-01.4)
- File in manifest with `status=failed`, `is_retriable=True` (`error_type="transient"`) → included
- File in manifest with `status=failed`, `error_type="business_date_eligibility"`, file now >= 5 days old → included (date filter already passed in step ii)
- File in manifest with `status=failed`, `error_type="business_date_eligibility"`, file still < 5 days old → excluded by date filter in step ii before manifest check even runs
- File in manifest with `status=failed`, `is_retriable=False`, `error_type="business"` → excluded
- File in manifest with `status=failed`, `is_retriable=False`, `error_type="validation"` → excluded
- File in manifest with `status=failed`, `is_retriable=False`, `error_type="permission"` → excluded
- Empty folder → returns empty list (AC-03.4)
- Rate limit error on `list_files` → wait and retry once
- Non-rate-limit error on `list_files` → re-raised
- Subfolder recursion: root folder contains a subfolder → files in subfolder are included
- Filter short-circuit: wrong MIME type skips date/manifest check (BR-I-04)

**Test cases for `download_file`**:
- Successful download → returns correct `Path`
- Collision handling: file exists → suffix appended (BR-I-06)
- `RateLimitError` → wait and retry → success
- `RateLimitError` → wait and retry → still fails → `DownloadError` raised
- Network timeout → `DownloadError` with `error_type="transient"`, `is_retriable=True` (AC-03.3)
- HTTP 403 / PermissionError → `DownloadError` with `error_type="permission"`, `is_retriable=False`
- Malformed API response → `DownloadError` with `error_type="validation"`, `is_retriable=False`
- Permanent business error → `DownloadError` with `error_type="business"`, `is_retriable=False`
- Date-eligibility error → `DownloadError` with `error_type="business_date_eligibility"`, `is_retriable=False` (accurate at point of failure; re-evaluated dynamically on next run via date filter)
- `DownloadError` does NOT write manifest (that is Coordinator's responsibility)

**Test cases for Coordinator error routing** (tested via helper functions, not full Coordinator):
- `is_retriable=True`, `error_type="transient"` → manifest written with failed; file eligible on next discovery
- `error_type="business_date_eligibility"`, `is_retriable=False` → manifest written with failed; re-discovery re-evaluates via date filter (file included if now past threshold, excluded if still too recent)
- `is_retriable=False`, `error_type="business"` → manifest written with failed; file NOT eligible on next discovery
- `error_type="validation"` → re-auth called, retry attempted; on success manifest written as success
- `error_type="permission"` → re-auth called, retry attempted; on second failure escalation handoff emitted
- Escalation handoff contains: `error_type`, `file_id`, `file_name`, `error_logs`, `summary`, `fix_suggestion`

**Mock `DriveClient`**: Use `unittest.mock.MagicMock` or a simple stub class that records calls.

**Fixtures**: Use `tmp_path` (pytest) for `staging_dir` and `manifest_dir`. Freeze time using `datetime` monkeypatching or `freezegun` (add to dev deps if needed — or just pass `now` as injectable param).

**Note on time injection**: `discover_eligible_files` needs a `now` parameter (defaulting to `datetime.now(timezone.utc)`) to make the 5-day calculation testable without real time dependencies.

**Updated signature**:
```python
def discover_eligible_files(
    config: Config,
    manifest: ManifestStore,
    drive_client: DriveClient,
    now: datetime | None = None,   # injectable for testing
) -> list[DriveFileMetadata]:
```

---

### Step 3 — `tests/integration/test_ingestion_drive.md`

**Purpose**: Document the integration test plan for a live Drive MCP connection. This is a Markdown stub — actual integration tests require a real MCP server and Drive credentials, which are not available in the unit test environment.

**Content**:
- What the integration tests verify (live folder scan, actual OAuth flow, real download)
- How to run them (prerequisites: credentials, MCP server running, test folder ID)
- Why they are not automated in CI (credentials + live network required)

Save as `tests/integration/test_ingestion_drive.md` (Markdown documentation, not a Python file).

---

### Step 4 — `tests/property/test_ingestion_pbt.py`

**Purpose**: Property-based tests enforcing PBT-03, PBT-07, PBT-08.

**PBT-03 — Invariant: `discover_eligible_files` respects manifest retry-eligibility**:

Two separate properties (date-eligibility and general manifest):

```python
# Property A: success records are never returned
@given(
    file_ids=st.lists(st.from_regex(r'[A-Za-z0-9_-]{10,44}', fullmatch=True), min_size=1, max_size=10),
    success_ids=st.sets(st.from_regex(r'[A-Za-z0-9_-]{10,44}', fullmatch=True), max_size=5),
)
@settings(max_examples=100)
def test_discover_never_returns_success_file(file_ids, success_ids, tmp_path): ...
# - Build manifest: status=success for each success_id
# - Mock DriveClient: all file_ids as FILES, supported MIME, > 5 days old
# - Assert: no result file_id in success_ids

# Property B: permanent failed records (is_retriable=False, non-date-eligibility) are never returned
@given(
    file_ids=st.lists(st.from_regex(r'[A-Za-z0-9_-]{10,44}', fullmatch=True), min_size=1, max_size=10),
    permanent_error_type=st.sampled_from(["business", "validation", "permission"]),
)
@settings(max_examples=100)
def test_discover_never_returns_permanent_failed_file(file_ids, permanent_error_type, tmp_path): ...
# - Build manifest: status=failed, is_retriable=False, error_type=permanent_error_type for all file_ids
# - Mock DriveClient: all file_ids as FILES, supported MIME, > 5 days old
# - Assert: result is empty

# Property C: business_date_eligibility records are returned if and only if file is now old enough
@given(
    file_id=st.from_regex(r'[A-Za-z0-9_-]{10,44}', fullmatch=True),
    days_old=st.floats(min_value=3.0, max_value=10.0),
)
@settings(max_examples=200)
def test_date_eligibility_retry_depends_on_current_age(file_id, days_old, tmp_path): ...
# - Build manifest: status=failed, error_type="business_date_eligibility", is_retriable=False
# - Mock DriveClient: file_id with last_modified = now - timedelta(days=days_old)
# - Assert: file in result if days_old >= 5.0; not in result if days_old < 5.0
```

**PBT-07 — Generator quality: date boundary coverage**:
```python
@given(
    days_old=st.one_of(
        st.floats(min_value=4.9999, max_value=5.0001),  # boundary
        st.floats(min_value=0.0, max_value=4.999),       # too recent
        st.floats(min_value=5.0, max_value=30.0),        # clearly eligible
    )
)
@settings(max_examples=200)
def test_eligibility_boundary(days_old, tmp_path): ...
```
- File modified `now - timedelta(days=days_old)`
- Assert: `days_old >= 5.0` → eligible; `days_old < 5.0` → not eligible

**PBT-07 — Generator quality: MIME type coverage**:
```python
@given(
    mime_type=st.one_of(
        st.just("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        st.just("application/pdf"),
        st.text(min_size=1, max_size=80).filter(lambda m: m not in ALLOWED_MIME_TYPES),
    )
)
@settings(max_examples=100)
def test_mime_filter(mime_type, tmp_path): ...
```
- Assert: only allowed MIME types pass through

**PBT-07 — Generator quality: `error_type` and date boundary for date-eligibility**:

Property C above (from PBT-03) already serves as the PBT-07 boundary generator for date-eligibility: `days_old` covers values straddling 5.0 using `st.floats(min_value=3.0, max_value=10.0)`, which Hypothesis will shrink to the boundary automatically. No separate PBT-07 test needed for this scenario — Property C covers it.

**PBT-08**: No `suppress_health_check` that disables shrinking; `@settings(max_examples=...)` used throughout.

---

## Story Traceability

| AC | Implemented by | Step |
|---|---|---|
| AC-01.1 (eligible file detected, 5+ days) | `_scan_folder` date filter | Step 1 |
| AC-01.2 (recently modified excluded, 3 days) | `_scan_folder` date filter | Step 1 |
| AC-01.3 (boundary: exactly 5 days) | `>=` comparison in date filter | Step 1 |
| AC-01.4 (already-processed excluded) | manifest filter in `_scan_folder` | Step 1 |
| AC-01.5 (unsupported type excluded) | MIME type filter in `_scan_folder` | Step 1 |
| AC-02.1 (first-time OAuth) | `authenticate()` browser flow | Step 1 |
| AC-02.2 (token reuse) | `authenticate()` valid token path | Step 1 |
| AC-02.3 (token refresh) | `authenticate()` refresh path | Step 1 |
| AC-02.4 (missing creds, non-interactive) | `CredentialsMissingError` + `isatty()` check | Step 1 |
| AC-03.1 (successful download) | `download_file()` happy path | Step 1 |
| AC-03.2 (rate limit retry) | `RateLimitError` handler in both functions | Step 1 |
| AC-03.3 (network/API error → failed manifest) | `DownloadError` with `error_type`; Coordinator routes per BR-I-10 | Step 1 |
| AC-03.4 (empty eligible list) | empty return from `discover_eligible_files` | Step 1 |
| BR-I-10 transient → retry eligible | `DownloadError(error_type="transient", is_retriable=True)` | Step 1 |
| BR-I-10 permanent business → no retry | `DownloadError(error_type="business", is_retriable=False)` | Step 1 |
| BR-I-10 date-eligibility → time-dependent retry | `DownloadError(error_type="business_date_eligibility", is_retriable=False)`; re-evaluated by date filter on next run | Step 1 |
| PBT-03 Property C (date-eligibility boundary) | `test_ingestion_pbt.py` — straddling 5-day boundary | Step 4 |
| BR-I-13 re-auth on validation/permission | Coordinator re-auth + retry once | Step 1 (Coordinator helper); Step 2 (test) |
| BR-I-14 escalation handoff | `EscalationHandoff` scratchpad entry on second failure | Step 1 (Coordinator helper); Step 2 (test) |
| PBT-03 manifest eligibility invariant | `test_ingestion_pbt.py` — all four error_type values tested | Step 4 |
| PBT-07 boundary + MIME + error_type coverage | `test_ingestion_pbt.py` | Step 4 |
