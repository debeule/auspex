# Corroboration late arrivals

**Status:** ready
**Branch:** `feature/corroboration-late-arrivals`

---

## Context

`services/core-hub/src/main/java/dev/auspex/corehub/corroboration/CorroborationScanner.java` finds new corroborations with a watermark: `findGroups` matches `(s:Signal) WHERE s.ingested_at > $watermark`, joins partners on shared `GeneTarget`/`Mechanism` nodes regardless of their own time, and `scan` advances the watermark (table `corroboration_state`, Flyway `V2`) to the largest trigger `ingested_at` it saw. The watermark is written only after every send is acknowledged (`specs/done/dead-letter-recovery.md`). Corroborations are inserted with `ON CONFLICT (entity_key, participants_hash) DO NOTHING`, and an event is published only when the row is new, so scanning a group twice is harmless. Nothing but the scanner reads `corroboration_state`.

`ingested_at` is set by the scraper when it extracts the document (`auspex_ingest/extraction_backend.py`) and carried in the event to `persistence/Neo4jWriteService.java` (`mergeSignal`). It says when the scraper extracted the document, not when core-hub wrote the node.

Found by the consolidated audit of 2026-10-10 (finding C4; the audit file is in the project's `audit/` folder) and checked against `develop` at `d615504`. A record on a lagging partition, or retried after a store outage, or replayed from the DLT (`POST /api/dlt/{topic}/replay`), is written after newer signals on other partitions were scanned. Its `ingested_at` is already behind the watermark and its partners are older still, so no later scan picks the pair up, and the corroboration is lost silently. (The audit also named re-extraction. That case does not apply, because a re-extraction gets a fresh `ingested_at`; a test below keeps it covered.)

A clock-based fix (scan on write time with a lookback) still loses a write whose transaction commits more than the lookback after it started, and nothing enforces such a bound. This spec removes the clock from the decision.

## What this builds

- **Every write marks the signal pending.** `mergeSignal` sets `s.corroboration_pending = true` and `s.write_token = $write_token` (a fresh random UUID per write) on every write, new or repeated, in the same transaction as the rest of the signal. A signal becomes visible to the scan only when that transaction commits, however late, and stays pending until a scan has handled that exact write.
- **The scan works from pending signals, not a watermark.** `scan` reads up to `corroboration.scan-batch-size` (default 500, in `application.yml`) pending signals with their `write_token`, finds their groups as triggers, inserts and sends as today, and only after every send is acknowledged clears the flag on the signals it read: `SET s.corroboration_pending = false` where `s.write_token` still equals the token it read. A signal rewritten while the scan ran has a new token, so it stays pending for the next scan. A pending signal with no partner is cleared the same way. A failure before the clear leaves every signal pending, and the next scan's repeats are absorbed by `ON CONFLICT DO NOTHING`.
- **No watermark.** `readWatermark`, `writeWatermark` and the `ingested_at` predicate go; Flyway `V5__drop_corroboration_watermark.sql` drops `corroboration_state` (`V2` stays untouched; applied migrations are frozen).
- **Index.** `Neo4jSchemaInitializer` creates `signal_corroboration_pending` on `Signal.corroboration_pending`.

## Out of scope

- Re-extraction removing relationships a new extraction no longer has (`specs/graph-relationship-replacement.md`).
- Withdrawing corroborations whose evidence later disappears.
- Changing the corroboration window, the degree cap or `CorroborationService`.
- Kafka Streams (`specs/kafka-streams-correlation.md`).

## Constraints

- Invariant 2: core-hub stays the only writer to Neo4j and Postgres.
- Invariant 5: all corroboration stays behind `CorroborationService`; `CorroborationServiceContractTest` passes unmodified.
- Invariant 10: corroboration inserts stay idempotent on `(entity_key, participants_hash)`, which is what makes re-scanning a pending signal safe.
- Invariant 12: event ids, tokens and the batch size are query parameters, never concatenated into Cypher.
- `ingested_at` keeps its meaning for the dashboard and health reporter; only the scan stops using it.

## Required tests

Unit (`./gradlew test`, `CorroborationScannerTest`):
- `scanReadsPendingSignalsAsTriggers` — no watermark or timestamp in the query parameters
- `pendingFlagIsClearedOnlyAfterEverySendIsAcknowledged` — a failed send leaves all read signals pending
- `clearUsesTheWriteTokenTheScanRead`
- `groupScannedTwiceIsNotRepublished` — a second scan over the same pending group inserts nothing and returns no event

Integration (`./gradlew integrationTest`, `CorroborationServiceIT`):
- `signalWrittenAfterNewerSignalsWereScannedIsCorroborated` — scan once with a newer signal, then write a partner-matching signal with an older `ingested_at`; the next scan corroborates it
- `writeCommittingLongAfterItStartedIsCorroborated` — open a Neo4j transaction that writes a partner-matching signal, run several scans while it stays open (none sees the uncommitted write) and newer signals are written and scanned, then commit; the next scan corroborates it, however long the transaction was open
- `signalRewrittenDuringAScanStaysPending` — rewrite a signal between the scan's read and its clear; it is still pending afterwards
- `reExtractedSignalIsScannedAgain` — the same `event_id` rewritten with a new mechanism shared by an older signal from another source is corroborated on the next scan
- `pendingSignalWithoutPartnersIsCleared`
- `corroborationStateTableIsGone` — after migrations, `corroboration_state` does not exist

## Definition of done

```bash
cd services/core-hub && ./gradlew test --rerun-tasks
cd services/core-hub && ./gradlew integrationTest --rerun-tasks
```

Expected: the 10 tests above pass with the rest of both suites; test counts read from `build/reports/tests/`. Integration tests need Docker and run in CI.

## Notes

- **Why a pending flag, not write time plus lookback or a reconciliation sweep:** Neo4j has no commit-ordered sequence, and transaction start time bounds nothing about commit time. A flag set inside the write's own transaction is visible exactly when the write is, so no committed signal can be skipped, and the token stops a scan from clearing a write it never saw. A periodic full reconciliation would also work, but it costs a whole-graph scan and still leaves a window until it runs.
- No graph exists yet on any stack, so no existing node needs a backfilled flag.
