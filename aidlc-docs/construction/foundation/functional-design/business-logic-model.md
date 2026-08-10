# Business Logic Model — Unit 1: Foundation

## Responsibilities

Unit 1 owns three distinct areas of business logic:

1. **Configuration loading and validation** (`Config` + `config.toml`)
2. **Per-document idempotency state** (`ManifestStore` + `ManifestRecord`)
3. **Shared data type contracts** (`models.py` — no logic, pure structure)

No external API calls. No async operations. Pure Python.

---

## 1. Configuration Loading Logic

### Config.from_toml(path: Path) → Config

**Input**: Path to `config.toml`

**Processing sequence**:
1. Read and parse the TOML file using `tomllib` (Python 3.11+) or `tomli` (fallback for <3.11).
2. Extract all required fields. Raise `ConfigError("Missing required field: {field}")` for any absent field.
3. Convert all path strings to `pathlib.Path` objects.
4. **Validate paths** (BR-03):
   - `vault_path`, `images_path`, `manifest_dir`, `staging_dir` → must be existing directories (`Path.is_dir()`)
   - `credentials_path` → must be an existing file (`Path.is_file()`)
   - `scratchpad_path` → parent must be an existing directory (`Path.parent.is_dir()`)
   - On any failure: raise `ConfigError(f"{field}: path does not exist: {path}")`
5. **Validate categories** (BR-04):
   - Load `categories` from TOML.
   - List `vault_path` subdirectories.
   - For each category in `categories` that has no matching vault subfolder: emit a warning string (collected and returned, not printed — the Coordinator will log them).
6. Validate `eligibility_days` is a positive integer.
7. Return frozen `Config` instance with all fields populated.

**Output**: `Config` (frozen dataclass)

**Errors**:
- `ConfigError` — missing field, invalid path, invalid eligibility_days value

---

## 2. ManifestStore Logic

### ManifestStore.__init__(manifest_dir: Path)

- Ensures `manifest_dir` exists (`manifest_dir.mkdir(parents=True, exist_ok=True)`).
- Stores `manifest_dir` as instance attribute.

### ManifestStore.get(file_id: str) → ManifestRecord | None

**Processing sequence**:
1. Construct path: `manifest_dir / f"{file_id}.json"`
2. If file does not exist → return `None`
3. Read file contents
4. Attempt JSON parse:
   - On `json.JSONDecodeError` → raise `ManifestCorruptionError(f"Corrupted manifest for {file_id}")`
5. Deserialize into `ManifestRecord` dataclass
6. Return `ManifestRecord`

### ManifestStore.set(file_id: str, record: ManifestRecord) → None

1. Serialize `ManifestRecord` to JSON dict
2. Write atomically: write to `{file_id}.json.tmp`, then rename to `{file_id}.json`
   - Atomic rename prevents partial writes from corrupting manifests (BR-05 prevention)
3. No return value

### ManifestStore.is_processed(file_id: str) → bool

1. Call `self.get(file_id)` — propagates `ManifestCorruptionError` if thrown
2. If result is `None` → return `False`
3. Return `record.status == "success"`

### ManifestStore.list_failed() → list[ManifestRecord]

1. List all `.json` files in `manifest_dir`
2. For each file: call `get()` (propagate `ManifestCorruptionError`)
3. Filter to records where `status == "failed"`
4. Return list (may be empty)

---

## 3. Data Type Contracts (models.py — no logic)

All types in `models.py` are pure data containers with no methods beyond `__init__` / dataclass defaults. Business logic is never placed in models.

**Type hierarchy**:

```
pipeline/models.py
  DriveFileMetadata        (dataclass)
  ImageMetadata            (dataclass)
  CompactArtifact          (TypedDict)
  EnrichedDocument         (dataclass)
  ManifestRecord           (dataclass)
  RunSummary               (dataclass)
  ExportResult             (dataclass)
```

`CompactArtifact` uses `TypedDict` (not dataclass) because it is passed as a dict-like object to prompt-building functions; this avoids conversion overhead and matches the in-memory handoff pattern chosen in Application Design.

---

## 4. config.toml Structure

```toml
[paths]
vault_path       = "C:\\Users\\bfranchi\\Documents\\Obsidian Vault"
images_path      = "C:\\Users\\bfranchi\\Documents\\Obsidian Images"
manifest_dir     = "C:\\Users\\bfranchi\\AppData\\Local\\docs-extraction\\manifests"
staging_dir      = "C:\\Users\\bfranchi\\AppData\\Local\\docs-extraction\\staging"
scratchpad_path  = "C:\\Users\\bfranchi\\AppData\\Local\\docs-extraction\\scratchpad.log"
credentials_path = "C:\\Users\\bfranchi\\AppData\\Local\\docs-extraction\\credentials.json"

[drive]
folder_id = "YOUR_DRIVE_FOLDER_ID"

[pipeline]
eligibility_days  = 5
extraction_model  = "claude-haiku-4-5-20251001"
analysis_model    = "claude-sonnet-4-5-20251001"

[categories]
list = [
  "Work",
  "Research",
  "Personal",
  "Meetings",
  "Reference"
]
```

The `[categories].list` array is the canonical category source. At startup, `Config.from_toml()` validates it against the actual vault subdirectories and warns on mismatch (BR-04).

---

## 5. Error Types

| Error | Module | When raised |
|---|---|---|
| `ConfigError` | `pipeline/config.py` | Missing TOML field, path validation failure, invalid config value |
| `ManifestCorruptionError` | `pipeline/manifest.py` | `ManifestStore.get()` reads malformed JSON |

Both inherit from a common base `ExtractionPipelineError(Exception)` defined in `pipeline/models.py` to allow unified catch blocks at the Coordinator level.

---

## 6. PBT Scope for Unit 1

Per NFR-07 (partial PBT enforcement), Unit 1 requires:

- **PBT-02 (round-trip)**: `ManifestRecord` → serialize to JSON → deserialize → must equal original. Test via `tests/property/test_manifest_pbt.py`.
- **PBT-03 (invariants)**: `ManifestStore.set()` then `ManifestStore.get()` always returns a record with the same `file_id` and `status`. `is_processed()` always returns `True` after a successful `set()` with `status="success"`.
- **PBT-07 (generator quality)**: Hypothesis generators for `ManifestRecord` must produce realistic `file_id` strings (alphanumeric + hyphens, 10-44 chars, matching Drive ID format).
- **PBT-08 (shrinking)**: Hypothesis strategies must use `@given` decorators that support shrinking; no `assume()` overuse that defeats shrinking.
- **PBT-09 (framework selection)**: Use `hypothesis` library. No other PBT framework.
