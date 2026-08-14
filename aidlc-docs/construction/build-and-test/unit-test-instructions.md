# Unit Test Execution

## Test Suite Overview

| File | Tests | What it covers |
|---|---|---|
| `tests/unit/test_extraction.py` | 7 | `parse_document` FastMCP tool (3) + `ExtractionAgent.process()` via mammoth (4) |
| `tests/unit/test_scratchpad.py` | 6 | `Scratchpad` JSONL logger — full coverage |
| `tests/property/test_extraction_pbt.py` | 1 | `CompactArtifact` JSON round-trip (PBT-02) |
| **Total** | **15** | — |

Coverage target: **65%** (`main.py` excluded — CLI entry point, not unit-testable).

---

## Run All Unit Tests

```powershell
.venv\Scripts\pytest tests\ -v
```

### Expected output

```
tests/unit/test_extraction.py::TestParseDocument::test_docx_returns_paragraph_text PASSED
tests/unit/test_extraction.py::TestParseDocument::test_docx_text_order_preserved PASSED
tests/unit/test_extraction.py::TestParseDocument::test_corrupted_docx_raises_pipeline_error PASSED
tests/unit/test_extraction.py::TestExtractionAgentProcess::test_happy_path_returns_compact_artifact PASSED
tests/unit/test_extraction.py::TestExtractionAgentProcess::test_extracted_text_contains_all_paragraphs PASSED
tests/unit/test_extraction.py::TestExtractionAgentProcess::test_corrupted_file_raises_pipeline_error PASSED
tests/unit/test_extraction.py::TestExtractionAgentProcess::test_document_name_matches_filename PASSED
tests/unit/test_scratchpad.py::test_info_writes_valid_jsonl_entry PASSED
tests/unit/test_scratchpad.py::test_warn_writes_warn_level PASSED
tests/unit/test_scratchpad.py::test_error_writes_error_level PASSED
tests/unit/test_scratchpad.py::test_context_included_when_provided PASSED
tests/unit/test_scratchpad.py::test_context_omitted_when_none PASSED
tests/unit/test_scratchpad.py::test_multiple_writes_append_not_overwrite PASSED
tests/unit/test_scratchpad.py::test_each_entry_is_valid_json PASSED
tests/property/test_extraction_pbt.py::test_compact_artifact_text_fields_json_roundtrip PASSED

15 passed
Required test coverage of 65% reached. Total coverage: 98.73%
```

---

## Run with Coverage Report

```powershell
.venv\Scripts\pytest tests\ --cov=src/pipeline --cov-report=term-missing
```

Current verified coverage (with `main.py` excluded):

| Module | Coverage |
|---|---|
| `exceptions.py` | 92% |
| `extraction.py` | 100% |
| `extraction_server.py` | 100% |
| `models.py` | 100% |
| `scratchpad.py` | 100% |
| **Total** | **98.73%** |

The one uncovered line is `exceptions.py:27` — the `__str__` method path only reachable when `PipelineError` is cast to string outside `pytest.raises`. Not worth a dedicated test.

---

## Run a Single Test File

```powershell
# Unit tests only
.venv\Scripts\pytest tests/unit/test_extraction.py -v

# Scratchpad tests only
.venv\Scripts\pytest tests/unit/test_scratchpad.py -v

# Property-based tests only
.venv\Scripts\pytest tests/property/test_extraction_pbt.py -v
```

---

## Fix Failing Tests

1. Read the test output — pytest prints the failing assertion and the relevant stack frame.
2. Most failures will be in `test_extraction.py` — check that `mammoth` is installed and `ExtractionAgent` still calls `mammoth.extract_raw_text` directly.
3. For `test_extraction_pbt.py` failures — Hypothesis will print the minimal failing example. The round-trip invariant should never fail unless `CompactArtifact` fields are changed to a non-JSON-serialisable type.
4. Re-run after fixing: `pytest tests\ -v`
