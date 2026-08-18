# API Documentation

## REST APIs
None — this is a CLI tool with no HTTP server.

## Internal APIs

### Extractor
- **Module**: `pipeline.extraction`
- **Methods**:
  - `__init__(scratchpad: Scratchpad) -> None`
  - `async process(docx_path: Path) -> CompactArtifact` — extracts text from a `.docx` file; raises `PipelineError` on failure
- **Return Types**: `CompactArtifact` = `{"document_name": str, "extracted_text": str}`

### ClassificationAgent
- **Module**: `pipeline.classification`
- **Methods**:
  - `__init__(vault_root: Path, scratchpad: Scratchpad) -> None` — reads `LIGHT_MODEL` env var at construction time
  - `async classify(md_path: Path) -> bool` — classifies file and moves it; returns `True` on success, `False` on any failure (logged to scratchpad, no exception raised)
  - `_move_to_vault(md_path: Path, category: str) -> bool` — internal; moves file via `shutil.move`
- **Environment Variables**: `LIGHT_MODEL` (required), `ANTHROPIC_API_KEY` (required), `ANTHROPIC_BASE_URL` (optional proxy)

### Scratchpad
- **Module**: `pipeline.scratchpad`
- **Methods**:
  - `__init__(path: Path) -> None`
  - `info(msg: str, context: dict | None = None) -> None`
  - `warn(msg: str, context: dict | None = None) -> None`
  - `error(msg: str, context: dict | None = None) -> None`
- **Output Format**: JSONL — one JSON object per line: `{"ts": ISO8601, "level": "INFO"|"WARN"|"ERROR", "msg": str, "context": {...}}`

### MCP Tool: parse_document
- **Module**: `pipeline.extraction_server`
- **Factory**: `make_extraction_app(scratchpad: Scratchpad) -> FastMCP`
- **Tool**: `async parse_document(file_path: str) -> str` — parses a `.docx` and returns plain text; raises `PipelineError` on failure

## Data Models

### CompactArtifact
- **Type**: `TypedDict`
- **Fields**: `document_name: str`, `extracted_text: str`
- **Purpose**: In-memory handoff from Extractor to ClassificationAgent

### EnrichedDocument
- **Type**: `@dataclass`
- **Fields**: `document_name: str`, `markdown: str`
- **Purpose**: Defined for future Analysis stage (not yet used in active pipeline)

### PipelineError
- **Type**: `@dataclass` (inherits `ExtractionPipelineError`)
- **Fields**: `error_type: str`, `text: str`, `is_retriable: bool`, `suggestion: str`
- **Methods**: `__str__() -> str`, `to_dict() -> dict`
- **Valid error_type values**: `"transient"`, `"business"`, `"validation"`
