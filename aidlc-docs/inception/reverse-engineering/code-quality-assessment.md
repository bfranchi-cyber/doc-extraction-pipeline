# Code Quality Assessment

## Test Coverage

- **Overall**: Good — pytest-cov enforces >=65% minimum; coverage spans `src/pipeline` and `src/eval`
- **Unit Tests**: 4 files covering Extractor, ClassificationAgent, Scratchpad, tracing module
- **Eval Tests**: 1 file covering EvalAgent
- **Property-Based Tests**: 1 file (Hypothesis) for extraction properties
- **Integration Tests**: Folder exists, no tests yet
- **Excluded from coverage**: `pipeline/main.py`, `eval/eval_main.py` (entry point boilerplate)

## Code Quality Indicators

- **Linting**: Not explicitly configured (no ruff/flake8/mypy in pyproject.toml), but code follows consistent style
- **Code Style**: Consistent — `from __future__ import annotations`, type hints throughout, docstrings on public methods
- **Documentation**: Good — all public classes and methods have docstrings; code is self-documenting
- **Async**: Fully async — `asyncio.AsyncAnthropic`, `asyncio.gather`, `asyncio.to_thread` for blocking I/O

## Technical Debt

- `eval_agent.py`: Span filtering logic is fragile — depends on Phoenix DataFrame schema that could change between Phoenix versions. The conditional logic for finding classify spans by index level name vs. column is complex.
- `models.py`: `EnrichedDocument` is defined but unused — retained from a dropped analysis stage.
- `extraction_server.py`: FastMCP server is wired up but not integrated into the main CLI — unclear if it's actively used or a parallel interface.
- No `mypy` or type-checker configured despite comprehensive type annotations.

## Patterns and Anti-patterns

- **Good Patterns**:
  - Fail-soft tracing: `setup_tracing()` returns bool; pipeline continues without tracing
  - Structured errors: `PipelineError` dataclass with `error_type`, `is_retriable`, `suggestion`
  - Agent pattern: LLM interaction fully encapsulated in `ClassificationAgent` / `EvalAgent`
  - Async-first: all I/O is async; blocking mammoth wrapped in `asyncio.to_thread`
  - OTEL span attributes follow consistent `eval.*` and `document.*` namespaces

- **Anti-patterns**:
  - `eval_agent.py` imports `phoenix as px` inside the method body rather than at module level (deliberate: allows the module to load even when Phoenix is not installed, but reduces clarity)
  - No retry logic for classification API errors (fail-fast design; intentional per requirements)
