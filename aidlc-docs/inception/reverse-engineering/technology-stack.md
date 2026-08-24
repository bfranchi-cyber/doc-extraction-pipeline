# Technology Stack

## Programming Languages
- **Python** — >=3.11 — All application code and tests

## Frameworks & Libraries

### Core
| Library | Version | Purpose |
|---|---|---|
| anthropic | >=0.25 | Claude LLM API (AsyncAnthropic client) |
| mammoth | >=1.6 | .docx → plain text extraction |
| mcp | >=1.8,<2.0 | MCP server framework (FastMCP) |

### Observability / Tracing
| Library | Version | Purpose |
|---|---|---|
| arize-phoenix | >=4.0 | Local Phoenix OTEL collector + UI + px.Client |
| arize-phoenix-otel | >=0.6 | Phoenix OTEL provider registration |
| openinference-instrumentation-anthropic | >=0.1 | Auto-instrument Anthropic SDK as OTEL spans |
| opentelemetry | (transitive) | OTEL SDK — trace.get_tracer, span API |

## Build Tools
| Tool | Version | Purpose |
|---|---|---|
| setuptools | >=68 | Build backend |
| pip | — | Package installation |

## Testing Tools
| Tool | Version | Purpose |
|---|---|---|
| pytest | >=7.0 | Test runner |
| pytest-asyncio | >=0.23 | Async test support (asyncio_mode = auto) |
| pytest-cov | >=4.0 | Coverage reporting |
| hypothesis | >=6.0 | Property-based testing |

## Environment Variables (runtime)
| Variable | Required | Purpose |
|---|---|---|
| ANTHROPIC_API_KEY | Yes | Anthropic API authentication |
| LIGHT_MODEL | Yes | Claude model for classification (e.g. claude-haiku-4-5-20251001) |
| MEDIUM_MODEL | Yes | Claude model for eval judging |
| OBSIDIAN_VAULT_PATH | No | Path to vault; classification skipped if absent |
| PHOENIX_HOST | No | Phoenix host:port (default: localhost:6006) |
| ANTHROPIC_BASE_URL | No | Proxy override for Anthropic SDK |
