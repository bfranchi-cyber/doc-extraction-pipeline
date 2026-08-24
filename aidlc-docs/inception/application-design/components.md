# Components — Analysis Step & Classify Refactor (2026-08-21)

## Component Overview

| Component | Type | Change | Role |
|---|---|---|---|
| `AnalysisAgent` | Async class | **NEW** | Reads .md text, calls LLM via tool-use, writes YAML frontmatter |
| `ClassificationAgent` | Async class | **UPDATED** | Classifies .md using frontmatter context; discovers vault categories dynamically at init |
| `frontmatter` utility | Module | **NEW** | Shared read/write helpers for YAML frontmatter blocks |
| `Extractor` | Async class | **UNCHANGED** | Extracts text from one .docx via Claude + MCP |
| `main.py` / Orchestrator | Script | **UPDATED** | Inserts `analyze` step between `extract` and `classify` in `process_one()` |
| `EvalAgent` | Async class | **UPDATED** | Decoupled from `VALID_CATEGORIES`; reads vault at init time |

---

## Component: AnalysisAgent (NEW)

**File**: `src/pipeline/analysis.py`

**Purpose**: Enriches an extracted `.md` file with AI-generated YAML frontmatter (`summary`, `tags`, `confidence`) so that `ClassificationAgent` can use structured context instead of raw text.

**Responsibilities**:
- Read the `.md` file text
- Call the Anthropic async client using tool-use (structured output) to guarantee `{summary: str, tags: list[str], confidence: float}` schema compliance
- Use `MEDIUM_MODEL` env var for the LLM call
- Write YAML frontmatter block at the top of the file via `frontmatter.write_frontmatter()`
- Emit OTEL span `"analyze"` with attributes: `document.name`, `eval.latency_ms`, `eval.api_error`, `eval.confidence`
- On failure: log to Scratchpad, leave file without frontmatter, never raise

**Key Interfaces**:
- Input: `md_path: Path` (extracted `.md` file written by Extractor)
- Output: `AnalysisResult | None` (returns `None` on failure; file is side-effected with frontmatter on success)

---

## Component: ClassificationAgent (UPDATED)

**File**: `src/pipeline/classification.py`

**Purpose**: Classifies a `.md` file into a vault folder using a short LLM call. Now reads YAML frontmatter (summary + tags) as classification context and discovers valid categories by scanning vault subfolders at startup.

**Responsibilities**:
- Discover valid vault categories by scanning `vault_root` immediate subdirectories at `__init__` time; cache as `self._valid_categories: frozenset[str]`
- On each `classify()` call: read YAML frontmatter via `frontmatter.read_frontmatter()`; if present, use `summary` and `tags` as classification input; if absent, fall back to raw text excerpt (first 500 chars)
- Build LLM prompt from discovered categories list (replaces hard-coded `VALID_CATEGORIES`)
- Call `LIGHT_MODEL` for classification (unchanged)
- Move file to matching vault folder
- Emit OTEL span `"classify"` (unchanged attributes)
- Log failures to Scratchpad; never raise

**Key Interfaces**:
- Input to `classify()`: `md_path: Path`
- Output: `bool` (True if file was moved, False otherwise)

**Removed**: `VALID_CATEGORIES` module-level constant; `CATEGORY_DESCRIPTIONS` module-level constant

---

## Component: Frontmatter Utility (NEW)

**File**: `src/pipeline/frontmatter.py`

**Purpose**: Shared, stateless helpers for reading and writing YAML frontmatter blocks in `.md` files. Isolated in its own module so both `AnalysisAgent` and `ClassificationAgent` can import it without circular dependencies.

**Responsibilities**:
- Parse the `---\n...\n---\n` block from the top of a `.md` file
- Return `None` (not an error) when no frontmatter block is present
- Prepend a valid YAML frontmatter block to an existing `.md` file

**Key Interfaces**:
- `read_frontmatter(md_path: Path) -> dict | None`
- `write_frontmatter(md_path: Path, data: dict) -> None`

---

## Component: Extractor (UNCHANGED)

**File**: `src/pipeline/extraction.py`

**Purpose**: Extracts text from one `.docx` file via Claude + FastMCP. No changes in this iteration.

---

## Component: main.py / Pipeline Orchestrator (UPDATED)

**File**: `src/pipeline/main.py`

**Purpose**: CLI entry point. Discovers `.docx` files, instantiates all agents, and orchestrates `extract → analyze → classify` per document in parallel via `asyncio.gather`.

**Changes**:
- Instantiates `AnalysisAgent(scratchpad)`
- Calls `await analyzer.analyze(output_path)` in `process_one()` after extraction, before classification
- No changes to CLI interface or parallelism model

---

## Component: EvalAgent (UPDATED)

**File**: `src/eval/eval_agent.py`

**Purpose**: LLM-as-judge for classification quality. Decoupled from hard-coded `VALID_CATEGORIES` and `CATEGORY_DESCRIPTIONS` in `classification.py`.

**Changes**:
- Accepts `vault_root: Path | None` as constructor argument (was implicit via classification import)
- If `vault_root` is set: reads vault subdirectories at init time to build the category list for the judge prompt
- Requires `OBSIDIAN_VAULT_PATH` to be set when running eval (already required for classification; no new constraint)
