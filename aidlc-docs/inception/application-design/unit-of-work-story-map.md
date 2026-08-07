# Unit of Work — Story Map

## Story to Unit Mapping

| Story | Title | Unit |
|---|---|---|
| US-01 | Scheduled eligibility detection (5-day rule) | Unit 2: Ingestion |
| US-02 | Google Drive OAuth authentication setup | Unit 2: Ingestion |
| US-03 | Document ingestion from Google Drive | Unit 2: Ingestion |
| US-04 | Parallel document extraction | Unit 3: Extraction |
| US-05 | Document analysis and enrichment | Unit 4: Analysis |
| US-06 | Export to Obsidian vault and images folder | Unit 5: Export + Coordinator |
| US-07 | Coordinator handoff and scratchpad observability | Unit 5: Export + Coordinator |
| US-08 | Re-run safety and idempotency | Unit 1: Foundation + Unit 5 |

---

## Per-Unit Story Coverage

### Unit 1: Foundation
- **US-08** (partial) — `ManifestStore.is_processed()` and `ManifestStore.set()` implement idempotency state; AC-08.1, AC-08.2, AC-08.3

### Unit 2: Ingestion
- **US-01** — AC-01.1–AC-01.5 (eligibility detection)
- **US-02** — AC-02.1–AC-02.4 (OAuth authentication)
- **US-03** — AC-03.1–AC-03.4 (file download, rate limits, errors)

### Unit 3: Extraction
- **US-04** — AC-04.1–AC-04.6 (text extraction, classification, image staging, concurrency, error handling)

### Unit 4: Analysis
- **US-05** — AC-05.1–AC-05.5 (formatting, citations, frontmatter, abstract, semantic preservation)

### Unit 5: Export + Coordinator
- **US-06** — AC-06.1–AC-06.5 (vault write, image move, URI injection, unknown category fallback, manifest update)
- **US-07** — AC-07.1–AC-07.4 (scratchpad logging, failure recording, run summary, handoff validation)
- **US-08** (partial) — AC-08.4 (no duplicate vault files, enforced by ExportAgent + ManifestStore check)

---

## Acceptance Criteria Coverage Check

| AC | Story | Unit | Status |
|---|---|---|---|
| AC-01.1–01.5 | US-01 | Unit 2 | Assigned |
| AC-02.1–02.4 | US-02 | Unit 2 | Assigned |
| AC-03.1–03.4 | US-03 | Unit 2 | Assigned |
| AC-04.1–04.6 | US-04 | Unit 3 | Assigned |
| AC-05.1–05.5 | US-05 | Unit 4 | Assigned |
| AC-06.1–06.5 | US-06 | Unit 5 | Assigned |
| AC-07.1–07.4 | US-07 | Unit 5 | Assigned |
| AC-08.1–08.3 | US-08 | Unit 1 | Assigned |
| AC-08.4 | US-08 | Unit 5 | Assigned |

All acceptance criteria assigned. No gaps.
