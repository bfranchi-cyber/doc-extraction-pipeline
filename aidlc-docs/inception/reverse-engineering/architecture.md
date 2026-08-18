# System Architecture

## System Overview

`docs-extraction` is a single-process Python CLI application. It has no server, no database, and no cloud infrastructure. It runs locally, reading from a filesystem input folder and writing to a filesystem output folder. When `OBSIDIAN_VAULT_PATH` is set, it also writes to an Obsidian vault by moving classified `.md` files.

## Architecture Diagram

```
                         CLI Invocation
                    docs-extraction --input X --output Y
                                    |
                              +-----v------+
                              |  main.py   |
                              | (asyncio)  |
                              +-----+------+
                                    |
                    +---------------+---------------+
                    |                               |
             +------v------+              +---------v---------+
             |  Extractor  |              | ClassificationAgent|
             | (extraction |              | (classification.py)|
             |    .py)     |              +---------+---------+
             +------+------+                        |
                    |                    +----------v----------+
                    | CompactArtifact    | Anthropic API       |
                    | (in-memory)        | (LIGHT_MODEL / Haiku)|
                    |                    +----------+----------+
             +------v------+                        |
             | Output .md  |              +---------v---------+
             | files       |              | Obsidian Vault    |
             +------+------+              | (OBSIDIAN_VAULT_  |
                    |                    |  PATH)             |
                    +------+             +-------------------+
                           |
                    +------v------+
                    | scratchpad  |
                    |   .jsonl    |
                    +-------------+
```

## Component Descriptions

### main.py
- **Purpose**: CLI entry point and pipeline orchestrator
- **Responsibilities**: Parse args, discover `.docx` files, run asyncio event loop, call Extractor and ClassificationAgent per file
- **Dependencies**: `extraction.py`, `classification.py`, `scratchpad.py`, `exceptions.py`
- **Type**: Application

### extraction.py
- **Purpose**: DOCX-to-Markdown text extraction
- **Responsibilities**: Use mammoth to read `.docx`, return `CompactArtifact`, raise `PipelineError` on failure
- **Dependencies**: `mammoth`, `models.py`, `exceptions.py`, `scratchpad.py`
- **Type**: Application

### extraction_server.py
- **Purpose**: FastMCP server exposing `parse_document` tool
- **Responsibilities**: Wrap extraction capability for MCP tool-use pattern
- **Dependencies**: `mcp`, `mammoth`, `exceptions.py`, `scratchpad.py`
- **Type**: Application (not yet wired into active CLI)

### classification.py
- **Purpose**: LLM-based document classification + vault file routing
- **Responsibilities**: Build prompt, call Anthropic API, validate category, move file to vault subfolder
- **Dependencies**: `anthropic`, `scratchpad.py`
- **Type**: Application

### models.py
- **Purpose**: Shared data model definitions
- **Responsibilities**: Define `CompactArtifact` (TypedDict) and `EnrichedDocument` (dataclass)
- **Dependencies**: `exceptions.py` (re-export)
- **Type**: Shared/Models

### scratchpad.py
- **Purpose**: Structured JSONL event logger
- **Responsibilities**: Append log entries with timestamp/level/message/context
- **Dependencies**: stdlib only
- **Type**: Shared/Utility

### exceptions.py
- **Purpose**: Centralised exception hierarchy
- **Responsibilities**: Define `ExtractionPipelineError` base + `PipelineError` dataclass
- **Dependencies**: stdlib only
- **Type**: Shared/Utility

## Data Flow

```
.docx file on disk
      |
      | mammoth.extract_raw_text()
      v
CompactArtifact { document_name, extracted_text }
      |
      | write extracted_text to .md file
      v
.md file on disk (output folder)
      |
      | read first 500 chars + stem
      v
Anthropic API call (LIGHT_MODEL)
      |
      | category string
      v
shutil.move() → Obsidian vault subfolder
```

## Integration Points

- **External APIs**: Anthropic Messages API — used by `ClassificationAgent` for single-turn classification
- **Databases**: None
- **Third-party Services**:
  - Anthropic Claude (via `anthropic` SDK, env: `LIGHT_MODEL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`)
  - Obsidian vault (local filesystem, env: `OBSIDIAN_VAULT_PATH`)

## Infrastructure Components

- **CDK Stacks**: None
- **Deployment Model**: Local CLI, installed via `pip install -e .` or `uv sync`
- **Networking**: None (local only; outbound HTTPS to Anthropic API)
