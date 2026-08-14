# Business Rules — Extraction Unit (Revised 2026-08-14)

> **Scope change**: BR-E-01 (PDF), BR-E-04 (categories), BR-E-05 (rate-limit specifics),
> BR-E-06 (image staging), BR-E-07 (image isolation), BR-E-09 (concurrency),
> BR-E-10 (staging dirs) are all dropped — the features they governed are out of scope.
> Remaining rules updated to reflect the narrowed scope.

---

## BR-E-01: Supported Input Format

**Rule**: `parse_document` handles `.docx` files only via `mammoth.extract_raw_text()`.

Any other file type reaching `ExtractionAgent.process()` is a caller error.
Raise `PipelineError(error_type="validation", is_retriable=False)`.

**Source**: FR-03

---

## BR-E-02: Text Extraction Order Preservation

**Rule**: Text must be extracted in document reading order as returned by `mammoth`.
Semantic content must not be reordered or deduplicated.

**Source**: FR-07

---

## BR-E-03: Corrupted File Handling

**Rule**: If `parse_document` raises any exception from `mammoth` (e.g. invalid zip, malformed XML, `OSError`), the tool catches it and raises `PipelineError(error_type="business", is_retriable=False, text="Corrupted or unreadable file: {name}")`.

`process()` propagates `PipelineError` upward. `main.py` catches it, logs to scratchpad, and continues with the next file.

**Source**: FR-06

---

## BR-E-05: Claude API Rate-Limit Retry

**Rule**: If the Claude API call returns HTTP 429:
1. Read `retry-after` header (seconds). Default to 60 if absent.
2. Wait that many seconds (`asyncio.sleep`).
3. Retry the exact same API call once.
4. If retry also returns 429: raise `PipelineError(error_type="transient", is_retriable=True)`.
5. If retry returns any other error: raise `PipelineError` typed by status (5xx → transient, 4xx → validation).

**Source**: FR-06

---

## BR-E-08: Semantic Content Preservation

**Rule**: The Claude Haiku extraction prompt must instruct the model to reproduce all meaningful text verbatim. Summarization, paraphrasing, and reformatting are not permitted at this stage.

**Source**: FR-07
