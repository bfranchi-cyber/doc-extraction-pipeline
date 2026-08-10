# NFR Requirements — Unit 1: Foundation

## Scope

Unit 1 is a pure Python library unit — no network, no async, no external APIs. NFRs focus on
correctness, maintainability, testability, and local I/O performance.

---

## NFR-01: Python Version Compatibility

**Category**: Tech Stack / Maintainability
**Requirement**: The project targets Python 3.11 as the minimum supported version.
**Rationale**: Python 3.11 includes `tomllib` in the standard library, eliminating the need for
the `tomli` backport dependency. Python 3.11 also brings meaningful performance improvements
(10–60% faster than 3.10 on typical workloads) and improved error messages.

**Constraint**: No Python 3.10 or earlier syntax or stdlib APIs may be used. `tomllib` is
imported directly from the standard library (`import tomllib`).

---

## NFR-02: Scratchpad Logging Format

**Category**: Observability / Maintainability
**Requirement**: All entries written to `scratchpad_path` must use **JSON Lines (JSONL)** format —
one JSON object per line, UTF-8 encoded, newline-terminated.

**Minimum fields per entry**:

| Field | Type | Description |
|---|---|---|
| `ts` | `str` | ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SS.ffffffZ`) |
| `level` | `str` | One of: `"INFO"`, `"WARN"`, `"ERROR"` |
| `msg` | `str` | Human-readable message |
| `context` | `object` (optional) | Stage-specific structured data (e.g., `{"file_id": "...", "stage": "config"}`) |

**Example**:
```
{"ts": "2026-08-10T12:00:00.000000Z", "level": "WARN", "msg": "Category 'Work' not found in vault", "context": {"category": "Work"}}
```

**Rationale**: JSONL is machine-parseable (grep, jq, log aggregators) and human-readable. It
enables future tooling without reformatting. Each line is a complete, self-contained record.

**Implementation note**: Unit 1 provides a `Scratchpad` helper (or a `write_log()` utility
function) used by all downstream units to write entries. The scratchpad file is opened in append
mode; no log rotation is required at this stage.

---

## NFR-03: Manifest Serialization

**Category**: Correctness / Maintainability
**Requirement**: `ManifestRecord` serialization uses the **`dataclasses-json`** library.

**Rationale**: `dataclasses-json` provides `to_json()` / `from_json()` / `to_dict()` / `from_dict()`
methods directly on decorated dataclasses, avoiding manual field mapping. This is particularly
valuable for correctness of the PBT round-trip property (PBT-02): the serialization path is
library-managed, not hand-rolled, reducing the risk of field omission or type coercion bugs.

**Constraint**: `ManifestRecord` must be decorated with `@dataclass_json @dataclass`. The
`from_json()` method is used in `ManifestStore.get()` for deserialization; `to_json()` in
`ManifestStore.set()` for serialization.

**Dependency**: `dataclasses-json >= 0.6` (latest stable).

---

## NFR-04: Type Annotations (Documentation-Only)

**Category**: Maintainability
**Requirement**: All public functions, methods, and class fields carry Python type annotations.
No static type checker (mypy, pyright) is run as part of the build or CI workflow.

**Rationale**: Type hints serve as inline documentation and improve IDE autocompletion without
adding tooling overhead. The project is a single-developer local tool; strict type checking is
not a required safety gate at this scale.

**Constraint**: Type annotations are present and correct as documentation, but no `mypy` or
`pyright` configuration file is created, and no type-checking step appears in the test or build
scripts.

---

## NFR-05: Test Coverage

**Category**: Quality / Testability
**Requirement**: Unit 1 must achieve **≥ 90% line coverage** across all modules in the unit
(`pipeline/models.py`, `pipeline/config.py`, `pipeline/manifest.py`). This threshold applies
to the project as a whole across all units.

**Coverage tooling**: `pytest-cov` with `--cov-fail-under=90`.

**Rationale**: 90% line coverage for a small, pure-Python unit with well-defined inputs and
outputs is achievable and provides high confidence in the correctness of Config loading and
ManifestStore operations.

**PBT coverage**: PBT tests (hypothesis) count toward line coverage. Property tests for
`ManifestRecord` round-trips (PBT-02, PBT-03) contribute meaningfully to the 90% target.

---

## NFR-06: Local I/O Performance

**Category**: Performance
**Requirement**: `Config.from_toml()` must complete in under **500ms** on the target machine.
`ManifestStore.get()` and `ManifestStore.set()` must each complete in under **100ms** for a
single file operation.

**Rationale**: Config loading is a one-time startup cost; 500ms is imperceptible to the user.
Manifest operations are called once per document; sub-100ms keeps per-document overhead
negligible relative to API call latency (seconds).

**Measurement**: Not enforced by automated benchmarks at this stage. These are design-time
targets to flag obviously slow implementations during code review.

---

## NFR-07: Atomic Manifest Writes

**Category**: Reliability / Correctness
**Requirement**: `ManifestStore.set()` must write atomically: write to a `.tmp` file first, then
rename to the final `.json` filename. This prevents a crash mid-write from leaving a partially
written (and therefore corrupted) manifest file.

**Rationale**: Atomic rename is the standard pattern for crash-safe file writes on POSIX and
Windows NTFS. A partial write that produces malformed JSON would trigger `ManifestCorruptionError`
on the next run (BR-05), stalling the document permanently.

---

## NFR-08: Dependency Minimalism

**Category**: Maintainability
**Requirement**: Unit 1 introduces only the dependencies strictly required by its NFR decisions.

| Dependency | Version | Justification |
|---|---|---|
| `dataclasses-json` | `>= 0.6` | ManifestRecord serialization (NFR-03) |
| `hypothesis` | `>= 6.0` | PBT testing (PBT-09) |
| `pytest` | `>= 7.0` | Test runner |
| `pytest-cov` | `>= 4.0` | Coverage reporting (NFR-05) |

`tomllib` is stdlib (Python 3.11+) — no extra install needed. No networking, async, or
third-party HTTP client libraries are introduced in this unit.
