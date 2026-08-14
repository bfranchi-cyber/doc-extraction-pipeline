# Code Summary — Classification Agent

## Modified Files

| File | Change |
|---|---|
| `src/pipeline/extraction.py` | Renamed `ExtractionAgent` → `Extractor` (no behaviour change) |
| `src/pipeline/main.py` | Renamed usage; added `_resolve_vault_root()`; integrated `ClassificationAgent` into pipeline loop |
| `tests/unit/test_extraction.py` | Updated import and 4 class usages: `ExtractionAgent` → `Extractor` |

## Created Files

| File | Purpose |
|---|---|
| `src/pipeline/classification.py` | `ClassificationAgent` — two-step classify + move; `VALID_CATEGORIES` constant; `_SYSTEM_PROMPT` |
| `tests/unit/test_classification.py` | 6 unit tests + 2 PBT tests (PBT-02, PBT-07) for `ClassificationAgent` |

## Key Design Decisions Implemented

- **Two-step loop**: text-only API call (`max_tokens=20`, no tools) → code validates → `_move_to_vault` Python method
- **`LIGHT_MODEL` env var**: model name never hardcoded
- **`OBSIDIAN_VAULT_PATH` env var**: vault root; missing → warn once, skip all classification
- **`unknown` sentinel**: model outputs `"unknown"` → WARN + no move
- **No folder creation**: destination must pre-exist; missing folder → WARN + no move
- **Failure isolation**: any exception caught, logged, pipeline continues to next file
