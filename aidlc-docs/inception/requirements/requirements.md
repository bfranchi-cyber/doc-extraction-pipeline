# Requirements Document — Extraction Pipeline

## Intent Analysis Summary

- **User Request**: Build an agentic document extraction pipeline that monitors Google Drive, converts .docx/.pdf files to enriched Markdown, and writes them into a local Obsidian vault.
- **Request Type**: New Project (Greenfield)
- **Scope**: System-wide — multi-agent pipeline spanning Google Drive integration, parallel extraction, AI-powered analysis, and local file export
- **Complexity**: Complex — async multi-agent orchestration, prompt chaining pipeline with inter-phase Coordinator handoffs, stateful manifest tracking, image handling, Windows scheduled service

---

## Functional Requirements

### FR-01: Trigger & Scheduling
- The pipeline runs as a **Windows background service / scheduled task** (Windows Task Scheduler).
- On each run, it queries Google Drive for files that have not been modified for **exactly 5 days** from their last modification timestamp (i.e., eligible files satisfy `now - last_modified >= 5 days`).
- There is no separate webhook integration — the 5-day delay is enforced by the scheduler itself (schedule = `last_modified + 5 days` for each eligible file discovered).
- Scheduling is driven by a polling loop: the service wakes up periodically, checks Drive for newly eligible files, and queues them for processing.

### FR-02: Google Drive Authentication
- Authentication uses **OAuth 2.0** with a local credentials JSON file.
- The user authenticates once interactively; the token is persisted locally and refreshed automatically on subsequent runs.
- Uses the **Google Drive MCP** integration for Drive API calls.

### FR-03: Supported Input Formats
- `.docx` (Word documents)
- `.pdf` (PDF documents)
- All other file types are skipped silently.

### FR-04: Prompt Chaining Pipeline with Coordinator Handoffs
- The pipeline is a **fixed prompt chaining sequence**: Ingestion → Extraction → Analysis → Export. Each stage is a discrete agent step whose output feeds directly into the next as a structured prompt input.
- A **Coordinator Agent** acts as the hub between phases, responsible for structured and complete handoffs: it receives each stage's output, validates it, updates the scratchpad, and constructs the input prompt for the next stage.
- This is not a pure hub-and-spoke — the Coordinator does not re-dispatch work to arbitrary spokes. It orchestrates a linear chain with explicit handoff contracts between each link.
- The Coordinator maintains a **scratchpad log** of pipeline status, agent decisions, and errors throughout the entire run.

### FR-05: Ingestion Stage
- The Ingestion component queries Google Drive for files eligible under the 5-day rule.
- Files already recorded in the state manifest as successfully processed are skipped.
- Eligible file metadata (ID, name, MIME type, last modified timestamp) is passed to the Coordinator.

### FR-06: Extraction Stage (Parallel)
- Multiple Extraction agents run **concurrently via Python asyncio**, each processing one document.
- Uses **Claude Haiku 4.5** as the extraction model.
- For each document:
  - Extracts all text content into a **compact artifact** (structured intermediate representation for token-efficient handoff).
  - **Classifies the document into a category** by selecting the best fit from the **pre-defined categories that already exist in the Obsidian vault** — the agent does not invent new categories. This classification task is intentionally assigned to the extraction agent (cheaper/faster model).
  - **Image handling**: images are **not** included in the compact artifact in any form. During extraction, images are downloaded to a **local temporary staging folder** on disk. The compact artifact carries only lightweight metadata per image (image ID + alt-text string). Raw image data and base64 strings **never reach any LLM**.

### FR-07: Analysis Stage
- A single **Analysis Agent** uses **Claude Sonnet 4.5**.
- Receives the compact artifact from the extraction stage.
- Produces the final Markdown document with:
  - Formatted text (preserving semantic content, enhancing readability)
  - Citations and references properly formatted
  - **YAML frontmatter block** at the top (title, date, auto-generated tags)
  - **Short abstract/summary section** at the top of the document body
- Does **not** alter semantic content — enhancement only.

### FR-08: Export Stage
- Writes the final `.md` file to: `C:\Users\bfranchi\Documents\Obsidian Vault\{category}\{filename}.md`
  - `{category}` is the category selected by the Extraction Agent from the pre-existing vault folder structure.
  - Category folders already exist in the vault; the pipeline writes into them but does not create new category directories.
