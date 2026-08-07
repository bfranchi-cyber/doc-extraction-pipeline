# Component Dependencies — Extraction Pipeline

## Dependency Matrix

| Component | Depends On | Communication Pattern |
|---|---|---|
| `PipelineCoordinator` | `Config`, `ManifestStore`, `IngestionAgent`, `ExtractionAgent`, `AnalysisAgent`, `ExportAgent` | Direct async calls; owns all stage interactions |
| `IngestionAgent` | `Config`, `ManifestStore`, Google Drive API / Drive MCP | Async HTTP (Drive API); sync manifest read |
| `ExtractionAgent` | `Config`, Claude Haiku 4.5 (Anthropic SDK), `python-docx`, `pypdf` | Async HTTP (Claude API); sync file parse |
| `AnalysisAgent` | `CompactArtifact` (data type), Claude Sonnet 4.5 (Anthropic SDK) | Async HTTP (Claude API); in-memory data |
| `ExportAgent` | `Config`, `ManifestStore`, file system | Sync file I/O; sync manifest write |
| `ManifestStore` | `Config` (manifest_dir path), file system | Sync file I/O only |
| `Config` | `config.toml` (file system) | Loaded once at startup; read-only everywhere |

---

## Data Flow

```
[Google Drive]
     |
     | DriveFileMetadata list
     v
PipelineCoordinator
     |
     | DriveFileMetadata + local_path (per doc, concurrent)
     v
ExtractionAgent (one instance per doc)
     |
     | CompactArtifact (in-memory TypedDict)
     v
PipelineCoordinator  ← validates handoff
     |
     | CompactArtifact
     v
AnalysisAgent
     |
     | EnrichedDocument (in-memory dataclass)
     v
PipelineCoordinator  ← validates handoff
     |
     | EnrichedDocument + staged image paths
     v
ExportAgent
     |
     ├─► Vault .md file (file system)
     ├─► Images folder (file system)
     └─► ManifestStore (per-doc JSON file)
```

---

## External Dependencies

| External System | Used By | Protocol |
|---|---|---|
| Google Drive API | `IngestionAgent` | HTTPS (via Drive MCP or `google-api-python-client`) |
| Claude Haiku 4.5 | `ExtractionAgent` | HTTPS (Anthropic Python SDK async) |
| Claude Sonnet 4.5 | `AnalysisAgent` | HTTPS (Anthropic Python SDK async) |
| Local file system | `ExtractionAgent`, `ExportAgent`, `ManifestStore`, `Config` | OS file I/O |
| OAuth 2.0 token store | `IngestionAgent` | Local JSON file, managed by `google-auth` |

---

## Coupling Notes

- **PipelineCoordinator → all agents**: High coupling by design — the Coordinator is the hub that owns the pipeline flow. This is intentional.
- **ExtractionAgent → AnalysisAgent**: Zero direct coupling. Communication happens through `CompactArtifact` passed via the Coordinator. Agents never call each other directly.
- **ExportAgent → ManifestStore**: Sequential (not concurrent) writes, so no locking is needed.
- **Config**: Injected into all components at construction time; never mutated after startup.

---

## Concurrency Boundaries

```
Sequential (Coordinator driven):
  Ingestion → [batch of docs] → Export

Concurrent (asyncio.gather within batch):
  ExtractionAgent(doc_1) ──┐
  ExtractionAgent(doc_2) ──┤──► (all awaited together)
  ExtractionAgent(doc_N) ──┘

Sequential per document (chained coroutines):
  download → extract → analyse → export
  (each doc's chain runs independently but concurrently with other docs' chains)
```

Analysis and Export run sequentially **per document** — the Coordinator awaits each stage before moving to the next for that document, but multiple documents progress through their chains concurrently.
