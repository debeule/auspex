# Watchlist & Alerts

**Status:** hold
**Blocked by:** Phase 4 must show a real repeatable signal before notifications are worth building. Also: `watchlist-backend` spec must be done first — the `watchlist_entries` table planned in this spec is superseded by `watchlist` + `watchlist_gene_target` (see DECISIONS.md 2026-09-20). Rewrite the schema section of this spec before implementation.

**Schema section of this spec is stale.** Replace the `watchlist_entries` Flyway migration with a query against `watchlist_gene_target JOIN watchlist`. The `entity_key` format should use space-pipe-space (`"DMD | GENE_TARGET"`), not colon notation — verify against live data and record in DECISIONS.md.
**Branch:** `feature/watchlist-alerts`

---

## Context

`core-hub` publishes to `auspex.signals.corroborated` (via `ScheduledCorroborationService.runCorroboration()`). Requirements §12 specifies a health reporter that, from Phase 5, emits through a notification transport. This spec wires both concerns — new-corroboration notifications and health alerts — to Discord webhooks.

Existing infrastructure: Postgres, Flyway, `@Scheduled`, `JdbcTemplate`, all in `core-hub`. No new service is introduced.

## What this builds

**Watchlist storage:** A Flyway-managed Postgres table `watchlist_entries(id SERIAL PRIMARY KEY, entity_key TEXT NOT NULL UNIQUE, created_at TIMESTAMPTZ DEFAULT now())`. Pre-populated by the migration with the eight watched tickers' known gene targets (e.g. `BCL11A:GeneTarget`, `HBB:GeneTarget`, `DMD:GeneTarget`). Later additions are SQL inserts.

**Notification transport:** A `NotificationTransport` interface with a `DiscordWebhookTransport` implementation. Posts a JSON embed to `DISCORD_WEBHOOK_URL` via a plain `httpClient.POST`. On failure: one retry, then log at ERROR. Never propagates exceptions outside the transport — the corroboration loop must not be blocked by a Discord outage.

**Notification deduplication:** A Flyway-managed table `notifications_sent(entity_key TEXT, participants_hash TEXT, notified_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY(entity_key, participants_hash))`. Prevents re-notifying the same evidence set after re-extraction (which preserves `event_id`s and therefore the same `participants_hash`).

**WatchlistNotificationService:** Called from `ScheduledCorroborationService.runCorroboration()` after each new `CorroboratedSignalEvent` is published to Kafka. Checks the event's `entityKey` against `watchlist_entries`, deduplicates against `notifications_sent`, and sends via `NotificationTransport`.

**Health reporter:** A `@Scheduled` method in core-hub (separate from corroboration). On each run: queries DLT record count per topic and latest `ingested_at` per source type. If any DLT count exceeds `HEALTH_DLT_THRESHOLD` (default: 5), or any source has no signal in the past `HEALTH_SIGNAL_AGE_HOURS` (default: 48), sends one alert message via `NotificationTransport`. Configurable thresholds; both default to "warn late" rather than "warn early" to avoid noise during expected gaps.

**Supersession behaviour:** Each `CorroboratedSignalEvent` has a unique `participantsHash`. When a larger evidence set supersedes an older one, `runCorroboration()` publishes the new event (new hash). The notification service sees a new hash, checks `notifications_sent`, finds no entry, and notifies once. The old hash's notification is not re-sent because the `CorroboratedSignalEvent` for the superseded record is not re-emitted.

## Out of scope

Ticker-keyed watchlist lookup (matching `"BEAM"` → gene targets for BEAM). This requires a Neo4j traversal not in the current API; it is a future enhancement. For now, watchlist entries are full entity keys.

Slack, email, and other transports. The `NotificationTransport` interface makes substitution straightforward; a second implementation is out of scope.

Rate-of-change alerts, price alerts.

## Constraints

