# Code Generation Plan — Phoenix Tracing & Eval

## Unit Context
- **Unit**: Phoenix Tracing & Eval
- **Packages affected**: `src/pipeline/` (runtime), `src/eval/` (offline tooling)
- **Requirements**: FR-01..FR-10, NFR-01..NFR-05
- **Extension enforcement**: PBT Partial (PBT-02, PBT-07 carry forward on existing modules only — no new stateful/transform logic in this unit triggers PBT)
- **One-way dependency rule**: `eval` imports from `pipeline`; `pipeline` never imports from `eval`

## Dependencies on Existing Code
- `pipeline.classification.VALID_CATEGORIES` — already public; used by `eval_agent.py`
- `pipeline.classification.CATEGORY_DESCRIPTIONS` — new public export (Step 1); used by `eval_agent.py`
- `pipeline.tracing.get_tracer` — new (Step 2); imported by `extraction.py`, `classification.py`, `main.py`

## Step Sequence

---

### Step 1 — Refactor `src/pipeline/classification.py` (FR-08a)
**Action**: Modify existing file

Extract the category descriptions out of `_SYSTEM_PROMPT` into a public `CATEGORY_DESCRIPTIONS: dict[str, str]` mapping each category name to its description. Rebuild `_SYSTEM_PROMPT` from `CATEGORY_DESCRIPTIONS` at module level so behaviour is unchanged. No changes to `classify()` or `_move_to_vault()` signatures in this step.

- [ ] Add `CATEGORY_DESCRIPTIONS: dict[str, str]` as a public module-level constant
- [ ] Rebuild `_SYSTEM_PROMPT` from `CATEGORY_DESCRIPTIONS` (same final string, different construction)
- [ ] Confirm `VALID_CATEGORIES` still matches the keys of `CATEGORY_DESCRIPTIONS`

---

### Step 2 — Create `src/pipeline/tracing.py` (FR-07)
**Action**: Create new file

Two public functions:
- `setup_tracing(project_name: str) -> bool` — launches Phoenix in-process via `px.launch_app()`, calls `register(project_name=..., endpoint=..., auto_instrument=True)` from `phoenix.otel`, explicitly calls `AnthropicInstrumentor().instrument()`, returns `True` on success and `False` on any exception (logs warning to stderr — no Scratchpad dependency here since Scratchpad may not yet exist at call time)
- `get_tracer(name: str = __name__) -> opentelemetry.trace.Tracer` — returns `trace.get_tracer(name)`; works as a no-op when no provider is configured (OTEL guarantee)

- [ ] Create `src/pipeline/tracing.py` with `setup_tracing` and `get_tracer`

---

### Step 3 — Modify `src/pipeline/extraction.py` (FR-04)
**Action**: Modify existing file

Wrap the mammoth extraction block inside an `extract` child span. Span attributes: `document.name` (filename), `extracted_text_length` (character count of result). If tracing is unavailable the OTEL no-op tracer ensures no error.

- [ ] Import `get_tracer` from `pipeline.tracing`
- [ ] Wrap extraction logic in `tracer.start_as_current_span("extract")` context manager
- [ ] Set `document.name` and `extracted_text_length` span attributes

---

### Step 4 — Modify `src/pipeline/classification.py` (FR-04, FR-05)
**Action**: Modify existing file (second pass — spans and eval attributes)

Wrap the body of `classify()` in a `classify` child span. Record programmatic eval attributes on the span after the API call. Do **not** call EvalAgent here.

Span attributes:
- `document.name` — filename
- `eval.category` — raw LLM response string (including `unknown`)
- `eval.classified` — bool; `True` only when file was moved
- `eval.latency_ms` — duration of the `messages.create()` call in ms
- `eval.api_error` — bool; `True` when API exception was raised

- [ ] Import `get_tracer` and `time` (for latency measurement)
- [ ] Wrap `classify()` body in `tracer.start_as_current_span("classify")` context manager
- [ ] Measure `messages.create()` latency and record all eval attributes on the span

---

### Step 5 — Modify `src/pipeline/main.py` (FR-09)
**Action**: Modify existing file

- Call `setup_tracing("docs-extraction")` once, before the asyncio event loop, right after instantiating `Scratchpad`. Log a warning to the scratchpad if it returns `False`.
- Wrap each document's processing block (extraction + classification) in a `process_document` root span with attribute `document.name`.
- Do **not** import or reference anything from `eval`.

- [ ] Import `setup_tracing` from `pipeline.tracing`
- [ ] Call `setup_tracing("docs-extraction")` after `Scratchpad` instantiation; warn on failure
- [ ] Wrap per-document block in `tracer.start_as_current_span("process_document")` with `document.name` attribute

---

### Step 6 — Create `src/eval/__init__.py` (FR-08)
**Action**: Create new file

Empty package marker.

- [ ] Create empty `src/eval/__init__.py`

---

