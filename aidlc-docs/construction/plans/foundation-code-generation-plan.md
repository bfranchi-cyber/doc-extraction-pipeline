# Code Generation Plan — Unit 1: Foundation

## Unit Context

**Unit**: Unit 1 — Foundation
**Stories**: US-08 (partial) — AC-08.1, AC-08.2, AC-08.3
**Depends on**: nothing (this unit has no dependencies)
**Other units depend on this**: Units 2, 3, 4, 5

**Source root**: `src/pipeline/` (src/ layout, greenfield)
**Test root**: `tests/`
**Config root**: workspace root

**Key design decisions carried forward**:
- Python 3.11+, `pyproject.toml`, `pip install -e ".[dev]"` editable install
- `src/` layout: source lives under `src/pipeline/`
- `dataclasses-json` for ManifestRecord serialization
- `Scratchpad` class in `scratchpad.py` with `info()`, `warn()`, `error()` methods (JSONL output)
- `PipelineError` dataclass with `error_type` / `text` / `is_retriable` / `suggestion` fields
- Atomic manifest writes via `os.replace()`
- 90% line coverage, `hypothesis` for PBT (PBT-02, 03, 07, 08, 09 enforced)

---

## PBT Compliance Check (Partial enforcement: PBT-02, 03, 07, 08, 09)

| Rule | Applicability | Plan coverage |
|---|---|---|
| PBT-02 (round-trip) | YES — ManifestRecord JSON serialize/deserialize | Step 9: `test_manifest_pbt.py` round-trip test |
| PBT-03 (invariants) | YES — `set()` then `get()` returns equal record; `is_processed()` after success | Step 9: `test_manifest_pbt.py` invariant tests |
| PBT-07 (generator quality) | YES — `file_id` generator must match Drive ID format | Step 9: custom `st.from_regex()` generator |
| PBT-08 (shrinking + reproducibility) | YES — no `assume()` overuse; `@settings(suppress_health_check=[])` not set to disable shrinking | Step 9: enforced in test structure |
| PBT-09 (framework selection) | YES — `hypothesis` declared in `pyproject.toml` dev deps | Step 2: pyproject.toml |

---

## Generation Steps

- [ ] Step 1: Create project directory structure
- [ ] Step 2: Create `pyproject.toml`
- [ ] Step 3: Create `config.toml.example`
- [ ] Step 4: Create `.gitignore`
- [ ] Step 5: Create `src/pipeline/__init__.py`
- [ ] Step 6: Create `src/pipeline/models.py`
- [ ] Step 7: Create `src/pipeline/scratchpad.py`
- [ ] Step 8: Create `src/pipeline/config.py`
- [ ] Step 9: Create `src/pipeline/manifest.py`
- [ ] Step 10: Create `tests/unit/test_config.py` + `tests/unit/test_manifest.py` + `tests/unit/test_scratchpad.py`
- [ ] Step 11: Create `tests/property/test_manifest_pbt.py`

---

## Step Details

### Step 1 — Project directory structure
Create all required directories:
```
src/pipeline/
tests/unit/
tests/property/
tests/integration/   (empty, populated by later units)
```
Create `tests/__init__.py`, `tests/unit/__init__.py`, `tests/property/__init__.py`.

