# CLAUDE.md — services/

Auto-loaded when working in any service directory.

## Cross-service contract

`ResearchSignalEvent` is the Python↔Java handoff. The Pydantic model in
`ingestion-scraper` generates the Java contract fixture:

    cd services/ingestion-scraper && uv run pytest tests/unit/test_contract_fixture.py

The generated file is `services/core-hub/src/test/resources/contract/signal_event_v1.json`.
**If the Python model changes, regenerate and commit.** Java deserialization tests validate against it.

## Kafka topics (canonical list)

| Topic | Partitions | Produced by | Consumed by |
|---|---|---|---|
| `auspex.raw.ingested` | 6 | ingestion-scraper | core-hub |
| `auspex.signals.extracted` | 6 | ingestion-scraper | core-hub |
| `auspex.signals.corroborated` | 6 | core-hub | (downstream — Phase 6) |
| `*.dlt` | 6 (must match source) | Spring Kafka DLT | (monitoring) |

Topic provisioning is in `docker/topics.yaml`. DLT partition count must match the source topic — Spring's `DeadLetterPublishingRecoverer` publishes to the same partition number; a mismatch fails silently.

## Hard boundary (Invariants 1 & 2)

- `ingestion-scraper` writes **only** to MinIO and Kafka. No DB access, ever.
- `core-hub` is the **sole** writer to Postgres and Neo4j.

Crossing either boundary is not a refactor candidate; it is an architecture violation.
