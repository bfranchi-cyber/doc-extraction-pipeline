# NFR Design Patterns — Unit 1: Foundation

## Scope

Unit 1 has a narrow set of applicable NFR design patterns. There is no network, no async,
no queues, and no caches. The patterns below address: typed error classification, atomic
file I/O resilience, and fail-fast startup validation.

---

## PATTERN-01: Typed Error Classification

### Problem
BR-02 defined two error classes (transient / permanent). Pipeline stages need to communicate
not just whether an error is retryable, but also what kind of permanent failure it is, so the
Coordinator can log structured diagnostics and surface actionable guidance.

### Solution: PipelineError with Four Error Types

All pipeline errors inherit from `PipelineError(Exception)` and carry a structured payload
modelled on the Anthropic tool error contract:

```python
@dataclass
class PipelineError(Exception):
    error_type: str        # "transient" | "business" | "validation" | "permission"
    text: str              # Human-readable error message
    is_retriable: bool     # True only for "transient"
    suggestion: str        # Actionable guidance for the operator
```

**Error type taxonomy**:

| `error_type` | `is_retriable` | When to use | Example |
|---|---|---|---|
| `"transient"` | `True` | Rate limit, network timeout, temporary service unavailability | Drive API 429, Claude API timeout |
| `"business"` | `False` | Document content violates pipeline expectations | Empty extracted text, category not in list |
| `"validation"` | `False` | Input data fails structural/schema checks | Malformed TOML, missing required config field |
| `"permission"` | `False` | Access denied to a resource | Credentials rejected, file not readable |

**Manifest write rule from Q1**:
- `is_retriable == True` → do **not** write a manifest record; the document will be retried on the next run.
- `is_retriable == False` → write `status = "failed"`, serialize the full `PipelineError` payload into the `error` field of `ManifestRecord`.

**Error serialization in ManifestRecord.error**:
The `error` field on `ManifestRecord` (previously typed as `str | None`) is updated to hold
the JSON-serialized `PipelineError` payload on failure:

```json
{
  "error_type": "validation",
  "text": "Manifest file contains invalid JSON",
  "is_retriable": false,
  "suggestion": "Delete or repair manifest_dir/FILE_ID.json and re-run the pipeline"
}
```

**Specific subclasses defined in Unit 1**:

| Class | `error_type` | Raised by |
|---|---|---|
| `ConfigError` | `"validation"` | `Config.from_toml()` — missing field, bad path, bad eligibility_days |
| `CredentialsError` | `"permission"` | `Config.from_toml()` — credentials file missing, unreadable, or invalid JSON/type |
| `ManifestCorruptionError` | `"validation"` | `ManifestStore.get()` — malformed JSON in manifest file |

All three inherit from `PipelineError`. Additional subclasses (`IngestionError`,
`ExtractionError`, etc.) are defined in their respective units.

---

## PATTERN-02: Atomic Write for Manifest Resilience

### Problem
A crash or process kill during `ManifestStore.set()` mid-write would produce a partial JSON
file, triggering `ManifestCorruptionError` on the next run for that document.

### Solution: Write-Temp-Rename Pattern

```
1. Write serialized record to  {file_id}.json.tmp
2. fsync (optional, OS-level flush)
3. os.replace({file_id}.json.tmp, {file_id}.json)
   └─ atomic on NTFS (Windows) and POSIX filesystems
```

`os.replace()` is used (not `os.rename()`) because it is atomic even if the destination
already exists — a re-write of an existing record is safe.

**Invariant**: after `set()` returns, either the complete record exists at `{file_id}.json`,
or the original file (if any) is unchanged. A partial state never exists at the final path.

---

## PATTERN-03: Fail-Fast Startup Validation

### Problem
Missing paths or invalid credentials discovered mid-run cause cryptic errors deep in agent
code, far from the root cause.

### Solution: Two-Phase Config Validation at Load Time

`Config.from_toml()` runs two validation passes before returning:

**Pass 1 — Structural validation** (raises `ConfigError` / `"validation"`):
- All required TOML fields are present
- All `Path` fields resolve to existing directories or files (BR-03)
- `eligibility_days` is a positive integer

**Pass 2 — Credentials content validation** (raises `CredentialsError` / `"permission"`):
- Open `credentials_path` and parse as JSON
- Verify a `"type"` field is present
- Any failure here raises `CredentialsError` with `suggestion` pointing to the OAuth setup docs

**Category drift warning** (does not raise, does not block):
- Compare `categories` list against actual vault subdirectories
- For each mismatch: emit a `WARN` entry to the scratchpad via `Scratchpad.warn()`
- Pipeline continues; this is advisory only (BR-04)

After both passes succeed, the frozen `Config` instance is returned. The pipeline is
guaranteed to start with valid paths and readable credentials.

---

## PATTERN-04: ManifestCorruptionError Recovery Contract

### Problem
A document's manifest file is corrupted (invalid JSON). The Coordinator needs a clear,
documented contract for how to respond.

### Solution: Skip-Log-Fail Pattern

When the Coordinator encounters `ManifestCorruptionError` for a document during `is_processed()`:

1. **Log** — write a structured `ERROR` entry to the scratchpad via `Scratchpad.error()`,
   including `file_id` and the corruption error detail.
2. **Write failed manifest** — call `ManifestStore.set()` with a new `ManifestRecord`
   where `status = "failed"` and `error` is the serialized `PipelineError` payload
   (type `"validation"`, `is_retriable = False`,
   suggestion: `"Delete or repair manifest_dir/{file_id}.json and re-run"`).
3. **Count as failed** — increment `RunSummary.failed`; the document is not re-attempted
   in this run.
4. **Continue** — proceed to the next document; the run is not halted.

**Rationale**: Halting the entire run for one corrupted manifest would block all other
documents from processing. A targeted skip-and-record lets the operator identify and repair
the specific corrupted file while the rest of the batch completes.
