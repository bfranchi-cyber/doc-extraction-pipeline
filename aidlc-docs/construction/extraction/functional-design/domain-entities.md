# Domain Entities — Unit 3: Extraction

## Entities (from Unit 1 Foundation — used, not redefined)

### `DriveFileMetadata`
Produced by Unit 2 Ingestion. Carries the identity and location of a file ready for extraction.

| Field | Type | Description |
|---|---|---|
| `file_id` | `str` | Google Drive file ID |
| `name` | `str` | Original filename (e.g. `Report Q1.docx`) |
| `mime_type` | `str` | `application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `last_modified` | `datetime` | Drive last-modified timestamp (UTC) |
| `staging_path` | `Path` | Absolute path to the downloaded file on disk |

### `ImageMetadata`
Lightweight image descriptor. The only image data that ever reaches an LLM. No raw bytes, no base64.

| Field | Type | Description |
|---|---|---|
| `image_id` | `str` | Drive media ID or internal ID |
| `alt_text` | `str` | Alt-text string from the source document; empty string if absent |
| `staging_path` | `Path` | Absolute path to the image file in the staging directory |

### `CompactArtifact`
The structured output of the Extraction unit. Handed off to the Coordinator for routing to the Analysis unit.

| Field | Type | Description |
|---|---|---|
| `file_id` | `str` | Google Drive file ID (links artifact back to source file) |
| `name` | `str` | Original filename |
| `category` | `str` | Selected category (one value from `Config.categories`) |
| `text` | `str` | Extracted text content; semantic content unchanged from source |
| `images` | `list[ImageMetadata]` | Lightweight image descriptors; may be empty |
| `processed_at` | `str` | ISO 8601 UTC timestamp of extraction completion |

---

## New Entity: `ExtractionAgent`

A stateless async processor — one instance per document. Holds references to shared configuration and infrastructure but carries no per-document mutable state after `process()` returns.

| Attribute | Type | Description |
|---|---|---|
| `config` | `Config` | Pipeline configuration (model IDs, paths, categories) |
| `drive_client` | `DriveClient` | Injectable Drive protocol for image downloads |
| `scratchpad` | `Scratchpad` | Shared logging facility |
| `claude_client` | `anthropic.AsyncAnthropic` | Async Claude API client |

### Methods

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(config, drive_client, scratchpad)` | Initialize with shared dependencies |
| `process` | `async (file_metadata) -> CompactArtifact` | Full extraction pipeline for one file |
| `_parse_document` | `(staging_path, mime_type) -> str` | Parse raw file into plain text |
| `_extract_and_classify` | `async (file_metadata, raw_text) -> tuple[str, str]` | Call Claude Haiku; return (text, category) |
| `_stage_images` | `async (file_metadata) -> list[ImageMetadata]` | Download images to staging; return metadata list |

---

## Entity Relationships

```
DriveFileMetadata  ──(input to)──►  ExtractionAgent.process()
                                             │
                         ┌───────────────────┼────────────────────┐
                         ▼                   ▼                    ▼
                  _parse_document    _extract_and_classify   _stage_images
                         │                   │                    │
                         └───────────────────┴────────────────────┘
                                             │
                                             ▼
                                     CompactArtifact
                                      ├── text: str
                                      ├── category: str
                                      └── images: list[ImageMetadata]
```
