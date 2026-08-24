# Code Structure

## Build System
- **Type**: setuptools (PEP 517)
- **Configuration**: `pyproject.toml` — single-package project, `src/` layout

## Key Modules

### src/pipeline/
| File | Purpose |
|---|---|
| `main.py` | CLI entry point — arg parsing, tracing init, asyncio orchestration |
| `extraction.py` | `Extractor` class — mammoth .docx → text, emits OTEL "extract" span |
| `extraction_server.py` | FastMCP server exposing `parse_document` tool |
| `classification.py` | `ClassificationAgent` — Claude LIGHT_MODEL classifier, emits OTEL "classify" span |
| `tracing.py` | `setup_tracing()` / `get_tracer()` — Phoenix + OTEL + Anthropic instrumentation |
| `scratchpad.py` | `Scratchpad` — JSONL structured logger |
| `models.py` | `CompactArtifact` (TypedDict), `EnrichedDocument` (dataclass) |
| `exceptions.py` | `PipelineError` dataclass, `ExtractionPipelineError` base |
| `__init__.py` | Package init (empty) |

### src/eval/
| File | Purpose |
|---|---|
| `eval_main.py` | CLI entry point — connects to Phoenix, delegates to EvalAgent |
| `eval_agent.py` | `EvalAgent` — fetches classify spans, judges via Claude MEDIUM_MODEL, logs px.Evaluation |
| `__init__.py` | Package init (empty) |

### tests/
| File | Purpose |
|---|---|
| `unit/test_extraction.py` | Unit tests for Extractor |
| `unit/test_classification.py` | Unit tests for ClassificationAgent |
| `unit/test_scratchpad.py` | Unit tests for Scratchpad |
| `unit/test_tracing.py` | Unit tests for tracing setup/get_tracer |
| `eval/test_eval_agent.py` | Tests for EvalAgent |
| `property/test_extraction_pbt.py` | Property-based tests (Hypothesis) for extraction |
| `integration/` | Integration test folder (currently empty) |

## Design Patterns

### Agent Pattern
- **Location**: `ClassificationAgent`, `EvalAgent`
- **Purpose**: Encapsulate LLM interaction (prompt construction, API call, response parsing, error handling) behind a class interface
- **Implementation**: Async methods using `anthropic.AsyncAnthropic()`

### Observer / Structured Logging
- **Location**: `Scratchpad`
- **Purpose**: Append-only JSONL event log; fire-and-forget on each operation
- **Implementation**: Opens file in append mode per write — no persistent file handle

### OTEL Instrumentation
- **Location**: `pipeline.tracing`, `extraction.py`, `classification.py`, `main.py`
- **Purpose**: Emit structured telemetry spans for every document operation
- **Implementation**: Context-manager spans via `_tracer.start_as_current_span(...)`; span attributes follow `eval.*` and `document.*` namespaces

### Fail-soft Tracing
- **Location**: `tracing.setup_tracing()`
- **Purpose**: Phoenix/OTEL are optional — pipeline continues if setup fails
- **Implementation**: try/except returning bool; caller logs warning and proceeds

## Critical Dependencies
### anthropic
- **Version**: >=0.25
- **Usage**: Claude API calls in ClassificationAgent and EvalAgent
- **Purpose**: LLM backbone for classification and AI-as-judge evaluation

### mammoth
- **Version**: >=1.6
- **Usage**: Extractor, extraction_server
- **Purpose**: .docx → plain text extraction

### arize-phoenix / arize-phoenix-otel
- **Version**: >=4.0 / >=0.6
- **Usage**: tracing.setup_tracing(), EvalAgent
- **Purpose**: Local OTEL collector + evaluation backend

### openinference-instrumentation-anthropic
- **Version**: >=0.1
- **Usage**: tracing.setup_tracing()
- **Purpose**: Auto-instrument Anthropic SDK calls as OTEL spans

### mcp
- **Version**: >=1.8,<2.0
- **Usage**: extraction_server.py
- **Purpose**: FastMCP server for tool-based extraction interface
