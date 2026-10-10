# Corroboration late arrivals

**Status:** ready
**Branch:** `feature/corroboration-late-arrivals`

---

## Context

`services/core-hub/src/main/java/dev/auspex/corehub/corroboration/CorroborationScanner.java` finds new corroborations with a watermark: `findGroups` matches `(s:Signal) WHERE s.ingested_at > $watermark`, joins partners on shared `GeneTarget`/`Mechanism` nodes regardless of their own time, and `scan` advances the watermark (table `corroboration_state`) to the largest trigger `ingested_at` it saw. The watermark is written only after every send is acknowledged (`specs/done/dead-letter-recovery.md`). Corroborations are inserted with `ON CONFLICT (entity_key, participants_hash) DO NOTHING`, and an event is published only when the row is new, so scanning a group twice is harmless.

`ingested_at` is set by the scraper when it extracts the document (`auspex_ingest/extraction_backend.py`) and carried in the event to `persistence/Neo4jWriteService.java` (`mergeSignal`). It says when the scraper extracted the document, not when core-hub wrote the node.

Found by the consolidated audit of 2026-10-10 (finding C4; the audit file is in the project's `audit/` folder) and checked against `develop` at `d615504`. A signal whose graph write lands after the watermark has passed its `ingested_at` is never a trigger:
- a record on a lagging partition, or retried after a store outage or from the DLT replay (`POST /api/dlt/{topic}/replay`), is written after newer signals on other partitions were scanned.
Its partners are older still, so no later scan picks the pair up. The corroboration is lost silently. (The audit also named re-extraction; it does not apply, because a re-extraction gets a fresh `ingested_at`. The test below keeps it covered.)

## What this builds

- **The scan follows graph writes, not scrape times.** `mergeSignal` sets `s.graph_written_at = datetime()` on every write, new or repeated. `findGroups` selects triggers with `s.graph_written_at > $watermark - lookback`, and `scan` advances the watermark to the largest `graph_written_at` it saw. A signal written late, replayed or re-extracted becomes a trigger when it is written.
- **A lookback covers transactions that commit out of order.** `datetime()` is the transaction's start time, so a long write can commit after a shorter one that started later. The scan re-reads `corroboration.scan-lookback` (default 10 minutes, in `application.yml`) behind the watermark; groups it sees again are dropped by the existing `ON CONFLICT DO NOTHING` and not republished.
- **Index.** `Neo4jSchemaInitializer` creates `signal_graph_written_at` on `Signal.graph_written_at`.

## Out of scope

- Re-extraction removing relationships a new extraction no longer has (`specs/graph-relationship-replacement.md`).
- Withdrawing corroborations whose evidence later disappears.
- Changing the corroboration window, the degree cap or `CorroborationService`.
- Kafka Streams (`specs/kafka-streams-correlation.md`).

## Constraints

- Invariant 2: core-hub stays the only writer to Neo4j and Postgres.
- Invariant 5: all corroboration stays behind `CorroborationService`; `CorroborationServiceContractTest` passes unmodified.
- Invariant 9: `graph_written_at` and the watermark are UTC.
- Invariant 12: the lookback is a query parameter, never concatenated into Cypher.
- `ingested_at` keeps its meaning (when the scraper saw the document) for the dashboard and health reporter; only the scan stops using it.

## Required tests

Unit (`./gradlew test`, `CorroborationScannerTest`):
- `watermarkAdvancesToTheLatestGraphWriteNotTheLatestIngestion`
- `scanQueriesFromTheWatermarkMinusTheLookback`
- `groupSeenAgainInsideTheLookbackIsNotRepublished` — second scan over the same group inserts nothing and returns no event

Integration (`./gradlew integrationTest`, `CorroborationServiceIT`):
- `signalWrittenAfterTheWatermarkPassedItsIngestionTimeIsCorroborated` — scan once with a newer signal, then write a partner-matching signal with an older `ingested_at`; the next scan corroborates it
- `reExtractedSignalIsScannedAgain` — the same `event_id` rewritten with a new mechanism shared by an older signal from another source is corroborated on the next scan
- `signalsWithEqualIngestionTimesAcrossScansAreAllCorroborated`
- `graphWrittenAtIsSetOnEveryWrite` — the property is present after the first write and later after a rewrite

## Definition of done

```bash
cd services/core-hub && ./gradlew test --rerun-tasks
cd services/core-hub && ./gradlew integrationTest --rerun-tasks
```

Expected: the 7 tests above pass with the rest of both suites; test counts read from `build/reports/tests/`. Integration tests need Docker and run in CI.

## Notes

- **Why a write-time property plus lookback, not a commit sequence:** Neo4j has no commit-ordered sequence, and the corroboration insert is already idempotent, so a bounded re-read is the smallest change that cannot lose a trigger. A graph write runs in well under a second; ten minutes leaves a wide margin and costs one re-read of ten minutes of signals per scan.
- No graph exists yet on any stack, so existing nodes without `graph_written_at` need no backfill.
