# Units of Work — Extraction Pipeline

## Decomposition Strategy

The pipeline is decomposed into **5 units** ordered by dependency. Each unit is independently buildable and testable before the next unit begins. Foundation is built first to stabilize all shared types and utilities before any agent is implemented.

---

## Unit 1: Foundation

**Description**: Shared infrastructure on which all other units depend. Includes all data types, configuration loading, manifest management, and the scratchpad logging utility.

**Components**:
- `pipeline/models.py` — `DriveFileMetadata`, `CompactArtifact`, `EnrichedDocument`, `ImageMetadata`, `ManifestRecord`, `RunSummary`, `ExportResult`
- `pipeline/config.py` — `Config` dataclass + `Config.from_toml()`
- `pipeline/manifest.py` — `ManifestStore` class
- `config.toml` — runtime configuration file with all paths, Drive folder ID, category list, model IDs
- `tests/unit/test_config.py`
- `tests/unit/test_manifest.py`
- `tests/property/test_manifest_pbt.py` (PBT: round-trip and invariant tests for ManifestRecord serialization)

**Acceptance criteria covered**: AC-08.1, AC-08.2, AC-08.3 (idempotency via ManifestStore)

**Depends on**: nothing

---

## Unit 2: Ingestion

**Description**: Google Drive discovery and file download. Implements OAuth 2.0 authentication and the 5-day eligibility rule.

**Components**:
- `pipeline/ingestion.py` — `discover_eligible_files()`, `download_file()`
- `tests/unit/test_ingestion.py`
- `tests/integration/test_ingestion_drive.py`

**Acceptance criteria covered**: AC-01.1–AC-01.5 (eligibility), AC-02.1–AC-02.4 (OAuth), AC-03.1–AC-03.4 (ingestion + rate limits), AC-08.1 (manifest skip check)

**Depends on**: Unit 1 (Foundation) — uses `Config`, `DriveFileMetadata`, `ManifestStore`

---

## Unit 3: Extraction

**Description**: Per-document text extraction, category classification, and image staging. Runs concurrently via `asyncio.gather`.

**Components**:
- `pipeline/extraction.py` — `ExtractionAgent` class (`__init__`, `process`, `_parse_document`, `_extract_and_classify`, `_stage_images`)
- `tests/unit/test_extraction.py`
- `tests/integration/test_extraction_claude.py`
- `tests/property/test_extraction_pbt.py` (PBT: round-trip on CompactArtifact serialization, invariants on image metadata)

**Acceptance criteria covered**: AC-04.1–AC-04.6 (extraction, classification, image staging, concurrency, corrupted files, rate limits)

**Depends on**: Unit 1 (Foundation) — uses `Config`, `CompactArtifact`, `DriveFileMetadata`, `ImageMetadata`

---

## Unit 4: Analysis

**Description**: LLM-based document enrichment. Produces formatted Markdown with YAML frontmatter and abstract from a CompactArtifact.

**Components**:
- `pipeline/analysis.py` — `enrich_document()`, `_build_analysis_prompt()`
- `tests/unit/test_analysis.py`
- `tests/integration/test_analysis_claude.py`
- `tests/property/test_analysis_pbt.py` (PBT: invariants — frontmatter always present, abstract always present, semantic content preserved)

**Acceptance criteria covered**: AC-05.1–AC-05.5 (formatting, citations, frontmatter, abstract, semantic preservation, rate limits)

**Depends on**: Unit 1 (Foundation) — uses `CompactArtifact`, `EnrichedDocument`

---

## Unit 5: Export + Coordinator

**Description**: Final pipeline stage (file export, image move, manifest update) combined with the `PipelineCoordinator` class that wires all units into a runnable end-to-end pipeline, plus the main entry point and Windows Task Scheduler setup.

**Components**:
- `pipeline/export.py` — `ExportAgent` functions (`export`, `_resolve_vault_path`, `_inject_image_uris`, `_move_images`)
- `pipeline/coordinator.py` — `PipelineCoordinator` class (`__init__`, `run`, `log`, `validate_handoff`, `_build_run_summary`)
- `main.py` — entry point, loads `Config`, instantiates and runs `PipelineCoordinator`
- `scheduler/setup_task.ps1` — Windows Task Scheduler setup script
- `tests/unit/test_export.py`
- `tests/unit/test_coordinator.py`
- `tests/integration/test_pipeline_e2e.py` — end-to-end pipeline integration test
- `tests/property/test_export_pbt.py` (PBT: URI injection invariants, round-trip on manifest write/read)

**Acceptance criteria covered**: AC-06.1–AC-06.5 (export, images, URIs, manifest), AC-07.1–AC-07.4 (Coordinator, scratchpad, handoff validation), AC-08.4 (no duplicate vault files), US-09 scheduling (Task Scheduler)

**Depends on**: Units 1–4 — integrates all prior units

---

## Code Organization (Greenfield)

```
docs-extraction/
  main.py
  config.toml
  pipeline/
    __init__.py
    models.py          # Unit 1
    config.py          # Unit 1
    manifest.py        # Unit 1
    ingestion.py       # Unit 2
    extraction.py      # Unit 3
    analysis.py        # Unit 4
    export.py          # Unit 5
    coordinator.py     # Unit 5
  scheduler/
    setup_task.ps1     # Unit 5
  tests/
    unit/
      test_config.py
      test_manifest.py
      test_ingestion.py
      test_extraction.py
      test_analysis.py
      test_export.py
      test_coordinator.py
    integration/
      test_ingestion_drive.py
      test_extraction_claude.py
      test_analysis_claude.py
      test_pipeline_e2e.py
    property/
      test_manifest_pbt.py
      test_extraction_pbt.py
      test_analysis_pbt.py
      test_export_pbt.py
```
