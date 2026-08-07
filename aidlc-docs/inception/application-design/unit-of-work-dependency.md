# Unit of Work Dependencies — Extraction Pipeline

## Dependency Matrix

| Unit | Depends On | Type |
|---|---|---|
| Unit 1: Foundation | — | None |
| Unit 2: Ingestion | Unit 1 | Runtime (uses Config, DriveFileMetadata, ManifestStore) |
| Unit 3: Extraction | Unit 1 | Runtime (uses Config, CompactArtifact, ImageMetadata) |
| Unit 4: Analysis | Unit 1 | Runtime (uses CompactArtifact, EnrichedDocument) |
| Unit 5: Export + Coordinator | Units 1, 2, 3, 4 | Runtime (imports and wires all prior units) |

---

## Build Order

```
Unit 1: Foundation
    |
    +──── Unit 2: Ingestion   ──┐
    |                           |
    +──── Unit 3: Extraction ───┤──► Unit 5: Export + Coordinator
    |                           |
    +──── Unit 4: Analysis   ───┘
```

Units 2, 3, and 4 have no dependency on each other — they can be built in parallel after Unit 1 is complete.

---

## Shared Interfaces (Contract Points)

| Interface | Produced By | Consumed By |
|---|---|---|
| `Config` | Unit 1 | Units 2, 3, 4, 5 |
| `ManifestStore` | Unit 1 | Units 2, 5 |
| `DriveFileMetadata` | Unit 1 (type) / Unit 2 (value) | Units 3, 5 |
| `CompactArtifact` | Unit 1 (type) / Unit 3 (value) | Units 4, 5 |
| `EnrichedDocument` | Unit 1 (type) / Unit 4 (value) | Unit 5 |
| `ImageMetadata` | Unit 1 (type) / Unit 3 (value) | Unit 5 |

---

## Rollout Strategy

1. Build and test Unit 1 (Foundation) fully before starting any other unit
2. Build Units 2, 3, 4 independently and concurrently (no inter-unit dependency)
3. Build Unit 5 (Export + Coordinator) last — integration wiring and end-to-end test
4. Run full integration test (`test_pipeline_e2e.py`) only after Unit 5 is complete
