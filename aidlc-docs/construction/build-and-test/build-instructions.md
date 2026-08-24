# Build Instructions

## Prerequisites

- **Build Tool**: `uv` (Python package manager)
- **Python**: 3.11+
- **Dependencies**: `pyproject.toml` — `anthropic[mcp]`, `mammoth`, `arize-phoenix`, `arize-phoenix-otel`, `openinference-instrumentation-anthropic`
- **Dev dependencies**: `pytest`, `pytest-asyncio`, `pytest-cov`, `hypothesis`

## Environment Variables (runtime — not needed for build)

| Variable | Required | Description |
|---|---|---|
| `MEDIUM_MODEL` | Yes | Anthropic model for AnalysisAgent (e.g. `claude-haiku-4-5-20251001`) |
| `LIGHT_MODEL` | Yes | Anthropic model for ClassificationAgent |
| `OBSIDIAN_VAULT_PATH` | No | Path to Obsidian vault; classification skipped if unset |
| `PHOENIX_HOST` | No | Phoenix host for tracing (default: `localhost:6006`) |
| `ANTHROPIC_API_KEY` | Yes (runtime) | Anthropic API key |

## Build Steps

### 1. Install dependencies

```bash
uv sync
```

### 2. Install with dev extras

```bash
uv sync --extra dev
```

### 3. Verify installation

```bash
uv run docs-extraction --help
uv run docs-extraction-eval --help
```

### Expected output

Both commands print usage/help without errors.

### Build artifacts

No compiled artifacts. The package is installed as an editable install via `uv sync`.
Entry points available after install:
- `docs-extraction` → `pipeline.main:main`
- `docs-extraction-eval` → `eval.eval_main:main`
