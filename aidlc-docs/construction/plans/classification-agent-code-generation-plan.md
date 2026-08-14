# Code Generation Plan — Classification Agent

## Unit Context
- **Unit**: Classification Agent
- **Workspace root**: `c:\Users\bfranchi\Desktop\projetos\docs-extraction`
- **Application code**: `src/pipeline/`
- **Tests**: `tests/unit/`
- **PBT rules in scope**: PBT-02, PBT-07, PBT-08

## Steps

- [ ] Step 1: Rename `ExtractionAgent` → `Extractor` in `src/pipeline/extraction.py`
- [ ] Step 2: Update `src/pipeline/main.py` — rename import and usage of `ExtractionAgent`
- [ ] Step 3: Update `tests/unit/test_extraction.py` — rename import and all usages of `ExtractionAgent`
- [ ] Step 4: Create `src/pipeline/classification.py` — `ClassificationAgent` class
- [ ] Step 5: Update `src/pipeline/main.py` — integrate `ClassificationAgent` and `resolve_vault_root`
- [ ] Step 6: Create `tests/unit/test_classification.py` — unit + PBT tests
- [ ] Step 7: Create `aidlc-docs/construction/classification-agent/code/code-summary.md`

---

## Step Details

### Step 1 — Rename in `extraction.py`
- Class `ExtractionAgent` → `Extractor`
- No behaviour change

### Step 2 — Update `main.py` (rename only)
- `from pipeline.extraction import ExtractionAgent` → `from pipeline.extraction import Extractor`
- `agent = ExtractionAgent(scratchpad)` → `extractor = Extractor(scratchpad)`
- All call sites updated (currently: `agent.process(...)` → `extractor.process(...)`)

### Step 3 — Update `test_extraction.py` (rename only)
- `from pipeline.extraction import ExtractionAgent` → `from pipeline.extraction import Extractor`
- `ExtractionAgent(...)` → `Extractor(...)` in all test methods (4 occurrences)

### Step 4 — Create `classification.py`
New file: `src/pipeline/classification.py`

Contents:
- Module-level constants: `VALID_CATEGORIES` (frozenset of 5 categories), `_SYSTEM_PROMPT`
- `ClassificationAgent.__init__(vault_root, scratchpad)` — reads `LIGHT_MODEL` env var, instantiates `anthropic.Anthropic()`
- `async classify(md_path) -> bool` — Step 1 (API call) + Step 2 (move)
- `_move_to_vault(md_path, category) -> bool` — checks folder exists, calls `shutil.move`

### Step 5 — Update `main.py` (integration)
- Import `ClassificationAgent` and `os`
- Add `resolve_vault_root(scratchpad) -> Path | None` — reads `OBSIDIAN_VAULT_PATH`, warns if missing
- In `main()`: call `resolve_vault_root`, build `ClassificationAgent` if vault found
- In `run_all()` loop: after writing `.md` to output, call `await classifier.classify(output_path)`

### Step 6 — Create `test_classification.py`
New file: `tests/unit/test_classification.py`

Test classes:
- `TestClassificationAgent` — unit tests using `unittest.mock.patch`:
  - `test_valid_category_moves_file` — happy path; file lands in vault folder
  - `test_each_valid_category_moves_file` — parametrize over all 5 categories
  - `test_unknown_response_leaves_file_in_place`
  - `test_malformed_response_leaves_file_in_place`
  - `test_missing_vault_folder_leaves_file_in_place`
  - `test_api_error_leaves_file_in_place`

- PBT (hypothesis, PBT-02 / PBT-07):
  - `test_pbt_any_valid_category_succeeds` — given any element of `VALID_CATEGORIES` as model response, classify returns True and file is moved
  - `test_pbt_invalid_response_never_moves` — given any string not in `VALID_CATEGORIES | {"unknown"}`, classify returns False and file stays

### Step 7 — Code summary
Markdown file at `aidlc-docs/construction/classification-agent/code/code-summary.md`
Listing all created/modified files with one-line purpose descriptions.
