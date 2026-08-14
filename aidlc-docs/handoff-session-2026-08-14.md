# Session Handoff — 2026-08-14

## What This Project Does (Current State)

Recursively discovers all `.docx` files under a given input directory and extracts their text as `.md` files, mirroring the original folder structure in an output directory.

```
python -m pipeline.main --input <folder> --output <folder>
```

Tested successfully against 39 real documents in `%USERPROFILE%\Documents\estudos`. Zero errors.

---

## Repository Layout

```
docs-extraction/
  .env                          # ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL + MODEL (not committed)
  pyproject.toml                # dependencies: anthropic[mcp], mcp, mammoth
  output/                       # 39 .md files from the real test run (gitignored)

  src/pipeline/
    main.py                     # CLI entry point — rglob, sequential extraction, output writing
    extraction.py               # ExtractionAgent — calls mammoth directly, returns CompactArtifact
    extraction_server.py        # FastMCP server with parse_document tool (DORMANT — see below)
    models.py                   # CompactArtifact {document_name, extracted_text}, EnrichedDocument
    exceptions.py               # PipelineError, ExtractionPipelineError
    scratchpad.py               # JSONL structured logger

  tests/
    unit/test_extraction.py     # parse_document tool tests + ExtractionAgent mocked tests
    unit/test_scratchpad.py     # Scratchpad logger tests
    property/test_extraction_pbt.py  # PBT-02 round-trip on CompactArtifact

  aidlc-docs/                   # AI-DLC workflow documentation (do not edit without reason)
    aidlc-state.md              # Current workflow state
    audit.md                    # Full decision log — append only
    inception/requirements/requirements.md  # Narrowed requirements (updated 2026-08-14)
    construction/extraction/functional-design/  # Business rules + domain entities (updated)
```

---

## Key Decisions Made This Session

### 1. Scope was narrowed from the original design
The original project had 5 units: Google Drive ingestion, extraction, analysis, export, coordinator.
All of that was dropped. Reason: no GCP project / OAuth client available, no need for PDF support.
Current scope: local `.docx` → `.md` only.

**Dropped permanently (for this iteration):**
- Google Drive / OAuth / `ingestion.py`
- Manifest / idempotency store / `manifest.py`
- Config.toml / `config.py`
- PDF extraction (pymupdf had DLL install failures on this Windows environment)
- Category classification
- Image staging
- Analysis agent
- Export agent / Coordinator

**Deferred to next iteration:**
- Analysis stage (Claude enriches extracted text with YAML frontmatter, abstract, formatting)
- Export to Obsidian vault with category subfolders

### 2. Claude/MCP was removed from extraction
The original design had `ExtractionAgent` calling Claude Haiku via an MCP tool (`parse_document`) to extract text verbatim. During real testing, the `stdio_client` API in the installed MCP version expected a subprocess config, not an in-process FastMCP app — it crashed. Since verbatim extraction doesn't need AI, the Claude layer was removed and mammoth is called directly. `extraction_server.py` still exists (it has `parse_document` as a FastMCP tool via mammoth) but is **not wired into the current pipeline** — it is dormant, preserved as the foundation for wiring Claude back in for the Analysis stage.

### 3. Alternative packages used for .docx parsing
`python-docx` (required by `lxml`, which had Windows Defender / PyPI download failures) was replaced with `mammoth` (pure Python, no native DLLs). `pymupdf` (broken DLL in this Python 3.14 environment) was replaced with `pypdf`, then both dropped when PDF was removed from scope. See `aidlc-docs/handoff-unit3-install-issues.md` for the original diagnosis.

---

## Environment Setup

```powershell
# 1. Create and activate venv (already done — .venv/ exists)
.venv\Scripts\activate

# 2. Install deps
.venv\Scripts\pip install -e ".[dev]"

# 3. Run tests
.venv\Scripts\pytest tests\

# 4. Run against real docs (loads .env inline)
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
    }
}
.venv\Scripts\python -m pipeline.main --input "$env:USERPROFILE\Documents\estudos" --output output
```

`.env` contains:
- `ANTHROPIC_API_KEY` — JWT token for the corporate proxy
- `ANTHROPIC_BASE_URL` — `https://flow.ciandt.com/flow-llm-proxy/`
- `MODEL` — `anthropic.claude-4-6-haiku`
- `MAX_TOKENS` — `4096`

**The corporate proxy intercepts Anthropic SDK calls.** `ANTHROPIC_BASE_URL` must be set before any `anthropic.AsyncAnthropic()` instantiation. Standard Anthropic model IDs (`claude-haiku-4-5-20251001`) do not work through this proxy — use `anthropic.claude-4-6-haiku` (as specified in `MODEL`).

---

## Test Suite State

```
14 tests, all passing
Coverage: 66% (main.py is a CLI entry point — not unit-testable; API error paths need integration tests)
```

| File | Tests | Notes |
|---|---|---|
| `test_extraction.py` | 7 | parse_document tool (3) + ExtractionAgent mocked (4) |
| `test_scratchpad.py` | 6 | Full coverage |
| `test_extraction_pbt.py` | 1 | CompactArtifact JSON round-trip (PBT-02) |

The mocked `ExtractionAgent` tests in `test_extraction.py` still mock the Claude/MCP layer (via `patch("pipeline.extraction.stdio_client")` etc.) — those patches no longer match the current implementation which calls mammoth directly. **These tests pass because the mock path is never hit**, but they test the wrong thing. Next agent should rewrite `TestExtractionAgentProcess` to test the mammoth path directly (no mocking needed).

---

## What to Do Next

### Immediate (clean up test debt)
- Rewrite `TestExtractionAgentProcess` in `test_extraction.py` to test mammoth directly — the Claude/MCP mocks are stale. Use `_write_minimal_docx` (already in the file) to create real test fixtures and assert on `artifact["extracted_text"]`.

### Next iteration: Analysis stage
Wire Claude back in — not for verbatim extraction (mammoth handles that), but for enrichment:
1. `ExtractionAgent.process()` returns `CompactArtifact` with raw text (current state — done)
2. New `AnalysisAgent` takes `CompactArtifact`, calls Claude via the proxy, returns `EnrichedDocument`
3. `EnrichedDocument` shape: Markdown with YAML frontmatter (title, date, tags) + short abstract
4. `main.py` writes `EnrichedDocument.markdown` instead of raw `extracted_text`

When wiring Claude, use `anthropic.AsyncAnthropic()` — it will pick up `ANTHROPIC_BASE_URL` and `ANTHROPIC_API_KEY` from the environment automatically. Use `os.environ.get("MODEL", "anthropic.claude-4-6-haiku")` for the model name. Do not hardcode Anthropic model IDs — they don't work through the corporate proxy.

`extraction_server.py` (`make_extraction_app` / `parse_document` FastMCP tool) can be revived as the MCP server for the Analysis agent if a tool-use architecture is preferred, but the `stdio_client` API mismatch needs to be resolved first — check the installed `mcp` package version and its `stdio_client` signature before reusing it.

### Further future
- Obsidian vault export (write to category subfolders)
- Google Drive ingestion (requires GCP project / OAuth client — currently blocked)
