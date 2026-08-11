# Business Logic Model — Unit 3: Extraction

## Overview

The Extraction unit is responsible for three sequential operations per document:

1. **Parse** — convert the raw downloaded file (`.docx` or `.pdf`) into structured text content
2. **Classify** — select the best-fit category from the existing Obsidian vault folders
3. **Stage images** — download image assets from Drive to a local staging directory and record lightweight metadata only

These three operations run inside `ExtractionAgent.process()`. Multiple `ExtractionAgent` instances are invoked concurrently by the Coordinator via `asyncio.gather` — one agent per eligible file.

---

## Core Workflow: `ExtractionAgent.process(file_metadata)`

```
Input : DriveFileMetadata  (file_id, name, mime_type, last_modified, staging_path)
Output: CompactArtifact    (text, category, images: list[ImageMetadata])
Errors: PipelineError      (error_type in {"transient","business","validation"})
```

### Step 1 — `_parse_document(staging_path, mime_type)`

- If `mime_type` == `.docx`: use `python-docx` to extract paragraph text and table cell text, in document order.
- If `mime_type` == `.pdf`: use `pdfplumber` to extract text page-by-page in order.
- If the file is unreadable / corrupted: raise `PipelineError(error_type="business", is_retriable=False)` with a descriptive message. The Coordinator catches this and marks the file failed without halting the pipeline.
- Output: `raw_text: str` (plain text, whitespace-normalized).

### Step 2 — `_extract_and_classify(file_metadata, raw_text, config)`

- Build a prompt to Claude Haiku 4.5 (`config.extraction_model`) that includes:
  - The full `raw_text`
  - The list of valid categories (`config.categories`)
  - Instructions: extract all meaningful content verbatim; pick the single best-fit category from the provided list.
- Call the Claude API (via `anthropic.AsyncAnthropic`).
- Parse the response to extract:
  - `extracted_text: str` — the model's cleaned/extracted text content (semantic content unchanged)
  - `category: str` — one value from `config.categories`; validated post-parse.
- **Category validation**: if the model returns a value not in `config.categories`, default to the first category and log a warning to the scratchpad (not a fatal error).
- Rate-limit handling: if the Claude API returns HTTP 429 with `retry-after`, wait and retry once (BR-E-05).
- Output: `(extracted_text, category)`

### Step 3 — `_stage_images(file_metadata, drive_client)`

- Query the Drive API for inline images attached to the document (via `drive_client.list_images(file_id)` — returns list of image items with `id` and `alt_text`).
- For each image:
  - Download to `config.staging_dir / file_metadata.name / {image_id}_{original_filename}`.
  - Record `ImageMetadata(image_id=..., alt_text=..., staging_path=...)`.
  - Never pass raw bytes or base64 to any LLM.
- If an image download fails: skip that image (log warning), do not abort the document.
- Output: `images: list[ImageMetadata]`

### Final assembly

```python
return CompactArtifact(
    file_id       = file_metadata.file_id,
    name          = file_metadata.name,
    category      = category,
    text          = extracted_text,
    images        = images,
    processed_at  = datetime.now(timezone.utc).isoformat(),
)
```

---

## Concurrency Model

- `ExtractionAgent` is instantiated once per file inside the Coordinator.
- The Coordinator calls `asyncio.gather(*[agent.process(f) for f in eligible_files])`.
- Each agent independently makes async calls to the Claude API.
- Results are collected as a list of `CompactArtifact | PipelineError` values — failures do not cancel other concurrent agents.
- Claude API rate limits across concurrent agents are managed by Anthropic SDK's built-in retry behaviour plus the per-agent single-retry on 429 (BR-E-05).

---

## Corrupted File Handling

When `_parse_document` raises a `PipelineError(error_type="business")`, `process()` propagates it to the Coordinator. The Coordinator:
1. Logs the error to the scratchpad (level=error).
2. Writes `ManifestRecord(status="failed", error=...)`.
3. Continues processing remaining files — no pipeline halt.

This satisfies AC-04.5 (corrupted file graceful handling).
