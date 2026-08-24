# Component Methods — Analysis Step & Classify Refactor (2026-08-21)

> **Note**: Detailed business logic (prompt templates, retry logic, YAML escaping rules) is defined
> in Functional Design (CONSTRUCTION phase). This document covers method signatures, purposes,
> and I/O contracts only.

---

## AnalysisAgent (`src/pipeline/analysis.py`)

### `__init__(scratchpad: Scratchpad) -> None`
- Initializes `anthropic.AsyncAnthropic()` client
- Reads `MEDIUM_MODEL` env var; raises `KeyError` at startup if unset
- Holds reference to `Scratchpad`
- No vault interaction; no category discovery

### `analyze(md_path: Path) -> AnalysisResult | None`
- **Input**: path to an extracted `.md` file
- **Process**:
  1. Read file text from `md_path`
  2. Call Anthropic async client with tool-use, enforcing schema `{summary: str, tags: list[str], confidence: float}`
  3. On success: call `frontmatter.write_frontmatter(md_path, result)` and return `AnalysisResult`
  4. On API error or parse failure: log to scratchpad, return `None` (file left without frontmatter)
- **Output**: `AnalysisResult` on success, `None` on failure
- **Side effect**: YAML frontmatter prepended to `md_path` on success
- **Span**: emits `"analyze"` with `document.name`, `eval.latency_ms`, `eval.api_error`, `eval.confidence`

---

## ClassificationAgent (`src/pipeline/classification.py`)

### `__init__(vault_root: Path, scratchpad: Scratchpad) -> None`
- Initializes `anthropic.AsyncAnthropic()` client
- Reads `LIGHT_MODEL` env var
- Calls `self._valid_categories = self._discover_categories()` and caches result

### `_discover_categories() -> frozenset[str]`
- Lists immediate subdirectories of `self._vault_root`
- Returns `frozenset` of folder names as valid categories
- If no subdirectories found: logs scratchpad warning, returns empty `frozenset`
- Called once at `__init__`; result cached for the lifetime of the instance

### `classify(md_path: Path) -> bool`
- **Input**: path to a `.md` file (after extraction and analysis)
- **Process**:
  1. Call `frontmatter.read_frontmatter(md_path)` to obtain analysis context
  2. If frontmatter present: build classification input from `summary` and `tags`
  3. If frontmatter absent (fallback): use raw text excerpt (first 500 chars)
  4. Build LLM prompt using `self._valid_categories` (dynamic, not hard-coded)
  5. Call LLM; validate returned category against `self._valid_categories`
  6. On valid category: call `_move_to_vault(md_path, category)`; return `True`
  7. On unknown/invalid category or API error: log to scratchpad; return `False`
- **Output**: `bool` (True if file moved, False otherwise)
- **Span**: emits `"classify"` with `document.name`, `eval.category`, `eval.latency_ms`, `eval.api_error`, `eval.classified`

### `_move_to_vault(md_path: Path, category: str) -> bool`
- Unchanged from current implementation
- Moves file to `vault_root / category / md_path.name`
- Returns `True` on success, `False` if destination folder missing

---

## Frontmatter Utility (`src/pipeline/frontmatter.py`)

### `read_frontmatter(md_path: Path) -> dict | None`
- **Input**: path to a `.md` file
- **Process**: reads file; if content starts with `---\n`, parses YAML block up to the next `---` line
- **Output**: parsed `dict` on success; `None` if no frontmatter block found
- Does not raise on missing frontmatter (absence is a valid state)
- Uses `yaml.safe_load()` for parsing

### `write_frontmatter(md_path: Path, data: dict) -> None`
- **Input**: `md_path` to an existing `.md` file; `data` dict to serialize
- **Process**: reads existing file content; prepends `---\n{yaml.dump(data)}\n---\n\n`; writes result back
- **Output**: none (file is side-effected)
- Uses `yaml.dump()` with `allow_unicode=True`, `default_flow_style=False`

---

## Models (`src/pipeline/models.py`)

### `AnalysisResult` (NEW TypedDict)

```python
class AnalysisResult(TypedDict):
    summary: str
    tags: list[str]       # 3-5 strings, enforced via tool-use schema
    confidence: float     # 0.0 – 1.0
```

### `CompactArtifact`, `EnrichedDocument` (UNCHANGED)

---

## EvalAgent (`src/eval/eval_agent.py`)

### `__init__(vault_root: Path | None, scratchpad: Scratchpad) -> None`
- **Updated**: accepts `vault_root` parameter (was sourced via `VALID_CATEGORIES` import)
- If `vault_root` is not `None`: reads immediate subdirectories at init time to build category list for judge prompt
- If `vault_root` is `None`: judge prompt omits category list (graceful degradation)

### `evaluate(md_path: Path, expected_category: str) -> EvalResult`
- Unchanged external interface
- Internally: uses dynamically discovered categories for judge prompt instead of imported `CATEGORY_DESCRIPTIONS`

---

## main.py Changes (method-level)

### `process_one(docx_path: Path) -> None` (UPDATED)

Updated call sequence:
```
artifact = await extractor.process(docx_path)
output_path.write_text(artifact["extracted_text"], encoding="utf-8")
await analyzer.analyze(output_path)          # NEW — injects YAML frontmatter
if classifier:
    await classifier.classify(output_path)
```

### `main() -> None` (UPDATED)

Instantiation additions:
```python
analyzer = AnalysisAgent(scratchpad)
```
