# Business Overview

## Business Context Diagram

```
+------------------+      .docx files      +---------------------------+
|  User / Operator | --------------------> | docs-extraction CLI       |
+------------------+                       | (--input / --output)      |
                                           +---------------------------+
                                                       |
                                          +------------+-------------+
                                          |                          |
                                   Extracted .md             Classify + Move
                                          |                          |
                                   +------+------+        +----------+--------+
                                   | Output dir  |        | Anthropic API     |
                                   | (--output)  |        | (LIGHT_MODEL)     |
                                   +-------------+        +-------------------+
                                                                   |
                                                        +----------+--------+
                                                        | Obsidian Vault    |
                                                        | (OBSIDIAN_VAULT_  |
                                                        |  PATH)            |
                                                        +-------------------+
```

## Business Description

- **Business Description**: A local command-line tool that transforms Microsoft Word (`.docx`) documents into Markdown files and optionally organises them into an Obsidian knowledge vault by category.
- **Business Transactions**:
  1. **Extract** — Scan an input folder recursively, convert each `.docx` to plain Markdown text, write to a mirrored output folder.
  2. **Classify** — For each extracted `.md` file, call an LLM (Claude Haiku) with a short excerpt; receive a category label; move the file to the matching Obsidian vault sub-folder.
  3. **Log** — Write structured JSONL entries (INFO / WARN / ERROR) to a `scratchpad.jsonl` file for every pipeline event.
- **Business Dictionary**:
  - **Vault** — The Obsidian folder hierarchy at `OBSIDIAN_VAULT_PATH`; contains sub-folders matching the known categories.
  - **Category** — One of: `Architecture`, `CI&T`, `Cloud`, `Coding`, `ML & AI`, `unknown`.
  - **CompactArtifact** — In-memory handoff between Extractor and ClassificationAgent; carries `document_name` + `extracted_text`.
  - **Scratchpad** — Append-only JSONL log file written to the output directory.
  - **LIGHT_MODEL** — Environment variable naming the cheap/fast LLM used for classification.

## Component Level Business Descriptions

### CLI Entry Point (`main.py`)
- **Purpose**: Orchestrates the full pipeline for a batch of `.docx` files.
- **Responsibilities**: Parse CLI args, discover `.docx` files, drive Extractor + ClassificationAgent, surface errors to stderr.

### Extractor (`extraction.py`)
- **Purpose**: Converts a single `.docx` file into plain Markdown text.
- **Responsibilities**: Open file with mammoth, strip whitespace, return `CompactArtifact`; raise `PipelineError` on failure.

### ClassificationAgent (`classification.py`)
- **Purpose**: Assigns an Obsidian category to a `.md` file and moves it to the vault.
- **Responsibilities**: Build a short user message (filename + 500-char excerpt), call Anthropic API, validate response, call `_move_to_vault`; log warnings on unknown/missing-folder cases.

### Scratchpad (`scratchpad.py`)
- **Purpose**: Structured append-only event log.
- **Responsibilities**: Write JSONL entries with timestamp, level, message, and optional context dict.

### MCP Extraction Server (`extraction_server.py`)
- **Purpose**: Exposes the DOCX parsing capability as a FastMCP tool (`parse_document`).
- **Responsibilities**: Wrap mammoth in an async MCP tool; raise `PipelineError` on failure. (Present in codebase; not yet wired into the active CLI pipeline.)
