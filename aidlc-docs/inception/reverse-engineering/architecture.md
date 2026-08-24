# System Architecture

## System Overview

A local Python CLI system with two executable entry points:
- `docs-extraction`: Extracts .docx → .md and classifies into an Obsidian vault. Emits OTEL spans to Phoenix.
- `docs-extraction-eval`: Reads Phoenix spans, judges classification quality with Claude, writes eval labels back.

Both share the `pipeline.tracing` module for OTEL setup and tracer access.

## Architecture Diagram

```
+------------------------------------------------------------------+
|                        CLI Entry Points                          |
|   docs-extraction (main.py)    docs-extraction-eval (eval_main)  |
+------------------------------------------------------------------+
          |                                      |
          v                                      v
+-------------------+                  +-------------------+
|  pipeline.tracing |                  |  eval.EvalAgent   |
|  setup_tracing()  |                  |  run_evals()      |
|  get_tracer()     |                  |  _judge_span()    |
+-------------------+                  +-------------------+
          |                                      |
          v                                      v
+-------------------+              +----------------------+
|  Extractor        |              | Phoenix px.Client    |
|  (mammoth)        |              | (localhost:6006)     |
+-------------------+              +----------------------+
          |                                      |
          v                                      v
+-------------------+              +----------------------+
|  ClassificationA  |              | Anthropic Claude API |
|  gent (Claude     |              | (MEDIUM_MODEL)       |
|  LIGHT_MODEL)     |              +----------------------+
+-------------------+
          |
          v
+-------------------+
|  Obsidian Vault   |
|  (filesystem)     |
+-------------------+
          |
          v
+-------------------+
|  Scratchpad       |
|  (JSONL log)      |
+-------------------+
```

## Component Descriptions

### pipeline.main
- **Purpose**: CLI entry point for the extraction+classification pipeline
- **Responsibilities**: Parse CLI args, initialise tracing, coordinate Extractor and ClassificationAgent via asyncio.gather
- **Dependencies**: pipeline.extraction, pipeline.classification, pipeline.tracing, pipeline.scratchpad
- **Type**: Application

### pipeline.tracing
- **Purpose**: OTEL/Phoenix tracing setup and tracer factory
- **Responsibilities**: Launch Phoenix in-process, register OTEL provider, instrument Anthropic SDK, return tracers
- **Dependencies**: opentelemetry, arize-phoenix, openinference-instrumentation-anthropic
- **Type**: Shared utility

### pipeline.extraction / Extractor
- **Purpose**: Extract text from .docx files
- **Responsibilities**: Read .docx via mammoth, emit "extract" OTEL span, return CompactArtifact
- **Dependencies**: mammoth, pipeline.tracing, pipeline.scratchpad
- **Type**: Application

### pipeline.classification / ClassificationAgent
- **Purpose**: LLM-powered document classifier
- **Responsibilities**: Build classification prompt, call Claude (LIGHT_MODEL), validate response, move file to vault, emit "classify" OTEL span with eval attributes
- **Dependencies**: anthropic, pipeline.tracing, pipeline.scratchpad
- **Type**: Application

### pipeline.extraction_server
- **Purpose**: MCP-based extraction server (FastMCP)
- **Responsibilities**: Expose `parse_document` tool over MCP protocol
- **Dependencies**: mcp.server.fastmcp, mammoth
- **Type**: Application (alternative interface)

### pipeline.scratchpad / Scratchpad
- **Purpose**: Structured JSONL event logger
- **Responsibilities**: Write INFO/WARN/ERROR entries as JSONL to a file alongside output
- **Dependencies**: stdlib only
- **Type**: Shared utility

### pipeline.models
- **Purpose**: Shared data models
- **Responsibilities**: Define CompactArtifact (TypedDict) and EnrichedDocument (dataclass)
- **Dependencies**: stdlib only
- **Type**: Shared models

### pipeline.exceptions
- **Purpose**: Structured error types
- **Responsibilities**: PipelineError dataclass with error_type, retriability, suggestion
- **Dependencies**: stdlib only
- **Type**: Shared utility

### eval.eval_main
- **Purpose**: CLI entry point for the evaluation pipeline
- **Responsibilities**: Instantiate EvalAgent, run evals, print summary
- **Dependencies**: eval.eval_agent
- **Type**: Application

### eval.eval_agent / EvalAgent
- **Purpose**: AI-as-judge evaluation agent
- **Responsibilities**: Fetch classify spans from Phoenix, call Claude (MEDIUM_MODEL) to judge each, log px.Evaluation results back
- **Dependencies**: anthropic, arize-phoenix, pipeline.classification (for CATEGORY_DESCRIPTIONS, VALID_CATEGORIES)
- **Type**: Application

## Data Flow

```
Sequence: Extraction + Classification
1. main() -> setup_tracing("docs-extraction")
2. main() -> asyncio.gather(process_one per .docx)
3. process_one -> Extractor.process(docx_path)
   - OTEL span "extract" emitted
4. process_one -> ClassificationAgent.classify(md_path)
   - OTEL span "classify" emitted with eval.* attributes
5. ClassificationAgent -> move file to vault subfolder
6. Scratchpad.info() logged

Sequence: Evaluation
1. eval_main() -> EvalAgent.run_evals()
2. EvalAgent -> px.Client.get_spans_dataframe()
3. EvalAgent -> asyncio.gather(_judge_span per unevaluated span)
4. _judge_span -> Claude MEDIUM_MODEL judges "correct"/"incorrect"
5. EvalAgent -> px.Client.log_evaluations(px.Evaluation per span)
```

## Integration Points

- **External APIs**: Anthropic Claude API (LIGHT_MODEL for classification, MEDIUM_MODEL for eval judging)
- **Local Services**: Phoenix (arize-phoenix) on localhost:6006 — OTEL collector + UI
- **Filesystem**: Input .docx folder, output .md folder, Obsidian vault (OBSIDIAN_VAULT_PATH)

## Infrastructure Components

- **Deployment Model**: Local CLI — no cloud, no containers
- **Environment Variables**: LIGHT_MODEL, MEDIUM_MODEL, ANTHROPIC_API_KEY, OBSIDIAN_VAULT_PATH, PHOENIX_HOST
