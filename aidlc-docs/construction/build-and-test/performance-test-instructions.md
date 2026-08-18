# Performance Test Instructions

## Applicability

**Status**: N/A for this iteration.

This is a local CLI tool that processes `.docx` files sequentially. Performance is bounded by:
- Anthropic API latency (network I/O — not addressable at this layer)
- `mammoth` extraction speed (CPU-bound, typically < 1s per file)
- Phoenix OTEL span export (async, non-blocking — fire-and-forget via OTEL SDK)

There are no throughput, concurrency, or SLA requirements for this tool (NFR-02 explicitly states only that normal-path latency must not be increased by more than 100ms, which is met by the OTEL no-op guarantee when Phoenix is unavailable).

## Observability via Phoenix (Recommended Approach)

Instead of load testing, use the Phoenix tracing UI to monitor per-run performance:

1. Run the pipeline with Phoenix active (see integration test instructions).
2. Open `http://localhost:6006`.
3. Select project `docs-extraction`.
4. Review `eval.latency_ms` attribute on `classify` spans to identify slow API calls.

This is the intended performance monitoring approach for this tool.

## Future Considerations

If the tool is extended to process files in parallel (asyncio task pool), revisit with:
- Hypothesis-based property tests for concurrency edge cases
- A timing harness measuring wall-clock per batch of N files
