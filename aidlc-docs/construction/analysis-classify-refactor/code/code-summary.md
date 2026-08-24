# Code Summary — Analysis + Classify Refactor (2026-08-24)

## Created Files

| File | Purpose |
|---|---|
| `src/pipeline/analysis.py` | `AnalysisAgent` — reads .md text, calls MEDIUM_MODEL via tool-use, writes YAML frontmatter, emits OTEL span `"analyze"` |
| `src/pipeline/frontmatter.py` | Shared utility: `read_frontmatter(Path) -> dict | None`, `write_frontmatter(Path, dict) -> None` |
| `tests/unit/test_analysis.py` | Unit tests for AnalysisAgent (5 tests): success path, content preservation, API error, missing tool block, error logging |
| `tests/unit/test_frontmatter.py` | Unit tests for frontmatter utility (12 tests): read/write, round-trips, edge cases, unicode |
| `tests/property/test_frontmatter_pbt.py` | PBT (3 properties): write→read round-trip, body preservation, never-raises on arbitrary content |

## Modified Files

| File | Change |
|---|---|
| `src/pipeline/models.py` | Added `AnalysisResult` TypedDict: `{summary: str, tags: list[str], confidence: float}` |
| `src/pipeline/classification.py` | Removed `VALID_CATEGORIES`, `CATEGORY_DESCRIPTIONS` constants. Added `_discover_categories()` (scans vault subfolders at init), `_build_system_prompt()` (dynamic), updated `classify()` to read frontmatter first with raw-text fallback |
| `src/pipeline/main.py` | Added `AnalysisAgent` import and instantiation; added `await analyzer.analyze(output_path)` call in `process_one()` between extraction and classification |
| `src/eval/eval_agent.py` | Removed `from pipeline.classification import VALID_CATEGORIES, CATEGORY_DESCRIPTIONS`. Added `vault_root: Path | None = None` constructor param; discovers categories from vault at init; judge prompt includes dynamic category list when vault_root is set |
| `src/eval/eval_main.py` | Reads `OBSIDIAN_VAULT_PATH` env var; passes `vault_root=vault_root` to `EvalAgent()` |
| `tests/unit/test_classification.py` | Removed `VALID_CATEGORIES` import; uses local `_TEST_CATEGORIES`; added `TestCategoryDiscovery` class (3 tests); added `TestClassificationAgentFrontmatter` class (3 tests); updated PBT tests to use `_TEST_CATEGORIES` |
| `tests/eval/test_eval_agent.py` | Added `vault_root` fixture; updated `agent` fixture to pass `vault_root`; added 2 new tests: `test_judge_prompt_includes_discovered_categories`, `test_eval_agent_without_vault_root_omits_category_list` |

## Architecture Change Summary

**Before**: `VALID_CATEGORIES` was a hard-coded frozenset in `classification.py`, imported by both the classifier and `eval_agent.py`. Classification input was always raw text excerpt.

**After**: Categories discovered dynamically from vault subfolders at `ClassificationAgent.__init__()`. Classification input is YAML frontmatter (summary + tags) when present, raw text when absent. `eval_agent.py` discovers categories independently from the vault. No shared module-level coupling between pipeline and eval packages.

## Pipeline Flow (Updated)

```
extract → analyze (NEW) → classify (UPDATED)
           |                  |
           v                  v
      YAML frontmatter    reads frontmatter
      prepended to .md   (fallback: raw text)
```
