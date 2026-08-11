# Business Logic Model — Unit 2: Ingestion

## Overview

Unit 2 implements two discrete workflows: **authentication** (one-time setup + token refresh) and **discovery + download** (per pipeline run). Both are invoked by the Coordinator before any extraction begins.

---

## Workflow 1: Authentication

### Trigger
Called once at pipeline startup before any Drive API call.

### Logic

```
authenticate(config: Config) -> DriveCredentials

1. Check if config.credentials_path exists.
   - If NOT exists: raise CredentialsMissingError (non-interactive exit — BR-I-07)
   
2. Load token from config.credentials_path.
   - If token does not exist (first run): proceed to step 3.
   - If token exists and is valid: return credentials immediately (AC-02.2).
   - If token expired and refresh token present: refresh automatically, save updated
     token to config.credentials_path, return credentials (AC-02.3).
   - If token expired and no refresh token:
       - If sys.stdin.isatty(): run browser OAuth flow → save token → return credentials.
       - If NOT sys.stdin.isatty(): raise CredentialsMissingError (AC-02.4).

3. First-time browser OAuth flow (interactive only):
   - Open browser to Google OAuth consent screen.
   - Receive authorization code.
   - Exchange code for access + refresh tokens.
   - Save token to config.credentials_path (BR-I-08).
   - Return credentials.
```

### Output
`DriveCredentials` (opaque auth object passed into all MCP tool calls)

---

## Workflow 2: Discover Eligible Files

### Trigger
Called by the Coordinator once per pipeline run, after authentication.

### Logic

```
discover_eligible_files(config: Config, manifest: ManifestStore) -> list[DriveFileMetadata]

1. Initialize eligible_files = []
2. Call _scan_folder(config.drive_folder_id, config, manifest, eligible_files)
3. Return eligible_files

_scan_folder(folder_id, config, manifest, accumulator):
  1. Call Drive MCP tool: list_files(folder_id)
     - On rate-limit error: wait (BR-I-09), retry once.
     - On other error: re-raise.
  
  2. For each item in result:
     a. If item is a FOLDER: recurse → _scan_folder(item.id, ...)
        (automatic — triggers only when subfolders are present; BR-I-05)
     b. If item is a FILE:
        i.  Apply MIME type filter (BR-I-02) — skip if wrong type
        ii. Apply date filter (BR-I-01) — skip if too recent
        iii.Apply manifest retry-eligibility check (BR-I-03):
              - No manifest record → eligible
              - status="success" → skip
              - status="failed": deserialize error JSON, read error_type and is_retriable
                  - is_retriable=True → eligible (transient errors)
                  - is_retriable=False, error_type="business_date_eligibility" → eligible
                    (file passed date filter in step ii, so condition is now met)
                  - is_retriable=False, all other error_type → skip
        iv. If all pass: append DriveFileMetadata to accumulator
  
  3. Return (accumulator modified in place)

Note: The scan root (config.drive_folder_id) is set in config.toml by the user.
To narrow scope, point drive_folder_id at a more specific subfolder — no code change needed.
```

### Filter Evaluation Order
Per BR-I-04: MIME type → date → manifest retry-eligibility. Short-circuit on first exclusion.

### Output
`list[DriveFileMetadata]` — zero or more eligible files, in depth-first discovery order.

---

## Workflow 3: Download File

### Trigger
Called by the Coordinator once per eligible file (sequentially, not concurrently — downloading is I/O-bound but not parallelized at the ingestion stage; parallelism is in the Extraction stage).

### Logic

```
download_file(file_metadata: DriveFileMetadata, staging_dir: Path, drive_client: DriveClient) -> Path

1. Determine local filename:
   - Start with file_metadata.name (original Drive filename) (BR-I-06)
   - If staging_dir / name already exists:
       suffix = 2
       while staging_dir / f"{stem} ({suffix}){ext}" exists: suffix += 1
       local_name = f"{stem} ({suffix}){ext}"
   - Else: local_name = file_metadata.name

2. Call drive_client.download_file(file_metadata.file_id, destination=staging_dir / local_name)
   - On rate-limit error: wait (BR-I-09), retry once.
   - On other error: classify and raise DownloadError(file_id, name, error_type, message) (BR-I-10)

3. Return Path(staging_dir / local_name)
```

### Output
`Path` — absolute path to the downloaded file in `staging_dir`.

### On Failure — Error Classification
Raises `DownloadError` with a classified `error_type`. The Coordinator applies BR-I-10 logic:

