# Services — Analysis Step & Classify Refactor (2026-08-21)

## Overview

The pipeline has no explicit service layer — `main.py` directly coordinates the agents as an
orchestration script. This document captures the orchestration flow and instantiation contract.

---

## Pipeline Orchestration Service (`src/pipeline/main.py`)

### Updated Orchestration Flow

```
process_one(docx_path):
  1. artifact = await extractor.process(docx_path)        # extract text from .docx
  2. output_path.write_text(artifact["extracted_text"])    # write raw .md file
  3. await analyzer.analyze(output_path)                   # inject YAML frontmatter (NEW)
  4. if classifier:
         await classifier.classify(output_path)           # classify + move to vault
```

Each `process_one()` coroutine is independent. All are launched concurrently via `asyncio.gather`.

### Agent Instantiation

```python
extractor  = Extractor(scratchpad)
analyzer   = AnalysisAgent(scratchpad)                        # NEW
vault_root = _resolve_vault_root(scratchpad)
classifier = ClassificationAgent(vault_root, scratchpad) if vault_root else None
```

- `ClassificationAgent.__init__()` discovers vault categories synchronously at instantiation
- No `AnalysisAgent` is conditionally skipped — it always runs if the step is reached

### Failure Isolation

Each step is fail-soft:
- If `analyze()` returns `None` (failure): `classify()` still runs using the fallback raw-text path
- If `classify()` returns `False`: file stays in `--output` directory (unchanged behavior)
- Failures logged to `scratchpad.jsonl`; pipeline continues with remaining documents

---

## Eval Orchestration Service (`src/eval/eval_main.py`)

Minor update: `EvalAgent` constructor now receives `vault_root` instead of reading from `VALID_CATEGORIES` import.

```python
vault_root = Path(os.environ["OBSIDIAN_VAULT_PATH"]) if os.environ.get("OBSIDIAN_VAULT_PATH") else None
eval_agent = EvalAgent(vault_root=vault_root, scratchpad=scratchpad)
```

No changes to eval orchestration loop or CLI interface.
