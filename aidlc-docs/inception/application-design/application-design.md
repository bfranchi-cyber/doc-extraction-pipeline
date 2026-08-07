# Application Design — Extraction Pipeline

## Design Summary

The Extraction Pipeline is a fixed prompt-chaining system implemented in Python. A stateful `PipelineCoordinator` class drives a linear sequence of four agent stages (Ingestion → Extraction → Analysis → Export), acting as the inter-phase hub that validates structured handoffs, writes scratchpad log entries, and manages run-level state. Extraction runs concurrently across all eligible documents via `asyncio.gather`. All other stages are sequential per document.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Coordinator pattern | Stateful class | Holds scratchpad and run state across the entire pipeline run |
| Compact artifact | Python TypedDict (in-memory) | Type-safe, no disk I/O overhead, validated at handoff boundary |
| Extraction concurrency | One `ExtractionAgent` class instance per doc | Clean encapsulation; asyncio.gather drives all concurrently |
| Configuration | `config.toml` loaded at startup | Human-readable, no secrets in code, easy to edit |
| Manifest concurrency | Per-document JSON files | No locking needed; sequential writes via ExportAgent |

---

## Components

See [components.md](components.md) for full component descriptions.

| Component | Role |
|---|---|
| `PipelineCoordinator` | Hub — orchestrates pipeline, validates handoffs, writes scratchpad |
| `IngestionAgent` | Discovers eligible Drive files, filters manifest |
| `ExtractionAgent` | Per-document: parse, extract, classify, stage images |
| `AnalysisAgent` | Enrich compact artifact → formatted Markdown + frontmatter + abstract |
| `ExportAgent` | Write vault .md, move images, update manifest |
| `ManifestStore` | Per-document JSON idempotency state |
| `Config` | Immutable runtime configuration from `config.toml` |

---

## Method Signatures

See [component-methods.md](component-methods.md) for full method signatures and data type definitions.

**Core data flow types**:
- `DriveFileMetadata` → output of Ingestion
- `CompactArtifact` (TypedDict) → output of Extraction, input to Analysis
- `EnrichedDocument` → output of Analysis, input to Export
- `ManifestRecord` → persisted per-document state

---

## Service Orchestration

See [services.md](services.md) for the full service interaction map.

**Pipeline execution sequence** (within `PipelineCoordinator.run()`):

```
1. IngestionAgent.discover_eligible_files()        → list[DriveFileMetadata]
2. [concurrent per doc via asyncio.gather]:
   a. IngestionAgent.download_file()               → local Path
   b. ExtractionAgent.process()                    → CompactArtifact
   c. [Coordinator validates handoff]
   d. AnalysisAgent.enrich_document()              → EnrichedDocument
   e. [Coordinator validates handoff]
   f. ExportAgent.export()                         → ExportResult
3. Write RunSummary to scratchpad
```

---

## Component Dependencies

See [component-dependency.md](component-dependency.md) for dependency matrix, data flow diagram, and concurrency boundaries.

**External dependencies**:
- Google Drive API (via Drive MCP / `google-api-python-client`)
- Anthropic Python SDK (Claude Haiku 4.5, Claude Sonnet 4.5)
- `python-docx` (`.docx` parsing)
- `pypdf` (`.pdf` parsing)
- `google-auth` (OAuth 2.0 token management)
- `tomllib` / `tomli` (config.toml parsing)

---

## Directory Structure (planned)

```
docs-extraction/
  main.py                      # Entry point: loads Config, runs PipelineCoordinator
  config.toml                  # Runtime configuration
  pipeline/
    coordinator.py             # PipelineCoordinator class
    ingestion.py               # IngestionAgent functions
    extraction.py              # ExtractionAgent class
    analysis.py                # AnalysisAgent functions
    export.py                  # ExportAgent functions
    manifest.py                # ManifestStore class
    config.py                  # Config dataclass + from_toml()
    models.py                  # Shared data types (CompactArtifact, EnrichedDocument, etc.)
  tests/
    unit/
    integration/
    property/                  # Hypothesis PBT tests
```
