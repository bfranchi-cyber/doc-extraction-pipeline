# Services — Extraction Pipeline

## Service Layer Overview

The pipeline has a thin, explicit service layer. Rather than a generic service bus, each inter-component interaction is a direct, typed function call or method invocation coordinated by `PipelineCoordinator`. The services below describe the orchestration responsibilities.

---

## Service: PipelineOrchestrationService (PipelineCoordinator)

**Purpose**: Controls the end-to-end execution sequence. Holds all pipeline-level state for a single run.

**Orchestration Pattern**: Fixed linear prompt chain with Coordinator as inter-phase hub.

```
run() sequence:
  1. Load config, initialize ManifestStore and scratchpad
  2. Call IngestionAgent.discover_eligible_files()  → list[DriveFileMetadata]
  3. validate_handoff(ingestion output)
  4. For each DriveFileMetadata:
       a. Call IngestionAgent.download_file()       → local Path
       b. Instantiate ExtractionAgent, call process() → CompactArtifact | ExtractionError
       c. validate_handoff(extraction output)
       d. Call AnalysisAgent.enrich_document()      → EnrichedDocument
       e. validate_handoff(analysis output)
       f. Call ExportAgent.export()                 → ExportResult
       g. log stage transitions and outcomes
  5. Write run summary to scratchpad
  6. Return RunSummary
```

**Async strategy**: Steps 4a–4g run concurrently for all documents via `asyncio.gather` (one `ExtractionAgent` instance per document, steps b–f run as a coroutine chain per document).

---

## Service: DriveAccessService (IngestionAgent module)

**Purpose**: Encapsulates all Google Drive API interactions — authentication, file listing, and file downloading.

**Interactions**:
- Uses `google-auth` + `google-api-python-client` (or Drive MCP) for OAuth 2.0 token management
- Token stored at `config.credentials_path`; refreshed automatically on expiry
- All Drive API calls respect rate-limit responses (wait `retry-after` before retrying)

---

## Service: ExtractionService (ExtractionAgent class)

**Purpose**: Encapsulates per-document text parsing and LLM-based extraction/classification. Stateless between documents — one instance per document, discarded after `process()` returns.

**Interactions**:
- Calls Claude Haiku 4.5 via Anthropic SDK (`anthropic.AsyncAnthropic`)
- Delegates local file parsing to `python-docx` (`.docx`) and `pypdf` (`.pdf`)
- Writes image binaries to `config.staging_dir` — no image data passed upstream

---

## Service: AnalysisService (AnalysisAgent module)

**Purpose**: Stateless enrichment service. Takes a `CompactArtifact`, calls Claude Sonnet 4.5, returns `EnrichedDocument`.

**Interactions**:
- Calls Claude Sonnet 4.5 via Anthropic SDK
- No file system access — operates entirely in memory

---

## Service: ExportService (ExportAgent module)

**Purpose**: Writes pipeline outputs to disk. Final step before manifest update.

**Interactions**:
- Writes `.md` file to `config.vault_path/{category}/`
- Moves images from `config.staging_dir` to `config.images_path/{doc_name}/`
- Calls `ManifestStore.set()` to record success

---

## Service: ManifestService (ManifestStore class)

**Purpose**: Idempotency store. One JSON file per Drive document in `config.manifest_dir`. No locking needed — all manifest writes happen sequentially via `ExportAgent` (one document at a time in the export step).

**Interactions**:
- File system only; no external dependencies
- Used by `IngestionAgent` (read — check if already processed) and `ExportAgent` (write — record outcome)

---

## Service Interaction Summary

```
PipelineCoordinator
  │
  ├─► DriveAccessService (IngestionAgent)
  │       └─► ManifestStore [read — skip check]
  │
  ├─► ExtractionService (ExtractionAgent) [concurrent, one per doc]
  │       ├─► python-docx / pypdf [local parse]
  │       └─► Claude Haiku 4.5 [extract + classify]
  │
  ├─► AnalysisService (AnalysisAgent)
  │       └─► Claude Sonnet 4.5 [enrich]
  │
  └─► ExportService (ExportAgent)
          ├─► File system [write .md, move images]
          └─► ManifestStore [write — record outcome]
```
