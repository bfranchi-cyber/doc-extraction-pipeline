# Requirements — Analysis Step & Classify Refactor

## Intent Analysis

- **User Request**: Add a new Analysis pipeline step that enriches .md files with AI-generated YAML frontmatter (summary, tags, confidence), refactor ClassificationAgent to use that frontmatter as classification context, and make category discovery dynamic (scan vault folders at runtime).
- **Request Type**: New Feature + Enhancement to existing feature
- **Scope Estimate**: Cross-package — `pipeline` (new module + updated modules) and `eval` (updated eval judge context)
- **Complexity Estimate**: Moderate — clear implementation path with several design decisions to be resolved in Application Design

---

## Functional Requirements

### FR-1: AnalysisAgent (NEW)

A new pipeline component that runs after extraction and before classification.

- **Input**: Path to an extracted `.md` file
- **Process**: Reads the file text, calls an LLM (model TBD — see design decisions), and produces structured output with:
  - `summary` (string): concise document summary
  - `tags` (list of 3–5 strings): relevant keywords
  - `confidence` (float 0.0–1.0): agent's confidence in its analysis
- **Output**: Writes a YAML frontmatter block at the top of the `.md` file before any other content:
  ```yaml
  ---
  summary: "..."
  tags: ["...", "...", "..."]
  confidence: 0.85
  ---
  ```
- **Error handling**: Failures are logged to the Scratchpad; file is left without frontmatter; pipeline continues (same fail-soft pattern as classification)
- **Tracing**: Emits an OTEL span `"analyze"` consistent with existing `eval.*` attribute namespace

### FR-2: ClassificationAgent — frontmatter-based context (UPDATED)

- **Change**: Instead of reading raw file text for the classification prompt, ClassificationAgent reads the YAML frontmatter injected by AnalysisAgent
- **Classification input**: `summary` and `tags` from frontmatter (not the raw document excerpt)
- **Fallback**: If no frontmatter is present (AnalysisAgent failed), fall back to current raw-text excerpt behavior

### FR-3: ClassificationAgent — dynamic category discovery (UPDATED)

- **Change**: Remove hardcoded `VALID_CATEGORIES` frozenset; instead discover valid categories by scanning subfolders of `OBSIDIAN_VAULT_PATH` at runtime
- **Discovery**: At classification time (or once per pipeline run — see design decisions), list immediate subdirectories of `OBSIDIAN_VAULT_PATH`; use their names as valid categories
- **Edge cases**:
  - Vault not set: classification skipped (existing behavior preserved)
  - No subdirectories found: log warning, skip classification
  - Category returned by LLM not matching any discovered folder: log warning, skip move (existing behavior)
- **Impact on eval**: `VALID_CATEGORIES` and `CATEGORY_DESCRIPTIONS` are currently imported by `eval_agent.py`. Dynamic categories break this coupling — see Design Decision 3.

### FR-4: Pipeline orchestration (UPDATED)

- **New order**: extract → **analyze** → classify
- `main.py` `process_one()` must call `AnalysisAgent.analyze()` between `Extractor.process()` and `ClassificationAgent.classify()`
- All three steps run per-document within the existing `asyncio.gather` parallelism

---

## Non-Functional Requirements

### NFR-1: Performance
- AnalysisAgent adds one LLM call per document; must remain async and parallelized via `asyncio.gather` (no sequential bottleneck)

### NFR-2: Correctness
- YAML frontmatter must be valid YAML parseable by Obsidian (no special characters unescaped)
- Tags must always be a list of 3–5 strings
- Frontmatter block must appear before any other file content

### NFR-3: Testability
- New tests for AnalysisAgent (unit — mock LLM, assert frontmatter written correctly)
- Updated tests for ClassificationAgent (frontmatter path + fallback path + dynamic discovery)
- Manual verification: run pipeline on a sample .docx, confirm frontmatter in output .md, confirm file placed in correct vault folder
- Existing test suite must continue to pass (no regressions)

### NFR-4: Observability
- AnalysisAgent emits OTEL span `"analyze"` with attributes: `document.name`, `eval.latency_ms`, `eval.api_error`, `eval.confidence`
- Span attribute naming follows existing `eval.*` convention

### NFR-5: Eval compatibility
- If `VALID_CATEGORIES` is removed from classification.py, eval_agent.py must source category information from another mechanism (see Design Decision 3)

---

## Design Decisions (to be resolved in Application Design)

The following decisions are intentionally deferred to Application Design per user direction (Q3: "discuss pros and cons before defining"):

| # | Decision | Options to discuss |
|---|---|---|
| DD-1 | LLM model for AnalysisAgent | LIGHT_MODEL (fast, cheap) vs. MEDIUM_MODEL (more capable) vs. new ANALYSIS_MODEL env var |
| DD-2 | Structured output method | Native Anthropic tool-use / structured output vs. JSON in system prompt + regex parse |
| DD-3 | Dynamic category coupling with eval | (a) pass discovered categories into EvalAgent at call time, (b) keep CATEGORY_DESCRIPTIONS as a static registry separate from folder names, (c) EvalAgent queries vault at eval time |
| DD-4 | Discovery timing | Discover categories once at startup vs. per-classify call (affects hot-reload of vault folders) |
| DD-5 | Confidence threshold | Informational only (always attempt classify) vs. skip classify if confidence < threshold (e.g. < 0.5) |

---

## Extension Configuration

| Extension | Enabled | Decided At |
|---|---|---|
| Security Baseline | No | Requirements Analysis |
| Resiliency Baseline | No | Requirements Analysis |
| Property-Based Testing | Partial (pure functions + serialization round-trips) | Requirements Analysis |

**PBT scope**: YAML frontmatter serialization/deserialization and AnalysisAgent JSON output parsing are in scope for property-based testing.

---

## Affected Files (preliminary)

| File | Change Type |
|---|---|
| `src/pipeline/analysis.py` | NEW — AnalysisAgent |
| `src/pipeline/models.py` | UPDATE — AnalysisArtifact or extended CompactArtifact |
| `src/pipeline/classification.py` | UPDATE — frontmatter reader, dynamic discovery, remove VALID_CATEGORIES |
| `src/pipeline/main.py` | UPDATE — insert analyze step, pass AnalysisAgent |
| `src/eval/eval_agent.py` | UPDATE — decouple from VALID_CATEGORIES |
| `tests/unit/test_analysis.py` | NEW |
| `tests/unit/test_classification.py` | UPDATE — new test paths |
