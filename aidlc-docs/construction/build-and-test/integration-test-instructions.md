# Integration Test Instructions

## Purpose

Validate the full pipeline end-to-end: CLI entry point → `ExtractionAgent` → mammoth → `.md` output files, including folder mirroring, scratchpad logging, and error handling for bad files.

There is a single unit (Extraction), so "integration" here means CLI-level testing of `main.py` against real `.docx` files on disk — not service-to-service integration.

No external services, databases, or network calls are required.

---

## Scenario 1: Single .docx file — happy path

**Description**: Verify that a valid `.docx` file produces a `.md` output with the expected text.

**Setup**:
```powershell
# Create a test directory with one .docx (use any real .docx you have)
$testInput = "$env:TEMP\docs-extraction-test\input"
$testOutput = "$env:TEMP\docs-extraction-test\output"
New-Item -ItemType Directory -Force $testInput, $testOutput | Out-Null
# Copy a known .docx into $testInput
Copy-Item "path\to\sample.docx" "$testInput\sample.docx"
```

**Execution**:
```powershell
.venv\Scripts\python -m pipeline.main --input $testInput --output $testOutput
```

**Expected results**:
- Exit with no errors printed to stderr
- `$testOutput\sample.md` exists and contains the document text
- `$testOutput\scratchpad.jsonl` contains one `INFO` entry for `sample.docx`

**Cleanup**:
```powershell
Remove-Item -Recurse -Force "$env:TEMP\docs-extraction-test"
```

---

## Scenario 2: Nested folder structure — mirroring

**Description**: Verify that subdirectory structure under `--input` is mirrored in `--output`.

**Setup**:
```powershell
$testInput = "$env:TEMP\docs-extraction-mirror\input"
New-Item -ItemType Directory -Force "$testInput\subdir" | Out-Null
Copy-Item "path\to\doc1.docx" "$testInput\doc1.docx"
Copy-Item "path\to\doc2.docx" "$testInput\subdir\doc2.docx"
$testOutput = "$env:TEMP\docs-extraction-mirror\output"
```

**Execution**:
```powershell
.venv\Scripts\python -m pipeline.main --input $testInput --output $testOutput
```

**Expected results**:
- `$testOutput\doc1.md` exists
- `$testOutput\subdir\doc2.md` exists (subdirectory created automatically)
- Both `.md` files contain the expected text

**Cleanup**:
```powershell
Remove-Item -Recurse -Force "$env:TEMP\docs-extraction-mirror"
```

---

## Scenario 3: Corrupted .docx — error handling

**Description**: Verify that a corrupted file logs an error and does not crash the pipeline (other files in the same run continue processing).

**Setup**:
```powershell
$testInput = "$env:TEMP\docs-extraction-error\input"
New-Item -ItemType Directory -Force $testInput | Out-Null
# Write a fake (invalid) .docx
[System.IO.File]::WriteAllBytes("$testInput\bad.docx", [byte[]](0x00, 0x01, 0x02))
Copy-Item "path\to\good.docx" "$testInput\good.docx"
$testOutput = "$env:TEMP\docs-extraction-error\output"
```

**Execution**:
```powershell
.venv\Scripts\python -m pipeline.main --input $testInput --output $testOutput
```

**Expected results**:
- `$testOutput\good.md` exists and contains text
- `$testOutput\bad.md` does NOT exist
- An `ERROR:` line is printed to stderr for `bad.docx`
- `$testOutput\scratchpad.jsonl` contains an `ERROR` entry for `bad.docx`

**Cleanup**:
```powershell
Remove-Item -Recurse -Force "$env:TEMP\docs-extraction-error"
```

---

## Scenario 4: Real documents (smoke test against actual corpus)

**Description**: Run against the full `estudos` corpus used during development (39 documents).

**Prerequisite**: Load `.env` into the current PowerShell session (needed only if `ANTHROPIC_*` vars are required at runtime — currently mammoth does not need them, but future Analysis stage will).

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
    }
}
```

**Execution**:
```powershell
.venv\Scripts\python -m pipeline.main `
    --input "$env:USERPROFILE\Documents\estudos" `
    --output output
```

**Expected results**:
- All `.docx` files found and processed (count printed at start)
- No `ERROR:` lines in stderr
- `output/scratchpad.jsonl` contains one `INFO` entry per file
- `output/` mirrors the `estudos` folder structure with `.md` files

---

## No External Services Required

This pipeline uses only:
- Local filesystem reads/writes
- `mammoth` (pure Python, no network)

No database, Docker, or external API is required for integration testing. The `ANTHROPIC_*` environment variables are loaded but not called until the Analysis stage is implemented.
