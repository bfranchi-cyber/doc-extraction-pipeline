# Infrastructure Design Plan — Unit 1: Foundation

## Unit Summary

Unit 1 is a local Python library — no cloud services, no network, no queues.
Infrastructure scope is limited to: Python project packaging and local filesystem layout.

---

## Plan Steps

- [x] Step 1: Analyze functional and NFR design artifacts
- [x] Step 2: Assess applicable infrastructure categories
- [x] Step 3: Collect user answers
- [x] Step 4: Generate infrastructure-design.md and deployment-architecture.md

---

## Infrastructure Category Assessment

| Category | Applicable? | Rationale |
|---|---|---|
| Deployment Environment | Yes (local only) | Windows local machine; Python process invoked by user |
| Compute Infrastructure | N/A | No cloud compute; local Python interpreter only |
| Storage Infrastructure | Yes (local FS) | All paths defined in config.toml; no database |
| Messaging Infrastructure | N/A | No queues; pipeline is synchronous in-process |
| Networking Infrastructure | N/A | No network in Unit 1; Drive API calls are Unit 2 |
| Monitoring Infrastructure | Yes (local) | Scratchpad JSONL already designed; question on test infra |
| Shared Infrastructure | N/A | Single-user local tool |

---

## Questions

Please answer each question by filling in the letter after `[Answer]:`.

---

## Question 1
How should the project be packaged and installed on the local machine?

A) `pyproject.toml` (PEP 517/518) with `pip install -e .` for editable install — standard
modern Python project layout; dependencies declared under `[project.dependencies]`

B) `requirements.txt` only — flat dependency list, no packaging; run directly as a script
(`python -m pipeline` or `python main.py`)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 2
What Python source layout should be used?

A) `src/` layout — source lives under `src/pipeline/`; guards against accidental imports
from the project root during testing (recommended for installable packages)

B) Flat layout — source lives directly at `pipeline/` in the project root; simpler, no
install step needed if running scripts directly

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 3
Should a `Makefile` (or `tasks.py` / `justfile`) be provided with standard developer
commands (`make test`, `make lint`, `make run`)?

A) Yes — provide a `Makefile` with targets: `test`, `coverage`, `run`

B) No — document commands in README only; no task runner

C) Other (please describe after [Answer]: tag below)

[Answer]: B
