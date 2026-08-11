# Business Rules — Unit 3: Extraction

## BR-E-01: Supported MIME Types

**Rule**: `_parse_document` handles exactly two MIME types:

| MIME type | Parser |
|---|---|
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `python-docx` |
| `application/pdf` | `pdfplumber` |

Any other MIME type reaching `ExtractionAgent.process()` indicates a bug in the Ingestion unit (which already filters by MIME). Raise `PipelineError(error_type="validation", is_retriable=False)`.

**Source**: FR-03, AC-04.1

---

## BR-E-02: Text Extraction Order Preservation

**Rule**: Text must be extracted in document reading order:
- `.docx`: paragraphs first (top-to-bottom), then table cells (row-major, left-to-right within each row). Tables interleaved with paragraphs retain their document position.
- `.pdf`: page-by-page (page 1 → page N), within each page in the order returned by `pdfplumber`.

Semantic content must not be reordered or deduplicated.

**Source**: FR-11, AC-04.2

---

## BR-E-03: Corrupted File Handling

**Rule**: If `_parse_document` raises any exception from the parsing library (e.g. `docx.opc.exceptions.PackageNotFoundError`, `pdfplumber.utils.exceptions.PDFSyntaxError`, `OSError`), the agent catches it and raises `PipelineError(error_type="business", is_retriable=False, text="Corrupted or unreadable file: {name}")`.

`process()` propagates `PipelineError` upward — it does NOT catch it. The Coordinator catches it.

**Source**: FR-10, AC-04.5

---

## BR-E-04: Category Selection — Constraint and Fallback

**Rule**: The Claude Haiku call in `_extract_and_classify` must return a category that is a member of `config.categories`. Post-response validation:
1. If the returned category exactly matches one value in `config.categories` (case-sensitive): accept it.
2. If it does not match: attempt case-insensitive match. If found: use the canonical casing from `config.categories`.
3. If still no match: use `config.categories[0]` (first configured category) as fallback; log a warning to the scratchpad: `"ExtractionAgent: model returned unknown category '{returned}'; defaulting to '{fallback}' for file {name}"`.

This is not a fatal error. The document is still exported; the user can reclassify manually if needed.

**Source**: FR-06, AC-04.3

---

## BR-E-05: Claude API Rate-Limit Retry

**Rule**: If the Claude Haiku API call returns HTTP 429:
1. Read the `retry-after` header value (seconds). If absent, default to 60.
2. Wait exactly that many seconds (`asyncio.sleep`).
3. Retry the exact same API call once.
4. If the retry also returns 429: raise `PipelineError(error_type="transient", is_retriable=True, text="Rate-limited by Claude API after retry")`.
5. If the retry returns any other error: raise `PipelineError(error_type="transient", is_retriable=True)` for 5xx, or `PipelineError(error_type="validation", is_retriable=False)` for 4xx non-429.

**Source**: FR-10, AC-04.6

---

## BR-E-06: Image Staging — Failure Tolerance

**Rule**: Image download failures during `_stage_images` are non-fatal:
- Per image: if download fails for any reason, skip that image (log warning to scratchpad: `"ExtractionAgent: failed to stage image {image_id} for {name}: {error}"`).
- The `CompactArtifact` is still produced with whatever images were successfully staged.
- A file with zero successfully staged images is valid — `images: []` is a legal `CompactArtifact`.

**Rationale**: Image staging failure should not block the text extraction result, which is the primary value.

**Source**: FR-06, AC-04.4

---

## BR-E-07: Image Data Isolation from LLMs

**Rule**: At no point during Extraction may raw image bytes or base64-encoded image data be included in any LLM prompt. Only `ImageMetadata(image_id, alt_text, staging_path)` is constructed. The staging path is a local disk reference only — it is never serialized into a prompt.

**Source**: FR-06, NFR-01, AC-04.4

---

## BR-E-08: Semantic Content Preservation

**Rule**: The Claude Haiku extraction prompt must instruct the model to reproduce all meaningful text verbatim. Enhancement (reformatting, summarization, paraphrasing) is not permitted at this stage. The model's output `text` field must preserve the semantic content of the source document.

**Source**: FR-11, AC-04.2

---

## BR-E-09: Concurrency — No Shared Mutable State

**Rule**: `ExtractionAgent` instances MUST NOT share mutable state. Each instance is created fresh per document by the Coordinator. The `anthropic.AsyncAnthropic` client may be shared across agents (it is thread/async safe) but the agent's per-call state (staging paths, intermediate text) must not leak between agents.

**Source**: NFR-02, AC-04.6

---

## BR-E-10: Staging Directory Structure

**Rule**: Images for a given document are staged under:
`config.staging_dir / {document_name_without_extension} / {image_id}_{original_filename}`

If `config.staging_dir / {document_name_without_extension}` does not exist, create it automatically.

Filename collision within the same document's staging folder: append `_(2)`, `_(3)` suffixes (same pattern as BR-I-06).

**Source**: FR-06, AC-04.4
