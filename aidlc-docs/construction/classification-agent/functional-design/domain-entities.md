# Domain Entities — Classification Agent

## Entities

### ClassificationAgent
Primary orchestrator for the classification stage.

| Attribute | Type | Description |
|---|---|---|
| `_client` | `anthropic.Anthropic` | SDK client (reads ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL from env) |
| `_model` | `str` | Value of `LIGHT_MODEL` env var |
| `_vault_root` | `Path` | Resolved `OBSIDIAN_VAULT_PATH` |
| `_scratchpad` | `Scratchpad` | Shared logger |

| Method | Signature | Description |
|---|---|---|
| `classify` | `async (md_path: Path) -> bool` | Classifies one file; returns True if moved, False if not |

---

### VaultCategory (Enum)
Represents the five valid Obsidian vault folders plus the unclassifiable sentinel.

| Member | Value | Description |
|---|---|---|
| `ARCHITECTURE` | `"Architecture"` | Software/system architecture |
| `CI_T` | `"CI&T"` | Corporate knowledge and methodology |
| `CLOUD` | `"Cloud"` | Cloud computing and infrastructure |
| `CODING` | `"Coding"` | Programming and software development |
| `ML_AI` | `"ML&AI"` | Machine learning and AI |
| `UNKNOWN` | `"unknown"` | Sentinel — unclassifiable; never maps to a folder |

Used in the `move_to_vault` tool schema enum to validate the model's output. `UNKNOWN` is a programmatic gate: when returned, the code logs a WARN and skips the move — no folder named `unknown` is ever created.

---

### move_to_vault (Python Function)
A plain Python function called by the code in Step 2 — **not** an Anthropic tool schema. No API call is made in Step 2.

```
def move_to_vault(md_file_path: Path, vault_root: Path, category: str) -> bool

Inputs:
  md_file_path  Path   the .md file in the output folder
  vault_root    Path   resolved OBSIDIAN_VAULT_PATH
  category      str    one of the five valid categories (never "unknown" — filtered before call)

Returns:
  True   file moved successfully
  False  destination folder missing; WARN logged; file left in place
```

---

### Extractor (renamed from ExtractionAgent)
Unchanged in behaviour. Name updated across all files.

| Attribute | Type | Description |
|---|---|---|
| `_scratchpad` | `Scratchpad` | Shared logger |

| Method | Signature | Description |
|---|---|---|
| `process` | `async (docx_path: Path) -> CompactArtifact` | Extracts text from a .docx file |

---

## Entity Relationships

```
main.py
  |-- uses --> Extractor          (extraction.py)
  |-- uses --> ClassificationAgent (classification.py)
  |-- uses --> Scratchpad          (scratchpad.py)

ClassificationAgent
  |-- uses --> anthropic.Anthropic (SDK)
  |-- uses --> VaultCategory       (enum, for tool schema)
  |-- uses --> Scratchpad          (logging)

Extractor
  |-- uses --> Scratchpad (logging)
  |-- produces --> CompactArtifact (models.py)
```
