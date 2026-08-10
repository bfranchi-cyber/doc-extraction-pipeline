# NFR Design Plan — Unit 1: Foundation

## Unit Summary

Unit 1 is pure Python — no network, no async, no external APIs. NFR design focuses on:
- Atomic file I/O pattern for ManifestStore
- Scratchpad JSONL writer component
- Startup fail-fast validation pattern (Config)

---

## Plan Steps

- [x] Step 1: Analyze NFR requirements artifacts
- [x] Step 2: Identify applicable NFR design categories
- [x] Step 3: Collect user answers
- [x] Step 4: Generate nfr-design-patterns.md and logical-components.md

---

## Applicable NFR Design Categories

| Category | Applicable? | Rationale |
|---|---|---|
| Resilience Patterns | Yes (limited) | ManifestCorruptionError handling — Coordinator must decide halt vs. skip |
| Scalability Patterns | N/A | Single-user local tool; no scaling mechanism needed |
| Performance Patterns | N/A | Sub-500ms startup + sub-100ms manifest ops; no optimization pattern needed |
| Security Patterns | N/A | Security extension disabled; credentials path validated at startup only |
| Logical Components | Yes | Scratchpad writer + ManifestStore + Config loader are distinct logical components |

---

## Questions

Please answer each question by filling in the letter after `[Answer]:`.

---

## Question 1
When `ManifestStore.get()` raises `ManifestCorruptionError` during a pipeline run, the
Coordinator must decide what to do. Which behaviour should Unit 1 document as the
**intended Coordinator response** (this will become part of the NFR design contract)?

A) Halt the entire pipeline run — a corrupted manifest means the pipeline cannot safely
determine prior state for any document; the operator must inspect and repair before re-running

B) Skip the affected document and continue — log the corruption to the scratchpad, write a
`"failed"` manifest record for that document, and proceed with the remaining files

C) Skip the affected document and continue — log the corruption to the scratchpad but do NOT
write a manifest record (leave it corrupted so the operator can see it on the next run)

D) Other (please describe after [Answer]: tag below)

[Answer]: B, not just failed but detail it in the anthropic guideline for tool errors:
{
    "content": [
        {
            "type": "transient, business, validation, permission",
            "text": "Your error message here"
            "is_retriable": True only for transient
            "suggestion": "Text suggesting an action"
        }
    ],
    "is_error": True
}

---

## Question 2
The `write_log()` utility that writes JSONL entries to the scratchpad will be used by all
pipeline units. Where should it live?

A) `pipeline/scratchpad.py` — a dedicated module with a `Scratchpad` class that holds the
path and exposes `info()`, `warn()`, `error()` methods

B) `pipeline/scratchpad.py` — a module-level `write_log(path, level, msg, context)` function,
no class; callers pass the path each time

C) Inside `pipeline/models.py` alongside the data types — keeps Unit 1's surface area minimal

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 3
`Config.from_toml()` validates that `credentials_path` is an existing, readable file (BR-03).
Should it also validate the **content** of the credentials file (e.g., check that it is valid
JSON and contains a `"type"` field expected by the Google OAuth library)?

A) Yes — validate that `credentials_path` contains valid JSON with a `"type"` field; raise
`ConfigError` if not. Fail fast before any API call is attempted.

B) No — validate existence and readability only; content validation is delegated to the Google
auth library when it first attempts to load the credentials

C) Other (please describe after [Answer]: tag below)

[Answer]: A
