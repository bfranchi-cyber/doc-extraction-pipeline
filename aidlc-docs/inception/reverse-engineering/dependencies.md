# Dependencies

## Internal Dependencies

```
eval.eval_main
    --> eval.eval_agent
            --> pipeline.classification (CATEGORY_DESCRIPTIONS, VALID_CATEGORIES)
            --> anthropic (AsyncAnthropic)
            --> arize-phoenix (px.Client, px.Evaluation)

pipeline.main
    --> pipeline.extraction
    --> pipeline.classification
    --> pipeline.tracing
    --> pipeline.scratchpad
    --> pipeline.exceptions

pipeline.extraction
    --> pipeline.models (CompactArtifact)
    --> pipeline.tracing (get_tracer)
    --> pipeline.scratchpad
    --> mammoth (via asyncio.to_thread)

pipeline.classification
    --> pipeline.scratchpad
    --> pipeline.tracing (get_tracer)
    --> anthropic (AsyncAnthropic)

pipeline.extraction_server
    --> pipeline.exceptions
    --> pipeline.scratchpad
    --> mcp.server.fastmcp (FastMCP)
    --> mammoth

pipeline.tracing
    --> opentelemetry.trace
    --> arize-phoenix (px.launch_app)
    --> arize-phoenix-otel (register)
    --> openinference-instrumentation-anthropic (AnthropicInstrumentor)

pipeline.scratchpad  -- no internal deps
pipeline.models      -- no internal deps
pipeline.exceptions  -- no internal deps
```

## External Dependencies

### anthropic (>=0.25)
- **Purpose**: LLM API for classification and eval judging
- **Usage**: `anthropic.AsyncAnthropic()` in ClassificationAgent and EvalAgent
- **License**: MIT

### mammoth (>=1.6)
- **Purpose**: .docx text extraction
- **Usage**: `mammoth.extract_raw_text(f).value` in Extractor and extraction_server
- **License**: BSD-2-Clause

### mcp (>=1.8,<2.0)
- **Purpose**: MCP server framework
- **Usage**: `FastMCP` in extraction_server.py
- **License**: MIT

### arize-phoenix (>=4.0)
- **Purpose**: Local OTEL telemetry collector + evaluation storage; `px.Client` for span querying
- **Usage**: `px.launch_app()`, `px.Client`, `px.Evaluation`, `px.EvaluationResult`
- **License**: Apache-2.0

### arize-phoenix-otel (>=0.6)
- **Purpose**: Phoenix OTEL provider registration
- **Usage**: `register(project_name=..., endpoint=...)` in tracing.setup_tracing()
- **License**: Apache-2.0

### openinference-instrumentation-anthropic (>=0.1)
- **Purpose**: Auto-instrument Anthropic SDK calls as OTEL spans
- **Usage**: `AnthropicInstrumentor().instrument()` in tracing.setup_tracing()
- **License**: Apache-2.0

### opentelemetry (transitive via phoenix-otel)
- **Purpose**: OTEL SDK — tracer, span context manager
- **Usage**: `opentelemetry.trace.get_tracer()`, `_tracer.start_as_current_span(...)`
- **License**: Apache-2.0