### Step 2 — `pyproject.toml`
Full `pyproject.toml` with build-system, project metadata, `requires-python = ">=3.11"`, all
runtime dependencies (including future units' deps), `[dev]` optional group, and
`[tool.pytest.ini_options]` with `--cov=src/pipeline --cov-fail-under=90`.

### Step 3 — `config.toml.example`
Template config with placeholder values. Documents all required fields with inline comments.
Committed to git; actual `config.toml` is git-ignored.

### Step 4 — `.gitignore`
Excludes: `config.toml`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `htmlcov/`, `.coverage`,
`dist/`, `*.egg-info/`, `.venv/`.

### Step 5 — `src/pipeline/__init__.py`
Empty (marks `pipeline` as a package).

### Step 6 — `src/pipeline/models.py`
All shared types and error hierarchy:
- `ExtractionPipelineError(Exception)` — base
- `PipelineError(ExtractionPipelineError)` — dataclass with `error_type`, `text`, `is_retriable`, `suggestion`
- `ConfigError(PipelineError)` — validation errors
- `CredentialsError(PipelineError)` — permission errors
- `ManifestCorruptionError(PipelineError)` — manifest validation errors
- `DriveFileMetadata`, `ImageMetadata`, `EnrichedDocument`, `RunSummary`, `ExportResult` — dataclasses
- `CompactArtifact` — TypedDict
- `ManifestRecord` — `@dataclass_json @dataclass` (for serialization)

### Step 7 — `src/pipeline/scratchpad.py`
`Scratchpad` class:
- `__init__(self, path: Path)` — stores path, no file creation
- `info(msg, context=None)`, `warn(msg, context=None)`, `error(msg, context=None)` — write JSONL entry
- Private `_write(level, msg, context)` — formats and appends one JSON line

### Step 8 — `src/pipeline/config.py`
`Config` frozen dataclass + `Config.from_toml(path)`:
- Parse TOML with `tomllib`
- Pass 1: field presence + path existence validation → `ConfigError`
- Pass 2: credentials JSON content + `"type"` field → `CredentialsError`
- Category drift warning via `Scratchpad` (requires Scratchpad instance — accept as optional param)
- Return frozen `Config`

**Note on Scratchpad dependency**: `Config.from_toml()` accepts an optional
`scratchpad: Scratchpad | None = None` parameter. When provided, category warnings are
written to it. When `None` (e.g., during tests), warnings are silently discarded.

### Step 9 — `src/pipeline/manifest.py`
`ManifestStore` class:
- `__init__(manifest_dir: Path)` — `mkdir(parents=True, exist_ok=True)`
- `get(file_id)` → `ManifestRecord | None` — read JSON, raise `ManifestCorruptionError` on bad JSON
- `set(file_id, record)` → atomic write via `os.replace(tmp → final)`
- `is_processed(file_id)` → `bool`
- `list_failed()` → `list[ManifestRecord]`

### Step 10 — Unit tests
`tests/unit/test_config.py`:
- Test: all valid paths loads successfully
- Test: missing required field raises `ConfigError`
- Test: non-existent path raises `ConfigError`
- Test: invalid credentials JSON raises `CredentialsError`
- Test: credentials missing `"type"` field raises `CredentialsError`
- Test: category mismatch emits warning (does not raise)

`tests/unit/test_manifest.py`:
- Test: `get()` on missing file returns `None`
- Test: `set()` + `get()` round-trip returns equal record (example-based)
- Test: `get()` on malformed JSON raises `ManifestCorruptionError`
- Test: `is_processed()` returns `True` only for `status == "success"`
- Test: `is_processed()` returns `False` for `status == "failed"`
- Test: `list_failed()` returns only failed records
- Test: atomic write — no `.tmp` file left on success

`tests/unit/test_scratchpad.py`:
- Test: `info()` writes valid JSONL with `level == "INFO"`
- Test: `warn()` writes valid JSONL with `level == "WARN"`
- Test: `error()` writes valid JSONL with `level == "ERROR"`
- Test: context is omitted when `None`
- Test: multiple writes append (not overwrite)

### Step 11 — PBT tests (`tests/property/test_manifest_pbt.py`)
PBT-02: Round-trip property
- Generator: `file_id` via `st.from_regex(r'[A-Za-z0-9_-]{10,44}')` (Drive ID format — PBT-07)
- Generator: `status` via `st.sampled_from(["success", "failed"])`
- Generator: `error` as `st.none() | st.text(min_size=1, max_size=200)`
- Property: `ManifestRecord.from_json(record.to_json()) == record`

PBT-03: Invariant properties
- Property: after `store.set(file_id, record)`, `store.get(file_id)` returns record with same `file_id` and `status`
- Property: after `store.set(file_id, ManifestRecord(..., status="success", ...))`, `store.is_processed(file_id) == True`
- Property: after `store.set(file_id, ManifestRecord(..., status="failed", ...))`, `store.is_processed(file_id) == False`

PBT-08: Tests use `@given` decorators; no `suppress_health_check` that disables shrinking;
`@settings(max_examples=100)` for adequate coverage.

---

## Story Traceability

| AC | Implemented by | Step |
|---|---|---|
| AC-08.1 (manifest check before processing) | `ManifestStore.is_processed()` | Step 9 |
| AC-08.2 (write success on completion) | `ManifestStore.set(..., status="success")` | Step 9 |
| AC-08.3 (write failed on permanent error) | `ManifestStore.set(..., status="failed")` | Step 9 |
