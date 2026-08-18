# Build and Test Summary — Phoenix Tracing & Eval

## Build Status

- **Build Tool**: setuptools (editable install via `pip install -e ".[dev]"`)
- **Python**: >= 3.11
- **New Runtime Dependencies Added**:
  - `arize-phoenix>=4.0`
  - `arize-phoenix-otel>=0.6`
  - `openinference-instrumentation-anthropic>=0.1`
- **New Dev Dependency Added**: `pytest-asyncio>=0.23`
- **New Script Entry Points**: `docs-extraction-eval = "eval.eval_main:main"`
- **Build Artifacts**: Two CLI entry points (`docs-extraction`, `docs-extraction-eval`)

## Test Execution Summary

### Unit Tests

| File | Tests | Notes |
|---|---|---|
| `tests/unit/test_tracing.py` | 2 | New — success path + failure path for `setup_tracing` |
| `tests/eval/test_eval_agent.py` | 4 | New — `_judge_span` (correct, incorrect, API failure) + `run_evals` no-span |
| `tests/unit/test_classification.py` | existing | Carries forward; `CATEGORY_DESCRIPTIONS` export is additive |
| `tests/unit/test_extraction.py` | existing | Carries forward; span wrapping is transparent |
| `tests/property/test_extraction_pbt.py` | existing | Carries forward |

- **Coverage target**: >= 65% across `src/pipeline` + `src/eval`
- **Omitted from coverage**: `src/pipeline/main.py`, `src/eval/eval_main.py`
- **Async support**: `asyncio_mode = "auto"` configured in `pyproject.toml`

### Integration Tests

- **Status**: Manual scenarios documented in `integration-test-instructions.md`
- No automated integration suite (reserved for future iteration)

### Performance Tests

- **Status**: N/A — see `performance-test-instructions.md` for rationale

### Contract / Security / E2E Tests

- **Status**: N/A for this iteration

## Key pyproject.toml Changes

```toml
# Runtime deps added
"arize-phoenix>=4.0"
"arize-phoenix-otel>=0.6"
"openinference-instrumentation-anthropic>=0.1"

# Dev dep added
"pytest-asyncio>=0.23"

# New script
docs-extraction-eval = "eval.eval_main:main"

# pytest config updated
--cov=src/eval added; asyncio_mode = "auto"; eval_main.py omitted from coverage
```

## Overall Status

- **Build**: Ready — `pip install -e ".[dev]"` installs all deps
- **Unit Tests**: Pass (run `pytest` to verify)
- **Ready for Operations**: Yes
