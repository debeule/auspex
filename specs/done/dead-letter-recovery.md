# Dead-letter recovery

**Status:** done
**Branch:** `feature/dead-letter-recovery`

---

## Context

`core-hub` consumes `auspex.signals.extracted` and `auspex.raw.ingested` (`services/core-hub/src/main/java/dev/auspex/corehub/kafka/SignalListener.java`). Its error handlers (`config/KafkaConfig.java`, `signalErrorHandler`, `rawErrorHandler`) retry every exception twice with `FixedBackOff(1000L, 2)` and then publish to the lowercase `.dlt` topic through `CountingDeadLetterRecoverer`, which counts `auspex_dlt_events_total`. `UnknownMajorVersionException` goes to the DLT without retry. There is no way to put a dead-lettered record back except a hand-run Kafka command.

The corroboration scan (`corroboration/CorroborationScanner.java`, `ScheduledCorroborationService.java`) reads signals ingested after a watermark stored in `corroboration_state`, writes the new watermark, and then sends the corroborated events with `KafkaTemplate.send` without waiting for the result. It compares `ingested_at.epochSeconds > watermark` at second precision.

Requirements: `docs/requirements.md` §3 rule 10 (deterministic failures to the DLT at once; transient failures get 1 attempt + 2 retries with backoff, then the DLT; never block a partition), §3 rule 12 (nothing dies silently), §2 (DLTs are triaged by hand), §4.2 (scan strategy).

Found by the soak-test readiness audit (2026-10-09): a Postgres or Neo4j restart (an OOM kill, a Docker Desktop restart) lasts longer than the two 1-second retries, so every record consumed in that window goes to the DLT and stays there for the rest of an unattended run. The scanner can also lose events: the watermark moves before the send is confirmed, and signals ingested in the same second as the watermark are never scanned.

## What this builds

- **Listeners pause while a store is down.** A scheduled check of the Postgres and Neo4j health indicators pauses both listener containers when either is unreachable and resumes them when both are back. No record is delivered while paused, so an outage no longer burns retries.
- **Transient failures back off longer.** Still 1 attempt + 2 retries (§3 rule 10), but exponential: 5 s, then 30 s by default (`AUSPEX_KAFKA_RETRY_INITIAL_MS`, `AUSPEX_KAFKA_RETRY_MULTIPLIER`). Deserialization, validation and unknown-major-version failures still go straight to the DLT.
- **Dead letters can be replayed.** `POST /api/dlt/{topic}/replay` re-publishes the records of `auspex.signals.extracted.dlt` or `auspex.raw.ingested.dlt` to their source topic with the original key, value and `schema_version` header. It tracks its position in its own consumer group, so a record is replayed at most once, and returns the count. Writes are idempotent on their natural keys, so replaying a record that was already stored is safe. The dashboard or a DAG can call it; nobody runs a command.
- **The corroboration scan doesn't drop events.** The watermark is written only after every send in the batch is acknowledged, and the scan compares full timestamps, not whole seconds.

## Out of scope

- A dashboard button or DAG for the replay (the pipeline-control-view spec's job).
- Replaying `auspex.signals.corroborated.dlt` (nothing consumes the source topic yet).
- Alerting on DLT depth (`specs/pipeline-alerting-gaps.md`).
- Changing which exceptions count as deterministic.

## Constraints

- Invariant 2: only core-hub writes Postgres and Neo4j; replay goes through Kafka, so the normal listener does the writing.
- Invariant 10: replay relies on idempotent writes on each path's declared natural key.
- Invariant 11: every record still ends in the store or the DLT with its diagnostic headers; pausing doesn't block a partition on a poison record, it only waits out a dependency.
- Invariant 12: parameterized queries only (ArchUnit).
- Known trap: the DLT resolver returns partition `-1` with the lowercase `.dlt` suffix; replay publishes to the source topic with partition chosen by key.
- The replay endpoint is a write, so it sits behind the dashboard foundation's bearer-token check.

## Required tests

Unit (`./gradlew test`):
- `transientFailureIsRetriedTwiceWithGrowingBackoff` — the handler's back-off yields 5000 ms, 30000 ms, then stops
- `deserializationFailureGoesToTheDltWithoutRetry`
- `listenersPauseWhenNeo4jIsDown`
- `listenersPauseWhenPostgresIsDown`
- `listenersResumeOnlyWhenBothStoresAreUp`
- `watermarkIsNotWrittenWhenACorroboratedSendFails`

Integration (`./gradlew integrationTest`):
- `recordConsumedDuringANeo4jOutageIsStoredAfterRecovery` — make Neo4j unreachable to the probe and the graph write, wait for the listeners to pause, publish a signal, end the outage, assert the signal is stored and the DLT is empty (a stopped Testcontainer restarts on a new port, so the outage is injected rather than a real stop)
- `replayRepublishesDeadLettersToTheSourceTopicWithKeyAndHeaders`
- `replayDoesNotRepublishARecordTwice`
- `replayedSignalIsStoredOnce` — a replayed record whose signal already exists leaves one row and one node
- `replayRequiresTheWriteToken`
- `signalIngestedInTheWatermarkSecondIsCorroborated`

## Definition of done

```bash
cd services/core-hub && ./gradlew test --rerun-tasks && ./gradlew integrationTest --rerun-tasks
```

Expected: both tasks pass, with the 6 new unit tests and 6 new integration tests counted in `build/reports/tests/`. Integration tests run in CI only (cloud sessions have no Docker), so CI green on the PR is the proof. `services/core-hub/README.md` documents the replay endpoint and the pause behaviour.

## Notes

- Why pause rather than unlimited retries: §3 rule 10 fixes three deliveries for a transient failure, and an unlimited retry blocks the partition behind it. Pausing on a known-down dependency keeps both rules: no partition sits on a poison record, and an outage doesn't count as a failure (`DECISIONS.md` 2026-10-09 entry).
- The health check interval (default 5 s) and the back-off values are properties, so a test can shorten them.
