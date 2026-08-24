# Code Generation Plan — Analysis + Classify Refactor

## Unit
**Name**: analysis-classify-refactor  
**Iteration**: 2026-08-21  
**Type**: Brownfield — modify existing files + create new files

## Context Summary

| What | Detail |
|---|---|
| New files | `analysis.py`, `frontmatter.py`, `test_analysis.py`, `test_frontmatter.py`, `test_frontmatter_pbt.py`, `code-summary.md` |
| Modified files | `models.py`, `classification.py`, `main.py`, `eval_agent.py`, `eval_main.py`, `test_classification.py`, `test_eval_agent.py` |
| Design refs | `application-design/application-design.md`, `application-design/component-methods.md` |
| Requirements refs | `FR-1` (AnalysisAgent), `FR-2` (classify frontmatter context), `FR-3` (dynamic categories), `FR-4` (orchestration) |
| Extension: PBT | Partial — `test_frontmatter_pbt.py` covers YAML serialization round-trips |

## Plan Checkboxes

- [x] Step 1 — Update `src/pipeline/models.py`: add `AnalysisResult` TypedDict
- [x] Step 2 — Create `src/pipeline/frontmatter.py`: `read_frontmatter`, `write_frontmatter`
- [x] Step 3 — Create `src/pipeline/analysis.py`: `AnalysisAgent` class
- [x] Step 4 — Update `src/pipeline/classification.py`: dynamic discovery + frontmatter context
- [x] Step 5 — Update `src/pipeline/main.py`: instantiate `AnalysisAgent`, call `analyze()`
- [x] Step 6 — Update `src/eval/eval_agent.py`: accept `vault_root`, discover categories dynamically
- [x] Step 7 — Update `src/eval/eval_main.py`: pass `vault_root` to `EvalAgent()`
- [x] Step 8 — Create `tests/unit/test_analysis.py`: AnalysisAgent unit tests
- [x] Step 9 — Create `tests/unit/test_frontmatter.py`: frontmatter utility unit tests
- [x] Step 10 — Update `tests/unit/test_classification.py`: frontmatter + dynamic discovery tests
- [x] Step 11 — Update `tests/eval/test_eval_agent.py`: vault_root parameter tests
- [x] Step 12 — Create `tests/property/test_frontmatter_pbt.py`: PBT YAML round-trips
- [x] Step 13 — Create `aidlc-docs/construction/analysis-classify-refactor/code/code-summary.md`

---

## Step Details

### Step 1 — Update `src/pipeline/models.py`
Add new `AnalysisResult` TypedDict below the existing `CompactArtifact`:

```python
class AnalysisResult(TypedDict):
    summary: str
    tags: list[str]     # 3-5 strings, enforced by tool-use schema
    confidence: float   # 0.0 – 1.0
```

Keep `CompactArtifact` and `EnrichedDocument` unchanged.

---

### Step 2 — Create `src/pipeline/frontmatter.py`

New file. Provides two public functions:

**`read_frontmatter(md_path: Path) -> dict | None`**
- Read file at `md_path` (UTF-8)
- If content starts with `---\n`: find closing `---` line; parse inner YAML with `yaml.safe_load()`
- Return parsed dict on success; `None` if no frontmatter block present
- Does not raise; absence of frontmatter is not an error

**`write_frontmatter(md_path: Path, data: dict) -> None`**
- Read existing file content (UTF-8)
- Serialize `data` with `yaml.dump(data, allow_unicode=True, default_flow_style=False)`
- Prepend `---\n{yaml_text}---\n\n` to existing content
- Write result back to file (UTF-8)

Imports: `from __future__ import annotations`, `from pathlib import Path`, `import yaml`

---

### Step 3 — Create `src/pipeline/analysis.py`

New file. `AnalysisAgent` class:

**`__init__(scratchpad: Scratchpad) -> None`**
- `self._client = anthropic.AsyncAnthropic()`
- `self._model = os.environ["MEDIUM_MODEL"]` (KeyError at startup if unset)
- `self._scratchpad = scratchpad`

**`async analyze(md_path: Path) -> AnalysisResult | None`**
- Read file text from `md_path`
- Define tool schema:
  ```python
  ANALYSIS_TOOL = {
      "name": "record_analysis",
      "description": "Record the document analysis result.",
      "input_schema": {
          "type": "object",
          "properties": {
              "summary": {"type": "string", "description": "Concise 1-2 sentence summary"},
              "tags": {
                  "type": "array",
                  "items": {"type": "string"},
                  "minItems": 3,
                  "maxItems": 5,
                  "description": "3-5 relevant keyword tags"
              },
              "confidence": {
                  "type": "number",
                  "minimum": 0.0,
                  "maximum": 1.0,
                  "description": "Confidence in the analysis (0.0-1.0)"
              }
          },
          "required": ["summary", "tags", "confidence"]
      }
  }
  ```
