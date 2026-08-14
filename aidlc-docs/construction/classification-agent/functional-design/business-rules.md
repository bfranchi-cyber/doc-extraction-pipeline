# Business Rules — Classification Agent

## Classification Rules

### BR-01: Category Exhaustiveness
The six valid enum values are:
`Architecture`, `CI&T`, `Cloud`, `Coding`, `ML&AI`, `unknown`
The first five are Obsidian vault folder names. `unknown` is a sentinel — it never maps to a folder.
No other values are accepted by the tool schema (enforced by JSON Schema enum).

### BR-02: Two-Step Agent Loop — Classify Then Move
The agent operates in two explicit steps. **Step 1**: a text-only API call (no tools provided, `max_tokens: 20`) where the model outputs *only* the category name — no explanation, no verbose text. **Step 2**: the code validates the response and calls `move_to_vault` as a plain Python function. No Anthropic tool schema is used. No second API call is made. This separation ensures the model classifies before any side effect is triggered.

### BR-03: Unclassifiable = `unknown` + WARN + No Move
If the model responds with `"unknown"`, the file is left in the output folder unchanged and a `WARN` entry is written to the Scratchpad. If the response is not in the valid enum set at all (malformed), the same WARN + no-move applies.

### BR-04: Input Truncation
Only the first **500 characters** of the `.md` file content are sent. The filename stem (no extension) is prepended as `Filename: {stem}`. Content is stripped before truncating.

### BR-05: Vault Path is Required at Runtime
`OBSIDIAN_VAULT_PATH` must be a non-empty string resolving to an accessible directory. If absent or empty, `classify()` is never called for any file — a single `WARN` is logged once before the pipeline loop.

### BR-06: Destination Folder Must Pre-Exist
The destination folder `OBSIDIAN_VAULT_PATH/<category>/` must already exist. The agent **never creates folders**. If the folder is missing, a `WARN` is logged and the file is left in the output folder unchanged. This prevents unexpected directory creation inside the vault.

### BR-07: File Overwrite Behaviour
If a file with the same name already exists in the destination vault folder, `shutil.move` overwrites it. No conflict resolution or renaming.

### BR-08: Classification Failure Isolation
Any exception raised during the Anthropic API call or the file move is caught, logged as `ERROR` to the Scratchpad, and the pipeline continues to the next file. Classification failure must never abort the extraction run.

### BR-09: Rename — ExtractionAgent → Extractor
`ExtractionAgent` is renamed to `Extractor`. The class behaviour is identical. All call sites in `main.py` and test files are updated. No other changes to extraction logic.

---

## Validation Rules

### VR-01: Model Env Var
`LIGHT_MODEL` must be set. If absent, `ClassificationAgent.__init__` raises `EnvironmentError` to fail fast — this is a configuration error, not a runtime error to swallow.

### VR-02: Category Enum
The `move_to_vault` tool schema declares an `enum` on the `category` parameter. The Anthropic API will reject responses that supply a value outside the enum, preventing silent miscategorisation.
