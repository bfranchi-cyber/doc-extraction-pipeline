# Build Instructions

## Prerequisites

- **Build Tool**: setuptools >= 68, pip
- **Python**: >= 3.11
- **Dependencies**: See `pyproject.toml` — runtime deps include `anthropic`, `mammoth`, `arize-phoenix`, `arize-phoenix-otel`, `openinference-instrumentation-anthropic`
- **Environment Variables**:
  - `LIGHT_MODEL` — Anthropic model ID for classification (e.g. `claude-haiku-4-5-20251001`)
  - `MEDIUM_MODEL` — Anthropic model ID for eval judging (e.g. `claude-sonnet-5`)
  - `ANTHROPIC_API_KEY` — Anthropic API key
  - `OBSIDIAN_VAULT_PATH` — (optional) path to Obsidian vault for classification filing
  - `PHOENIX_HOST` — (optional) Phoenix host, defaults to `localhost:6006`
- **System Requirements**: Python 3.11+, internet access for Anthropic API

## Build Steps

### 1. Create and Activate Virtual Environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 2. Install Runtime + Dev Dependencies

```bash
pip install -e ".[dev]"
```

This installs:
- All runtime dependencies (including Phoenix packages)
- Dev dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `hypothesis`
- The two CLI entry points: `docs-extraction` and `docs-extraction-eval`

### 3. Verify Installation

```bash
docs-extraction --help
docs-extraction-eval --help
```

Both commands should print usage without error.

### 4. Verify Entry Points Resolve

```bash
python -c "from pipeline.tracing import setup_tracing, get_tracer; print('tracing OK')"
python -c "from eval.eval_agent import EvalAgent; print('eval OK')"
```

## Expected Build Output

```
Successfully installed docs-extraction-0.1.0 ...
```

Both entry points available, no import errors.

## Troubleshooting

### `ModuleNotFoundError: No module named 'phoenix'`
- Cause: Phoenix packages not installed.
- Solution: `pip install -e ".[dev]"` (installs all deps including Phoenix).

### `ModuleNotFoundError: No module named 'eval'`
- Cause: Package not installed in editable mode or `src/eval/` missing `__init__.py`.
- Solution: Confirm `src/eval/__init__.py` exists, then `pip install -e .`.

### `KeyError: 'MEDIUM_MODEL'` at runtime
- Cause: Required env var not set.
- Solution: Export `MEDIUM_MODEL` before running `docs-extraction-eval`.
