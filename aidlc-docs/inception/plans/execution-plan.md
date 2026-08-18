# Execution Plan — Phoenix Tracing & Eval

## Detailed Analysis Summary

### Transformation Scope
- **Transformation Type**: Multi-package enhancement — new observability layer (`pipeline`) + new offline eval package (`eval`)
- **Primary Changes**: 1 new module in `pipeline` (`tracing.py`), 3 new modules in `eval` (`__init__.py`, `eval_agent.py`, `eval_main.py`), modifications to 3 existing `pipeline` modules (`main.py`, `extraction.py`, `classification.py`), 3 new runtime dependencies
- **Related Components**: `pyproject.toml` (dep additions + new CLI script entry), test suite (2 new test files + 2 `__init__.py` markers)

### Change Impact Assessment
- **User-facing changes**: Minor — new `docs-extraction-eval` CLI command added; existing `docs-extraction` CLI interface unchanged
- **Structural changes**: Yes — new top-level `src/eval/` package introduced alongside `src/pipeline/`; one-way dependency enforced (`eval` → `pipeline`, never the reverse)
- **Data model changes**: No — no schema or TypedDict changes
- **API changes**: Additive only — `classification.py` gains a public `CATEGORY_DESCRIPTIONS` export; existing public signatures of `Extractor` and `ClassificationAgent` unchanged
- **NFR impact**: Tracing adds minimal OTEL span overhead per document (no LLM calls); normal pipeline runs have **zero eval latency** — LLM-as-judge runs only on-demand via the separate `docs-extraction-eval` command

### Component Relationships
- **Primary Component (runtime)**: `src/pipeline/` — modified to add tracing; `eval` package never imported here
- **New Package (offline tooling)**: `src/eval/` — imports `VALID_CATEGORIES` and `CATEGORY_DESCRIPTIONS` from `pipeline.classification`; one-way dependency
- **Modified modules**: `main.py` (tracing init + root span), `extraction.py` (extract child span), `classification.py` (classify child span + eval attributes + public `CATEGORY_DESCRIPTIONS`)
- **Config change**: `pyproject.toml` (3 new runtime deps + `docs-extraction-eval` script entry pointing to `eval.eval_main:main`)
- **New tests**: `tests/unit/test_tracing.py`, `tests/eval/__init__.py`, `tests/eval/test_eval_agent.py`

### Risk Assessment
- **Risk Level**: Low
- **Rollback Complexity**: Easy — remove `src/eval/`, remove `src/pipeline/tracing.py`, revert 3 module edits, revert `pyproject.toml`
- **Testing Complexity**: Simple — mocked Anthropic client + mocked Phoenix launch + mocked Phoenix client for eval

## Workflow Visualization

```
INCEPTION PHASE
  [x] Workspace Detection       — COMPLETED
  [x] Reverse Engineering       — COMPLETED
  [x] Requirements Analysis     — COMPLETED
  [-] User Stories              — SKIPPED (no UX change, single dev)
  [x] Workflow Planning         — IN PROGRESS
  [-] Application Design        — SKIPPED (components fully specified in FR-07..FR-10)
  [-] Units Generation          — SKIPPED (single unit across 2 packages: pipeline + eval)

CONSTRUCTION PHASE (Single Unit: Phoenix Tracing & Eval)
  [-] Functional Design         — SKIPPED (FR-01..FR-10 fully specify logic)
  [-] NFR Requirements          — SKIPPED (NFR-01..NFR-05 captured in requirements)
  [-] NFR Design                — SKIPPED (Phoenix/OTEL pattern well-known; no new patterns needed)
  [-] Infrastructure Design     — SKIPPED (local CLI, no cloud resources)
  [ ] Code Generation           — EXECUTE
  [ ] Build and Test            — EXECUTE

OPERATIONS PHASE
  [-] Operations                — PLACEHOLDER
```

## Files to Create / Modify

### `pipeline` package (runtime)
| File | Action | Reason |
|---|---|---|
| `src/pipeline/tracing.py` | CREATE | FR-07: Phoenix setup + tracer |
| `src/pipeline/main.py` | MODIFY | FR-09: tracing init + root span; no EvalAgent |
| `src/pipeline/extraction.py` | MODIFY | FR-04: extract child span |
| `src/pipeline/classification.py` | MODIFY | FR-04/FR-05/FR-08a: classify span + eval attributes + public `CATEGORY_DESCRIPTIONS` export |

### `eval` package (offline tooling)
| File | Action | Reason |
|---|---|---|
| `src/eval/__init__.py` | CREATE | FR-08: new package marker |
| `src/eval/eval_agent.py` | CREATE | FR-08: LLM-as-judge; imports from `pipeline.classification` |
| `src/eval/eval_main.py` | CREATE | FR-10: `docs-extraction-eval` CLI entry point |

### Config & Tests
| File | Action | Reason |
|---|---|---|
| `pyproject.toml` | MODIFY | NFR-04: 3 new runtime deps + `docs-extraction-eval = "eval.eval_main:main"` script entry |
| `tests/unit/test_tracing.py` | CREATE | NFR-05: unit tests for `setup_tracing` (mocked Phoenix launch) |
| `tests/eval/__init__.py` | CREATE | NFR-05: eval test package marker |
| `tests/eval/test_eval_agent.py` | CREATE | NFR-05: unit tests for `EvalAgent` (mocked Anthropic client + mocked Phoenix client) |

## Phases to Execute

### INCEPTION PHASE
- [x] Workspace Detection — COMPLETED
- [x] Reverse Engineering — COMPLETED
- [x] Requirements Analysis — COMPLETED
- [-] User Stories — SKIPPED (no UX change, single developer, requirements clear)
- [x] Workflow Planning — IN PROGRESS
- [-] Application Design — SKIPPED (FR-07/FR-08/FR-08a/FR-10 fully define all new components)
- [-] Units Generation — SKIPPED (single unit spanning pipeline + eval packages; no independent decomposition needed)

### CONSTRUCTION PHASE (Unit: Phoenix Tracing & Eval)
- [-] Functional Design — SKIPPED (requirements specify logic at implementation level for all FR-01..FR-10)
- [-] NFR Requirements — SKIPPED (NFR-01..NFR-05 captured in requirements)
- [-] NFR Design — SKIPPED (no new patterns; Phoenix/OTEL is the established pattern)
- [-] Infrastructure Design — SKIPPED (local CLI, no infrastructure changes)
- [ ] Code Generation — EXECUTE
- [ ] Build and Test — EXECUTE

### OPERATIONS PHASE
- [-] Operations — PLACEHOLDER

## Success Criteria
- **Primary Goal**: Every document classification produces a Phoenix trace (extraction + classification spans + programmatic eval attributes); LLM-as-judge runs on-demand via `docs-extraction-eval` against collected traces
- **Key Deliverables**: `src/pipeline/tracing.py`, `src/eval/__init__.py`, `src/eval/eval_agent.py`, `src/eval/eval_main.py`, updated `src/pipeline/main.py` / `extraction.py` / `classification.py`, updated `pyproject.toml`, `tests/unit/test_tracing.py`, `tests/eval/__init__.py`, `tests/eval/test_eval_agent.py`
- **Quality Gates**: All existing tests still pass; new unit tests pass; normal pipeline runs add zero eval latency; pipeline continues when Phoenix is unavailable (graceful degradation); `pipeline` never imports from `eval`
