# core-hub input health

**Status:** ready
**Branch:** `feature/core-hub-input-health`
**Docs impact:** `HUB-new` ([docs/core-hub/http-api.md](../docs/core-hub/http-api.md)): the input health route and what makes each input `UP`, called *input health* below; and an unknown route answering 404, called *unknown route* below. `RES-new` ([docs/research/market-data.md](../docs/research/market-data.md)): the price service's freshness route, called *price freshness* below · changed: `STR-023` in [docs/strategy/runtime.md](../docs/strategy/runtime.md) (`divergent` to `tested`, and its known trap removed) · retired: none

---

## Context

Written against `develop` @ `c471130`.

- The strategy runtime polls `GET <CORE_HUB_URL>/api/v1/health/inputs` every `HEALTH_CHECK_INTERVAL_SECONDS` and expects `{"inputs": {"<input_source>": "UP" | "DOWN"}}` (STR-022, STR-023; client in `services/strategy/src/auspex_strategy/runtime/health.py`). The four input sources are the values of `InputSource` in `services/strategy/src/auspex_strategy/models.py`: `corroboration_store`, `price_data`, `graph_query`, `extraction_model`. A missing source or no answer counts as unhealthy, so every `paper` strategy that declares an input stays paused.
- core-hub has no such route. STR-023 is `divergent`; the gap is `## 2026-10-10 — Strategy runtime — FLAG — the live data channel is not fully served by core-hub yet` (item 1), whose Action asks for this spec before `forward-paper-trading` starts.
- On the stack machine (audit of 2026-11-13) each poll logs an error in both services, about 1,400 a day each since 2026-11-08. core-hub answers the unknown path with 500 `Internal server error`: `GlobalExceptionHandler` (`services/core-hub/src/main/java/dev/auspex/corehub/rest/GlobalExceptionHandler.java`) sends Spring's `NoResourceFoundException` to its catch-all handler.
- What core-hub already knows: Postgres and Neo4j through Spring's health indicators (actuator `health`, HUB-051); each source's latest stored signal from `signal_current` (`PostgresSignalAgeReader`, HUB-052).
- What it does not know: price freshness. Prices are Parquet snapshots in MinIO `auspex-prices` (RES-001) refreshed by the price service (`services/backtesting/src/auspex_backtesting/api.py`, port 8001, `PRICE_API_URL` in `.env.example`), which owns the NYSE calendar (`MarketCalendar`) and the benchmark ticker (`BENCHMARK_TICKER` in `prices/price_refresher.py`, RES-008). Its `auspex_price_refresh_sessions_since_success` gauge is in-process and resets on restart, so it cannot vouch for the data.

## What this builds

1. **Price freshness on the price service.** `GET /prices/freshness` reads the benchmark snapshot's last stored bar and answers `{"ticker": "<benchmark>", "last_bar": "<yyyy-mm-dd>", "sessions_behind": <n>}`, `n` the NYSE sessions after `last_bar` whose bar is settled by now (RES-004), so a session not yet settled is never counted as missed. With no benchmark snapshot it answers 503 with a JSON error.
2. **Input health on core-hub.** `GET /api/v1/health/inputs` answers 200 with all four sources, each `UP` or `DOWN`, computed per request:
   - `corroboration_store`: `UP` when the Postgres health indicator is `UP`.
   - `graph_query`: `UP` when the Neo4j health indicator is `UP`.
   - `extraction_model`: `UP` when the newest signal in `signal_current`, over all sources, was ingested no longer ago than `auspex.health.inputs.extraction-max-age`. No signal at all is `DOWN`. A stopped model stops new signals, so the outcome is the measure, not the model's process.
   - `price_data`: `UP` when the price service answers within `auspex.health.inputs.price-timeout` and its `sessions_behind` is at most `auspex.health.inputs.price-max-sessions-behind`.
   Each check is bounded and isolated: one that throws or times out makes only its own input `DOWN` and is logged once per state change, not once per poll.
3. **Unknown routes answer 404.** A request to a path no controller serves answers 404 with the JSON error body of HUB-049, and is not logged as an unhandled exception.
4. **Wiring.** core-hub gets `PRICE_API_URL` in `docker/docker-compose.yml` (a plain `${PRICE_API_URL}`, OPS-006); the three thresholds live in `services/core-hub/src/main/resources/application.yml` under `auspex.health.inputs`, with the values in Notes.

## Out of scope

- Ticker and source types on corroborated events (STR-024, item 2 of the same FLAG); that is its own core-hub spec.
- Changing the runtime's client, its poll interval or its pause rules (STR-022).
- Taking any strategy to `paper`, or starting forward paper trading.
- Alerting on input health in Grafana; the runtime's pause log is the record (STR-017).
- The scraper image on the stack machine and the alert contact point (separate items from the same audit).

## Constraints

