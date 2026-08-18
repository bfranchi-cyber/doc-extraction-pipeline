# Technology Stack

## Programming Languages
- Python 3.11+ — primary and only language

## Frameworks / Libraries
- `anthropic[mcp] >=0.25` — Anthropic Python SDK (LLM API client + MCP extras)
- `mcp >=1.8,<2.0` — Model Context Protocol SDK (`FastMCP` server)
- `mammoth >=1.6` — DOCX to plain text converter

## Infrastructure
- Local filesystem only — no cloud services, no databases

## Build Tools
- `setuptools >=68` — build backend
- `uv` — fast Python package manager and project tool (replaces pip+venv)
- `pyproject.toml` — PEP 517/518 project configuration

## Testing Tools
- `pytest >=7.0` — test runner
- `pytest-cov >=4.0` — coverage reporting (threshold: 65%)
- `hypothesis >=6.0` — property-based testing

## Environment Variables (runtime)
| Variable | Required | Purpose |
|---|---|---|
| `LIGHT_MODEL` | Yes | Claude model ID for classification (e.g., `claude-haiku-4-5-20251001`) |
| `MEDIUM_MODEL` | No | Reserved for future Sonnet-class agents |
| `HEAVY_MODEL` | No | Reserved for future Opus-class agents |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API authentication |
| `ANTHROPIC_BASE_URL` | No | Proxy URL override (defaults to Anthropic SDK default) |
| `OBSIDIAN_VAULT_PATH` | No | Root path of Obsidian vault; classification is skipped if unset |
