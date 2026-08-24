# Unit Test Execution

## Run All Unit + Property Tests

```bash
uv run pytest -v
```

### Expected results

```
59 passed, 0 failed
Coverage: 93%+ (threshold: 65%)
```

## Run Specific Test Modules

```bash
# Frontmatter utilities
uv run pytest tests/unit/test_frontmatter.py -v

# AnalysisAgent
uv run pytest tests/unit/test_analysis.py -v

# ClassificationAgent (dynamic discovery + frontmatter path)
uv run pytest tests/unit/test_classification.py -v

# EvalAgent (vault_root decoupling)
uv run pytest tests/eval/test_eval_agent.py -v

# PBT: YAML round-trips
uv run pytest tests/property/test_frontmatter_pbt.py -v
```

## Run Without Coverage (faster)

```bash
uv run pytest --no-cov -v
```

## Test Coverage by Module

| Module | Coverage |
|---|---|
| `pipeline/analysis.py` | 100% |
| `pipeline/frontmatter.py` | 91% |
| `pipeline/classification.py` | 97% |
| `pipeline/models.py` | 100% |
| `eval/eval_agent.py` | 71% |

## Fix Failing Tests

1. Read the full pytest output (failing test name + assertion error)
2. Check the module under test matches what the test expects
3. Re-run the single failing test: `uv run pytest tests/unit/test_X.py::TestClass::test_method -v`
