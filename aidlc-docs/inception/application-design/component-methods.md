# Component Methods — Extraction Pipeline

**Note**: Method signatures show interfaces and I/O types. Detailed business logic and validation rules are defined in Functional Design (Construction phase, per unit).

---

## PipelineCoordinator

```python
class PipelineCoordinator:

    def __init__(self, config: Config) -> None
    # Initializes scratchpad, loads ManifestStore, prepares run state.

    async def run(self) -> RunSummary
    # Entry point. Drives full pipeline: ingestion → extraction → analysis → export.
    # Returns a RunSummary with counts of processed/failed/skipped documents.

    def log(self, level: str, stage: str, message: str, doc_id: str | None = None) -> None
    # Appends a timestamped entry to the scratchpad log.

    def validate_handoff(self, stage: str, data: Any, schema: type) -> bool
    # Validates a stage output against its expected type/schema before handoff.
    # Logs validation failure and marks doc as failed if invalid.

    def _build_run_summary(self) -> RunSummary
    # Aggregates per-document outcomes into a final run summary.
```

---

## IngestionAgent

```python
async def discover_eligible_files(
    config: Config,
    manifest: ManifestStore,
) -> list[DriveFileMetadata]
# Queries Google Drive for .docx and .pdf files with last_modified >= 5 days ago.
# Filters out files already in manifest with status=success.
# Returns list of eligible DriveFileMetadata for the Coordinator.

async def download_file(
    file_metadata: DriveFileMetadata,
    staging_dir: Path,
) -> Path
# Downloads a Drive file binary to a local staging directory.
# Returns the local file path.
```

---

## ExtractionAgent

```python
class ExtractionAgent:

    def __init__(self, config: Config) -> None

    async def process(self, file_metadata: DriveFileMetadata, local_path: Path) -> CompactArtifact | ExtractionError
    # Top-level per-document processing method.
    # Orchestrates: parse → extract text → classify → stage images → build CompactArtifact.

    def _parse_document(self, local_path: Path) -> RawDocumentContent
    # Parses .docx (python-docx) or .pdf (pypdf) into raw text + embedded image binaries.
    # Raises DocumentParseError on corruption or unsupported format.

    async def _extract_and_classify(self, raw: RawDocumentContent) -> tuple[str, str]
    # Calls Claude Haiku 4.5 with raw text.
    # Returns (extracted_text, selected_category) where category is from config.categories list.

    def _stage_images(self, raw: RawDocumentContent, doc_name: str) -> list[ImageMetadata]
    # Downloads embedded image binaries to config.staging_dir/{doc_name}/.
    # Returns list of ImageMetadata (id, alt_text, staged_path). No image data in return value.
```

---

## AnalysisAgent

```python
async def enrich_document(
    artifact: CompactArtifact,
) -> EnrichedDocument
# Calls Claude Sonnet 4.5 with the compact artifact text.
# Returns EnrichedDocument with: formatted Markdown body, YAML frontmatter, abstract, category.

def _build_analysis_prompt(artifact: CompactArtifact) -> str
# Constructs the prompt for Sonnet 4.5 from the compact artifact fields.
# Instructs model: format text, add citations, generate frontmatter + abstract, preserve semantics.
```

---

## ExportAgent

```python
async def export(
    document: EnrichedDocument,
    staged_images: list[ImageMetadata],
    config: Config,
    manifest: ManifestStore,
    coordinator_log: Callable[[str, str, str], None],
) -> ExportResult
# Writes .md to vault, moves images, injects file:/// URIs, updates manifest.
# Returns ExportResult with status and output paths.

def _resolve_vault_path(category: str, filename: str, config: Config) -> Path
# Returns the target vault path for the .md file.
# Falls back to config.vault_path / "Uncategorized" / filename if category folder missing.

def _inject_image_uris(markdown: str, images: list[ImageMetadata], doc_name: str, config: Config) -> str
# Replaces image placeholders in Markdown with absolute file:/// URIs.

def _move_images(staged_images: list[ImageMetadata], doc_name: str, config: Config) -> list[Path]
# Moves images from staging dir to config.images_path / doc_name /.
# Returns list of final image paths.
```

---

## ManifestStore

```python
class ManifestStore:

    def __init__(self, manifest_dir: Path) -> None
    # Ensures manifest directory exists.

    def get(self, file_id: str) -> ManifestRecord | None
    # Reads and returns the manifest JSON for a given Drive file ID, or None if absent.

    def set(self, file_id: str, record: ManifestRecord) -> None
    # Writes (creates or overwrites) the manifest JSON for a Drive file ID.

    def is_processed(self, file_id: str) -> bool
    # Returns True if manifest record exists with status == "success".

    def list_failed(self) -> list[ManifestRecord]
    # Returns all manifest records with status == "failed".
```

---

## Config

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
    extraction_model: str       # "claude-haiku-4-5-20251001"
    analysis_model: str         # "claude-sonnet-4-5-..."
    eligibility_days: int       # 5

    @classmethod
    def from_toml(cls, path: Path) -> "Config"
    # Parses config.toml and returns a validated Config instance.
    # Raises ConfigError on missing required fields.
```

---

## Key Data Types

```python
@dataclass
class DriveFileMetadata:
    file_id: str
    name: str
    mime_type: str              # "application/vnd.openxmlformats..." or "application/pdf"
    last_modified: datetime
    download_url: str

@dataclass
class ImageMetadata:
    image_id: str
    alt_text: str
    staged_path: Path           # local temp path during extraction

class CompactArtifact(TypedDict):
    file_id: str
    document_name: str
    extracted_text: str         # full text, no image data
    category: str               # selected from config.categories
    images: list[ImageMetadata] # metadata only — no binary data

@dataclass
class EnrichedDocument:
    file_id: str
    document_name: str
    category: str
    markdown: str               # final enriched Markdown (frontmatter + abstract + body)

@dataclass
class ManifestRecord:
    file_id: str
    name: str
    status: str                 # "success" | "failed"
    processed_at: str           # ISO 8601 timestamp
    error: str | None           # error message if failed

@dataclass
class RunSummary:
    eligible: int
    processed: int
    failed: int
    skipped: int

@dataclass
class ExportResult:
    file_id: str
    status: str
    vault_path: Path | None
    error: str | None
```