```
Coordinator.handle_download_error(error: DownloadError, file_metadata, drive_client):

  1. Write ManifestRecord(status="failed", error=<serialized error>) immediately.

  2. If error.is_retriable (error_type="transient"):
       - Log warning to scratchpad. Continue to next file.
       - File is eligible for retry on next run (BR-I-03).

  3. If not error.is_retriable and error.error_type="business_date_eligibility":
       - Log warning to scratchpad. Continue to next file.
       - File re-eligibility is time-dependent: _scan_folder will include it once
         now - last_modified >= eligibility_days (detected dynamically via the date
         filter in step ii — no stored flag needed).

  4a. If not error.is_retriable and error.error_type="business":
       - Log warning to scratchpad. Continue to next file.
       - File is permanently ineligible (BR-I-03).

  4b. If error.error_type in {"validation", "permission"}:
       - Run re-auth flow: credentials = authenticate(config) (BR-I-13)
       - Rebuild drive_client with new credentials.
       - Retry download_file() once:
           - If succeeds: overwrite manifest with status="success". Continue.
           - If fails again (any error_type): emit escalation handoff (BR-I-14).
             Write ManifestRecord(status="failed", error=<escalation error>). Continue.
```

---

## Coordinator Integration Points

| Coordinator Action | When | Ingestion Output Consumed |
|---|---|---|
| Call `authenticate()` | Pipeline startup | `DriveCredentials` (passed to DriveClient) |
| Call `discover_eligible_files()` | After auth | `list[DriveFileMetadata]` — used to drive extraction loop |
| Call `download_file()` per file | After discovery | `Path` — local file path passed to Extraction stage |
| Catch `DownloadError` (`is_retriable=True`, non-auth) | On transient or date-eligibility failure | Write failed manifest, log warn, continue; eligible for next-run retry |
| Catch `DownloadError` (`is_retriable=False`, non-auth) | On permanent business failure | Write failed manifest, log warn, continue; NOT retried |
| Catch `DownloadError` (validation/permission) | On auth/config failure | Re-auth + retry once; escalate to human if still failing (BR-I-14) |
| Handle empty eligible list | If `len(eligible) == 0` | Log "no eligible files found", exit with `RunSummary(eligible=0, ...)` (BR-I-11) |

---

## Data Flow Diagram

```
                    config.credentials_path
                           |
                           v
                    authenticate()
                           |
                     DriveCredentials
                           |
                           v
              discover_eligible_files()
           (config, manifest, drive_client)
                           |
               Recursive Drive folder scan
               (BR-I-05: depth-first traversal)
                           |
             Per-file eligibility filter
        (BR-I-04: type → date → manifest retry-eligibility)
        [skip success; skip is_retriable=False non-date-eligibility failed;
         retry is_retriable=True failed; retry business_date_eligibility if date
         filter already passed; include no-record]
                           |
               list[DriveFileMetadata]
                           |
                  (for each file)
                           |
                           v
                    download_file()
              (metadata, staging_dir, drive_client)
                           |
              +------+-----+------+----------+
              |      |            |           |
           Success Transient  Business  Validation/
              |    failure    failure   Permission
              |      |            |      failure
         Path on   Write       Write        |
           disk   failed      failed    Re-auth +
              |   manifest   manifest   retry once
         passed    log warn   log warn       |
           to        cont.    NOT retried  +--+--+
        Extraction                        |     |
                                       Success Fails again
                                          |       |
                                       Write   Escalation
                                      success  handoff (BR-I-14)
                                      manifest + write failed
                                                  manifest
```

---

## PBT Applicability (Partial enforcement: PBT-02, 03, 07, 08, 09)

Unit 2 has limited pure-function surface area. PBT applies to:

| Rule | Applies? | Target |
|---|---|---|
| PBT-02 (round-trip) | No | No serialization round-trips in this unit |
| PBT-03 (invariants) | Yes | `discover_eligible_files` invariant: result never contains a `file_id` whose manifest record makes it ineligible (success; or failed with non-transient error_type) |
| PBT-07 (generator quality) | Yes | Date and MIME type generators must cover boundary (exactly 5 days) and edge cases; error_type generator must cover all four values |
| PBT-08 (shrinking) | Yes | Hypothesis auto-shrinking applies to list-of-file inputs |
| PBT-09 (framework) | Yes | Hypothesis is the required framework |

The primary invariants for PBT-03:
1. No file returned by `discover_eligible_files` has `manifest.get(file_id).status == "success"`.
2. No file returned by `discover_eligible_files` has a failed manifest record with `is_retriable=False` and `error_type` not in `{"business_date_eligibility"}` — unless the file also passed the date filter in step ii (in which case `business_date_eligibility` records are eligible).
3. Any file with `is_retriable=True` (transient) IS returned.
4. A file with `error_type="business_date_eligibility"` IS returned if and only if `now - last_modified >= eligibility_days` (already guaranteed by the date filter running before the manifest check).