- Invariant 2 holds: `core-hub` is still the sole writer. No new service.
- Transport failure never blocks the corroboration pipeline. Exceptions from `NotificationTransport` are caught inside `WatchlistNotificationService`; the caller (`runCorroboration()`) does not see them.
- Deduplication on `participants_hash`, not `entity_key` alone — a new evidence set (new hash) for the same entity must notify; a re-processed identical evidence set must not.
- Every `@Transactional` stays qualified. The notification insert uses `jpaTransactionManager`.
- `DISCORD_WEBHOOK_URL` is required. If absent, `WatchlistNotificationService` logs a startup warning and becomes a no-op — it does not prevent the application from starting.

## Required tests

Unit tests, no Spring context (`*Test.java`):

- `test_matching_entity_key_triggers_transport_call` — `WatchlistNotificationService` is constructed with a mock `NotificationTransport` and a `JdbcTemplate` stub that returns `["BCL11A:GeneTarget"]` from `watchlist_entries`; a `CorroboratedSignalEvent` with `entityKey = "BCL11A:GeneTarget"` and a hash not in `notifications_sent` is processed; `transport.send()` is called exactly once.
- `test_non_matching_entity_key_does_not_call_transport` — same setup; event has `entityKey = "VEGFA:GeneTarget"`; `transport.send()` is never called.
- `test_already_notified_hash_is_not_re_sent` — `notifications_sent` stub returns that the hash is already present; `transport.send()` is never called regardless of entity key match.
- `test_superseded_evidence_set_does_not_re_notify_old_hash` — `notifications_sent` contains hash1 (the old smaller set); event arrives with hash2 (new larger set) for the same `entityKey`; `transport.send()` is called exactly once (for hash2).
- `test_transport_failure_is_retried_once_then_logged_not_propagated` — `transport.send()` throws `RuntimeException` on the first call and succeeds on the second; the service makes exactly two calls and does not propagate the exception to the caller.
- `test_dlt_depth_above_threshold_triggers_health_alert` — `HealthReporterService` is constructed with a `JdbcTemplate` stub returning DLT count = 6 (above default threshold of 5) and a mock `NotificationTransport`; `reportHealth()` is called; `transport.send()` is called exactly once.

Integration test (`*IT.java`):

- `test_watchlist_notification_fires_on_real_corroboration` — using the existing Testcontainers stack (Postgres + Neo4j + Kafka): insert a `watchlist_entries` row, run `corroborationService.runCorroboration()` after inserting two qualifying signals, assert that the `NotificationTransport` stub (wired via Spring test config) received exactly one `send()` call and that `notifications_sent` has one row.

## Definition of done

```bash
cd services/core-hub && ./gradlew test --tests '*WatchlistNotificationServiceTest' --tests '*HealthReporterServiceTest' --rerun-tasks
```

All 6 unit tests pass.

```bash
cd services/core-hub && ./gradlew integrationTest --tests '*WatchlistNotificationIT' --rerun-tasks
```

Integration test passes.

```bash
cd services/core-hub && ./gradlew check --rerun-tasks
```

Full suite green. `CorroborationServiceContractTest` passes unmodified (the notification side effect in `runCorroboration()` must not break any existing contract test).

## Notes

- `NotificationTransport` is a `@FunctionalInterface` with one method: `void send(String message)`. `DiscordWebhookTransport` uses `java.net.http.HttpClient` (standard library, no new dependency).
- Discord webhook payload: `{"content": "..."}`. Format the corroboration notification as plain text: entity key, source types, corroboration date, confidence score.
- The Flyway migration populating initial `watchlist_entries` rows is a data migration, not a schema migration — write it as `V{n}__seed_watchlist.sql` and seed the eight watched tickers' gene targets from `DECISIONS.md`.
- In the integration test, inject `NotificationTransport` as a Spring bean (annotated `@TestConfiguration`) rather than relying on `DISCORD_WEBHOOK_URL` being set. The `DiscordWebhookTransport` bean is only created when `DISCORD_WEBHOOK_URL` is present (`@ConditionalOnProperty`); tests inject a `@Primary` stub instead.
- `HEALTH_DLT_THRESHOLD` and `HEALTH_SIGNAL_AGE_HOURS` are `@Value`-injected with defaults. The health reporter runs on a separate fixed-delay schedule (`HEALTH_CHECK_INTERVAL_MS`, default 3600000 — once per hour).
