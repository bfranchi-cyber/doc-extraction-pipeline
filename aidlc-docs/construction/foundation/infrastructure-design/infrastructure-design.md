# Infrastructure Design — Unit 1: Foundation

## Overview

Unit 1 runs entirely on the local Windows machine. There are no cloud services, no network
calls, and no external infrastructure in this unit. Infrastructure scope covers Python
packaging, project layout, and local filesystem allocation.

---

## ID-01: Python Packaging

**Tool**: `pyproject.toml` (PEP 517/518) with `hatchling` or `setuptools` as build backend.
**Install method**: `pip install -e .` (editable install) during development.

**`pyproject.toml` structure**:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "docs-extraction"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "dataclasses-json>=0.6",
    "google-auth>=2.0",
    "google-auth-oauthlib>=1.0",
    "google-api-python-client>=2.0",
    "anthropic>=0.25",
    "python-docx>=1.1",
    "pymupdf>=1.24",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "hypothesis>=6.0",
]

[project.scripts]
docs-extraction = "pipeline.main:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src/pipeline --cov-report=term-missing --cov-fail-under=90"
```

**Rationale**: `pyproject.toml` is the modern standard. An editable install means changes to
`src/pipeline/` are immediately reflected without reinstalling. The `docs-extraction` console
script entry point allows running the pipeline as `docs-extraction` from any terminal after
install.

---

## ID-02: Source Layout (`src/` layout)

All application source lives under `src/pipeline/`. Tests live under `tests/`.

```
docs-extraction/                  ← project root / workspace root
  src/
    pipeline/
      __init__.py
      models.py                   ← Unit 1
      config.py                   ← Unit 1
      manifest.py                 ← Unit 1
      scratchpad.py               ← Unit 1
      ingestion.py                ← Unit 2
      extraction.py               ← Unit 3
      analysis.py                 ← Unit 4
      export.py                   ← Unit 5
      coordinator.py              ← Unit 5
      main.py                     ← entry point (Unit 5)
  tests/
    unit/
      test_config.py
      test_manifest.py
      test_models.py
      test_scratchpad.py
    property/
      test_manifest_pbt.py
  config.toml                     ← runtime config (not committed; .gitignore)
  pyproject.toml
  README.md
  .gitignore
```

**Rationale**: The `src/` layout prevents Python from accidentally importing the local
`pipeline/` directory when running `pytest` from the project root — it forces the installed
(editable) package to be used, which is the correct behaviour for testing an installable
package.

---

## ID-03: Local Filesystem Allocation

All runtime data lives outside the project root, under the user's Windows `AppData\Local`
directory. This keeps the project root clean and prevents runtime data from being committed.

| Purpose | Path |
|---|---|
| Manifest files | `C:\Users\bfranchi\AppData\Local\docs-extraction\manifests\` |
| Image staging | `C:\Users\bfranchi\AppData\Local\docs-extraction\staging\` |
| Scratchpad log | `C:\Users\bfranchi\AppData\Local\docs-extraction\scratchpad.log` |
| OAuth credentials | `C:\Users\bfranchi\AppData\Local\docs-extraction\credentials.json` |
| Obsidian vault | `C:\Users\bfranchi\Documents\Obsidian Vault\` |
| Obsidian images | `C:\Users\bfranchi\Documents\Obsidian Images\` |

These paths are defined in `config.toml` and validated at startup by `Config.from_toml()`
(PATTERN-03). All directories must exist before the first run; `config.toml` documents this
pre-requisite.

---

## ID-04: Version Control Exclusions

`.gitignore` must exclude all runtime data and local secrets:

```gitignore
# Runtime data
config.toml

# Python
__pycache__/
*.pyc
*.pyo
.pytest_cache/
htmlcov/
.coverage
dist/
*.egg-info/
```

`config.toml` is excluded because it contains local paths and the Drive folder ID. A
`config.toml.example` with placeholder values is committed instead.

---

## ID-05: Developer Setup Procedure

No Makefile. Developer setup documented in README:

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows

# 2. Install project + dev dependencies
pip install -e ".[dev]"

# 3. Create runtime directories
mkdir "C:\Users\bfranchi\AppData\Local\docs-extraction\manifests"
mkdir "C:\Users\bfranchi\AppData\Local\docs-extraction\staging"

# 4. Copy and edit config
copy config.toml.example config.toml
# edit config.toml with real paths and Drive folder ID

# 5. Run tests
pytest

# 6. Run pipeline
docs-extraction
```
