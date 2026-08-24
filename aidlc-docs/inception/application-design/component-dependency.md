# Component Dependencies — Analysis Step & Classify Refactor (2026-08-21)

## Dependency Matrix

| Component | Imports / Depends On |
|---|---|
| `main.py` | `Extractor`, `AnalysisAgent` (NEW), `ClassificationAgent`, `Scratchpad`, `tracing` |
| `AnalysisAgent` | `frontmatter.write_frontmatter` (NEW), `Scratchpad`, `tracing`, `anthropic` SDK |
| `ClassificationAgent` | `frontmatter.read_frontmatter` (NEW), `Scratchpad`, `tracing`, `anthropic` SDK |
| `frontmatter` utility | `yaml` stdlib, `pathlib` stdlib |
| `Extractor` | `Scratchpad`, FastMCP, `anthropic` SDK |
| `EvalAgent` | `Scratchpad`, `anthropic` SDK, vault filesystem (at init via `OBSIDIAN_VAULT_PATH`) |
| `models.py` | No internal imports (pure data types) |

No circular dependencies.

---

## Data Flow Diagram

```
.docx file
    |
    v
[Extractor.process()]
    |
    v
.md file (raw extracted text written to --output/)
    |
    v
[AnalysisAgent.analyze()]
    |
    +--> calls frontmatter.write_frontmatter()
    |
    v
.md file (YAML frontmatter prepended)
    |
    ---
    summary: "..."
    tags: [...]
    confidence: 0.9
    ---
    <original extracted text>
    |
    v
[ClassificationAgent.classify()]
    |
    +--> calls frontmatter.read_frontmatter()  ---> summary + tags
    |    (fallback: raw text excerpt if None)
    |
    +--> LLM call (LIGHT_MODEL)
    |
    +--> _move_to_vault()
    |
    v
vault/{category}/{filename}.md
```

---

## Key Decoupling Changes

### Before this iteration

```
classification.py
    VALID_CATEGORIES = frozenset({"Architecture", ...})    # hard-coded
    CATEGORY_DESCRIPTIONS = {...}                          # hard-coded

eval_agent.py
    from pipeline.classification import VALID_CATEGORIES   # tight coupling
    from pipeline.classification import CATEGORY_DESCRIPTIONS
```

### After this iteration

```
classification.py
    # No module-level constants
    ClassificationAgent.__init__() discovers categories from vault subfolders

eval_agent.py
    # No import from classification.py
    EvalAgent.__init__(vault_root) discovers categories from vault subfolders independently

frontmatter.py  (NEW)
    # Shared by AnalysisAgent and ClassificationAgent
    read_frontmatter(path) -> dict | None
    write_frontmatter(path, data) -> None
```

### Communication Pattern

All inter-agent communication happens via the filesystem (`.md` files).
No direct method calls between agents. Orchestration through `main.py` only.

```
main.py
  |-- instantiates --> AnalysisAgent
  |-- instantiates --> ClassificationAgent
  |-- instantiates --> Extractor
  |
  process_one():
    extractor  --[file write]--> md_path
    analyzer   --[file write]--> md_path (frontmatter prepend)
    classifier --[file move]-->  vault/{category}/
```

---

## Affected Files Summary

| File | Change |
|---|---|
| `src/pipeline/analysis.py` | NEW — AnalysisAgent |
| `src/pipeline/frontmatter.py` | NEW — shared frontmatter utility |
| `src/pipeline/models.py` | UPDATE — add `AnalysisResult` TypedDict |
| `src/pipeline/classification.py` | UPDATE — dynamic discovery, frontmatter context, remove VALID_CATEGORIES |
| `src/pipeline/main.py` | UPDATE — instantiate AnalysisAgent, call analyze() in process_one() |
| `src/eval/eval_agent.py` | UPDATE — accept vault_root, discover categories dynamically |
| `tests/unit/test_analysis.py` | NEW — AnalysisAgent unit tests |
| `tests/unit/test_frontmatter.py` | NEW — frontmatter utility tests |
| `tests/unit/test_classification.py` | UPDATE — frontmatter path + fallback path + dynamic discovery |
