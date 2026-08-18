# Unit Test Execution

## Test Suites

| Suite | Location | Count | Notes |
|---|---|---|---|
| Pipeline unit tests | `tests/unit/` | ~20 tests | Existing + new `test_tracing.py` |
| Eval unit tests | `tests/eval/` | 4 tests | New — requires `pytest-asyncio` |
| Property-based tests | `tests/property/` | 2+ tests | Hypothesis-based |

## Run All Tests

```bash
pytest
```

Pytest is configured in `pyproject.toml`:
- Covers `src/pipeline` and `src/eval`
- Coverage threshold: 65%
- Async mode: `auto` (no `@pytest.mark.asyncio` decoration needed beyond class-level)
- Omits `src/pipeline/main.py` and `src/eval/eval_main.py` (entry points with no unit-testable logic)

## Run Specific Suites

```bash
# Pipeline unit tests only
pytest tests/unit/

# Eval unit tests only
pytest tests/eval/

# Property-based tests only
pytest tests/property/

# New tracing tests
pytest tests/unit/test_tracing.py -v

# New eval agent tests
pytest tests/eval/test_eval_agent.py -v
```

## Review Test Results

- **Expected**: all tests pass, 0 failures
- **Coverage target**: >= 65% across `src/pipeline` + `src/eval`
- **Coverage report**: printed to terminal after each run

## Fix Failing Tests

1. Run `pytest -v` to see which tests fail and the error message
2. Common causes:
   - `test_tracing.py` fails: check that `sys.modules` patching is applied before the import inside `setup_tracing`
   - `test_eval_agent.py` fails with `RuntimeError: no event loop`: ensure `asyncio_mode = "auto"` is set in `pyproject.toml`
   - Import errors for `phoenix` / `openinference`: install deps with `pip install -e ".[dev]"` (Phoenix is a runtime dep, so it is always installed)
3. Rerun `pytest` until all pass