### Step 7 — Create `src/eval/eval_agent.py` (FR-08)
**Action**: Create new file

`class EvalAgent`:
- `__init__(self)` — reads `MEDIUM_MODEL` and `PHOENIX_HOST` (default `localhost:6006`) from env vars; instantiates `anthropic.Anthropic()` client
- `async run_evals(self) -> dict` — connects to Phoenix via `phoenix.Client(endpoint=...)`, queries `classify` spans from project `docs-extraction` that have no `eval.judge_verdict` annotation, calls `_judge_span` for each, uploads results via `client.log_evaluations(...)`, returns `{"evaluated": int, "correct": int, "incorrect": int}`
- `async _judge_span(self, span: dict) -> str` — extracts `document.name`, excerpt (from span input), and `eval.category` from span attributes; calls `MEDIUM_MODEL` with judge prompt built from `CATEGORY_DESCRIPTIONS`; returns `"correct"` or `"incorrect"`; returns `"skipped"` on exception

Imports: `VALID_CATEGORIES`, `CATEGORY_DESCRIPTIONS` from `pipeline.classification`.

- [ ] Create `src/eval/eval_agent.py` with `EvalAgent` class

---

### Step 8 — Create `src/eval/eval_main.py` (FR-10)
**Action**: Create new file

`def main()` — entry point for `docs-extraction-eval`:
- Reads `PHOENIX_HOST` env var (default `localhost:6006`)
- Instantiates `EvalAgent`, calls `asyncio.run(agent.run_evals())`
- Prints summary: `Evaluated N spans — correct: X, incorrect: Y`
- Exits with code 1 and clear error message if Phoenix is unreachable

- [ ] Create `src/eval/eval_main.py` with `main()` function

---

### Step 9 — Modify `pyproject.toml` (NFR-04)
**Action**: Modify existing file

- Add 3 runtime dependencies: `arize-phoenix`, `arize-phoenix-otel`, `openinference-instrumentation-anthropic`
- Add new script entry: `docs-extraction-eval = "eval.eval_main:main"`
- Confirm `find: where = ["src"]` already covers both `pipeline` and `eval` packages (no change needed)

- [ ] Add 3 new deps to `[project] dependencies`
- [ ] Add `docs-extraction-eval` to `[project.scripts]`

---

### Step 10 — Create `tests/unit/test_tracing.py` (NFR-05)
**Action**: Create new file

Unit tests for `setup_tracing`:
- Test success path: mocked `px.launch_app()` + `register` + `AnthropicInstrumentor` → returns `True`
- Test failure path: `px.launch_app()` raises exception → returns `False`, no exception propagated

- [ ] Create `tests/unit/test_tracing.py`

---

### Step 11 — Create `tests/eval/__init__.py` (NFR-05)
**Action**: Create new file

Empty package marker for the eval test directory.

- [ ] Create empty `tests/eval/__init__.py`

---

### Step 12 — Create `tests/eval/test_eval_agent.py` (NFR-05)
**Action**: Create new file

Unit tests for `EvalAgent`:
- Test `_judge_span` correct verdict: mocked Anthropic response `"correct"` → returns `"correct"`
- Test `_judge_span` incorrect verdict: mocked Anthropic response `"incorrect"` → returns `"incorrect"`
- Test `_judge_span` API failure: Anthropic raises exception → returns `"skipped"`
- Test `run_evals` with no unevaluated spans: mocked Phoenix client returns empty list → returns `{"evaluated": 0, "correct": 0, "incorrect": 0}`

- [ ] Create `tests/eval/test_eval_agent.py`

---

### Step 13 — Create code summary doc (documentation)
**Action**: Create new file

- [ ] Create `aidlc-docs/construction/phoenix-tracing-eval/code/code-summary.md` with a brief summary of all generated/modified files, key design decisions, and the one-way dependency rule

---

## Checklist Summary

| Step | File | Action |
|---|---|---|
| 1 | `src/pipeline/classification.py` | MODIFY — public `CATEGORY_DESCRIPTIONS` |
| 2 | `src/pipeline/tracing.py` | CREATE |
| 3 | `src/pipeline/extraction.py` | MODIFY — extract span |
| 4 | `src/pipeline/classification.py` | MODIFY — classify span + eval attributes |
| 5 | `src/pipeline/main.py` | MODIFY — tracing init + root span |
| 6 | `src/eval/__init__.py` | CREATE |
| 7 | `src/eval/eval_agent.py` | CREATE |
| 8 | `src/eval/eval_main.py` | CREATE |
| 9 | `pyproject.toml` | MODIFY |
| 10 | `tests/unit/test_tracing.py` | CREATE |
| 11 | `tests/eval/__init__.py` | CREATE |
| 12 | `tests/eval/test_eval_agent.py` | CREATE |
| 13 | `aidlc-docs/construction/phoenix-tracing-eval/code/code-summary.md` | CREATE |
