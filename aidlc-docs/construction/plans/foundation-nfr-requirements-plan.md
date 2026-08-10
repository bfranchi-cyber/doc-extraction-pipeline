# NFR Requirements Plan — Unit 1: Foundation

## Unit Summary

Unit 1 is pure Python — no external APIs, no async, no network. It owns configuration loading,
manifest persistence (local JSON files), and shared data type contracts.

---

## Plan Steps

- [x] Step 1: Analyze functional design artifacts
- [x] Step 2: Identify NFR question areas
- [x] Step 3: Collect user answers
- [x] Step 4: Generate nfr-requirements.md and tech-stack-decisions.md

---

## Questions

Please answer each question by filling in the letter after `[Answer]:`.

---

## Question 1
What Python version should be targeted as the **minimum** for this project?

A) Python 3.11+ — use `tomllib` from the standard library (no extra dependency)

B) Python 3.10 — use `tomli` as a backport dependency for TOML parsing

C) Other (please describe after [Answer]: tag below)

[Answer]:  A

---

## Question 2
The `scratchpad_path` in `Config` points to a log file written by the pipeline.
What format should entries in that file use?

A) Plain text lines — human-readable, one line per event (e.g., `[2026-08-10 12:00:00] WARN: category "Work" not found in vault`)

B) Structured JSON Lines (JSONL) — one JSON object per line, machine-parseable (e.g., `{"ts": "...", "level": "WARN", "msg": "..."}`)

C) Python `logging` module output — use a `FileHandler` on the root logger directed to `scratchpad_path`

D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 3
`ManifestStore.set()` needs to serialize a `ManifestRecord` dataclass to JSON for file storage.
Which serialization approach should be used?

A) `dataclasses.asdict()` + `json.dumps()` — stdlib only, no extra dependency

B) `dataclasses-json` library — adds `to_json()` / `from_json()` convenience methods to dataclasses

C) Manual `__dict__`-style serialization with a custom `to_dict()` method on `ManifestRecord`

D) Other (please describe after [Answer]: tag below)

[Answer]:  B

---

## Question 4
Should static type checking be enforced as part of the development workflow for this project?

A) Yes — `mypy` in strict mode (`--strict`), enforced in CI / as a pre-commit check

B) Yes — `mypy` in standard mode (no `--strict`), main type errors caught without strict exhaustiveness

C) No — type hints are documentation-only; no type checker is run

D) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 5
What is the expected **minimum test coverage** target for Unit 1 (and the project as a whole)?

A) 80% line coverage — standard threshold for production code

B) 90% line coverage — high confidence, suitable for a small codebase

C) No hard coverage threshold — tests are written for critical paths; coverage is informational only

D) Other (please describe after [Answer]: tag below)

[Answer]: B