- Call with `tool_choice={"type": "tool", "name": "record_analysis"}` to force tool use
- `api_error = False`; wrap in try/except; on exception: `api_error = True`, log scratchpad error, return `None`
- On success: extract `response.content[0].input` as `AnalysisResult`
- Call `write_frontmatter(md_path, result)`
- Emit span `"analyze"` with:
  - `document.name` = `md_path.name`
  - `eval.latency_ms` = elapsed ms
  - `eval.api_error` = bool
  - `eval.confidence` = result["confidence"] (or 0.0 on error)
- Return `AnalysisResult` on success, `None` on failure

Imports: `from __future__ import annotations`, `import os`, `import time`, `from pathlib import Path`, `import anthropic`, `from pipeline.frontmatter import write_frontmatter`, `from pipeline.models import AnalysisResult`, `from pipeline.scratchpad import Scratchpad`, `from pipeline.tracing import get_tracer`

---

### Step 4 — Update `src/pipeline/classification.py`

**Remove**:
- `VALID_CATEGORIES` frozenset (module-level constant)
- `CATEGORY_DESCRIPTIONS` dict (module-level constant)
- `_all_names`, `_category_lines`, `_SYSTEM_PROMPT` module-level variables
- `_UNKNOWN = "unknown"` — keep this local to methods or as private module-level

**Add to `__init__`**:
```python
self._valid_categories = self._discover_categories()
self._system_prompt = self._build_system_prompt()
```

**Add `_discover_categories(self) -> frozenset[str]`**:
- `dirs = [p.name for p in self._vault_root.iterdir() if p.is_dir()]`
- If empty: log scratchpad warning; return `frozenset()`
- Return `frozenset(dirs)`

**Add `_build_system_prompt(self) -> str`**:
- Build prompt dynamically from `self._valid_categories`
- Include `"unknown"` as an option
- Format: `You are a document classifier...` with all category names + unknown

**Update `classify()`**:
- After span setup and before building `user_message`:
  ```python
  from pipeline.frontmatter import read_frontmatter
  fm = read_frontmatter(md_path)
  if fm:
      summary = fm.get("summary", "")
      tags = ", ".join(fm.get("tags") or [])
      user_message = f"Filename: {md_path.stem}\n\nSummary: {summary}\nTags: {tags}"
  else:
      content = md_path.read_text(encoding="utf-8").strip()
      user_message = f"Filename: {md_path.stem}\n\n{content[:500]}"
  ```
- Use `self._system_prompt` instead of module-level `_SYSTEM_PROMPT`
- Validation: use `self._valid_categories` instead of `VALID_CATEGORIES`
- Keep `_UNKNOWN = "unknown"` check unchanged

**Add import** at top: `from pipeline.frontmatter import read_frontmatter`

---

### Step 5 — Update `src/pipeline/main.py`

**Add import**:
```python
from pipeline.analysis import AnalysisAgent
```

**In `main()`**, after `extractor = Extractor(scratchpad)`:
```python
analyzer = AnalysisAgent(scratchpad)
```

**In `process_one()`**, after `output_path.write_text(...)`:
```python
await analyzer.analyze(output_path)
```

The `process_one` function uses `analyzer` from the enclosing `main()` scope (closure), same pattern as `extractor` and `classifier`.

---

### Step 6 — Update `src/eval/eval_agent.py`

**Remove**:
```python
from pipeline.classification import CATEGORY_DESCRIPTIONS, VALID_CATEGORIES
```

**Update `__init__`**:
```python
def __init__(self, vault_root: Path | None = None) -> None:
    self._model = os.environ["MEDIUM_MODEL"]
    self._phoenix_host = os.environ.get("PHOENIX_HOST", "localhost:6006")
    self._client = anthropic.AsyncAnthropic()
    self._categories: list[str] = []
    if vault_root is not None:
        self._categories = [p.name for p in vault_root.iterdir() if p.is_dir()]
```

**Add import**: `from pathlib import Path`

**Update `_judge_span()`**: replace the `CATEGORY_DESCRIPTIONS`/`VALID_CATEGORIES` section:
```python
if self._categories:
    valid_names = ", ".join(sorted(self._categories))
    category_section = f"\nValid categories: {valid_names}\n"
else:
    category_section = ""

judge_prompt = (
    f"You are evaluating a document classification.\n\n"
    f"Document: {document_name}\n"
    f"Excerpt: {str(input_value)[:500]}\n"
    f"Predicted category: {category}\n"
    f"{category_section}"
    f"\nIs the predicted category correct for this document?\n"
    f"Respond with ONLY 'correct' or 'incorrect'."
)
```

---

### Step 7 — Update `src/eval/eval_main.py`

Add vault_root resolution and pass it to `EvalAgent`:

```python
import os
from pathlib import Path

vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
vault_root = Path(vault_path) if vault_path else None
agent = EvalAgent(vault_root=vault_root)
```

Remove existing bare `EvalAgent()` instantiation.

---

### Step 8 — Create `tests/unit/test_analysis.py`

New file. Test class `TestAnalysisAgent`:

