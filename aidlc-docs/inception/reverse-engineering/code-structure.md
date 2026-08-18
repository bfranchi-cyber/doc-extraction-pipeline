# Code Structure

## Build System
- **Type**: setuptools + uv
- **Configuration**: `pyproject.toml` (PEP 517/518)
- **Layout**: `src/` layout — `src/pipeline/` is the installable package
- **Entry Point**: `docs-extraction` → `pipeline.main:main`

## Key Classes/Modules

```
pipeline/
  __init__.py            (empty)
  main.py                CLI entry point + asyncio orchestrator
  extraction.py          Extractor class
  extraction_server.py   FastMCP server (parse_document tool)
  classification.py      ClassificationAgent class
  models.py              CompactArtifact, EnrichedDocument
  scratchpad.py          Scratchpad class
  exceptions.py          ExtractionPipelineError, PipelineError

tests/
  unit/
    test_extraction.py        Unit tests for Extractor
    test_classification.py    Unit tests for ClassificationAgent
    test_scratchpad.py        Unit tests for Scratchpad
  property/
    test_extraction_pbt.py    Hypothesis property-based tests for Extractor
  integration/
    __init__.py               (empty placeholder)
```

### Existing Files Inventory
- `src/pipeline/__init__.py` — Empty package marker
- `src/pipeline/main.py` — CLI arg parsing, asyncio event loop, per-file orchestration
- `src/pipeline/extraction.py` — `Extractor.process()`: mammoth DOCX extraction, returns `CompactArtifact`
- `src/pipeline/extraction_server.py` — `make_extraction_app()`: FastMCP server factory with `parse_document` tool
- `src/pipeline/classification.py` — `ClassificationAgent.classify()`: LLM call + `_move_to_vault()`
- `src/pipeline/models.py` — `CompactArtifact` (TypedDict), `EnrichedDocument` (dataclass)
- `src/pipeline/scratchpad.py` — `Scratchpad.info/warn/error()`: JSONL append-only log
- `src/pipeline/exceptions.py` — `PipelineError` dataclass + `ExtractionPipelineError` base
- `tests/unit/test_extraction.py` — Mocked mammoth tests for Extractor
- `tests/unit/test_classification.py` — Mocked Anthropic client tests for ClassificationAgent
- `tests/unit/test_scratchpad.py` — File-based tests for Scratchpad
- `tests/property/test_extraction_pbt.py` — Hypothesis PBT for Extractor (PBT-02, 07)
- `tests/integration/__init__.py` — Empty placeholder

## Design Patterns

### Dependency Injection via Constructor
- **Location**: `Extractor.__init__`, `ClassificationAgent.__init__`
- **Purpose**: Inject `Scratchpad` so tests can use a temp-dir scratchpad
- **Implementation**: Constructor parameters; no IoC container

### Two-Step LLM Classification Loop
- **Location**: `ClassificationAgent.classify()`
- **Purpose**: Avoid tool-use overhead; force single-token category output
- **Implementation**: Step 1 — text-only API call (`max_tokens=20`); Step 2 — Python validates response and calls `_move_to_vault()` as plain function

### Structured Error Taxonomy
- **Location**: `exceptions.py`, `PipelineError`
- **Purpose**: Distinguish transient / business / validation failures for retry logic
- **Implementation**: `PipelineError` dataclass with `error_type`, `is_retriable`, `suggestion`

## Critical Dependencies

### anthropic
- **Version**: `>=0.25` (with `[mcp]` extra)
- **Usage**: `ClassificationAgent` — synchronous `client.messages.create()`
- **Purpose**: LLM API client for classification

### mammoth
- **Version**: `>=1.6`
- **Usage**: `Extractor.process()`, `extraction_server.parse_document`
- **Purpose**: DOCX-to-plain-text conversion

### mcp
- **Version**: `>=1.8,<2.0`
- **Usage**: `extraction_server.py` — `FastMCP`
- **Purpose**: MCP server framework (not yet active in CLI)

### hypothesis
- **Version**: `>=6.0` (dev)
- **Usage**: `test_extraction_pbt.py`
- **Purpose**: Property-based testing
