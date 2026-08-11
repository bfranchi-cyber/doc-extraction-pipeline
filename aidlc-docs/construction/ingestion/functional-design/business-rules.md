# Business Rules — Unit 2: Ingestion

## BR-I-01: Eligibility Threshold (5-Day Rule)

**Rule**: A Drive file is eligible for processing if and only if:
`datetime.now(UTC) - file.last_modified >= timedelta(days=config.eligibility_days)`

**Boundary**: The comparison is inclusive (`>=`). A file last modified exactly 5 days ago is eligible.
**Source**: FR-01, AC-01.1, AC-01.3

---

## BR-I-02: MIME Type Filter

**Rule**: Only `.docx` and `.pdf` files are eligible. All other MIME types are silently skipped — not logged to the scratchpad, not added to the eligible list.

| Allowed MIME types |
|---|
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (`.docx`) |
| `application/pdf` |

**Source**: FR-03, AC-01.5

---

## BR-I-03: Manifest Skip and Retry-Eligibility Rule

**Rule**: Files are filtered based on their manifest state as follows:

| Manifest state | Retry eligible? | Reason |
|---|---|---|
| `status = "success"` | **No** — skip silently | Already completed |
| `status = "failed"`, `is_retriable = True` | **Yes** — include in eligible list | Error is known to be transient (network, Drive 5xx) |
| `status = "failed"`, `is_retriable = False`, `error_type = "business_date_eligibility"` | **Conditional** — re-evaluate BR-I-01 dynamically | Retriability is time-dependent: the file was too recent at time of failure; include if and only if `now - file.last_modified >= eligibility_days` holds at current run time |
| `status = "failed"`, `is_retriable = False`, all other `error_type` | **No** — skip silently | Permanent failure or requires human intervention |
| No manifest record | **Yes** — include | Not yet seen |

**Determining retry eligibility in `_scan_folder`**:

The filter evaluation order (BR-I-04) already applies the date check (step ii) before the manifest check (step iii). This means by the time step iii runs, the file has already passed `now - last_modified >= eligibility_days`. Therefore, the manifest check for `business_date_eligibility` records is:

```
If status="failed" and error_type="business_date_eligibility":
    # The file passed the date filter in step ii — it is now old enough.
    # Include it: the prior failure condition no longer applies.
    eligible = True
```

No dynamic date recalculation is needed in step iii — the date filter in step ii already did it.

**`is_retriable` assignment by error scenario**:

| Error scenario | `error_type` | `is_retriable` |
|---|---|---|
| Network timeout, connection reset, Drive 5xx | `"transient"` | `True` |
| File was too recent at time of prior run | `"business_date_eligibility"` | `False` (accurate at time of failure; retriability re-evaluated dynamically via date filter) |
| File type not downloadable, permanently deleted, quota permanently exceeded | `"business"` | `False` |
| OAuth scope insufficient, HTTP 403 Forbidden | `"permission"` | `False` |
| Malformed API response, unexpected data shape | `"validation"` | `False` |

**Note**: `validation` and `permission` failures are handled by re-auth + escalation (BR-I-13, BR-I-14), not by re-discovery. They are excluded from the eligible list.

**Silent skip**: Files excluded by this rule are not logged to the scratchpad by `discover_eligible_files`.

**Source**: FR-05, FR-09, AC-01.4, AC-08.2; updated per error-classification design changes 2026-08-11

---

## BR-I-04: Filter Evaluation Order

**Rule**: Eligibility filters are applied in this order (short-circuit on first exclusion):
1. MIME type check (BR-I-02) — skip if wrong type
2. Eligibility date check (BR-I-01) — skip if too recent
3. Manifest success check (BR-I-03) — skip if already processed

**Rationale**: Type check is cheapest (no I/O); date check is next; manifest I/O is last.

---

## BR-I-05: Configurable Scan Root with Automatic Subfolder Recursion

**Rule**: The user specifies the scan root via `drive_folder_id` in `config.toml`. `discover_eligible_files` always starts from that folder. If the root folder contains subfolders, they are traversed recursively (depth-first, no depth limit). If there are no subfolders, only the root folder's direct files are scanned — recursion is automatic, not forced.

**Configuration**: `drive_folder_id` in `config.toml` is the single control point. To limit scope, point it to a more specific subfolder.

**Traversal**: Depth-first starting at `drive_folder_id`. Files at any depth within the tree are included if they pass eligibility filters.

**Source**: FR-05, Q2=B answer

---

## BR-I-06: Local Filename — Collision Handling

**Rule**: Downloaded files are saved using the original Drive filename (BR-I-06a). If the original name already exists in `config.staging_dir` (collision from a recursive scan of folders with duplicate filenames), a numeric suffix is appended:
- First occurrence: `My Report.docx`
- Second occurrence: `My Report (2).docx`
- Third occurrence: `My Report (3).docx`

**Source**: Q2=B (recursive), Q3=A (original filename) — collision risk derived from combination.

