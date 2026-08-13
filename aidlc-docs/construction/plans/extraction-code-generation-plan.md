# Code Generation Plan — Unit 3: Extraction (MCP Revision)

## Unit Context

**Unit**: Unit 3 — Extraction
**Stories**: US-04 (AC-04.1–AC-04.6)
**Depends on**: Unit 1 (Foundation) — `Config`, `CompactArtifact`, `DriveFileMetadata`, `ImageMetadata`, `PipelineError`, `Scratchpad`
**Other units depend on this**: Unit 5 (Coordinator invokes `ExtractionAgent.process()`)

**Source root**: `src/pipeline/` (src/ layout, greenfield)
**Test root**: `tests/`
**Workspace root**: `c:\Users\bfranchi\Desktop\projetos\docs-extraction`

---

## Architecture Decision: MCP via local stdio + tool_runner

The extraction pipeline is restructured as a **local stdio MCP server** whose tools Claude
orchestrates via `client.beta.messages.tool_runner(...)`.

```
ExtractionAgent.process()
    │
    ├─ starts in-process FastMCP server (stdio transport)
    │
    └─ client.beta.messages.tool_runner(
           model=config.extraction_model,
           tools=[async_mcp_tool(t, mcp_session) for t in tools],
           messages=[{"role": "user", "content": <task prompt>}]
       )
           │
           Claude reasons and dispatches tool calls in sequence:
           │
           ├─ parse_document(file_path, mime_type) → raw_text
           ├─ (Claude internally selects category from config.categories)
           └─ stage_images(file_id, document_name) → list[ImageMetadata as dicts]
           │
           └─ tool_runner loop ends when Claude returns final text response:
              JSON {"extracted_text": "...", "category": "..."}
```

**Key decisions**:
- `mcp` package (v1.8.0) is already installed system-wide; must be added to `pyproject.toml`
- `anthropic[mcp]` extra required: `pip install "anthropic[mcp]"` — adds `async_mcp_tool` helper
- FastMCP server runs **in-process** via `stdio_server()` context manager (no subprocess)
- `tool_runner` handles the tool-call loop; `await runner.until_done()` blocks until final response
- `parse_document` and `stage_images` are `@tool`-decorated async functions on the FastMCP app
- Category selection remains Claude's LLM reasoning (in the task prompt, not a tool call)
- `process()` signature unchanged: `async def process(self, file_metadata, staging_path) -> CompactArtifact`
- `asyncio.run()` pattern for tests (no `pytest-asyncio` dependency)

---

## PBT Compliance Check (Partial enforcement: PBT-02, 03, 07, 08, 09)

| Rule | Applicability | Plan coverage |
|---|---|---|
| PBT-02 (round-trip) | YES — `CompactArtifact` text fields survive JSON round-trip | Step 5: `test_extraction_pbt.py` round-trip test |
| PBT-03 (invariants) | YES — category always in `config.categories`; images list valid `ImageMetadata` | Step 5: invariant tests |
| PBT-07 (generator quality) | YES — MIME generators, category boundary generators | Step 5: custom generators |
| PBT-08 (shrinking) | YES — no `suppress_health_check` disabling shrinking; `@settings(max_examples=...)` | Step 5: enforced in test structure |
| PBT-09 (framework) | YES — `hypothesis` in pyproject.toml dev deps | Already satisfied |

---

## Generation Steps

- [x] Step 1: Update `pyproject.toml` — add `anthropic[mcp]` and `mcp` dependencies
- [x] Step 2: Create `src/pipeline/extraction_server.py` — FastMCP server with `parse_document` and `stage_images` tools
- [x] Step 3: Create `src/pipeline/extraction.py` — `ExtractionAgent` using `tool_runner` + MCP session
- [x] Step 4: Create `tests/unit/test_extraction.py` — unit tests with mocked MCP tools and mocked tool_runner
- [x] Step 5: Create `tests/property/test_extraction_pbt.py` — PBT-02, 03, 07, 08 property tests
- [x] Step 6: Create `tests/integration/test_extraction_claude.md` — integration test plan doc

---

## Step Details

### Step 1 — Update `pyproject.toml`

Add to `[project].dependencies`:
```toml
"anthropic[mcp]>=0.25",
"mcp>=1.8",
```