- `test_analyze_success_writes_frontmatter`: mock Anthropic tool-use response with `{summary, tags, confidence}`; assert `write_frontmatter` is called; assert returned `AnalysisResult` has correct values
- `test_analyze_api_error_returns_none`: mock LLM call raises exception; assert returns `None`; assert file has no frontmatter written
- `test_analyze_returns_none_leaves_file_unchanged`: on failure path, file content must be unchanged

Fixture: `MEDIUM_MODEL` env var patched to `"test-model"`.
All LLM calls mocked via `AsyncMock`.
Use `tmp_path` for temp `.md` files.

---

### Step 9 — Create `tests/unit/test_frontmatter.py`

New file. Tests for `read_frontmatter` and `write_frontmatter`:

- `test_write_then_read_round_trip`: write frontmatter to file, read it back, assert values match
- `test_read_returns_none_when_no_frontmatter`: file with no `---` block; assert returns `None`
- `test_write_prepends_to_existing_content`: existing text preserved after frontmatter block
- `test_read_file_with_only_frontmatter`: edge case — file is only YAML block
- `test_write_unicode_values`: tags with non-ASCII characters round-trip correctly

---

### Step 10 — Update `tests/unit/test_classification.py`

**Key changes**:

1. **Remove** `from pipeline.classification import VALID_CATEGORIES`
2. **Add** local constant:
   ```python
   _TEST_CATEGORIES = frozenset({"Architecture", "Cloud", "Coding"})
   ```
3. **Update `vault_root` fixture**: create dirs from `_TEST_CATEGORIES` instead of `VALID_CATEGORIES`
4. **Update `_make_agent`**: after instantiation, agent will call `_discover_categories()` — since vault dirs exist, discovery returns `_TEST_CATEGORIES`
5. **Add new test class `TestClassificationAgentFrontmatter`**:
   - `test_classify_uses_frontmatter_when_present`: create `.md` with valid frontmatter `{summary, tags}`; assert LLM prompt contains summary (verify by capturing `create` call kwargs)
   - `test_classify_falls_back_to_raw_text_when_no_frontmatter`: no frontmatter; assert LLM called with raw text excerpt
6. **Update PBT class `TestClassificationAgentPBT`**:
   - Use `_TEST_CATEGORIES` instead of `VALID_CATEGORIES` in `st.sampled_from` and filter
7. **Update `test_missing_vault_folder_leaves_file_in_place`**: vault_root is empty → `_discover_categories()` returns empty set → all responses are "not in valid categories" → returns False. Adjust test to not need to mock LLM (or mock it returning any string).

---

### Step 11 — Update `tests/eval/test_eval_agent.py`

**Update `agent` fixture**:
- Create a temp vault directory with subdirs `["Coding", "Cloud", "Architecture"]`
- Pass `vault_root=vault_dir` to `EvalAgent()`

**Update `test_judge_span_correct` and `test_judge_span_incorrect`**: no functional change needed — just ensure the new `vault_root` kwarg is in the fixture.

**Update `test_run_evals_no_spans`**: same — fixture update propagates.

---

### Step 12 — Create `tests/property/test_frontmatter_pbt.py`

New file. PBT for YAML serialization round-trips (PBT scope: YAML frontmatter serialization/deserialization).

```python
@given(
    summary=st.text(min_size=1, max_size=200),
    tags=st.lists(st.text(min_size=1, max_size=30), min_size=3, max_size=5),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_frontmatter_round_trip(tmp_path, summary, tags, confidence):
    """write_frontmatter then read_frontmatter always returns the same data."""
    md_file = tmp_path / "doc.md"
    md_file.write_text("original content", encoding="utf-8")
    data = {"summary": summary, "tags": tags, "confidence": confidence}
    write_frontmatter(md_file, data)
    result = read_frontmatter(md_file)
    assert result is not None
    assert result["summary"] == summary
    assert result["tags"] == tags
    assert abs(result["confidence"] - confidence) < 1e-9

@given(content=st.text())
def test_read_frontmatter_on_arbitrary_text_never_raises(tmp_path, content):
    """read_frontmatter must never raise regardless of file content."""
    md_file = tmp_path / "arbitrary.md"
    md_file.write_text(content, encoding="utf-8")
    result = read_frontmatter(md_file)
    assert result is None or isinstance(result, dict)
```

---

### Step 13 — Create `aidlc-docs/construction/analysis-classify-refactor/code/code-summary.md`

Markdown summary documenting all created/modified files with brief descriptions.

---

## Dependency Order

Steps must be executed in order — later steps depend on earlier ones:

```
Step 1 (models.py)
    → Step 2 (frontmatter.py)
        → Step 3 (analysis.py)          [imports frontmatter, models]
        → Step 4 (classification.py)    [imports frontmatter]
    → Step 5 (main.py)                  [imports analysis]
    → Step 6 (eval_agent.py)            [no pipeline imports]
    → Step 7 (eval_main.py)             [imports eval_agent]
Steps 8-12 (tests) — after their implementation target
Step 13 (summary) — last
```