- Moves extracted images from the temporary staging folder to: `C:\Users\bfranchi\Documents\Obsidian Images\{document-name}\`
- Injects **absolute local file URIs** into the Markdown for images: `![Alt Text](file:///C:/Users/bfranchi/Documents/Obsidian Images/{document-name}/{image-file})`

### FR-09: State Manifest
- A **JSON manifest file** is maintained locally, recording:
  - Google Drive file ID
  - File name
  - Last-processed timestamp
  - Processing status (success / failed)
- On each run, the manifest is consulted to skip already-successfully-processed files.
- Failed files are retried on the next run.

### FR-10: Error Handling
- **Rate limits (Google Drive API)**: Wait the required retry-after time as specified by the API response before retrying — follow Anthropic SDK and Google API error handling guidelines.
- **Rate limits (Claude API)**: Follow Anthropic SDK guidelines (respect `retry-after` headers, exponential backoff as directed by the SDK).
- **Corrupted or unreadable files**: The Extraction Agent passes the corruption information to the Coordinator Agent, which handles it gracefully — logs the issue to the scratchpad, marks the file as failed in the manifest, and continues pipeline execution without halting.
- **Scratchpad logging**: The Coordinator maintains a human-readable scratchpad log of all pipeline events, decisions, and errors for observability.

### FR-11: Semantic Preservation
- The pipeline must not alter the semantic content of documents. 
- Enhancement is limited to: formatting, citations, frontmatter generation, and abstract writing.

---

## Non-Functional Requirements

### NFR-01: Token Efficiency
- Raw image data and base64 strings must **never** be included in any LLM prompt.
- Only lightweight image metadata (ID + alt-text) is passed through the compact artifact.
- Model selection reflects cost/capability tradeoff: Haiku 4.5 for extraction/classification, Sonnet 4.5 for analysis.

### NFR-02: Concurrency
- Extraction runs in parallel using **Python `asyncio`** with async HTTP calls to the Claude API.
- The Coordinator manages concurrency to avoid overwhelming the Claude API rate limits.

### NFR-03: Platform
- Runs on **Windows 11**.
- Deployed as a **Windows Task Scheduler** task (background service pattern).
- No Docker or containerization required.

### NFR-04: Idempotency
- The manifest-based state tracking ensures that successfully processed files are never re-extracted on subsequent runs.
- Re-running the pipeline is safe at any time.

### NFR-05: Vault Organization
- Output vault: `C:\Users\bfranchi\Documents\Obsidian Vault\`
- Organization: category subfolders assigned by the Extraction Agent.
- Images folder: `C:\Users\bfranchi\Documents\Obsidian Images\`

### NFR-06: Scratchpad Observability
- The Coordinator Agent maintains a scratchpad (text log) tracking pipeline status, agent decisions, and errors for human review.

### NFR-07: Property-Based Testing (Partial Enforcement)
- **Hypothesis** (Python PBT framework) is used for property-based tests.
- Enforcement scope: PBT-02 (round-trip), PBT-03 (invariants), PBT-07 (generator quality), PBT-08 (shrinking & reproducibility), PBT-09 (framework selection).
- All other PBT rules are advisory only.
- PBT complements (does not replace) example-based tests.

---

## Architecture Overview

```
Google Drive
     |
     | (OAuth 2.0 / Drive MCP)
     v
+-------------------------+
|   Ingestion Agent       |  queries Drive, checks manifest
+-------------------------+
     |
     | eligible file list
     v
+-------------------------+     scratchpad + handoff validation
|   Coordinator Agent     | <--------------------------------+
+-------------------------+                                  |
     |                                                       |
     | dispatches per-file                                   |
     v                                                       |
+-------------------------+                                  |
|  Extraction Agents      |  (parallel, asyncio, Haiku 4.5) |
|  - text -> compact      |                                  |
|  - classify category    |  (picks from existing vault      |
|  - image -> staging     |   folders, no raw data to LLM)  |
+-------------------------+                                  |
     |                                                       |
     | compact artifact (text + image metadata only)         |
     v                                                       |
+-------------------------+                                  |
|  Coordinator Agent      | -- validates, builds next prompt-+
+-------------------------+
     |
     v
+-------------------------+
|  Analysis Agent         |  (Sonnet 4.5)
|  - formatting           |
|  - citations            |
|  - YAML frontmatter     |
|  - abstract             |
+-------------------------+
     |
     | enriched Markdown
     v
+-------------------------+
|  Coordinator Agent      | -- validates, builds export handoff
+-------------------------+
     |
     v
+-------------------------+
|  Export                 |
|  - write .md to vault   |
|  - move images to folder|
|  - update manifest      |
+-------------------------+
```

**Key pattern**: The pipeline is a fixed linear prompt chain. The Coordinator Agent sits at each junction, performs structured handoff validation, updates the scratchpad, and constructs the prompt for the next stage. It does not fan out to arbitrary agents — it enforces an ordered sequence.

---

## Key Decisions & Constraints

| Decision | Choice | Rationale |
|---|---|---|
| Trigger | Scheduled polling (modification + 5 days) | Enforces 5-day rule; no webhook complexity |
| Auth | OAuth 2.0 local credentials | Simple single-user setup |
| Input formats | .docx, .pdf | As specified; other formats skipped |
| Extraction model | Claude Haiku 4.5 | Low cost, fast, sufficient for extraction + classification |
| Analysis model | Claude Sonnet 4.5 | Higher capability for formatting/enrichment |
| Concurrency | Python asyncio | Efficient async I/O for Claude API calls |
| Image handling | Staging folder → Images folder, metadata only to LLM | Token efficiency |
| Vault organization | Pre-existing category subfolders; Extraction Agent picks best fit | Categories defined by user in vault; cheap model does classification |
| State tracking | JSON manifest | Simple, reliable idempotency |
| Deployment | Windows Task Scheduler | Native Windows, no extra dependencies |
| Security extension | Disabled | PoC/personal tool |
| Resiliency extension | Disabled | Personal tool, not production-critical |
| PBT enforcement | Partial (PBT-02, 03, 07, 08, 09) | Data transformation pipeline benefits from round-trip and invariant testing |
