# Requirements Document — Extraction Pipeline (Revised 2026-08-14)

> **Scope change**: Original scope included Google Drive integration, OAuth, PDF extraction,
> category classification, image handling, and Obsidian vault export. All of those are deferred
> to a future iteration. The current scope is narrowed to local .docx → .md extraction only.
> The original requirements are preserved in git history.

---

## Intent Analysis Summary

- **User Request**: Extract text from local .docx files and convert them to Markdown files.
- **Request Type**: Brownfield (existing extraction codebase, scope-narrowed refactor)
- **Scope**: Single-agent pipeline — scan a local folder, extract text from .docx files via Claude, write .md output files mirroring the input folder structure.
- **Complexity**: Low — single agent, local file I/O, no external APIs beyond Claude.

---

## Functional Requirements

### FR-01: Input Discovery
- The pipeline accepts an `--input` directory path and recursively discovers all `.docx` files within it, including nested subdirectories.
- No manual file list — discovery is automatic via `rglob("*.docx")`.

### FR-02: Output Structure
- The pipeline accepts an `--output` directory path.
- For each discovered `.docx` file, a corresponding `.md` file is written to `--output`, preserving the relative subdirectory structure of the input.
- Example: `input/legal/contract.docx` → `output/legal/contract.md`
- Output directories are created automatically as needed.

### FR-03: Supported Input Formats
- `.docx` only. All other file types are ignored silently.

### FR-04: Text Extraction
- Text is extracted from each `.docx` file using the `parse_document` MCP tool (backed by `mammoth`).
- The extracted text is written verbatim to the output `.md` file — no summarization, formatting, or paraphrasing.

### FR-05: Extraction Agent
- A single `ExtractionAgent` processes files sequentially.
- Uses Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) as the extraction model.
- The agent calls `parse_document` via MCP and returns a `CompactArtifact` with `document_name` and `extracted_text`.

### FR-06: Error Handling
- **Corrupted or unreadable files**: logged to scratchpad, pipeline continues with next file.
- **Claude API rate limits**: one retry after `retry-after` seconds; if second attempt also fails, error is logged and pipeline continues.
- **Scratchpad log**: written to `{output}/scratchpad.jsonl` — one JSONL entry per event.

### FR-07: Semantic Preservation
- The pipeline must not alter the semantic content of documents.
- No summarization, paraphrasing, or reformatting at this stage.

---

## Non-Functional Requirements

### NFR-01: No External Service Dependencies
- No Google Drive, no OAuth, no GCP project required.
- Only dependency beyond stdlib: `anthropic[mcp]`, `mcp`, `mammoth`.
- `ANTHROPIC_API_KEY` must be set in the environment.

### NFR-02: Platform
- Runs on Windows 11 (and any platform with Python 3.11+).
- Invoked from the terminal: `python -m pipeline.main --input ./docs --output ./output`

### NFR-03: Property-Based Testing (Partial Enforcement)
- **Hypothesis** is used for property-based tests.
- Enforcement scope: PBT-02 (round-trip), PBT-07 (generator quality), PBT-08 (shrinking).

---

## Architecture

```
--input directory
     |
     | rglob("*.docx")
     v
+---------------------------+
|  main.py                  |  discovers files, iterates
+---------------------------+
     |  docx_path (Path)
     v
+---------------------------+
|  ExtractionAgent          |  Claude Haiku + MCP
|  - parse_document tool    |  (mammoth)
+---------------------------+
     |  CompactArtifact
     |  {document_name, extracted_text}
     v
+---------------------------+
|  main.py                  |  writes {stem}.md to --output
+---------------------------+
     |
     v
--output directory (mirrored structure)
```

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Input | Local directory, recursive | No GCP/OAuth available |
| Format | .docx only | PDF dropped — no pymupdf install path on this environment |
| Output | .md files, mirrored structure | Simple, predictable, no vault dependency |
| Parser | mammoth | Pure Python, no native DLLs, always installable |
| Model | Claude Haiku 4.5 | Fast, low cost, sufficient for verbatim extraction |
| Drive / OAuth | Deferred | No GCP project access; next iteration |
| Categories / Analysis | Deferred | Out of scope for this iteration |
| Images | Deferred | Out of scope for this iteration |
