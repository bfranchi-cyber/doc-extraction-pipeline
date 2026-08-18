# Requirements — Phoenix Tracing & Eval

## Intent Analysis

| Field | Value |
|---|---|
| **User Request** | Implement tracing and eval metrics using the Phoenix framework for the classification agent |
| **Request Type** | Enhancement — new observability layer on existing pipeline |
| **Scope** | Multiple components — `main.py` (pipeline orchestration), `classification.py` (ClassificationAgent), `extraction.py` (Extractor) |
| **Complexity** | Moderate — Phoenix/OpenInference instrumentation, OTEL span hierarchy, LLM-as-judge eval |

---

## Functional Requirements

### FR-01 — Phoenix In-Process Server
At pipeline startup, launch a Phoenix OSS server in-process via `px.launch_app()`.
- The server runs on localhost (default port 6006) for the duration of the pipeline execution.
- Startup must happen before any traces are emitted.
- If Phoenix fails to start, log a warning to the scratchpad and continue without tracing (graceful degradation).

### FR-02 — OTEL Tracer Configuration
Configure an OpenTelemetry tracer that exports spans to the in-process Phoenix server via OTLP.
- Tracer provider and OTLP exporter must be set up immediately after `px.launch_app()`.
- Phoenix project name: `docs-extraction`.

### FR-03 — Anthropic Auto-Instrumentation
Instrument the `anthropic` client using `openinference-instrumentation-anthropic` (`AnthropicInstrumentor`).
- Must be registered before the first `ClassificationAgent` is instantiated.
- Auto-captures: model name, input messages, output text, token counts, latency per API call.

### FR-04 — Full Pipeline Trace Per Document
Each document processed in `main.py` must produce one root trace with two child spans:
- **Root span**: `process_document` — covers the full document lifecycle (attributes: `document.name`, `document.path`)
- **Child span 1**: `extract` — covers `Extractor.process()` (attributes: `document.name`, `extracted_text_length`)
- **Child span 2**: `classify` — covers `ClassificationAgent.classify()`; the Anthropic API call within it is auto-instrumented as a grandchild span (attributes: `category`, `classified`, `document.name`)

### FR-05 — Programmatic Eval Metrics (Online)
After each classification, record the following as span attributes on the `classify` span:
- `eval.category` — the category string returned by the LLM (`unknown` if unclassifiable)
- `eval.classified` — boolean; `True` if file was successfully moved
- `eval.latency_ms` — classification API call duration in milliseconds
- `eval.api_error` — boolean; `True` if an API exception was raised

### FR-06 — LLM-as-Judge Quality Eval (On-Demand, Eval Context Only)
The LLM-as-judge evaluator does NOT run during normal pipeline execution. It runs on-demand via a separate `docs-extraction-eval` CLI entry point.
- The eval CLI connects to a running Phoenix instance, queries collected `classify` spans from the `docs-extraction` project, and runs the judge LLM (`MEDIUM_MODEL`) on any span not yet evaluated.
- Judge prompt: provide filename, 500-char excerpt (from `input.value` span attribute), assigned category, category descriptions; ask the judge to respond with only `correct` or `incorrect`.
- Results are uploaded back to Phoenix as span annotations: `eval.judge_verdict` (`correct` | `incorrect`).
- If no Phoenix instance is reachable, the eval CLI exits with a clear error message.

### FR-07 — New `tracing.py` Module (inside `pipeline`)
Isolate all Phoenix/OTEL setup in a new `src/pipeline/tracing.py` module with two public functions:
- `setup_tracing(project_name: str) -> bool` — launches Phoenix, configures OTLP exporter, registers AnthropicInstrumentor; returns `True` on success, `False` on failure.
- `get_tracer() -> opentelemetry.trace.Tracer` — returns the configured tracer for span creation in `main.py`, `extraction.py`, and `classification.py`.

### FR-08 — New `eval` Package (`src/eval/`)
Create a new top-level package `src/eval/` (separate from `src/pipeline/`) containing all offline eval tooling.
- `src/eval/__init__.py` — empty package marker.
- `src/eval/eval_agent.py` — `class EvalAgent` with:
  - `__init__()` — reads `MEDIUM_MODEL` and `PHOENIX_HOST` (default `localhost:6006`) env vars.
  - `async run_evals() -> None` — connects to Phoenix, fetches unevaluated `classify` spans from the `docs-extraction` project, runs the judge LLM call for each, uploads results as Phoenix span annotations.
  - `async _judge_span(span: dict) -> str` — runs the judge LLM call for a single span; returns `"correct"` or `"incorrect"`.