Remove plain `"anthropic>=0.25"` (replaced by the `[mcp]` extra variant).
`pymupdf>=1.24` and `python-docx>=1.1` remain (used inside the MCP tools).

---

### Step 2 — `src/pipeline/extraction_server.py`

**Purpose**: In-process FastMCP server exposing two tools Claude orchestrates.

```python
from __future__ import annotations

from pathlib import Path

import fitz          # pymupdf
import docx          # python-docx

from mcp.server.fastmcp import FastMCP

from pipeline.exceptions import PipelineError
from pipeline.models import ImageMetadata

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"

def make_extraction_app(image_client: ImageClient, scratchpad: Scratchpad) -> FastMCP:
    """Factory — returns a fresh FastMCP app bound to the given clients. Safe for concurrent use."""
    app = FastMCP("extraction-server")
    # register tools on this instance ...
    return app
```

**`parse_document` tool**:
```python
@app.tool()
async def parse_document(file_path: str, mime_type: str) -> str:
    """Parse a .docx or .pdf file and return its text in document reading order."""
```
- `docx`: iterate `doc.paragraphs` + tables (row-major); join with `\n`; catch `Exception` → raise `PipelineError(error_type="business", is_retriable=False, text=f"Corrupted or unreadable file: {Path(file_path).name}", suggestion="Re-download or remove the file from Drive.")`
- `pdf`: `fitz.open(file_path)`, `page.get_text()` page 0→N-1; same error handling
- Unknown MIME → raise `PipelineError(error_type="validation", is_retriable=False, text=f"Unsupported MIME type: {mime_type}")`
- Return `raw_text.strip()`

**`stage_images` tool** — takes an injectable `ImageClient` stored on the app instance:
```python
@app.tool()
async def stage_images(file_id: str, document_name: str, staging_dir: str) -> list[dict]:
    """Download images for a document; return list of ImageMetadata dicts. Failures are skipped."""
```
- Calls `app.image_client.list_images(file_id)` — list of `{"id": ..., "filename": ..., "alt_text": ...}`
- For each item: `dest_dir = Path(staging_dir) / Path(document_name).stem`; `dest_dir.mkdir(parents=True, exist_ok=True)`
- `filename = _resolve_image_filename(dest_dir, item["id"], item.get("filename", item["id"]))`
- `app.image_client.download_image(item["id"], dest_dir / filename)` — on any exception: log via `app.scratchpad`; skip
- Append `{"image_id": item["id"], "alt_text": item.get("alt_text", ""), "staged_path": str(dest_dir / filename)}`
- Return list of dicts (JSON-serializable for MCP tool result)

**`_resolve_image_filename(dest_dir, image_id, original_filename) -> str`** (module-level):
- Collision-safe: `f"{image_id}_{original_filename}"` → if exists, append `_(2)`, `_(3)` etc. (BR-E-10)

**`ImageClient` protocol** (injectable for tests):
```python
class ImageClient(Protocol):
    def list_images(self, file_id: str) -> list[dict]: ...
    def download_image(self, image_id: str, destination: Path) -> None: ...
```

---

### Step 3 — `src/pipeline/extraction.py`

**Purpose**: `ExtractionAgent` — owns the MCP session lifecycle and drives Claude via `tool_runner`.

```python
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from mcp.server.fastmcp import FastMCP

from pipeline.config import Config
from pipeline.exceptions import PipelineError
from pipeline.models import CompactArtifact, DriveFileMetadata, ImageMetadata
from pipeline.scratchpad import Scratchpad
from pipeline.extraction_server import make_extraction_app, ImageClient
```

**`ExtractionAgent`**:
```python
class ExtractionAgent:
    def __init__(self, config: Config, image_client: ImageClient, scratchpad: Scratchpad) -> None:
        self._config = config
        self._image_client = image_client
        self._scratchpad = scratchpad
        self._client = anthropic.AsyncAnthropic()

    async def process(self, file_metadata: DriveFileMetadata, staging_path: Path) -> CompactArtifact:
        """Drive the full extraction pipeline for one file via MCP tool_runner."""
        # Fresh app instance per call — safe for concurrent asyncio.gather use (BR-E-09)
        app = make_extraction_app(self._image_client, self._scratchpad)

        async with _mcp_session(app) as mcp_session:
            tools_result = await mcp_session.list_tools()
            tools = [async_mcp_tool(t, mcp_session) for t in tools_result.tools]

            task_prompt = _build_prompt(file_metadata, staging_path, self._config)
            runner = self._client.beta.messages.tool_runner(
                model=self._config.extraction_model,
                max_tokens=4096,
                messages=[{"role": "user", "content": task_prompt}],
                tools=tools,
            )
            final_message = await runner.until_done()

        return _parse_final_message(final_message, file_metadata, self._config)
```

