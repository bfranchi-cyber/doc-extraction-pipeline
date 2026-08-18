# Component Inventory

## Application Packages
- `pipeline` (`src/pipeline/`) — Core CLI application: extraction, classification, logging, orchestration

## Infrastructure Packages
None — local-only tool, no cloud infrastructure.

## Shared Packages (within `pipeline`)
- `models.py` — `CompactArtifact`, `EnrichedDocument` data models
- `scratchpad.py` — Shared JSONL logger
- `exceptions.py` — Shared error hierarchy

## Test Packages
- `tests/unit/` — Unit tests (mocked I/O): `test_extraction`, `test_classification`, `test_scratchpad`
- `tests/property/` — Property-based tests (Hypothesis): `test_extraction_pbt`
- `tests/integration/` — Integration test placeholder (empty)

## Source File Count
- **Total source files**: 8 (in `src/pipeline/`)
- **Total test files**: 4 (3 unit + 1 property)

## Total Count
- **Total Packages**: 1 installable package (`pipeline`)
- **Application Modules**: 5 (`main`, `extraction`, `extraction_server`, `classification`, `__init__`)
- **Shared Modules**: 3 (`models`, `scratchpad`, `exceptions`)
- **Infrastructure**: 0
- **Test Modules**: 4
