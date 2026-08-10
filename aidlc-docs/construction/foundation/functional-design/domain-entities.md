# Domain Entities — Unit 1: Foundation

## Overview

All domain entities are defined in `pipeline/models.py`. They are shared across all units and represent the stable data contracts of the pipeline.

---

## DriveFileMetadata

Represents a file discovered in Google Drive that is eligible for processing.

| Field | Type | Description |
|---|---|---|
| `file_id` | `str` | Unique Drive file identifier |
| `name` | `str` | File name including extension |
| `mime_type` | `str` | `"application/vnd.openxmlformats-officedocument.wordprocessingml.document"` or `"application/pdf"` |
| `last_modified` | `datetime` | UTC timestamp of last modification on Drive |
| `download_url` | `str` | Direct download URL for the file binary |

**Invariants**:
- `mime_type` must be one of the two supported values
- `last_modified` must be timezone-aware (UTC)
- `file_id` is non-empty

---

## ImageMetadata

Lightweight metadata for a single image extracted from a document. Raw image data is never stored here.

| Field | Type | Description |
|---|---|---|
| `image_id` | `str` | Unique identifier within the document (e.g., `"img_001"`) |
| `alt_text` | `str` | Alt-text string (may be empty string if none present in source) |
| `staged_path` | `Path` | Absolute path to the locally staged image file during extraction |

**Invariants**:
- `image_id` is non-empty and unique within its document
- `staged_path` is set during extraction; may not yet exist on disk until `_stage_images` completes

---

## CompactArtifact

TypedDict representing the structured output of the Extraction stage. Designed for token-efficient handoff to the Analysis stage. Image binary data is never included.

| Field | Type | Description |
|---|---|---|
| `file_id` | `str` | Drive file ID (links back to `DriveFileMetadata`) |
| `document_name` | `str` | File name without extension, used as folder/file stem downstream |
| `extracted_text` | `str` | Full plain text extracted from the document |
| `category` | `str` | Category label selected from the pre-existing vault category list |
| `images` | `list[ImageMetadata]` | Metadata-only list; no binary data |

**Invariants**:
- `category` must be a value present in `Config.categories`
- `extracted_text` is non-empty (a document with no extractable text is a failure, not a valid artifact)
- `images` may be empty (documents with no images are valid)

---

## EnrichedDocument

Output of the Analysis stage. Contains the final Markdown with frontmatter, abstract, and body.

| Field | Type | Description |
|---|---|---|
| `file_id` | `str` | Drive file ID |
| `document_name` | `str` | Document name stem |
| `category` | `str` | Category from `CompactArtifact` (propagated unchanged) |
| `markdown` | `str` | Complete Markdown: YAML frontmatter + abstract section + enriched body |

**Invariants**:
- `markdown` must start with a YAML frontmatter block (`---\n...\n---`)
- `markdown` must contain an abstract section
- `category` is unchanged from the `CompactArtifact` that produced this document

---

## ManifestRecord

Persisted state for a single Drive document. One JSON file per document in `manifest_dir/`.

| Field | Type | Description |
|---|---|---|
| `file_id` | `str` | Drive file ID (also used as the filename: `{file_id}.json`) |
| `name` | `str` | Human-readable file name |
| `status` | `str` | `"success"` or `"failed"` |
| `processed_at` | `str` | ISO 8601 UTC timestamp of when the record was written |
| `error` | `str \| None` | Error message if `status == "failed"`, otherwise `None` |

**Invariants**:
- `status` is exactly `"success"` or `"failed"` — no other values are valid
- A record is only written on terminal outcome (full pipeline success, or permanent/non-retryable failure)
- Transient errors (rate limits, timeouts) do not produce a manifest record — they are retried silently
- `error` is `None` when `status == "success"` and non-None when `status == "failed"`

---

## RunSummary

Aggregated statistics for a single pipeline run. Produced by `PipelineCoordinator._build_run_summary()`.

| Field | Type | Description |
|---|---|---|
| `eligible` | `int` | Total files discovered as eligible for this run |
| `processed` | `int` | Files that completed the full pipeline successfully |
| `failed` | `int` | Files that hit a permanent/non-retryable error |
| `skipped` | `int` | Files skipped because they are already in the manifest with `status == "success"` |

**Invariants**:
- `eligible == processed + failed + skipped` (all eligible files must be accounted for)
- `skipped` counts only manifest-based skips — unsupported format files are not counted in `eligible` (they are filtered before eligibility assessment)
- All counts are non-negative

---

## ExportResult

Return value of `ExportAgent.export()`. Reports outcome of the export step for one document.

| Field | Type | Description |
|---|---|---|
| `file_id` | `str` | Drive file ID |
| `status` | `str` | `"success"` or `"failed"` |
| `vault_path` | `Path \| None` | Absolute path of the written `.md` file, or `None` on failure |
| `error` | `str \| None` | Error detail on failure, otherwise `None` |

---

## Config

Immutable runtime configuration. Loaded once at startup from `config.toml`.

| Field | Type | Description |
|---|---|---|
| `vault_path` | `Path` | Root of the Obsidian vault (`C:\Users\bfranchi\Documents\Obsidian Vault`) |
| `images_path` | `Path` | Root images folder (`C:\Users\bfranchi\Documents\Obsidian Images`) |
| `manifest_dir` | `Path` | Directory for per-document manifest JSON files |
| `staging_dir` | `Path` | Temporary directory for image staging during extraction |
| `scratchpad_path` | `Path` | Path to the scratchpad log file |
| `credentials_path` | `Path` | Path to OAuth 2.0 credentials JSON |
| `drive_folder_id` | `str` | Google Drive folder ID to monitor |
| `categories` | `list[str]` | Ordered list of category names loaded from `config.toml` |
| `extraction_model` | `str` | Model ID for Haiku 4.5 |
| `analysis_model` | `str` | Model ID for Sonnet 4.5 |
| `eligibility_days` | `int` | Days since last modification before a file is eligible (default: 5) |

**Invariants**:
- All `Path` fields are validated to exist on disk at load time (raises `ConfigError` if any is missing)
- `categories` is non-empty
- `eligibility_days` is a positive integer
- `credentials_path` must exist and be a readable file
