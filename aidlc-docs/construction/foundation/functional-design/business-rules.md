# Business Rules — Unit 1: Foundation

## BR-01: Manifest Write Policy (Terminal Outcomes Only)

A `ManifestRecord` is written **only on terminal outcomes**:

- **Write `status = "success"`** when the full pipeline completes successfully for a document (all stages: ingestion, extraction, analysis, export).
- **Write `status = "failed"`** when a permanent, non-retryable error occurs at any stage. A permanent error is one that is not a transient condition (see BR-02).
- **Do not write** a manifest record for transient errors — those are retried silently without touching the manifest.

Rationale: This ensures that a failed-mid-pipeline file is retried on the next run. Only a confirmed terminal result (success or permanent failure) produces a record.

---

## BR-02: Error Classification

Errors are classified into two categories for manifest purposes:

| Class | Definition | Manifest action |
|---|---|---|
| **Transient** | Rate limit hit (Drive API, Claude API), network timeout, temporary service unavailability | Do not write manifest — retry on next pipeline run |
| **Permanent** | Document parse failure (corrupted/unsupported file), business rule violation, validation failure, unrecoverable API error (e.g., 404 file not found) | Write `status = "failed"` with error detail |

The Coordinator is responsible for classifying errors and directing the appropriate manifest action.

---

## BR-03: Config Path Validation at Load Time

`Config.from_toml()` validates that **all** `Path` fields exist on disk before returning the Config instance:

- `vault_path` — must be an existing directory
- `images_path` — must be an existing directory
- `manifest_dir` — must be an existing directory
- `staging_dir` — must be an existing directory
- `scratchpad_path` — parent directory must exist (file itself may not yet exist)
- `credentials_path` — must be an existing, readable file

If **any** required path fails validation, a `ConfigError` is raised with a message identifying which path failed and why. The pipeline does not start.

Rationale: Fail fast — catching missing paths at startup prevents cryptic mid-run failures.

---

## BR-04: Categories — Load from TOML, Validate Against Vault

Categories follow a two-step process:

1. **Primary source**: Load `categories` list from `config.toml`. This is the authoritative list used at runtime.
2. **Startup validation**: At config load time, list the immediate subdirectories of `vault_path` and compare against `categories`. If any `config.toml` category has no matching vault subfolder, log a **warning** (not an error) to the scratchpad. The pipeline continues regardless.

Rationale: The vault is the ground truth for which categories exist. A warning on mismatch surfaces drift between config and vault without breaking the run. The Extraction Agent uses `Config.categories` as its selection list — it will never invent a category not in this list.

---

## BR-05: Manifest Corruption Handling

If `ManifestStore.get()` reads a manifest file that contains invalid/malformed JSON:

- Raise `ManifestCorruptionError` (a subclass of the general manifest error type).
- Do **not** silently return `None` or treat the file as unprocessed.
- The calling code (Coordinator) catches this and decides whether to halt or skip the document.

Rationale: A corrupted manifest means we cannot safely determine whether this document was previously processed. Silently re-processing could cause duplicate vault entries (violates AC-08.4). The Coordinator must make an explicit decision.

---

## BR-06: ManifestStore.is_processed() Semantics

`is_processed(file_id)` returns `True` if and only if:
- A manifest record exists for `file_id`, **AND**
- Its `status` is exactly `"success"`

Returns `False` if:
- No record exists
- Record exists with `status == "failed"`

Does **not** catch `ManifestCorruptionError` — that propagates to the caller.

---

## BR-07: RunSummary Accounting Identity

At the end of every pipeline run, the following must hold:

```
eligible == processed + failed + skipped
```

- `eligible`: files returned by Drive query that pass the 5-day rule and are not filtered by MIME type
- `processed`: completed the full pipeline → manifest written as `"success"`
- `failed`: hit a permanent error → manifest written as `"failed"`
- `skipped`: already in manifest with `status == "success"` → not re-processed

Files filtered out by MIME type (neither `.docx` nor `.pdf`) are **not counted** in `eligible`. They are silently ignored before the accounting window opens.

---

## BR-08: Config Immutability

`Config` is a frozen dataclass (`frozen=True`). Once loaded, no field may be modified at runtime. All agents receive the same `Config` instance. Any runtime state (e.g., discovered categories on disk) is computed once at load time and stored in the `Config`.

---

## BR-09: Manifest File Naming Convention

Each manifest record is stored as `{file_id}.json` inside `manifest_dir`. The `file_id` is the Google Drive file ID (alphanumeric + hyphens/underscores). No subdirectory structure within `manifest_dir`.
