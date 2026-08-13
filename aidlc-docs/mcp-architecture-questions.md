# MCP Architecture Questions

You want to use MCPs with the `anthropic` SDK's tool use feature in `ExtractionAgent`.

I need to understand the architecture before updating the code generation plan,
because the answer changes what code is generated significantly.

---

## Background: What the Anthropic MCP connector supports

The `client.beta.messages.create(mcp_servers=[...], betas=["mcp-client-2025-11-20"])` API:
- Connects Claude to **remote HTTPS MCP servers** (Streamable HTTP or SSE transport only)
- Servers must be **publicly reachable via URL** — local stdio servers are NOT supported by this path
- Claude calls tools from those servers as part of its response

The `anthropic[mcp]` client-side helpers (`from anthropic.lib.tools.mcp import async_mcp_tool`):
- Work with **local stdio MCP servers** (subprocess-based)
- Use `client.beta.messages.tool_runner(...)` which handles the tool-call loop automatically
- Require the `mcp` extra: `pip install "anthropic[mcp]"`

---

## Question 1
What role do you see MCP servers playing in the Extraction pipeline?

A) The **document parsing** step (pdf/docx → text) is exposed as an MCP tool — Claude calls a
   tool like `parse_document(path, mime_type)` instead of the agent calling the parser directly

B) The **extract and classify** step is restructured as MCP tools — e.g. `extract_text(raw_text)`,
   `classify_document(text, categories)` — so Claude dispatches these as tool calls

C) The **entire** extraction pipeline is wrapped as a set of MCP tools that Claude orchestrates
   (parse, classify, stage_images all become tools Claude calls in sequence)

D) MCP servers are used to connect external services to Claude — e.g. the Google Drive image
   download is exposed as an MCP tool that Claude can call

E) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 2
Where will the MCP server(s) run?

A) Locally in the same process / machine as the pipeline (stdio transport via `anthropic[mcp]` helpers)

B) As a remote HTTPS service (the MCP connector beta `mcp-client-2025-11-20`)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 3
The current `ExtractionAgent._extract_and_classify()` makes a single `messages.create` call
and Claude returns JSON `{"extracted_text": "...", "category": "..."}`.
With MCP/tool use, the model would instead dispatch tool calls. What is your preferred shape?

A) Keep the single-call JSON response approach — just switch to `client.beta.messages.create`
   with `betas=["mcp-client-2025-11-20"]` to stay consistent with the new SDK path, even if
   no MCP tools are actually called for this agent today

B) Restructure so Claude dispatches `extract_text` and `classify_document` as separate tool calls,
   and the agent collects the tool results to build the `CompactArtifact`

C) Use `client.beta.messages.tool_runner(...)` — let the SDK handle the tool-call loop automatically,
   with custom tools defined via `@tool` decorator or equivalent

D) Other (please describe after [Answer]: tag below)

[Answer]: C
