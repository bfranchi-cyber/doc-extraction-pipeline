# Tech Stack Decisions — Unit 1: Foundation

## Decision Summary

| Decision | Choice | Alternatives Considered |
|---|---|---|
| Python version | 3.11+ | 3.10 (rejected — requires `tomli` backport) |
| TOML parsing | `tomllib` (stdlib) | `tomli`, `toml`, `rtoml` |
| Manifest serialization | `dataclasses-json` | `dataclasses.asdict()` + `json`, manual `to_dict()` |
| Scratchpad format | JSONL | Plain text, Python `logging` FileHandler |
| Type checking | None (annotations as docs) | mypy strict, mypy standard |
| Test framework | `pytest` + `pytest-cov` | `unittest` |
| PBT framework | `hypothesis` | `returns`, custom generators |
| Test coverage target | 90% line coverage | 80%, none |

---

## TSD-01: Python 3.11+

**Decision**: Python 3.11 minimum.

**Chosen because**:
- `tomllib` is in the standard library — no extra dependency for TOML parsing.
- Better runtime performance vs 3.10.
- Modern type annotation syntax (`X | Y` union shorthand) supported natively.

**Impact**: `pyproject.toml` (or `setup.cfg`) must declare `python_requires = ">=3.11"`. CI
must run on 3.11 or higher.

---

## TSD-02: `tomllib` (stdlib) for TOML Parsing

**Decision**: Use `import tomllib` (standard library, Python 3.11+).

**Chosen because**:
- Zero external dependency.
- Maintained by the Python core team.
- API is simple: `tomllib.load(fp)` where `fp` is a binary-mode file handle.

**Usage pattern**:
```python
import tomllib

with open(config_path, "rb") as f:
    data = tomllib.load(f)
```

---

## TSD-03: `dataclasses-json` for Manifest Serialization

**Decision**: Use `dataclasses-json` library for `ManifestRecord` serialization.

**Chosen because**:
- Eliminates hand-rolled field mapping.
- `to_json()` / `from_json()` methods are directly testable by PBT round-trip tests (PBT-02).
- Library handles `datetime` and `Path` field conversion if needed.

**Usage pattern**:
```python
from dataclasses import dataclass
from dataclasses_json import dataclass_json

@dataclass_json
@dataclass
class ManifestRecord:
    file_id: str
    name: str
    status: str
    processed_at: str
    error: str | None
```

**Serialization in ManifestStore**:
```python
# Write
record.to_json()  # returns JSON string

# Read
ManifestRecord.from_json(raw_text)  # raises JSONDecodeError on malformed input
```

**Note**: `dataclasses-json` raises `json.JSONDecodeError` on malformed JSON, which aligns with
the `ManifestCorruptionError` handling in BR-05. `ManifestStore.get()` catches `JSONDecodeError`
and raises `ManifestCorruptionError`.

---

## TSD-04: JSONL Scratchpad

**Decision**: Scratchpad log file uses JSON Lines format (one JSON object per line).

**Chosen because**:
- Machine-parseable with standard tools (`jq`, `grep`, log aggregators).
- Each line is self-contained — a truncated file still yields valid records up to the truncation point.
- Easy to extend with new fields without breaking existing consumers.

**Write utility** (provided by Unit 1, used by all units):
```python
import json
from datetime import datetime, timezone
from pathlib import Path

def write_log(scratchpad_path: Path, level: str, msg: str, context: dict | None = None) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
    }
    if context:
        entry["context"] = context
    with open(scratchpad_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
```

---

## TSD-05: No Static Type Checker

**Decision**: Type annotations are present throughout but no mypy/pyright is run.

**Chosen because**:
- Single-developer local tool — runtime errors surface quickly in manual testing.
- Adds tooling complexity without meaningful safety gain at this scale.
- IDE (VS Code / PyCharm) provides inline type feedback from annotations without a CI step.

**Constraint**: This decision may be revisited if the project grows or gains additional contributors.

---

## TSD-06: `pytest` + `pytest-cov` + `hypothesis`

**Decision**: Test stack is `pytest` (runner), `pytest-cov` (coverage), `hypothesis` (PBT).

**Chosen because**:
- `pytest` is the de-facto standard for Python testing with rich plugin ecosystem.
- `pytest-cov` integrates cleanly with `pytest` via `--cov` flags.
- `hypothesis` is the dominant Python PBT library, required by PBT-09.

**`pyproject.toml` test configuration**:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=pipeline --cov-report=term-missing --cov-fail-under=90"
```

**Test directory layout**:
```
tests/
  unit/
    test_config.py
    test_manifest.py
    test_models.py
  property/
    test_manifest_pbt.py
```
