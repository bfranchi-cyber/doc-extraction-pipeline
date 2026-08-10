# Logical Components — Unit 1: Foundation

## Overview

Unit 1 introduces four logical components. All are pure Python — no external services,
no network, no queues. Each component has a single, well-bounded responsibility.

```
pipeline/
  models.py       → PipelineError hierarchy + all shared data types
  config.py       → Config dataclass + Config.from_toml()
  manifest.py     → ManifestStore
  scratchpad.py   → Scratchpad
config.toml       → runtime configuration file
```

---

## Component 1: models.py — Shared Data Types + Error Hierarchy

**Responsibility**: Defines all shared dataclasses, TypedDicts, and the error type hierarchy
used across every unit. No business logic; pure data contracts.

**Contents**:

```
ExtractionPipelineError(Exception)   ← base for all pipeline errors
  PipelineError(ExtractionPipelineError)
    └─ error_type: str               ← "transient"|"business"|"validation"|"permission"
    └─ text: str
    └─ is_retriable: bool
    └─ suggestion: str
  ConfigError(PipelineError)         ← validation errors from Config.from_toml()
  CredentialsError(PipelineError)    ← permission errors from credentials validation
  ManifestCorruptionError(PipelineError) ← validation errors from ManifestStore.get()

DriveFileMetadata    (dataclass)
ImageMetadata        (dataclass)
CompactArtifact      (TypedDict)
EnrichedDocument     (dataclass)
ManifestRecord       (dataclass_json + dataclass)
RunSummary           (dataclass)
ExportResult         (dataclass)
```

**Note on ManifestRecord.error field**: Updated from `str | None` to `str | None` where the
string, when present, is the JSON-serialized `PipelineError` payload. This preserves the
`dataclasses-json` serialization contract while carrying structured error context.

**Dependencies**: none (pure stdlib + `dataclasses-json`).

---

## Component 2: config.py — Config + Config.from_toml()

**Responsibility**: Loads and validates the runtime configuration. Provides the single
frozen `Config` instance passed to every agent.

**Interface**:

```python
@dataclass(frozen=True)
class Config:
    vault_path: Path
    images_path: Path
    manifest_dir: Path
    staging_dir: Path
    scratchpad_path: Path
    credentials_path: Path
    drive_folder_id: str
    categories: list[str]
    extraction_model: str
    analysis_model: str
    eligibility_days: int

    @classmethod
    def from_toml(cls, path: Path) -> "Config":
        ...
```

**Validation sequence** (PATTERN-03):
1. Parse TOML with `tomllib`
2. Validate all required fields present → `ConfigError` if missing
3. Validate all `Path` fields exist on disk → `ConfigError` if not
4. Validate credentials JSON content → `CredentialsError` if invalid
5. Validate `eligibility_days > 0` → `ConfigError` if not
6. Warn on category/vault mismatch via `Scratchpad.warn()` (advisory only)
7. Return frozen `Config`

**Dependencies**: `models.py` (for `ConfigError`, `CredentialsError`), `scratchpad.py` (for
category drift warnings), `tomllib` (stdlib).

---

## Component 3: manifest.py — ManifestStore

**Responsibility**: Per-document idempotency state. Reads and writes `ManifestRecord` JSON
files from `manifest_dir`. The Coordinator's only interface for checking and recording
document processing outcomes.

**Interface**:

```python
class ManifestStore:
    def __init__(self, manifest_dir: Path) -> None: ...
    def get(self, file_id: str) -> ManifestRecord | None: ...
    def set(self, file_id: str, record: ManifestRecord) -> None: ...
    def is_processed(self, file_id: str) -> bool: ...
    def list_failed(self) -> list[ManifestRecord]: ...
```

**Key design points**:
- `set()` uses write-temp-rename (PATTERN-02) for atomic writes.
- `get()` raises `ManifestCorruptionError` (not `None`) on malformed JSON (BR-05).
- `is_processed()` returns `True` only on `status == "success"` (BR-06).
- Coordinator handles `ManifestCorruptionError` per PATTERN-04 (skip-log-fail).

**Dependencies**: `models.py` (for `ManifestRecord`, `ManifestCorruptionError`).

---

## Component 4: scratchpad.py — Scratchpad

**Responsibility**: Writes structured JSONL log entries to `scratchpad_path`. Used by all
pipeline units for observability. Holds the path and exposes typed logging methods.

**Interface**:

```python
class Scratchpad:
    def __init__(self, path: Path) -> None: ...
    def info(self, msg: str, context: dict | None = None) -> None: ...
    def warn(self, msg: str, context: dict | None = None) -> None: ...
    def error(self, msg: str, context: dict | None = None) -> None: ...
```

**Entry format** (JSONL, UTF-8, append mode):
```json
{"ts": "2026-08-10T12:00:00.000000Z", "level": "INFO", "msg": "...", "context": {...}}
```

**Design points**:
- `__init__` does not create the file; entries are appended on each call.
- File is opened and closed on every write (no persistent file handle) — safe for a
  single-process, low-frequency writer like this pipeline.
- `context` is omitted from the JSON output when `None` (keep entries compact).

**Dependencies**: none (pure stdlib: `json`, `datetime`, `pathlib`).

---

## Component Dependency Graph

```
config.toml
     |
     v
  config.py  ──uses──>  scratchpad.py
     |                       ^
     |                       |
     v                       |
  models.py  <──────  manifest.py
     ^
     |
  (all other units inherit these types)
```

**Load order at pipeline startup**:
1. `Scratchpad(config.scratchpad_path)` — instantiated first so Config warnings can be logged
2. `Config.from_toml(config_path)` — validates everything; uses Scratchpad for category warnings
3. `ManifestStore(config.manifest_dir)` — instantiated after Config is valid
4. Agents receive `Config` + `ManifestStore` + `Scratchpad` as constructor arguments
