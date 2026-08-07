# Components — Extraction Pipeline

## Component Overview

| Component | Type | Role |
|---|---|---|
| `PipelineCoordinator` | Stateful class | Hub — orchestrates all stages, validates handoffs, writes scratchpad |
| `IngestionAgent` | Async function module | Queries Google Drive, applies 5-day eligibility rule, returns eligible file list |
| `ExtractionAgent` | Async class | Processes one document: extracts text, classifies category, stages images |
| `AnalysisAgent` | Async function module | Enriches compact artifact into final Markdown with frontmatter and abstract |
| `ExportAgent` | Async function module | Writes `.md` to vault, moves images, updates per-document manifest |
| `ManifestStore` | Class | Manages per-document JSON manifest files; tracks processing state |
| `Config` | Data class (loaded from `config.toml`) | Holds all runtime configuration (paths, Drive folder ID, category list) |

---

## Component: PipelineCoordinator

**Purpose**: Central hub of the prompt chaining pipeline. Instantiated once per run. Owns the scratchpad log, drives the pipeline sequence, validates stage outputs before handoff, and handles run-level error aggregation.

**Responsibilities**:
- Initialize and hold scratchpad state for the duration of the run
- Invoke each pipeline stage in sequence (Ingestion → Extraction → Analysis → Export)
- Validate each stage's structured output before constructing the next stage's input
- Log every stage transition, validation event, and error to the scratchpad
- Write a run summary to the scratchpad on completion
- Report per-document failures without halting the overall pipeline

**Key Interfaces**:
- Input: `Config` instance
- Output: scratchpad log file written to disk; per-document manifest files updated by `ExportAgent`

---

## Component: IngestionAgent

**Purpose**: Discovers eligible documents from Google Drive using the 5-day eligibility rule, skipping already-processed files.

**Responsibilities**:
- Authenticate via OAuth 2.0 (delegated to `google-auth` library + Drive MCP)
- Query Google Drive for `.docx` and `.pdf` files not modified in >= 5 days
- Filter against the `ManifestStore` to skip successfully-processed files
- Return a list of eligible `DriveFileMetadata` objects to the Coordinator
- Handle Drive API rate limits (wait retry-after duration) and transient errors

**Key Interfaces**:
- Input: `Config`, `ManifestStore`
- Output: `list[DriveFileMetadata]`

---

## Component: ExtractionAgent

**Purpose**: Processes a single document. Downloads it, extracts text via Claude Haiku 4.5, classifies it into a pre-defined vault category, and stages any embedded images to a temporary local folder.

**Responsibilities**:
- Download the document binary from Google Drive to a temporary path
- Extract full text content using the appropriate parser (`.docx` via `python-docx`, `.pdf` via `pypdf`)
- Call Claude Haiku 4.5 to extract structured text and select the best-fit vault category from the configured list
- Detect embedded images; download each to a temporary staging folder; record image ID and alt-text only
- Produce a `CompactArtifact` TypedDict
- Report parsing failures to the caller without raising unhandled exceptions

**Key Interfaces**:
- Input: `DriveFileMetadata`, `Config`
- Output: `CompactArtifact` or `ExtractionError`

---

## Component: AnalysisAgent

**Purpose**: Receives a `CompactArtifact` and produces a fully enriched Markdown document using Claude Sonnet 4.5.

**Responsibilities**:
- Format document text for Markdown readability (headings, lists, emphasis)
- Properly format citations and references found in the source
- Generate a YAML frontmatter block (title, date, auto-generated tags)
- Write a short abstract/summary section at the top of the document body
- Preserve all semantic content exactly — no facts added, altered, or removed
- Handle Claude API rate limits per Anthropic SDK guidance

**Key Interfaces**:
- Input: `CompactArtifact`
- Output: `EnrichedDocument` (final Markdown string + metadata)

---

## Component: ExportAgent

**Purpose**: Writes the enriched Markdown to the correct vault category folder, moves staged images to the images folder, injects absolute local image URIs, and updates the per-document manifest.

**Responsibilities**:
- Resolve the vault subfolder from `EnrichedDocument.category`; fall back to `Uncategorized/` if the category folder does not exist
- Write the `.md` file to `{vault_path}/{category}/{filename}.md`
- Move all staged images for the document from the temporary folder to `{images_path}/{document_name}/`
- Rewrite image references in the Markdown to absolute `file:///` URIs
- Update the per-document manifest file (status: `success`, timestamp)
- Log the fallback-to-Uncategorized event to the scratchpad if triggered

**Key Interfaces**:
- Input: `EnrichedDocument`, `Config`, list of staged image paths
- Output: written `.md` file; updated manifest file; images moved to final location

---

## Component: ManifestStore

**Purpose**: Manages idempotency state. One JSON file per Google Drive document, stored in a configured manifest directory. No concurrent write conflicts because manifest updates happen sequentially via `ExportAgent`.

**Responsibilities**:
- Load a document's manifest record by Drive file ID (returns `None` if not yet processed)
- Write or update a document's manifest record (status, timestamps)
- Enumerate all failed records for retry logic
- Provide a method to check if a document was successfully processed

**Key Interfaces**:
- Input: `Config` (manifest directory path)
- Methods: `get(file_id)`, `set(file_id, record)`, `is_processed(file_id)`, `list_failed()`

---

## Component: Config

**Purpose**: Single source of truth for all runtime configuration. Loaded from `config.toml` at startup. Immutable after load.

**Responsibilities**:
- Hold all file system paths (vault, images, manifest directory, temp staging, credentials, scratchpad)
- Hold Google Drive folder ID to monitor
- Hold the list of valid vault category names (pre-existing vault folders)
- Hold model IDs (Haiku 4.5 for extraction, Sonnet 4.5 for analysis)

**Key Interfaces**:
- Loaded via `Config.from_toml(path)` class method
- Accessed as a read-only dataclass throughout the pipeline
