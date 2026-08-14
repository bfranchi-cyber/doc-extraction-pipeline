# Application Design — Extraction Pipeline (Revised 2026-08-14)

> **Scope change**: Original design included PipelineCoordinator, IngestionAgent, AnalysisAgent,
> ExportAgent, ManifestStore, and Google Drive integration. All dropped. See git history for
> the original design. Current design covers local .docx → .md extraction only.

---

## Design Summary

The pipeline is a simple sequential script. `main.py` discovers `.docx` files recursively under `--input`, calls `ExtractionAgent.process()` for each, and writes the extracted text as a `.md` file under `--output` mirroring the input structure.

---

## Components

| Component | Role |
|---|---|
| `main.py` | Entry point — CLI args, file discovery, output writing |
| `ExtractionAgent` | Calls Claude Haiku via MCP to extract text from one .docx |
| `make_extraction_app` | Creates FastMCP server with `parse_document` tool |
| `Scratchpad` | JSONL structured logger |

---

## Data Flow

```
--input/
  a/doc1.docx  ──►  ExtractionAgent.process(doc1.docx)  ──►  CompactArtifact
  b/doc2.docx  ──►  ExtractionAgent.process(doc2.docx)  ──►  CompactArtifact
                                                                     |
                                                                     v
                                                             --output/
                                                               a/doc1.md
                                                               b/doc2.md
```

## Key Data Types

- `CompactArtifact` (TypedDict): `{document_name: str, extracted_text: str}`
- `EnrichedDocument` (dataclass): reserved for future Analysis stage

## Directory Structure

```
docs-extraction/
  src/pipeline/
    __init__.py
    main.py              # Entry point
    extraction.py        # ExtractionAgent
    extraction_server.py # FastMCP server (parse_document tool)
    models.py            # CompactArtifact, EnrichedDocument
    exceptions.py        # PipelineError, ExtractionPipelineError
    scratchpad.py        # Scratchpad logger
  tests/
    unit/
      test_extraction.py
      test_scratchpad.py
    property/
      test_extraction_pbt.py
```

## External Dependencies

- `anthropic[mcp]` — Claude API + MCP tool runner
- `mcp` — MCP client/server protocol
- `mammoth` — .docx text extraction (pure Python, no native DLLs)
