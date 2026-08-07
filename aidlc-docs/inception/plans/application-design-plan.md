# Application Design Plan — Extraction Pipeline

Please answer each question by filling in the letter choice after the `[Answer]:` tag.

---

## Question 1
How should the Coordinator Agent be implemented?

A) A stateful Python class that holds the scratchpad in memory and is instantiated once per pipeline run

B) A standalone async function (no persistent class state) that receives structured outputs and constructs the next stage's input, with scratchpad written directly to a log file

C) A Claude agent call — the Coordinator is itself an LLM call that receives structured stage outputs and decides what to do next

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 2
How should the compact artifact (the structured handoff from Extraction to Analysis) be represented?

A) A Python dataclass / TypedDict — validated in-process, passed as a Python object between agent functions

B) A JSON file written to disk — each extraction agent writes its result to disk, the Coordinator reads and validates it before passing to Analysis

C) A JSON string passed in-memory — serialized/deserialized between stages but never written to disk

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 3
How should the Extraction Agents be structured?

A) One reusable async function called concurrently for each document via `asyncio.gather`

B) A class with a `process(document)` async method, one instance per document, all instantiated and awaited together

C) A pool pattern — a fixed number of worker coroutines pulling from an async queue of documents

D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 4
Where should configuration (vault path, images path, manifest path, Drive folder ID, category list) live?

A) A `.env` file loaded at startup via `python-dotenv`

B) A `config.yaml` or `config.toml` file parsed at startup

C) Hard-coded constants in a dedicated `config.py` module

D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 5
How should the manifest (idempotency state) be managed — particularly around concurrent writes during parallel extraction?

A) Sequential manifest writes only — all manifest updates happen after the async extraction batch completes, not during

B) Per-document manifest file (one JSON file per Drive file ID) — no concurrent write conflicts possible

C) Async-safe single manifest with file locking (e.g., `filelock` library) for concurrent access

D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Execution Checklist

- [x] Step 1: Analyze context (requirements.md, stories.md)
- [x] Step 2: Create application design plan
- [x] Step 3: Include mandatory artifacts
- [x] Step 4: Generate questions
- [x] Step 5: Store plan (this file)
- [x] Step 6: Request user input
- [x] Step 7: Collect answers
- [x] Step 8: Analyze answers for ambiguities — no ambiguities detected
- [x] Step 9: Follow-up questions — N/A
- [x] Step 10: Generate application design artifacts
- [x] Step 11: Log approval in audit.md
- [x] Step 12: Present completion message
- [ ] Step 13: Wait for explicit approval

## Planned Artifacts
- `aidlc-docs/inception/application-design/components.md`
- `aidlc-docs/inception/application-design/component-methods.md`
- `aidlc-docs/inception/application-design/services.md`
- `aidlc-docs/inception/application-design/component-dependency.md`
- `aidlc-docs/inception/application-design/application-design.md`
