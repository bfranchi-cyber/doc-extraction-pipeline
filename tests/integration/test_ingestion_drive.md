# Integration Test Plan — Unit 2: Ingestion (Live Drive)

## Purpose

This document describes the integration tests that verify `ingestion.py` against a real Google Drive folder via the Drive REST API. These tests are **not automated in CI** — they require live credentials, a real Drive folder, and network access.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Valid `token.json` at `credentials_path` | Run the pipeline interactively once to generate |
| `client_secrets.json` in parent directory | Download from Google Cloud Console |
| Test Drive folder ID | A dedicated folder, separate from production |
| At least two `.docx` or `.pdf` files in the test folder | One modified > 5 days ago, one < 5 days ago |
| Python environment with all runtime deps installed | `pip install -e ".[dev]"` |

---

## Test Scenarios

### IT-ING-01: Live folder scan returns eligible files

**Setup**: Place 2 `.docx` files in the test folder — one modified 10 days ago, one modified 2 days ago.

**Steps**:
1. Load `Config` with `drive_folder_id` pointing at the test folder.
2. Call `discover_eligible_files(config, ManifestStore(manifest_dir), GoogleDriveClient(creds))`.
3. Assert: result contains exactly the file modified 10 days ago.
4. Assert: file modified 2 days ago is absent.

---

### IT-ING-02: OAuth token refresh

**Setup**: Manually expire the access token in `token.json` (set `expiry` to a past timestamp, keep `refresh_token`).

**Steps**:
1. Call `authenticate(config)`.
2. Assert: call succeeds and returns valid credentials.
3. Assert: `token.json` is updated with a new expiry.

---

### IT-ING-03: Non-interactive failure on missing token

**Setup**: Delete `token.json`. Run under a non-interactive context (redirect stdin from `/dev/null`).

**Steps**:
1. Call `authenticate(config)`.
2. Assert: `CredentialsMissingError` is raised with a helpful message.

---

### IT-ING-04: File download to staging directory

**Setup**: One eligible `.docx` file in the test folder.

**Steps**:
1. Call `discover_eligible_files` to get `DriveFileMetadata`.
2. Call `download_file(metadata, staging_dir, client)`.
3. Assert: file exists at the returned `Path`.
4. Assert: file is non-empty.
5. Assert: filename matches the Drive filename (or collision suffix if a file already exists at that path).

---

### IT-ING-05: Subfolder recursion

**Setup**: Test folder contains a subfolder with a `.pdf` file modified 7 days ago.

**Steps**:
1. Call `discover_eligible_files` with root folder ID.
2. Assert: the `.pdf` in the subfolder is included in results.

---

### IT-ING-06: Rate-limit handling (manual simulation)

**Note**: This cannot be triggered deterministically. If a rate-limit response is observed during manual testing, verify in the scratchpad log that a `WARN` entry was written with the retry-after duration.

---

## How to Run

```bash
# From workspace root with deps installed
python -m pytest tests/integration/ -v --no-header -k "ingestion"
```

**Important**: Integration tests are skipped in CI. Mark them with `@pytest.mark.integration` and add `-m "not integration"` to the CI `pytest` invocation.

---

## Why Not Automated in CI

- Requires live OAuth credentials (cannot be safely stored in CI environment)
- Depends on a real Google Drive folder with specific test data
- Network access to Drive API may be unavailable in isolated CI runners
- Rate limits could cause non-deterministic failures

Integration tests should be run manually before a release and after any changes to `ingestion.py` that affect Drive API interaction or OAuth handling.