- The `eval` package imports `VALID_CATEGORIES` and `CATEGORY_DESCRIPTIONS` from `pipeline.classification` (one-way dependency: `eval` → `pipeline`, never the reverse).

### FR-08a — Public Category Descriptions Export (`classification.py`)
Refactor `classification.py` to export a public `CATEGORY_DESCRIPTIONS: dict[str, str]` mapping each category name to its description string.
- The existing `_SYSTEM_PROMPT` is assembled from `CATEGORY_DESCRIPTIONS` at module load (no behaviour change).
- `VALID_CATEGORIES` remains public (already is).
- `EvalAgent` imports `VALID_CATEGORIES` and `CATEGORY_DESCRIPTIONS` from `pipeline.classification` to build its judge prompt without duplicating the category taxonomy.

### FR-09 — Pipeline CLI Integration (`main.py`)
In `main.py`:
- Call `setup_tracing("docs-extraction")` before the asyncio event loop.
- Wrap the per-document processing block in a `process_document` root span.
- Pass the active span context into Extractor and ClassificationAgent so child spans are properly linked.
- **Do NOT import or instantiate EvalAgent** — it lives in the `eval` package and is never called from the pipeline.

### FR-10 — Eval CLI Entry Point (`src/eval/eval_main.py`)
Create `src/eval/eval_main.py` as the entry point for the `docs-extraction-eval` CLI command:
- Connects to a running Phoenix instance (using `PHOENIX_HOST` env var, default `localhost:6006`).
- Instantiates `EvalAgent` and calls `run_evals()`.
- Prints a summary: number of spans evaluated, count of `correct` / `incorrect` results.
- Register in `pyproject.toml` under `[project.scripts]`: `docs-extraction-eval = "eval.eval_main:main"`.

---

## Non-Functional Requirements

### NFR-01 — Graceful Degradation
If Phoenix or OTEL setup fails (import error, port conflict, etc.), the pipeline must continue processing documents normally. Tracing is best-effort, not mission-critical.

### NFR-02 — Eval Separation from Pipeline
The LLM-as-judge evaluator must not add any latency to normal `docs-extraction` CLI runs. Eval runs are entirely separate, on-demand invocations via `docs-extraction-eval`. This also means `MEDIUM_MODEL` is not required for normal pipeline execution.

### NFR-03 — Environment Variables
| Variable | Required for | Notes |
|---|---|---|
| `LIGHT_MODEL` | Classification (pipeline) | Existing |
| `MEDIUM_MODEL` | LLM-as-judge (eval CLI only) | New — only required when running `docs-extraction-eval` |
| `ANTHROPIC_API_KEY` | Both | Existing |
| `ANTHROPIC_BASE_URL` | Both | Existing optional proxy |
| `OBSIDIAN_VAULT_PATH` | Classification | Existing |
| `PHOENIX_HOST` | Eval CLI | New optional — Phoenix host:port (default `localhost:6006`) |

### NFR-04 — New Dependencies
Add to `pyproject.toml` (runtime, shared by both packages):
- `arize-phoenix` — Phoenix OSS server
- `arize-phoenix-otel` — lightweight OTEL setup helper
- `openinference-instrumentation-anthropic` — Anthropic auto-instrumentation

Both `pipeline` and `eval` are installed from the same `pyproject.toml`; `find: where = ["src"]` picks up both packages automatically.

### NFR-05 — Test Coverage
- `tests/eval/test_eval_agent.py` — unit tests for `EvalAgent` (mocked Anthropic client + mocked Phoenix client)
- `tests/unit/test_tracing.py` — unit tests for `setup_tracing` (mocked Phoenix launch)
- PBT-02 and PBT-07 carry forward for existing modules unchanged

---

## Extension Configuration (carried forward)

| Extension | Enabled | Decided At |
|---|---|---|
| Security Baseline | No | Requirements Analysis (2026-08-07) |
| Resiliency Baseline | No | Requirements Analysis (2026-08-07) |
| Property-Based Testing | Partial (PBT-02, 07, 08) | Requirements Analysis (2026-08-07) |
