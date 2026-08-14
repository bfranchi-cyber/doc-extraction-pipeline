# Units of Work — Extraction Pipeline (Revised 2026-08-14)

> **Scope change**: Original decomposition had 5 units (Foundation, Ingestion, Extraction,
> Analysis, Export+Coordinator). Units 1, 2, 4, and 5 are dropped. Only Unit 3 (Extraction)
> survives, renamed simply "Extraction". See git history for original unit decomposition.

---

## Unit: Extraction

**Description**: Local .docx → .md extraction pipeline. Discovers .docx files recursively, extracts text via Claude Haiku + MCP, writes .md output mirroring input structure.

**Components**:
- `src/pipeline/main.py` — CLI entry point, file discovery, output writing
- `src/pipeline/extraction.py` — `ExtractionAgent` class
- `src/pipeline/extraction_server.py` — FastMCP server with `parse_document` tool
- `src/pipeline/models.py` — `CompactArtifact`, `EnrichedDocument`
- `src/pipeline/exceptions.py` — `PipelineError`, `ExtractionPipelineError`
- `src/pipeline/scratchpad.py` — JSONL logger
- `tests/unit/test_extraction.py`
- `tests/unit/test_scratchpad.py`
- `tests/property/test_extraction_pbt.py`

**Acceptance criteria**:
- All .docx files under --input are discovered recursively
- Extracted text is written verbatim to .md (no summarization)
- Corrupted files are logged and skipped; pipeline continues
- Output mirrors input subdirectory structure

**Depends on**: nothing (self-contained)

---

## Dropped Units (scope change 2026-08-14)

| Unit | Status | Reason |
|---|---|---|
| Unit 1: Foundation | Dropped | Config/manifest/Drive types removed |
| Unit 2: Ingestion | Dropped | No Google Drive / OAuth |
| Unit 4: Analysis | Dropped | Deferred to next iteration |
| Unit 5: Export + Coordinator | Dropped | Deferred to next iteration |
