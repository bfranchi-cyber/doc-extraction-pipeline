# Refactor Spec — Centralize Exceptions into `exceptions.py`

## Problem

Exception definitions are spread across two modules:

- `models.py` — `ExtractionPipelineError`, `PipelineError`, `ConfigError`, `CredentialsError`, `ManifestCorruptionError`
- `ingestion.py` — `RateLimitError`, `CredentialsMissingError`, `DownloadError`

`models.py` mixes data types (dataclasses, TypedDicts) with exception classes. `ingestion.py` defines exceptions that are part of the pipeline's shared error contract, not ingestion-specific implementation detail.

## Goal

Single source of truth for all exceptions: `src/pipeline/exceptions.py`.  
`models.py` contains data types only.  
All other modules import exceptions from `pipeline.exceptions`.

---

## New file: `src/pipeline/exceptions.py`

Move ALL exception classes here, in this order:

1. `ExtractionPipelineError(Exception)` — base
2. `PipelineError(ExtractionPipelineError)` — structured dataclass with `error_type`, `text`, `is_retriable`, `suggestion`, `to_dict()`
3. `ConfigError(PipelineError)` — from `models.py`
4. `CredentialsError(PipelineError)` — from `models.py`
5. `ManifestCorruptionError(PipelineError)` — from `models.py`
6. `RateLimitError(ExtractionPipelineError)` — from `ingestion.py`
7. `CredentialsMissingError(ExtractionPipelineError)` — from `ingestion.py`
8. `DownloadError(ExtractionPipelineError)` — from `ingestion.py`

No other logic in this file — definitions only.

---

## Changes per file

### `src/pipeline/models.py`
- Remove: `ExtractionPipelineError`, `PipelineError`, `ConfigError`, `CredentialsError`, `ManifestCorruptionError`
- Add import: `from pipeline.exceptions import ExtractionPipelineError, PipelineError, ConfigError, CredentialsError, ManifestCorruptionError`
- Re-export them so existing code that does `from pipeline.models import ConfigError` keeps working without changes during transition
- Data types remain: `DriveFileMetadata`, `ImageMetadata`, `CompactArtifact`, `EnrichedDocument`, `ManifestRecord`, `RunSummary`, `ExportResult`

### `src/pipeline/config.py`
- Change: `from pipeline.models import ConfigError, CredentialsError` → `from pipeline.exceptions import ConfigError, CredentialsError`

### `src/pipeline/manifest.py`
- Change: `from pipeline.models import ManifestCorruptionError, ManifestRecord` → split into `from pipeline.exceptions import ManifestCorruptionError` and `from pipeline.models import ManifestRecord`

### `src/pipeline/ingestion.py`
- Remove: `RateLimitError`, `CredentialsMissingError`, `DownloadError` class definitions
- Remove: `from pipeline.models import ExtractionPipelineError` (no longer needed directly)
- Add: `from pipeline.exceptions import DownloadError, CredentialsMissingError, RateLimitError, ExtractionPipelineError`

### `tests/unit/test_config.py`
- Change: `from pipeline.models import ConfigError, CredentialsError` → `from pipeline.exceptions import ConfigError, CredentialsError`

### `tests/unit/test_manifest.py`
- Change: `from pipeline.models import ManifestCorruptionError, ManifestRecord` → `from pipeline.exceptions import ManifestCorruptionError` + `from pipeline.models import ManifestRecord`

### `tests/unit/test_ingestion.py`
- Change: `from pipeline.ingestion import (..., CredentialsMissingError, DownloadError, RateLimitError, ...)` → also import from `pipeline.exceptions` instead of `pipeline.ingestion` for the three exception types
- OR: keep importing them from `pipeline.ingestion` if `ingestion.py` re-exports them (see note below)

### `tests/property/test_ingestion_pbt.py`
- No exception imports — no change needed

### `tests/property/test_manifest_pbt.py`
- No exception imports — no change needed

---

## Re-export strategy (backwards compatibility)

To avoid breaking test imports that currently do `from pipeline.ingestion import DownloadError`:

- `ingestion.py` re-exports: `from pipeline.exceptions import DownloadError, CredentialsMissingError, RateLimitError`
- `models.py` re-exports: `from pipeline.exceptions import ExtractionPipelineError, PipelineError, ConfigError, CredentialsError, ManifestCorruptionError`

This means existing imports keep working. In future units, new code should import directly from `pipeline.exceptions`.

---

## File order after refactor

```
src/pipeline/
    exceptions.py   ← NEW — all exception definitions
    models.py       ← data types only + re-exports from exceptions
    config.py       ← imports from exceptions directly
    manifest.py     ← imports from exceptions directly
    ingestion.py    ← imports from exceptions; re-exports for test compatibility
    scratchpad.py   ← unchanged (no exceptions)
```

---

## Verification

Run after applying:
```
pytest tests/unit/test_ingestion.py tests/property/test_ingestion_pbt.py
       tests/unit/test_config.py tests/unit/test_manifest.py
       tests/unit/test_scratchpad.py tests/property/test_manifest_pbt.py
       -o "addopts="
```
All 42 ingestion tests + all existing tests must pass with no import errors.