**`_build_prompt(file_metadata, staging_path, config) -> str`**:
- Instructs Claude to:
  1. Call `parse_document` with `file_path=str(staging_path)`, `mime_type=file_metadata.mime_type`
  2. Select the best-fit category from the list (provided in prompt): `config.categories`
  3. Call `stage_images` with `file_id`, `document_name=file_metadata.name`, `staging_dir=str(config.staging_dir)`
  4. Return JSON: `{"extracted_text": "<verbatim text from parse_document>", "category": "<selected category>"}`
- Categories embedded in prompt as a bullet list
- Explicit instruction: preserve semantic content verbatim; no summarization (BR-E-08)
- Explicit instruction: never include image bytes in response; only use `stage_images` result (BR-E-07)

**`_parse_final_message(message, file_metadata, config) -> CompactArtifact`**:
- Extract text from the final assistant message content blocks
- Parse JSON `{"extracted_text": ..., "category": ...}`
- Category validation (BR-E-04):
  1. Exact match in `config.categories` → accept
  2. Case-insensitive match → use canonical casing
  3. No match → use `config.categories[0]`, log warning via scratchpad
- Extract image metadata from `stage_images` tool result in message history (or default to `[]`)
- Convert image dicts to `ImageMetadata(image_id=..., alt_text=..., staged_path=Path(...))`
- Return `CompactArtifact(file_id=..., document_name=..., extracted_text=..., category=..., images=...)`

**`_mcp_session(app) -> AsyncContextManager[ClientSession]`** (module-level async context manager):
```python
@asynccontextmanager
async def _mcp_session(app: FastMCP):
    async with stdio_client(app) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
```

**Rate-limit handling** (BR-E-05) — wraps the `runner.until_done()` call:
- Catch `anthropic.RateLimitError`; read `retry_after` (default 60); `await asyncio.sleep(...)`; retry once
- Second `RateLimitError` → `PipelineError(error_type="transient", is_retriable=True, ...)`
- Other 4xx `APIStatusError` on retry → `PipelineError(error_type="validation", is_retriable=False, ...)`
- 5xx or network error → `PipelineError(error_type="transient", is_retriable=True, ...)`

---

### Step 4 — `tests/unit/test_extraction.py`

**Purpose**: Unit tests for `ExtractionAgent` and `extraction_server` tools using mocks.
All async tests use `asyncio.run(...)` — no `pytest-asyncio`.

**Helpers**:
- `make_config(tmp_path, categories=None)` — minimal `Config` with `staging_dir=tmp_path`
- `make_metadata(mime_type=DOCX_MIME)` — `DriveFileMetadata` stub
- `MockImageClient` — configurable stub; `list_images` returns `[]` by default
- `MockToolRunner` — replaces `self._client.beta.messages.tool_runner`; returns a canned `until_done()` result

**Tests — `extraction_server.parse_document` (called directly, no Claude)**:
- Valid `.docx` → returns non-empty str (AC-04.1, AC-04.2)
- Valid `.pdf` → returns non-empty str (AC-04.1, AC-04.2)
- Corrupted `.docx` → raises `PipelineError(error_type="business")` (AC-04.5)
- Corrupted `.pdf` → raises `PipelineError(error_type="business")` (AC-04.5)
- Unknown MIME → raises `PipelineError(error_type="validation")` (BR-E-01)
- Text order: `.docx` with two paragraphs → first appears before second (BR-E-02)

**Tests — `extraction_server.stage_images` (called directly)**:
- Two images downloaded → returns 2 dicts (AC-04.4)
- One download fails → partial list, warning logged (BR-E-06)
- All downloads fail → empty list (BR-E-06)
- Image dicts never contain raw bytes (BR-E-07)

