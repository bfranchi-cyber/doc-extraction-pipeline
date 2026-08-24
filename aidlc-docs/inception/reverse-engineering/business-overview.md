# Business Overview

## Business Context Diagram

```
+-----------------------------------------------------------+
|                   docs-extraction System                  |
|                                                           |
|  [.docx files] --> [Extractor] --> [ClassificationAgent]  |
|                                         |                 |
|                                   [Obsidian Vault]        |
|                                                           |
|  [EvalAgent] <-- [Phoenix] <-- [OTEL Spans]               |
|       |                                                   |
|  [Anthropic Claude] (judge)                               |
+-----------------------------------------------------------+
```

## Business Description

- **Business Description**: A local CLI pipeline that converts `.docx` Word documents into Markdown files and automatically classifies them into domain-specific knowledge categories in an Obsidian vault. An evaluation subsystem uses AI-as-judge via Phoenix telemetry to measure classification quality.
- **Business Transactions**:
  1. **Document Extraction**: Scan a folder of `.docx` files, extract their text content, write `.md` files to an output directory (mirroring source structure).
  2. **Document Classification**: For each extracted `.md` file, use an LLM (Claude, LIGHT_MODEL) to categorise the document into one of: Architecture, CI&T, Cloud, Coding, ML & AI, or unknown. Move the file into the matching Obsidian vault subfolder.
  3. **Span Tracing**: All extract and classify operations emit OpenTelemetry spans to a local Phoenix server for observability and latency tracking.
  4. **Classification Evaluation**: Query Phoenix for recorded classify spans, have a second LLM (Claude, MEDIUM_MODEL) judge each classification as correct/incorrect, and write evaluation results back to Phoenix.
- **Business Dictionary**:
  - **Vault**: An Obsidian knowledge base folder with pre-existing category subfolders.
  - **Scratchpad**: A JSONL log file written alongside output files; captures INFO/WARN/ERROR events.
  - **Span**: An OpenTelemetry trace unit capturing a single classify or extract operation, its attributes, and latency.
  - **Eval / Judge**: The AI-as-judge process that retroactively assesses classification correctness.
  - **LIGHT_MODEL / MEDIUM_MODEL**: Environment variables controlling which Claude model is used for classification vs. evaluation respectively.

## Component Level Business Descriptions

### pipeline (src/pipeline/)
- **Purpose**: Core document processing — extract text from Word files and classify documents into Obsidian vault categories.
- **Responsibilities**: CLI entry point, extraction, classification, structured error handling, JSONL logging, OTEL span emission.

### eval (src/eval/)
- **Purpose**: Evaluate the quality of past classification decisions using AI-as-judge against Phoenix telemetry data.
- **Responsibilities**: Connect to Phoenix, fetch classify spans, invoke Claude to judge each classification, write evaluation labels back to Phoenix.
