# Requirements — Classification Agent

## Intent Analysis

| Field | Value |
|---|---|
| **User Request** | Add a classification agent that uses Claude Haiku 4.5 to classify extracted .md files into Obsidian vault categories and move them to the matching folder. Also rename ExtractionAgent to Extractor. |
| **Request Type** | New Feature + Refactoring |
| **Scope Estimate** | Multiple Components |
| **Complexity Estimate** | Moderate |

---

## Functional Requirements

### FR-01: Rename ExtractionAgent → Extractor
- `ExtractionAgent` in `src/pipeline/extraction.py` is renamed to `Extractor`
- All references updated: `main.py`, `extraction_server.py`, any tests
- No behaviour change — pure rename

### FR-02: ClassificationAgent
- New class `ClassificationAgent` in `src/pipeline/classification.py`
- Uses the **Anthropic SDK** with a **corporate proxy**
- Model name read from env var **`LIGHT_MODEL`** at runtime (Haiku variant)
- Proxy URL sourced automatically from **`ANTHROPIC_BASE_URL`** (SDK standard) and API key from **`ANTHROPIC_API_KEY`** — no custom client wiring needed
- Reads the Obsidian vault root path from env var `OBSIDIAN_VAULT_PATH`
- Accepts a `.md` file path as input

### FR-03: Classification Logic
- Sends the **file name + first 500 characters** of the .md file content to the model
- Claude must classify the document into exactly one of:
  - `Architecture`
  - `CI&T`
  - `Cloud`
  - `Coding`
  - `ML&AI`
- Classification is performed via the Anthropic tool-use API: the model calls a `move_to_vault` tool with the chosen category

### FR-04: move_to_vault Tool
- Tool name: `move_to_vault`
- Input: `category` (string, one of the five valid categories)
- Behaviour: moves the .md file from the output folder to `<OBSIDIAN_VAULT_PATH>/<category>/`
- Creates the destination folder if it does not exist

### FR-05: Unclassifiable Files
- If Claude Haiku does not call `move_to_vault` (low confidence or error), the file is **left in the output folder**
- A `WARN`-level entry is written to the Scratchpad log

### FR-06: Pipeline Integration
- Classification runs automatically after each file is extracted (integrated into `main.py`)
- Flow per document: `.docx` → extract to `.md` in output folder → classify → move to vault
- If extraction fails, classification is skipped for that file

### FR-07: Missing Vault Path
- If `OBSIDIAN_VAULT_PATH` is not set, log a `WARN` via Scratchpad and skip classification for all files (extraction still completes normally)

---

## Non-Functional Requirements

### NFR-01: Model
- Model name sourced from `LIGHT_MODEL` env var — lightweight, low latency, low cost
- No model name hardcoded in source code
- Three-tier naming convention in project: `LIGHT_MODEL` (Haiku), `MEDIUM_MODEL` (Sonnet), `HEAVY_MODEL` (Opus)

### NFR-02: Token Efficiency
- Only first 500 characters of the document are sent to the model

### NFR-03: Vault Path Configuration
- Vault root path sourced exclusively from `OBSIDIAN_VAULT_PATH` environment variable

### NFR-04: Error Isolation
- A classification failure must never prevent the next file from being processed
- Extraction output is preserved on classification failure

### NFR-05: Testability
- `ClassificationAgent` must be testable with a mock Anthropic client
- PBT rules PBT-02, PBT-07, PBT-08 apply (existing project configuration)

---

## Out of Scope

- PDF, Google Drive, or any non-.docx input formats
- Re-classification of already-moved files
- Batch undo / rollback of moves
- GUI or web interface
