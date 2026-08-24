# Component Inventory

## Application Packages

### `src/pipeline/`
- **Type**: Application package
- **Purpose**: Core .docx extraction and LLM classification pipeline

### `src/eval/`
- **Type**: Application package
- **Purpose**: AI-as-judge evaluation of classification quality via Phoenix telemetry

## Shared Utilities (within pipeline package)

| Module | Type | Purpose |
|---|---|---|
| `pipeline.tracing` | Shared utility | OTEL/Phoenix setup and tracer factory |
| `pipeline.scratchpad` | Shared utility | JSONL structured event logger |
| `pipeline.models` | Shared models | CompactArtifact, EnrichedDocument type definitions |
| `pipeline.exceptions` | Shared utility | PipelineError structured error type |

## Infrastructure Packages

None — local CLI only, no CDK, Terraform, or cloud resources.

## Test Packages

| Package | Type | Purpose |
|---|---|---|
| `tests/unit/` | Unit tests | Extraction, classification, scratchpad, tracing |
| `tests/eval/` | Eval tests | EvalAgent behavior |
| `tests/property/` | Property-based tests | Hypothesis-driven extraction properties |
| `tests/integration/` | Integration tests | Placeholder (no tests yet) |

## Entry Points (pyproject.toml scripts)

| Script | Module | Purpose |
|---|---|---|
| `docs-extraction` | `pipeline.main:main` | Run extraction + classification pipeline |
| `docs-extraction-eval` | `eval.eval_main:main` | Run AI-as-judge evaluation loop |

## Total Count
- **Total packages**: 2 (`pipeline`, `eval`)
- **Application modules**: 9 (main, extraction, extraction_server, classification, tracing, scratchpad, models, exceptions + eval_main, eval_agent)
- **Test files**: 6
- **Infrastructure**: 0
