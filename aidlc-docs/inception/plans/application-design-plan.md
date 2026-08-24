# Application Design Plan

## Scope
Analysis step + Classify refactor — new `AnalysisAgent`, updated `ClassificationAgent`, updated orchestration, eval decoupling.

## Plan Checkboxes

- [x] Answer design questions (below)
- [x] Generate components.md
- [x] Generate component-methods.md
- [x] Generate services.md
- [x] Generate component-dependency.md
- [x] Generate application-design.md (consolidated)

---

## Design Questions

Please fill in the `[Answer]:` tag after each question. Let me know when done.

---

### Q1 — AnalysisAgent: component location
Where should AnalysisAgent live?

A) New file `src/pipeline/analysis.py` — mirrors the ClassificationAgent pattern (one class per file)

B) Inline in `main.py` as a function — simpler, no new file, but mixes orchestration with business logic

C) Other (describe below)

**Tradeoffs**:
- A keeps the codebase consistent and testable in isolation
- B reduces file count but makes main.py harder to read and test

[Answer]: A

---

### Q2 — AnalysisAgent: LLM model (DD-1)
Which model should AnalysisAgent use?

A) `LIGHT_MODEL` env var — same as ClassificationAgent; fast and cheap, may produce lower-quality summaries

B) `MEDIUM_MODEL` env var — reuse existing env var; more capable for structured analysis

C) New `ANALYSIS_MODEL` env var — fully flexible, adds one more env var to configure

**Tradeoffs**:
- A/B reuse existing env vars (simpler ops)
- C gives independent control but adds config surface
- LIGHT_MODEL is designed for short, fast responses; MEDIUM_MODEL better for reasoning tasks

[Answer]: B

---

### Q3 — AnalysisAgent: structured output method (DD-2)
How should AnalysisAgent enforce the `{summary, tags, confidence}` schema?

A) Anthropic tool-use / structured output (force the model to call a tool with the exact schema) — guarantees schema compliance, slightly more complex prompt setup

B) JSON in system prompt + `json.loads()` parse — simpler code; brittle if model produces markdown fencing or prose; needs retry or fallback logic

C) Other (describe below)

[Answer]: A

---

### Q4 — Dynamic category discovery: timing (DD-4)
When should `ClassificationAgent` scan the vault for category folders?

A) Once per pipeline run — scan at instantiation time, cache the list; fast, deterministic, won't pick up folders added mid-run

B) Per-classify call — always fresh; handles vault changes during long runs; tiny extra filesystem stat per document

[Answer]: A

---

### Q5 — Confidence threshold behaviour (DD-5)
Should the `confidence` value from AnalysisAgent affect whether classification is attempted?

A) Informational only — always attempt classification regardless of confidence; confidence is written to frontmatter for human review only

B) Hard threshold — skip classification if `confidence < 0.5` (or another value); reduces noise but may silently skip valid documents

C) Soft threshold with warning — attempt classification always, but log a Scratchpad warning when `confidence < 0.5`

[Answer]: A but futurely after confirming that the confidence is correctly calibrated we implement a hard threshold

---

### Q6 — Eval decoupling from VALID_CATEGORIES (DD-3)
`eval_agent.py` currently imports `VALID_CATEGORIES` and `CATEGORY_DESCRIPTIONS` from `classification.py` to build the judge prompt. With dynamic categories this breaks. How should it be handled?

A) Keep `CATEGORY_DESCRIPTIONS` as a static dict in `classification.py` alongside dynamic discovery — eval imports it as before; descriptions are manually maintained when vault folders change

B) EvalAgent reads the vault at eval time to get current categories — fully dynamic, requires `OBSIDIAN_VAULT_PATH` to be set when running eval

C) Pass discovered categories into `EvalAgent` as a constructor argument — explicit dependency, most testable

D) Remove category descriptions from the judge prompt entirely — eval only judges "does the classification make sense for the document?" without needing a category list

[Answer]: B

---

### Q7 — Frontmatter reading in ClassificationAgent
How should `ClassificationAgent` read the YAML frontmatter written by AnalysisAgent?

A) Inline parsing inside `classify()` — read the file, strip the `---` block, parse with `yaml` stdlib; simple, self-contained

B) Shared utility function in `pipeline/models.py` or a new `pipeline/frontmatter.py` — reusable across agents; slight extra indirection

C) Pass the analysis result (summary + tags) directly as a parameter to `classify()` rather than re-reading the file — avoids file I/O, tighter coupling between caller (main.py) and agents

[Answer]: B 
