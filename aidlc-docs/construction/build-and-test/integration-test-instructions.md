# Integration Test Instructions

## Purpose
Test the full extraction → classification → move pipeline end-to-end using a real `.docx` file and the live Anthropic API.

## Prerequisites
- All environment variables set (see `build-instructions.md`)
- `OBSIDIAN_VAULT_PATH` set to a test vault with the five category folders pre-created
- At least one `.docx` test file available

## Setup

### 1. Create a test vault

```bash
mkdir -p /path/to/test-vault/Architecture
mkdir -p /path/to/test-vault/CI&T
mkdir -p /path/to/test-vault/Cloud
mkdir -p /path/to/test-vault/Coding
mkdir -p /path/to/test-vault/ML&AI
```

### 2. Set environment variables

```bash
export OBSIDIAN_VAULT_PATH=/path/to/test-vault
export LIGHT_MODEL=<your-haiku-model-name>
export ANTHROPIC_API_KEY=<your-key>
export ANTHROPIC_BASE_URL=<your-proxy-url>
```

### 3. Prepare test input

Place one or more `.docx` files in a test input folder, e.g. `/tmp/test-input/`.

## Scenario 1: Full Pipeline — Extract + Classify + Move

```bash
uv run docs-extraction --input /tmp/test-input --output /tmp/test-output
```

**Expected results:**
- `.md` files are written to `/tmp/test-output/`
- Each `.md` file is moved to the matching vault folder (e.g. `$OBSIDIAN_VAULT_PATH/Coding/my-doc.md`)
- `scratchpad.jsonl` in `/tmp/test-output/` contains `INFO` entries for classified files
- No `.md` files remain in `/tmp/test-output/` for successfully classified documents

## Scenario 2: Missing Vault Path — Classification Skipped

```bash
unset OBSIDIAN_VAULT_PATH
uv run docs-extraction --input /tmp/test-input --output /tmp/test-output
```

**Expected results:**
- `.md` files are written and remain in `/tmp/test-output/`
- `scratchpad.jsonl` contains a `WARN` entry: `OBSIDIAN_VAULT_PATH not set`
- No files moved

## Scenario 3: Unclassifiable Document

Use a `.docx` containing ambiguous or non-technical content (e.g. a recipe or poem).

**Expected results:**
- `.md` file stays in output folder
- `scratchpad.jsonl` contains `WARN` entry: `Unclassifiable: <filename>`

## Cleanup

```bash
rm -rf /tmp/test-output
```
