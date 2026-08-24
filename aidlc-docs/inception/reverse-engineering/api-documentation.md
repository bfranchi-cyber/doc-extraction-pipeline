# API Documentation

## CLI Entry Points

### docs-extraction (`pipeline.main:main`)
- **Invocation**: `docs-extraction --input <dir> --output <dir>`
- **Purpose**: Extract all .docx under --input, write .md to --output, classify into vault
- **Args**: `--input` (required, Path), `--output` (required, Path)
- **Side effects**: Writes .md files, moves classified files into vault, writes scratchpad.jsonl, emits OTEL spans to Phoenix

### docs-extraction-eval (`eval.eval_main:main`)
- **Invocation**: `docs-extraction-eval`
- **Purpose**: Run AI-as-judge evaluation over Phoenix classify spans
- **Environment**: `PHOENIX_HOST` (default: localhost:6006), `MEDIUM_MODEL`, `ANTHROPIC_API_KEY`
- **Output**: `Evaluated N spans — correct: X, incorrect: Y` printed to stdout

## Internal APIs

### `pipeline.tracing`

#### `setup_tracing(project_name: str) -> bool`
- **Purpose**: Launch Phoenix in-process and configure OTEL + Anthropic instrumentation
- **Returns**: True on success, False on any exception (non-fatal)
- **Side effects**: Phoenix UI available at localhost:6006; OTEL global provider registered

#### `get_tracer(name: str = __name__) -> opentelemetry.trace.Tracer`
- **Purpose**: Return an OTEL Tracer, falls back to no-op when no provider is configured
- **Usage**: Module-level `_tracer = get_tracer(__name__)` then `_tracer.start_as_current_span(...)`

### `pipeline.extraction.Extractor`

#### `__init__(scratchpad: Scratchpad) -> None`

#### `async process(docx_path: Path) -> CompactArtifact`
- **Purpose**: Extract text from a .docx file
- **Returns**: `CompactArtifact` with `document_name` and `extracted_text`
- **Raises**: `PipelineError(error_type="business", is_retriable=False)` on corrupt/unreadable file
- **Emits**: OTEL span "extract" with `document.name`, `extracted_text_length`

### `pipeline.classification.ClassificationAgent`

#### `__init__(vault_root: Path, scratchpad: Scratchpad) -> None`

#### `async classify(md_path: Path) -> bool`
- **Purpose**: Classify a .md file and move it to the matching vault subfolder
- **Returns**: True if file was moved, False otherwise
- **Emits**: OTEL span "classify" with attributes:
  - `document.name` — filename
  - `eval.category` — Claude's response
  - `eval.latency_ms` — API round-trip in ms
  - `eval.api_error` — bool
  - `eval.classified` — bool (whether file was successfully moved)

### `pipeline.extraction_server`

#### `make_extraction_app(scratchpad: Scratchpad) -> FastMCP`
- **Purpose**: Create a FastMCP server instance exposing `parse_document`
- **Tool — `parse_document(file_path: str) -> str`**: Parse .docx, return plain text

### `eval.eval_agent.EvalAgent`

#### `__init__() -> None`
- **Reads**: `MEDIUM_MODEL` (required), `PHOENIX_HOST` (default: localhost:6006)

#### `async run_evals() -> dict`
- **Purpose**: Fetch unevaluated classify spans from Phoenix and judge them
- **Returns**: `{"evaluated": int, "correct": int, "incorrect": int}`
- **Side effects**: Logs `px.Evaluation` with label `"eval.judge_verdict"` back to Phoenix

#### `async _judge_span(span) -> str`
- **Purpose**: Judge one span via Claude
- **Returns**: `"correct"` | `"incorrect"` | `"skipped"`

## Data Models

### `CompactArtifact` (TypedDict — `pipeline.models`)
- `document_name: str` — original filename
- `extracted_text: str` — raw text content

### `EnrichedDocument` (dataclass — `pipeline.models`, reserved for future use)
- `document_name: str`
- `markdown: str` — full markdown with YAML frontmatter

### `PipelineError` (dataclass — `pipeline.exceptions`)
- `error_type: str` — "transient" | "business" | "validation"
- `text: str` — human-readable message
- `is_retriable: bool`
- `suggestion: str` — operator guidance
- `to_dict() -> dict` — serialisable form

## Constants (`pipeline.classification`)
- `VALID_CATEGORIES: frozenset[str]` — {"Architecture", "CI&T", "Cloud", "Coding", "ML & AI"}
- `CATEGORY_DESCRIPTIONS: dict[str, str]` — description per category (used in classification prompt and eval judge prompt)