---

## BR-I-07: OAuth — Non-Interactive Failure

**Rule**: If the pipeline runs in a non-interactive context (no TTY, e.g., Task Scheduler) and no valid token exists, it MUST raise `CredentialsMissingError` with a clear message and exit cleanly. It must NOT attempt to open a browser flow.

**Interactive context detection**: Check `sys.stdin.isatty()`. If `False`, treat as non-interactive.

**Source**: FR-02, AC-02.4

---

## BR-I-08: OAuth — Token Persistence

**Rule**: After a successful first-time browser OAuth flow, the resulting token is saved to `config.credentials_path`. The token file path and the credentials (app client secrets) file path are separate:
- App credentials (never overwritten): provided externally by the user at setup time
- Token file (written/refreshed by the pipeline): `config.credentials_path`

**Source**: FR-02, AC-02.1, AC-02.2

---

## BR-I-09: Rate Limit Retry — Drive API

**Rule**: If a Drive MCP tool call returns a rate-limit error (HTTP 429 or equivalent tool error indicating quota exceeded), the retry strategy is:
1. Read the `retry-after` value from the error response if present.
2. If `retry-after` is present: wait exactly that many seconds.
3. If `retry-after` is absent: wait 60 seconds (default backoff).
4. Retry the same call once. If it fails again, propagate the error.

**Log**: Each wait event is logged to the Coordinator scratchpad (level=warn, stage="ingestion").

**Source**: FR-10, AC-03.2

---

## BR-I-10: Download Failure Classification and Escalation

**Rule**: If `download_file()` encounters a non-rate-limit error, it raises a typed `DownloadError` carrying `error_type` and `is_retriable`. The Coordinator handles it as follows:

| `error_type` | `is_retriable` | Example causes | Coordinator action |
|---|---|---|---|
| `"transient"` | `True` | Network timeout, Drive 5xx, connection reset | Write failed manifest; continue — eligible for re-discovery on next run |
| `"business_date_eligibility"` | `False` | File was too recent at time of prior run | Write failed manifest; continue — re-discovery re-evaluates the date condition dynamically (BR-I-03) |
| `"business"` | `False` | File type not downloadable, permanently deleted, permanent quota exceeded | Write failed manifest; continue — NOT eligible for re-discovery |
| `"validation"` | `False` | Malformed Drive API response, unexpected data shape | Write manifest failed; run re-auth flow once (BR-I-13); if still failing, escalate (BR-I-14) |
| `"permission"` | `False` | OAuth scope insufficient, HTTP 403 Forbidden | Write manifest failed; run re-auth flow once (BR-I-13); if still failing, escalate (BR-I-14) |

`download_file()` does NOT write to the manifest directly; the Coordinator does.

**Source**: FR-10, AC-03.3, Q4=B answer; updated per error-classification design changes 2026-08-11

---

## BR-I-13: Re-Auth Flow on Validation/Permission Error

**Rule**: When the Coordinator catches a `DownloadError` with `error_type` in `{"validation", "permission"}`, it triggers a fresh OAuth authentication flow before retrying:
1. Call `authenticate(config)` again to obtain fresh credentials.
2. Rebuild the `DriveClient` with the new credentials.
3. Retry `download_file()` exactly once with the new client.
4. If the retry succeeds: write `ManifestRecord(status="success")` and continue.
5. If the retry also fails (any error type): escalate to human (BR-I-14). Do NOT retry again.

**Source**: Error-classification design change 2026-08-11

---

## BR-I-14: Human Escalation Handoff

**Rule**: When a validation/permission failure persists after re-auth (BR-I-13), the Coordinator must emit a structured **escalation handoff** to the scratchpad at level=`error` containing:

| Field | Content |
|---|---|
| `error_type` | `"validation"` or `"permission"` |
| `file_id` | Drive file ID that failed |
| `file_name` | Human-readable filename |
| `error_logs` | Full traceback / error chain as a string |
| `summary` | One-sentence description of what went wrong |
| `fix_suggestion` | Specific, actionable steps for the operator to resolve the issue |

After writing the escalation handoff, write `ManifestRecord(status="failed", error=<serialized escalation error>)` and continue processing remaining files.

**Source**: Error-classification design change 2026-08-11

---

## BR-I-11: Empty Eligible List

**Rule**: If `discover_eligible_files()` returns an empty list (no files pass all eligibility filters), the Coordinator logs "no eligible files found" to the scratchpad at level=info and the pipeline exits cleanly with a `RunSummary` where `eligible=0`, `processed=0`, `failed=0`, `skipped=0`.

**Source**: AC-03.4

---

## BR-I-12: Retry Logic Scope

**Rule**: Rate-limit retry logic (BR-I-09) is implemented inline within each function (`discover_eligible_files` and `download_file`) independently — no shared retry helper. This avoids over-abstraction for two callers.

**Source**: Q5=B answer
