# Domain Entities — Extraction Unit (Revised 2026-08-14)

> **Scope change**: `DriveFileMetadata` and `ImageMetadata` are removed.
> `CompactArtifact` is simplified. `ExtractionAgent` no longer takes `image_client` or `config`.

---

## `CompactArtifact` (TypedDict)

The structured output of the Extraction unit.

| Field | Type | Description |
|---|---|---|
| `document_name` | `str` | Original filename (e.g. `contract.docx`) |
| `extracted_text` | `str` | Verbatim text content from the .docx file |

---

## `EnrichedDocument` (dataclass)

Reserved for the future Analysis stage — not used in the current iteration.

| Field | Type | Description |
|---|---|---|
| `document_name` | `str` | Original filename |
| `markdown` | `str` | Enriched Markdown output |

---

## `ExtractionAgent`

Processes one .docx file via Claude Haiku + MCP.

| Attribute | Type | Description |
|---|---|---|
| `_scratchpad` | `Scratchpad` | Structured JSONL logger |
| `_client` | `anthropic.AsyncAnthropic` | Async Claude API client |

### Methods

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(scratchpad: Scratchpad)` | Initialize with logger |
| `process` | `async (docx_path: Path) -> CompactArtifact` | Full extraction for one file |

---

## Entity Relationships

```
docx_path (Path)
     |
     v
ExtractionAgent.process()
     |
     v
parse_document MCP tool (mammoth)
     |
     v
CompactArtifact
  {document_name, extracted_text}
```
