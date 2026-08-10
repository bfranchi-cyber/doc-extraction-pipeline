# Deployment Architecture — Unit 1: Foundation

## Environment

**Type**: Local workstation (single-user, single-environment)
**OS**: Windows 11
**Python**: 3.11+ (installed system-wide or in a virtual environment)
**Deployment model**: Developer runs the pipeline manually from a terminal

There is no staging, no production, no CI/CD pipeline, and no containerisation. The tool
is a personal automation script, not a deployed service.

---

## Runtime Topology

```
User (terminal)
     |
     | docs-extraction   (console script entry point)
     v
pipeline.main:main()
     |
     +---> Config.from_toml("config.toml")
     |          |
     |          +---> validates local filesystem paths
     |          +---> validates credentials.json
     |          +---> warns on vault category drift
     |
     +---> Scratchpad(config.scratchpad_path)
     |
     +---> ManifestStore(config.manifest_dir)
     |
     +---> PipelineCoordinator(config, manifest, scratchpad)
               |
               | [Units 2-5 handle this part]
               v
         Drive API --> Ingestion --> Extraction --> Analysis --> Export
```

---

## Local Filesystem at Runtime

```
C:\Users\bfranchi\
  AppData\Local\docs-extraction\
    manifests\               ← one .json per processed Drive file
      <file_id>.json
      ...
    staging\                 ← temporary image files during extraction (cleaned up per doc)
      <file_id>\
        img_001.png
        ...
    scratchpad.log           ← JSONL, append-only, grows over time
    credentials.json         ← OAuth 2.0 credentials (never committed)

  Documents\
    Obsidian Vault\          ← output destination; pre-existing vault structure
      Work\
      Research\
      ...
    Obsidian Images\         ← image output destination

project-root\
  config.toml                ← local config (never committed)
  config.toml.example        ← committed template
  src\pipeline\...
  tests\...
```

---

## Dependency Graph (all units, for packaging completeness)

Unit 1 introduces the core dependencies. Later units add to `pyproject.toml`:

| Unit | Additional dependencies |
|---|---|
| Unit 1: Foundation | `dataclasses-json` |
| Unit 2: Ingestion | `google-auth`, `google-auth-oauthlib`, `google-api-python-client` |
| Unit 3: Extraction | `python-docx`, `pymupdf` |
| Unit 4: Analysis | `anthropic` |
| Unit 5: Export + Coordinator | none (uses stdlib + prior units) |

All declared together in `pyproject.toml` from the start (single `pip install -e .` installs
everything). Dev dependencies (`pytest`, `pytest-cov`, `hypothesis`) in `[dev]` optional group.

---

## No Infrastructure Shared Across Units

All four logical components from Unit 1 (`Config`, `ManifestStore`, `Scratchpad`, domain
models) are in-process Python objects — they are imported, not deployed as services. There
is no shared infrastructure file needed.
