# Build Instructions

## Prerequisites
- **Runtime**: Python 3.11+
- **Package manager**: `uv` (recommended) or `pip`
- **Dependencies**: See `pyproject.toml`

## Required Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `ANTHROPIC_BASE_URL` | Yes (corporate) | Corporate proxy base URL |
| `LIGHT_MODEL` | Yes | Model name for classification (e.g. claude-haiku-4-5-20251001) |
| `OBSIDIAN_VAULT_PATH` | Optional | Absolute path to Obsidian vault root; classification skipped if absent |

## Build Steps

### 1. Install Dependencies

```bash
uv sync
```

Or with pip:
```bash
pip install -e ".[dev]"
```

### 2. Verify Installation

```bash
uv run docs-extraction --help
```

Expected output: argument parser showing `--input` and `--output` flags.

### 3. Configure Environment

Copy `.env` to project root (if not already present) and ensure the four variables above are set.

## Build Artifacts
- `src/pipeline/` — installed as the `docs-extraction` package
- CLI entry point: `docs-extraction` (defined in `pyproject.toml` `[project.scripts]`)

## Troubleshooting

### `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`
**Cause**: MCP 2.0+ removed `fastmcp`. The project pins `mcp>=1.8,<2.0`.
**Solution**: Run `uv sync` — uv will downgrade to the pinned version automatically.

### `LIGHT_MODEL` not set
**Cause**: `.env` not loaded or missing variable.
**Solution**: Ensure `.env` is present and sourced, or export the variable manually.