**Tests — `ExtractionAgent.process()` via mocked tool_runner**:
- Happy path `.docx`: `CompactArtifact` has correct `file_id`, `document_name`, `category` (AC-04.1–04.4)
- `parse_document` raises `PipelineError` → propagates (AC-04.5)
- `RateLimitError` once → sleep + retry → success (AC-04.6)
- `RateLimitError` twice → `PipelineError(transient, is_retriable=True)` (BR-E-05)
- Category not in list → fallback to `categories[0]`, warning logged (BR-E-04)
- Category wrong case → canonical casing returned (BR-E-04)
- Two concurrent agents with different metadata → independent results, no shared state (BR-E-09)

---

### Step 5 — `tests/property/test_extraction_pbt.py`

**PBT-02** — `CompactArtifact` JSON round-trip (unchanged from original plan):
```python
@given(file_id=..., document_name=..., extracted_text=..., category=...)
@settings(max_examples=100)
def test_compact_artifact_text_fields_json_roundtrip(...): ...
```

**PBT-03** — Category invariant: `_apply_category_validation(returned, categories)` always returns member of `categories`.
`_apply_category_validation` extracted as a pure module-level function in `extraction.py`.

**PBT-03** — `stage_images` invariant: all returned dicts have non-empty `image_id` and non-empty `staged_path`.

**PBT-07** — MIME generator: `st.one_of(st.just(DOCX_MIME), st.just(PDF_MIME), st.text(...).filter(...))` exercises boundary.

**PBT-07** — Category boundary: exact/case-mismatch/no-match generators all resolve to a value in `categories`.

**PBT-08** — No `suppress_health_check` disabling shrinking; `@settings(max_examples=100/200)` throughout.

---

### Step 6 — `tests/integration/test_extraction_claude.md`

Markdown doc describing:
- What live integration tests verify (real Claude API + real MCP session loop)
- Prerequisites: `ANTHROPIC_API_KEY`, network access, real `.docx` / `.pdf` fixtures
- Why not automated in CI (cost, external dependency)
- How to run manually

---

## Story Traceability

| AC / BR | Implemented by | Step |
|---|---|---|
| AC-04.1 (supported MIME parsed) | `parse_document` MIME dispatch | Step 2 |
| AC-04.2 (text in reading order) | paragraph order in `parse_document` | Step 2 |
| AC-04.3 (category from config) | prompt + `_parse_final_message` BR-E-04 validation | Step 3 |
| AC-04.4 (images staged, metadata only to LLM) | `stage_images` tool; BR-E-07 enforced in prompt | Steps 2, 3 |
| AC-04.5 (corrupted file → graceful error) | `PipelineError(business)` in `parse_document` | Step 2 |
| AC-04.6 (concurrent, rate-limit retry) | `asyncio.gather` (Coordinator), rate-limit wrapper in `process()` | Step 3 |
| BR-E-01 (MIME allowlist) | `parse_document` MIME check | Step 2 |
| BR-E-02 (text order preserved) | paragraph + table iteration; page order pdf | Step 2 |
| BR-E-03 (corrupted → PipelineError) | try/except in `parse_document` | Step 2 |
| BR-E-04 (category validation + fallback) | `_apply_category_validation` in `_parse_final_message` | Step 3 |
| BR-E-05 (429 retry) | rate-limit wrapper around `runner.until_done()` | Step 3 |
| BR-E-06 (image failure tolerance) | per-image try/except in `stage_images` | Step 2 |
| BR-E-07 (no image bytes to LLM) | only dicts returned by tool; prompt instructs metadata-only | Steps 2, 3 |
| BR-E-08 (semantic content preserved) | prompt instructs verbatim reproduction | Step 3 |
| BR-E-09 (no shared mutable state) | `ExtractionAgent` stateless; `_extraction_app` attrs set per-call | Step 3 |
| BR-E-10 (image staging path + collision) | `_resolve_image_filename` in `extraction_server.py` | Step 2 |
| PBT-02 (round-trip) | `test_extraction_pbt.py` | Step 5 |
| PBT-03 (category + image invariants) | `test_extraction_pbt.py` | Step 5 |
| PBT-07 (MIME + category boundary generators) | `test_extraction_pbt.py` | Step 5 |
| PBT-08 (shrinking enabled) | `@settings` throughout | Step 5 |
