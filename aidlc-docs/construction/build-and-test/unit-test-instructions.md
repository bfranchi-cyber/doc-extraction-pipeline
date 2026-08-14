# Unit Test Execution

## Run All Unit Tests

```bash
uv run pytest tests/unit/ -v
```

## Expected Results

- **Total**: 26 tests
- **Passed**: 26
- **Failed**: 0
- **Coverage threshold**: 65% (enforced by `--cov-fail-under=65` in `pyproject.toml`)

## Test Breakdown

| Module | Class | Tests |
|---|---|---|
| `test_classification.py` | `TestClassificationAgent` | 10 (6 unit + 4 parametrized) |
| `test_classification.py` | `TestClassificationAgentPBT` | 2 (PBT-02, PBT-07) |
| `test_extraction.py` | `TestParseDocument` | 3 |
| `test_extraction.py` | `TestExtractionAgentProcess` | 4 |
| `test_scratchpad.py` | — | 7 |

## Run Specific Test File

```bash
# Classification tests only
uv run pytest tests/unit/test_classification.py -v

# Extraction tests only
uv run pytest tests/unit/test_extraction.py -v
```

## Coverage Report

```bash
uv run pytest tests/unit/ --cov=src/pipeline --cov-report=term-missing
```

## Notes
- Classification tests mock the Anthropic client — no API key needed to run unit tests
- PBT tests use Hypothesis; increase `max_examples` in `@settings` for deeper exploration
