# Watchlist & Alerts

**Status:** hold
**Blocked by:** the backtest must show a real repeatable signal before notifications are worth building.
**Branch:** `feature/watchlist-alerts`

---

## Context

`core-hub` publishes to `auspex.signals.corroborated` (via `ScheduledCorroborationService.runCorroboration()`). Requirements §12 specifies a health reporter that, from Phase 5, emits through a notification transport. This spec wires both concerns — new-corroboration notifications and health alerts — to Discord webhooks.

Existing infrastructure: Postgres, Flyway, `@Scheduled`, `JdbcTemplate`, all in `core-hub`. No new service is introduced.

## What this builds

**Watchlist lookup:** No new watchlist table. The watchlist is `watchlist` joined to `watchlist_gene_target` (Flyway V3), maintained through the watchlist API. A corroboration's entity key is `<normalised name>:<label>` (`CorroborationScanner`), for example `BCL11A:GeneTarget`. An event is watched when its label is `GeneTarget` and its name matches a `watchlist_gene_target.gene_target` (stored upper-cased) case-insensitively:

```sql
SELECT w.ticker FROM watchlist_gene_target g JOIN watchlist w ON w.id = g.watchlist_id
WHERE g.gene_target = upper(?)
```

The notification names the matching tickers.

**Notification transport:** A `NotificationTransport` interface with a `DiscordWebhookTransport` implementation. Posts a JSON embed to `DISCORD_WEBHOOK_URL` via a plain `httpClient.POST`. On failure: one retry, then log at ERROR. Never propagates exceptions outside the transport — the corroboration loop must not be blocked by a Discord outage.

**Notification deduplication:** A Flyway-managed table `notifications_sent(entity_key TEXT, participants_hash TEXT, notified_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY(entity_key, participants_hash))`. Prevents re-notifying the same evidence set after re-extraction (which preserves `event_id`s and therefore the same `participants_hash`).

**WatchlistNotificationService:** Called from `ScheduledCorroborationService.runCorroboration()` after each new `CorroboratedSignalEvent` is published to Kafka. Splits the event's `entityKey` into name and label, looks the name up as above, deduplicates against `notifications_sent`, and sends via `NotificationTransport`.

**Health reporter:** A `@Scheduled` method in core-hub (separate from corroboration). On each run: queries DLT record count per topic and latest `ingested_at` per source type. If any DLT count exceeds `HEALTH_DLT_THRESHOLD` (default: 5), or any source has no signal in the past `HEALTH_SIGNAL_AGE_HOURS` (default: 48), sends one alert message via `NotificationTransport`. Configurable thresholds; both default to "warn late" rather than "warn early" to avoid noise during expected gaps.

**Supersession behaviour:** Each `CorroboratedSignalEvent` has a unique `participantsHash`. When a larger evidence set supersedes an older one, `runCorroboration()` publishes the new event (new hash). The notification service sees a new hash, checks `notifications_sent`, finds no entry, and notifies once. The old hash's notification is not re-sent because the `CorroboratedSignalEvent` for the superseded record is not re-emitted.

## Out of scope

Mechanism and company entity keys. Only `GeneTarget` keys can match the watchlist, because the watchlist stores gene targets per ticker.

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

- `test_matching_entity_key_triggers_transport_call` — `WatchlistNotificationService` is constructed with a mock `NotificationTransport` and a `JdbcTemplate` stub that returns ticker `BEAM` for gene target `BCL11A`; a `CorroboratedSignalEvent` with `entityKey = "BCL11A:GeneTarget"` and a hash not in `notifications_sent` is processed; `transport.send()` is called exactly once with a message naming `BEAM`.
- `test_non_matching_entity_key_does_not_call_transport` — same setup; event has `entityKey = "VEGFA:GeneTarget"`; `transport.send()` is never called.
- `test_already_notified_hash_is_not_re_sent` — `notifications_sent` stub returns that the hash is already present; `transport.send()` is never called regardless of entity key match.
- `test_superseded_evidence_set_does_not_re_notify_old_hash` — `notifications_sent` contains hash1 (the old smaller set); event arrives with hash2 (new larger set) for the same `entityKey`; `transport.send()` is called exactly once (for hash2).
- `test_transport_failure_is_retried_once_then_logged_not_propagated` — `transport.send()` throws `RuntimeException` on the first call and succeeds on the second; the service makes exactly two calls and does not propagate the exception to the caller.
- `test_dlt_depth_above_threshold_triggers_health_alert` — `HealthReporterService` is constructed with a `JdbcTemplate` stub returning DLT count = 6 (above default threshold of 5) and a mock `NotificationTransport`; `reportHealth()` is called; `transport.send()` is called exactly once.

Integration test (`*IT.java`):

- `test_watchlist_notification_fires_on_real_corroboration` — using the existing Testcontainers stack (Postgres + Neo4j + Kafka): add a watchlist entry with gene target `BCL11A` through `WatchlistService`, run `corroborationService.runCorroboration()` after inserting two qualifying signals, assert that the `NotificationTransport` stub (wired via Spring test config) received exactly one `send()` call and that `notifications_sent` has one row.

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
- The only new migration is `notifications_sent`. Watchlist rows come from the watchlist API, not from a seed migration.
- In the integration test, inject `NotificationTransport` as a Spring bean (annotated `@TestConfiguration`) rather than relying on `DISCORD_WEBHOOK_URL` being set. The `DiscordWebhookTransport` bean is only created when `DISCORD_WEBHOOK_URL` is present (`@ConditionalOnProperty`); tests inject a `@Primary` stub instead.
- `HEALTH_DLT_THRESHOLD` and `HEALTH_SIGNAL_AGE_HOURS` are `@Value`-injected with defaults. The health reporter runs on a separate fixed-delay schedule (`HEALTH_CHECK_INTERVAL_MS`, default 3600000 — once per hour).
