# Integration Test Plan — Unit 3: Extraction (Claude + MCP)

## Purpose

These tests verify the full `ExtractionAgent.process()` pipeline against the live
Anthropic Claude API with a real local MCP session. They complement the unit tests
(mocked tool_runner) by exercising the actual MCP stdio transport, FastMCP tool dispatch,
and Claude's real tool-call loop behaviour.

---

## Prerequisites

| Requirement | Detail |
|---|---|
| `ANTHROPIC_API_KEY` env var | Valid Anthropic API key with access to `claude-haiku-4-5-20251001` |
| Network access | Outbound HTTPS to `api.anthropic.com` |
| Installed extras | `pip install -e ".[dev]"` with `anthropic[mcp]>=0.25` and `mcp>=1.8` |
| Fixture files | At least one real `.docx` and one real `.pdf` in `tests/integration/fixtures/` |

---

## Test Scenarios

### INT-E-01: Happy path — DOCX

- **Given**: A valid `.docx` fixture with at least two paragraphs
- **When**: `ExtractionAgent.process(metadata, staging_path)` is called with a real `Config`
  (categories: `["Finance", "HR", "Legal"]`)
- **Then**:
  - Returns a `CompactArtifact` with non-empty `extracted_text`
  - `category` is one of `["Finance", "HR", "Legal"]`
  - `file_id` and `document_name` match the input metadata

### INT-E-02: Happy path — PDF

- **Given**: A valid `.pdf` fixture with text on at least one page
- **When**: `ExtractionAgent.process(metadata, staging_path)` is called
- **Then**: Same assertions as INT-E-01

### INT-E-03: Category selection

- **Given**: A `.docx` fixture with clearly financial content (invoices, budget figures)
- **When**: Categories are `["Finance", "HR", "Legal"]`
- **Then**: Claude selects `"Finance"`

### INT-E-04: Image staging with real ImageClient stub

- **Given**: A `.docx` with two image items returned by a stub `ImageClient`
- **When**: `ExtractionAgent.process()` runs end-to-end
- **Then**: `CompactArtifact.images` contains two `ImageMetadata` entries with valid `staged_path`

### INT-E-05: Rate-limit retry path (manual / carefully)

- **Given**: Claude API key with very low rate limit OR mocked 429 injected at the `tool_runner` boundary
- **When**: First call returns 429
- **Then**: Agent sleeps, retries, and returns a valid `CompactArtifact`

---

## How to Run

```bash
# From the workspace root with the venv activated:
ANTHROPIC_API_KEY=sk-ant-... pytest tests/integration/ -v -k "extraction"
```

---

## Why Not Automated in CI

- **Cost**: Each test makes one or more live Claude API calls billed to the API key.
- **External dependency**: Tests depend on Anthropic network availability and API stability.
- **Latency**: A full extraction call takes 5–30 seconds depending on document size.

These tests run on-demand before releases or after significant changes to `extraction.py`
or `extraction_server.py`.