- INV-2: core-hub only reads here; it writes nothing new to Postgres or Neo4j and gains no MinIO access.
- HUB-041: the route is a GET and needs no token. HUB-049: every error body is JSON. HUB-050: timestamps, if any are added, are ISO-8601 UTC with `Z`. HUB-051: actuator exposure does not change; the route lives under `/api/v1`, not under `/actuator`.
- STR-022 and STR-023 fix the wire form; keys are exactly the four `InputSource` values, values exactly `UP` or `DOWN`.
- RES-004 decides which bars count as settled; reuse the refresher's settle rule and `MarketCalendar`, never a second calendar.
- HUB-026 does not apply (no transaction); do not add one to a health read.
- Values in `application.yml`, never in Java constants; the docs name the keys and never copy the values.
- Trap: Spring's `db` and `neo4j` indicators can take seconds when a store is down. Read them through `HealthContributorRegistry` with the same bound as the price call, so a dead store cannot hold the poll past the runtime's `timeout_seconds`.

## Required tests

Write these first; confirm each fails for the right reason before implementing (ENG-001).

core-hub, unit (`src/test/java/dev/auspex/corehub/health/InputHealthServiceTest.java`):
- `test_every_input_is_up_when_every_check_passes` — STR-023, input health
- `test_corroboration_store_is_down_when_the_postgres_indicator_is_down` — input health
- `test_graph_query_is_down_when_the_neo4j_indicator_is_down` — input health
- `test_extraction_model_is_down_when_the_newest_signal_is_older_than_the_max_age` — input health
- `test_extraction_model_is_down_when_no_signal_is_stored` — input health
- `test_price_data_is_down_when_the_price_service_is_more_sessions_behind_than_allowed` — input health
- `test_price_data_is_down_when_the_price_service_does_not_answer_in_time` — input health
- `test_one_failing_check_leaves_the_other_inputs_reported` — input health
- `test_a_check_failing_on_every_poll_is_logged_once_until_it_recovers` — input health

core-hub, integration (`src/integrationTest/java/dev/auspex/corehub/rest/InputHealthIT.java`, WireMock for the price service):
- `test_inputs_route_answers_exactly_the_four_input_sources` — STR-023 (keys and values pinned to the runtime's wire form)
- `test_inputs_route_needs_no_write_token` — HUB-041, input health
- `test_unknown_route_answers_404_json_not_500` — unknown route, HUB-049

price service (`services/backtesting/tests/unit/test_price_freshness.py`):
- `test_freshness_counts_settled_sessions_after_the_benchmark_last_bar` — price freshness
- `test_freshness_does_not_count_a_session_before_its_settle_time` — price freshness, RES-004
- `test_freshness_answers_503_when_the_benchmark_snapshot_is_missing` — price freshness

Mutation check (ENG-011), each on a disposable copy, each turning a named test red: flip the max-age comparison; drop the per-check timeout; map `NoResourceFoundException` back to 500; count the unsettled session.

## Definition of done

```bash
cd services/backtesting && uv run ruff check . && uv run pytest tests/unit/test_price_freshness.py -q
cd ../core-hub && ./gradlew test --tests '*InputHealthServiceTest' --rerun-tasks && ./gradlew integrationTest --tests '*InputHealthIT' --rerun-tasks
cd ../.. && python3 -m tools.docs_check --base origin/develop
```

Expected: 3 passed (price service); 9 unit and 3 integration tests passed in core-hub (CI proves the Gradle lines; cloud sessions have no Maven Central or Docker); `docs_check: clean`. STR-023 reads `tested` with the IT named. On the stack machine after deploy, `curl -s localhost:8080/api/v1/health/inputs` lists four inputs, and the error lines from the runtime's input poll stop.

## Compatibility

- The runtime needs no change; strategies that declare inputs resume on the first poll where all their inputs are `UP`, and each resume is recorded in `strategy/health/pauses.jsonl` (STR-022).
- No strategy is `paper` today, so no trading changes.
- Clients that relied on a 500 for an unknown path see 404; the dashboard calls only existing routes.

## Rollback

Revert the PR. The runtime goes back to pausing every input-declaring strategy, and the 500s return; no data or schema changes.

## Notes

Defaults chosen while scoping; the owner can change any before the build starts.
- `extraction-max-age`: 36h. Signals arrive from five sources every night; 36h tolerates one missed night before strategies pause.
- `price-max-sessions-behind`: 1. The nightly refresh runs after the close, so one settled but not yet refreshed session is normal; two means a missed refresh.
- `price-timeout`: 2s, also the bound for the Postgres and Neo4j indicators; the runtime's own client timeout is longer.
- Price freshness comes from the price service rather than core-hub reading MinIO, so core-hub keeps no MinIO client (INV-2 is about writes, but one owner of the calendar and the settle rule is simpler).
