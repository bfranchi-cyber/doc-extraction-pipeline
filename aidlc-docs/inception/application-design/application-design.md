# Application Design — Analysis Step & Classify Refactor (2026-08-21)

> Previous iteration design (2026-08-14) covered local .docx → .md extraction only.
> This document supersedes it for the current iteration.

---

## Design Summary

The pipeline gains an `AnalysisAgent` step between extraction and classification.
`AnalysisAgent` enriches each `.md` file with YAML frontmatter (`summary`, `tags`, `confidence`)
via Anthropic tool-use against `MEDIUM_MODEL`. `ClassificationAgent` is updated to read this
frontmatter as classification context and to discover valid vault categories dynamically
(scanning vault subfolders at startup). `EvalAgent` is decoupled from hard-coded category constants.

### Design Decisions Captured

| Decision | Choice | Rationale |
|---|---|---|
| AnalysisAgent location | `src/pipeline/analysis.py` | Mirrors ClassificationAgent; testable in isolation |
| LLM model for analysis | `MEDIUM_MODEL` env var | More capable for summarization reasoning tasks |
| Structured output method | Anthropic tool-use | Guarantees schema; no regex fallback needed |
| Category discovery timing | Once at `__init__` | Fast, deterministic per run; vault changes don't mid-run |
| Confidence threshold | Informational only (always classify) | Calibration first; hard threshold deferred |
| Eval decoupling | EvalAgent reads vault at eval init | Fully dynamic; no static coupling to classification.py |
| Frontmatter I/O | Shared `frontmatter.py` utility | Reusable; avoids duplication between Analysis and Classification |

---

## Components

| Component | Type | Change | Role |
|---|---|---|---|
| `AnalysisAgent` | Async class | **NEW** | Reads .md text, calls LLM via tool-use, writes YAML frontmatter |
| `ClassificationAgent` | Async class | **UPDATED** | Frontmatter context + dynamic category discovery |
| `frontmatter` utility | Module | **NEW** | Shared read/write helpers for YAML frontmatter blocks |
| `Extractor` | Async class | **UNCHANGED** | Extracts text from one .docx via Claude + MCP |
| `main.py` / Orchestrator | Script | **UPDATED** | Inserts `analyze` step between `extract` and `classify` |
| `EvalAgent` | Async class | **UPDATED** | Decoupled from `VALID_CATEGORIES`; reads vault at init |
| `AnalysisResult` | TypedDict | **NEW** | `{summary: str, tags: list[str], confidence: float}` |

---

## Data Flow

```
.docx file
    |
    v
[Extractor.process()]
    |
    v
.md file (raw extracted text)
    |
    v
[AnalysisAgent.analyze()]         <-- NEW STEP
    |
    v
.md file (YAML frontmatter prepended)
    ---
    summary: "..."
    tags: ["...", "...", "..."]
    confidence: 0.87
    ---
    <extracted text>
    |
    v
[ClassificationAgent.classify()]  <-- UPDATED: reads frontmatter
    |
    v
vault/{category}/{filename}.md
```

---

## Orchestration Flow (main.py `process_one`)

```python
artifact = await extractor.process(docx_path)
output_path.write_text(artifact["extracted_text"], encoding="utf-8")
await analyzer.analyze(output_path)          # NEW: injects YAML frontmatter
if classifier:
    await classifier.classify(output_path)   # reads frontmatter (fallback: raw text)
```

All `process_one()` coroutines run concurrently via `asyncio.gather` (unchanged parallelism model).

---

## Component Method Signatures (summary)

### AnalysisAgent
```python
def __init__(scratchpad: Scratchpad) -> None
async def analyze(md_path: Path) -> AnalysisResult | None
```

### ClassificationAgent (changes only)
```python
def __init__(vault_root: Path, scratchpad: Scratchpad) -> None   # now discovers categories
def _discover_categories() -> frozenset[str]                     # NEW private method
async def classify(md_path: Path) -> bool                        # reads frontmatter first
```

### Frontmatter Utility
```python
def read_frontmatter(md_path: Path) -> dict | None
def write_frontmatter(md_path: Path, data: dict) -> None
```

### EvalAgent (changes only)
```python
def __init__(vault_root: Path | None, scratchpad: Scratchpad) -> None   # vault_root added
```

---

## Dependency Overview

```
main.py
  +--> Extractor              (unchanged)
  +--> AnalysisAgent (NEW)
  |      +--> frontmatter.write_frontmatter
  |      +--> Anthropic SDK (MEDIUM_MODEL)
  +--> ClassificationAgent (UPDATED)
         +--> frontmatter.read_frontmatter
         +--> Anthropic SDK (LIGHT_MODEL)

eval_main.py
  +--> EvalAgent (UPDATED)
         +--> Anthropic SDK
         +--> vault filesystem (OBSIDIAN_VAULT_PATH)
         # no longer imports from classification.py
```

No circular dependencies. All inter-agent data exchange via `.md` files on disk.

---

## Affected Files

| File | Change |
|---|---|
| `src/pipeline/analysis.py` | NEW — AnalysisAgent |
| `src/pipeline/frontmatter.py` | NEW — shared frontmatter utility |
| `src/pipeline/models.py` | UPDATE — add `AnalysisResult` TypedDict |
| `src/pipeline/classification.py` | UPDATE — dynamic discovery, frontmatter context, remove VALID_CATEGORIES |
| `src/pipeline/main.py` | UPDATE — instantiate AnalysisAgent, call analyze() in process_one() |
| `src/eval/eval_agent.py` | UPDATE — accept vault_root, discover categories dynamically |
| `tests/unit/test_analysis.py` | NEW |
| `tests/unit/test_frontmatter.py` | NEW |
| `tests/unit/test_classification.py` | UPDATE |

---

## Directory Structure (updated)

```
docs-extraction/
  src/pipeline/
    __init__.py
    main.py              # Entry point (updated)
    extraction.py        # Extractor (unchanged)
    extraction_server.py # FastMCP server (unchanged)
    analysis.py          # AnalysisAgent (NEW)
    frontmatter.py       # Frontmatter utility (NEW)
    classification.py    # ClassificationAgent (updated)
    models.py            # CompactArtifact, EnrichedDocument, AnalysisResult (updated)
    exceptions.py        # PipelineError, ExtractionPipelineError (unchanged)
    scratchpad.py        # Scratchpad logger (unchanged)
    tracing.py           # OTEL tracing (unchanged)
  src/eval/
    __init__.py
    eval_agent.py        # EvalAgent (updated)
    eval_main.py         # Eval entry point (minor update)
  tests/
    unit/
      test_extraction.py         (unchanged)
      test_scratchpad.py         (unchanged)
      test_analysis.py           (NEW)
      test_frontmatter.py        (NEW)
      test_classification.py     (updated)
    eval/
      test_eval_agent.py         (updated)
    property/
      test_extraction_pbt.py     (unchanged)
      test_frontmatter_pbt.py    (NEW — PBT for serialization round-trips)
```
