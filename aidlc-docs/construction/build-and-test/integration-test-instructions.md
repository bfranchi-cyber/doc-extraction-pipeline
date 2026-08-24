# Integration Test Instructions

## Scope

This project is a local CLI pipeline with no inter-service communication. The integration test is a manual end-to-end run of the full pipeline on a real `.docx` file.

## Prerequisites

- `ANTHROPIC_API_KEY` set
- `MEDIUM_MODEL` and `LIGHT_MODEL` set (e.g. `claude-haiku-4-5-20251001`)
- `OBSIDIAN_VAULT_PATH` set to a directory that has at least one subdirectory (category folder)
- At least one `.docx` file available as test input

## Scenario 1: Full pipeline run (extract → analyze → classify)

### Setup

```bash
set ANTHROPIC_API_KEY=<your-key>
set MEDIUM_MODEL=claude-haiku-4-5-20251001
set LIGHT_MODEL=claude-haiku-4-5-20251001
set OBSIDIAN_VAULT_PATH=C:\path\to\your\vault
```

### Steps

```bash
uv run docs-extraction --input <path-to-docx-folder> --output <output-folder>
```

### Expected results

1. `.md` file created under `--output` for each `.docx`
2. `.md` file begins with a YAML frontmatter block:
   ```yaml
   ---
   summary: "..."
   tags:
   - "..."
   confidence: 0.85
   ---
   ```
3. File is moved to a matching subfolder of `OBSIDIAN_VAULT_PATH`
4. Scratchpad JSONL (`scratchpad.jsonl`) contains `analyze` and `classify` entries

## Scenario 2: Fail-soft — AnalysisAgent failure does not block classification

### Setup

Temporarily set `MEDIUM_MODEL` to an invalid value (e.g. `bad-model`) to force AnalysisAgent failure.

### Steps

```bash
set MEDIUM_MODEL=bad-model
uv run docs-extraction --input <docx-folder> --output <output-folder>
```

### Expected results

1. `.md` file created (extraction succeeded)
2. No frontmatter in the file (AnalysisAgent failed silently)
3. ClassificationAgent falls back to raw text excerpt
4. Scratchpad contains an `error` entry for AnalysisAgent
5. File is still classified (or logged as unclassifiable) — pipeline does not crash

## Scenario 3: Vault with no subdirectories

### Setup

Set `OBSIDIAN_VAULT_PATH` to an empty directory.

### Expected results

1. `.md` file created with frontmatter
2. Classification skipped with a `warn` in scratchpad ("No subdirectories found in vault root")
3. File remains in `--output` (not moved)
