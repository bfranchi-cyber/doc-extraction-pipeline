# Integration Test Instructions

## Scope

This project is a local CLI tool with two execution paths:
1. **Extraction + classification pipeline** (`docs-extraction`) — reads `.docx` files, produces `.md` files, optionally classifies into Obsidian vault folders, and emits OTEL spans to Phoenix.
2. **Eval runner** (`docs-extraction-eval`) — connects to a running Phoenix instance and judges unevaluated classify spans via LLM.

Integration tests verify the two paths work end-to-end without real Anthropic API calls.

## Scenario 1: End-to-end extraction pipeline with tracing

**What is tested**: `docs-extraction` runs against a folder of `.docx` files, produces `.md` files, and Phoenix tracing initialises without error.

**Setup**:
```bash
# Start Phoenix locally (if not already running)
python -c "import phoenix as px; px.launch_app()"
# Or: phoenix serve
```

**Test steps**:
```bash
export LIGHT_MODEL=claude-haiku-4-5-20251001
export ANTHROPIC_API_KEY=<key>
docs-extraction --input tests/fixtures/docx/ --output /tmp/docs-output/
```

**Expected results**:
- `.md` files created under `/tmp/docs-output/` mirroring the input structure
- `scratchpad.jsonl` written at `/tmp/docs-output/scratchpad.jsonl`
- No Python tracebacks in stderr
- If Phoenix is running: spans visible at `http://localhost:6006` under project `docs-extraction`
- If Phoenix is not running: warning printed to scratchpad, pipeline completes normally

**Cleanup**:
```bash
rm -rf /tmp/docs-output/
```

## Scenario 2: Eval runner against real Phoenix spans

**What is tested**: `docs-extraction-eval` connects to Phoenix, retrieves classify spans, and returns a verdict summary.

**Prerequisites**: Scenario 1 must have run at least once with Phoenix active so spans exist.

**Setup**:
```bash
export MEDIUM_MODEL=claude-sonnet-5
export ANTHROPIC_API_KEY=<key>
# Phoenix must be running
```

**Test steps**:
```bash
docs-extraction-eval
```

**Expected results**:
```
Evaluated N spans — correct: X, incorrect: Y
```
- Exit code 0
- If Phoenix unreachable: error printed to stderr, exit code 1

## Test Fixtures

Create minimal `.docx` fixtures for manual integration testing:
```bash
# Install python-docx for fixture creation
pip install python-docx
python - <<'EOF'
from docx import Document
doc = Document()
doc.add_paragraph("This document covers AWS Lambda and Terraform for cloud deployments.")
doc.save("tests/fixtures/docx/sample-cloud.docx")
EOF
```

## Notes

- No automated integration test suite exists yet; the `tests/integration/` directory is reserved for future automation.
- These manual scenarios double as smoke tests before any release.
