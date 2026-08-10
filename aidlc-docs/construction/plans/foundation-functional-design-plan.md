# Functional Design Plan — Unit 1: Foundation

## Unit Summary

Unit 1 provides all shared infrastructure: data types, configuration loading, manifest management, and the scratchpad utility. Every other unit depends on it. No external API calls are made in this unit.

**Components**:
- `pipeline/models.py` — all shared dataclasses and TypedDicts
- `pipeline/config.py` — `Config` dataclass + `Config.from_toml()`
- `pipeline/manifest.py` — `ManifestStore` class
- `config.toml` — runtime configuration file
- Unit tests + PBT tests for Config and ManifestStore

**Acceptance criteria in scope**: AC-08.1, AC-08.2, AC-08.3

---

## Functional Design Plan Steps

- [x] Step 1: Define all data models (types, fields, constraints)
- [x] Step 2: Define Config dataclass (fields, TOML structure, validation rules)
- [x] Step 3: Define ManifestStore business logic and invariants
- [x] Step 4: Define business rules and validation constraints
- [x] Step 5: Generate functional design artifacts (business-logic-model.md, domain-entities.md, business-rules.md)

---

## Clarifying Questions

Please answer each question by filling in the letter after `[Answer]:`.
If none of the options match, choose the last option and describe your preference.

---

## Question 1
The `ManifestRecord` has a `status` field with values `"success"` or `"failed"`. When a file fails partway through the pipeline (e.g., extraction succeeds but analysis fails), what status should the manifest record?

A) Always write `"failed"` if any stage fails — the whole document is considered failed regardless of which stage

B) Write the last successfully completed stage name (e.g., `"failed:analysis"`) to allow partial re-runs from that stage

C) Keep the manifest record absent (don't write anything) until the full pipeline completes — only write on terminal success or terminal failure

D) Other (please describe after [Answer]: tag below)

[Answer]: D, there will be automatic retrial for transient errors. Other types of errors may be direct failed (business, validation)

---

## Question 2
The `Config` dataclass uses `Path` types for file system paths (`vault_path`, `images_path`, `manifest_dir`, `staging_dir`, `scratchpad_path`, `credentials_path`). Should `Config.from_toml()` validate that these paths exist on disk at load time, or only that they are syntactically valid paths?

A) Validate existence on disk — raise `ConfigError` immediately if any required path does not exist

B) Validate syntax only (no filesystem check at config load time) — path existence is checked at runtime by each agent that uses them

C) Validate existence only for `credentials_path` (must exist to authenticate) — all other paths are created lazily by the agents that need them

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 3
The `ManifestStore` uses per-document JSON files (one file per Drive `file_id`). What should `ManifestStore.get()` do if the manifest file exists but its JSON is malformed (e.g., corrupted write)?

A) Raise an exception — treat it as a hard failure (corrupted manifest = cannot safely determine prior state)

B) Return `None` — treat a corrupted manifest record as if the file was never processed (safe re-processing)

C) Log a warning and return `None` — same behavior as B but with an observable signal for debugging

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 4
The `RunSummary` tracks `eligible`, `processed`, `failed`, `skipped` counts. Should `skipped` mean files skipped due to already being in the manifest (idempotency), or files skipped for any reason (including unsupported format, manifest skip, etc.)?

A) `skipped` = files already successfully processed (manifest skip only) — unsupported formats are a separate category or ignored in summary

B) `skipped` = all files not processed for any non-error reason (manifest + unsupported format + any other benign skip)

C) Track them separately: `skipped_manifest` and `skipped_format` as distinct counts on `RunSummary`

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 5
The `config.toml` will contain `drive_folder_id`, model IDs, `eligibility_days`, and all paths. Should the `categories` list (the list of pre-existing Obsidian vault folder names) also be stored in `config.toml` and loaded into `Config`, or should categories be discovered dynamically at runtime by listing the vault directory?

A) Store categories in `config.toml` — explicit, predictable, no filesystem dependency at startup

B) Discover categories dynamically at runtime by listing the vault directory — always in sync with the actual vault structure

C) Both: load from `config.toml` as the primary source, but validate against the actual vault folder listing at startup and warn on mismatch

D) Other (please describe after [Answer]: tag below)

[Answer]: C
