# Build Instructions

## Prerequisites

- **Runtime**: Python 3.11 or later (project was developed on 3.14)
- **Build tool**: pip / setuptools (no compiled build step — pure Python)
- **Dependencies**: mammoth, anthropic[mcp], mcp (see `pyproject.toml`)
- **Dev dependencies**: pytest, pytest-cov, hypothesis
- **Environment variables** (required at runtime, not at build time):
  - `ANTHROPIC_API_KEY` — JWT token for the corporate proxy
  - `ANTHROPIC_BASE_URL` — `https://flow.ciandt.com/flow-llm-proxy/`
  - `MODEL` — `anthropic.claude-4-6-haiku`
  - `MAX_TOKENS` — `4096`
- **System requirements**: Any OS with Python 3.11+. Windows tested. No native DLLs required (mammoth is pure Python).

---

## Build Steps

### 1. Create and activate virtual environment (first time only)

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install all dependencies (including dev)

```powershell
.venv\Scripts\pip install -e ".[dev]"
```

This installs the project in editable mode, making the `docs-extraction` CLI script available and ensuring `src/pipeline/` is on the path for tests.

### 3. Verify installation

```powershell
.venv\Scripts\python -c "import mammoth; import mcp; print('OK')"
```

Expected output: `OK`

### 4. Load environment variables (runtime only — not needed for tests)

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
    }
}
```

### 5. Verify CLI is available

```powershell
.venv\Scripts\docs-extraction --help
```

Expected output: argument parser usage for `--input` and `--output`.

---

## Build Artifacts

There is no compiled artifact — the project is pure Python installed in editable mode.

| Artifact | Location | Description |
|---|---|---|
| Editable install | `.venv/Lib/site-packages/docs_extraction.egg-link` | Points back to `src/` |
| CLI entry point | `.venv/Scripts/docs-extraction.exe` | Calls `pipeline.main:main` |
| Scratchpad log | `<output>/scratchpad.jsonl` | Written at runtime, not at build time |

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'pipeline'`
- **Cause**: Installed without `-e` flag, or venv not activated.
- **Fix**: `pip install -e ".[dev]"` with the venv active.

### `mammoth` import fails
- **Cause**: Dependencies not installed.
- **Fix**: Re-run `pip install -e ".[dev]"`.

### `docs-extraction` CLI not found
- **Cause**: Venv not activated, or installed without `-e`.
- **Fix**: Activate venv and reinstall with `pip install -e ".[dev]"`.
