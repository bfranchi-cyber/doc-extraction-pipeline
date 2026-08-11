# Domain Entities — Unit 2: Ingestion

## Inherited from Unit 1 (Foundation)

The following entities are defined in `pipeline/models.py` and used as-is by the Ingestion unit:

| Entity | Source | Role in Ingestion |
|---|---|---|
| `DriveFileMetadata` | `models.py` | Produced by `discover_eligible_files`; one instance per eligible file |
| `Config` | `config.py` | Provides `drive_folder_id`, `staging_dir`, `credentials_path`, `eligibility_days`, `manifest_dir` |
| `ManifestStore` | `manifest.py` | Consulted by `discover_eligible_files` to skip already-processed files |

---

## Ingestion-Specific Concepts

### EligibilityStatus

Conceptual classification of a Drive file's eligibility for processing. Not a formal dataclass — used to reason about the discovery filter logic.

| Status | Condition |
|---|---|
| `ELIGIBLE` | `now - last_modified >= eligibility_days` AND MIME type is .docx or .pdf AND manifest status is not `success` |
| `TOO_RECENT` | `now - last_modified < eligibility_days` |
| `WRONG_TYPE` | MIME type is neither `application/vnd.openxmlformats-officedocument.wordprocessingml.document` nor `application/pdf` |
| `ALREADY_PROCESSED` | `ManifestStore.is_processed(file_id)` returns `True` |

> Note: `ALREADY_PROCESSED` takes priority in filtering (checked after MIME type and date, but skip is based on manifest).

---

### CredentialState

Conceptual state of the OAuth 2.0 credentials on disk. Drives the authentication flow branching.

| State | Condition |
|---|---|
| `MISSING` | `config.credentials_path` does not exist |
| `VALID` | Token file exists and access token has not expired |
| `EXPIRED_REFRESHABLE` | Access token expired, refresh token present and valid |
| `EXPIRED_NO_REFRESH` | Access token expired, no valid refresh token — triggers interactive re-auth |
| `NEEDS_FIRST_AUTH` | Credentials file exists (app credentials) but no token file yet — triggers browser OAuth flow |

---

### DriveFolder (conceptual)

Not a formal dataclass. Represents a node in the recursive folder traversal.

| Attribute | Type | Description |
|---|---|---|
| `folder_id` | `str` | Google Drive folder ID |
| `name` | `str` | Folder display name |
| `children` | `list[DriveFolder]` | Subfolders (lazy, discovered during traversal) |
| `files` | `list[DriveFileMetadata]` | Eligible files found directly in this folder |

The root of the traversal is always `config.drive_folder_id`, which the user configures in `config.toml`. Recursion into subfolders is automatic — if a folder has no subfolders, only its direct files are scanned. Traversal is depth-first; no limit on depth.

---

### DownloadError (exception)

Raised by `download_file()` on non-rate-limit failures. Caught by the Coordinator, which routes it per BR-I-10 based on `error_type`.

| Attribute | Type | Description |
|---|---|---|
| `file_id` | `str` | Drive file ID of the failed download |
| `name` | `str` | Drive file name |
| `error_type` | `str` | `"transient"`, `"business"`, `"validation"`, or `"permission"` — governs retry behaviour |
| `message` | `str` | Human-readable error description |
| `cause` | `Exception \| None` | Original exception, for traceback capture |

**Classification guidance** (implemented in `download_file()` or its caller):

| Condition | `error_type` | `is_retriable` | Notes |
|---|---|---|---|
| Network timeout, connection reset, Drive 5xx | `"transient"` | `True` | Re-tried on next discovery run |
| File was too recent at time of prior run | `"business_date_eligibility"` | `False` | Stored `False` (accurate at failure time); `_scan_folder` re-evaluates dynamically via the date filter — included when `now - last_modified >= eligibility_days` |
| File type not downloadable, permanently deleted, permanent quota exceeded | `"business"` | `False` | Permanently excluded |
| OAuth scope insufficient, HTTP 403 Forbidden | `"permission"` | `False` | Re-auth + escalation (BR-I-13/14) |
| Malformed API response, unexpected response shape | `"validation"` | `False` | Re-auth + escalation (BR-I-13/14) |

---

### EscalationHandoff (dataclass)

Produced by the Coordinator when a validation/permission failure persists after re-auth (BR-I-14). Written to the scratchpad at level=`error`.

| Attribute | Type | Description |
|---|---|---|
| `file_id` | `str` | Drive file ID that triggered escalation |
| `file_name` | `str` | Human-readable filename |
| `error_type` | `str` | `"validation"` or `"permission"` |
| `error_logs` | `str` | Full traceback / exception chain as a string |
| `summary` | `str` | One-sentence description of the failure |
| `fix_suggestion` | `str` | Specific, actionable steps for the operator |

---

### CredentialsMissingError (exception)

Raised by the authentication flow when the credentials file is absent and no interactive auth is possible (e.g., running under Task Scheduler).

| Attribute | Type | Description |
|---|---|---|
| `credentials_path` | `Path` | The expected path that was not found |
| `message` | `str` | Clear instructions for the user to fix the issue |
