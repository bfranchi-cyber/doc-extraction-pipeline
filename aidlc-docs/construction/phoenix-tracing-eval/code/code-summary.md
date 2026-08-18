# Code Summary — Phoenix Tracing & Eval

## Files Modified

- **`src/pipeline/classification.py`** — Added `CATEGORY_DESCRIPTIONS` public constant; rebuilt `_SYSTEM_PROMPT` dynamically from it. Added `get_tracer` import and module-level `_tracer`. Wrapped `classify()` body in `classify` span with `document.name`, `eval.category`, `eval.classified`, `eval.latency_ms`, and `eval.api_error` attributes.
- **`src/pipeline/extraction.py`** — Added `get_tracer` import and module-level `_tracer`. Wrapped extraction block in `extract` span with `document.name` and `extracted_text_length` attributes.
- **`src/pipeline/main.py`** — Added `setup_tracing` + `get_tracer` imports. Calls `setup_tracing("docs-extraction")` after `Scratchpad` instantiation (warns via scratchpad on failure). Wraps each document's processing block in a `process_document` root span with `document.name`.
- **`pyproject.toml`** — Added 3 runtime deps (`arize-phoenix`, `arize-phoenix-otel`, `openinference-instrumentation-anthropic`). Added `docs-extraction-eval = "eval.eval_main:main"` script entry.

## Files Created

- **`src/pipeline/tracing.py`** — `setup_tracing(project_name)` launches Phoenix in-process and registers OTEL; returns `True`/`False`. `get_tracer(name)` returns an OTEL tracer (no-op when no provider).
- **`src/eval/__init__.py`** — Empty package marker.
- **`src/eval/eval_agent.py`** — `EvalAgent` class. `run_evals()` queries Phoenix for unevaluated `classify` spans, calls `_judge_span()` on each, uploads results via `client.log_evaluations()`. `_judge_span()` uses `MEDIUM_MODEL` with a prompt built from `CATEGORY_DESCRIPTIONS`.
- **`src/eval/eval_main.py`** — `main()` entry point for `docs-extraction-eval` CLI. Exits with code 1 if Phoenix unreachable.
- **`tests/unit/test_tracing.py`** — Unit tests for `setup_tracing`: success path and failure path (exception → returns `False`).
- **`tests/eval/__init__.py`** — Empty package marker.
- **`tests/eval/test_eval_agent.py`** — Unit tests for `EvalAgent`: `_judge_span` correct, incorrect, API failure (skipped); `run_evals` with no spans.

## Key Design Decisions

- **One-way dependency rule**: `eval` imports from `pipeline`; `pipeline` never imports from `eval`. Enforced structurally — `main.py` does not reference anything from `eval`.
- **OTEL no-op guarantee**: `get_tracer()` is safe to call even when `setup_tracing()` returns `False` — the OTEL spec guarantees a no-op tracer when no provider is configured.
- **On-demand eval**: The LLM-as-judge runs only via `docs-extraction-eval` CLI, not on every extraction run, avoiding latency overhead in the hot path.
- **`CATEGORY_DESCRIPTIONS` as single source of truth**: Both the system prompt and the eval judge prompt are built from the same dictionary, eliminating drift between classification and evaluation criteria.
