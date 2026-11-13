# core-hub input health

**Status:** ready
**Blocked by:** —
**Branch:** `feature/core-hub-input-health`
**Docs impact:** `HUB-new` ([docs/core-hub/http-api.md](../docs/core-hub/http-api.md)): the `GET /api/v1/health/inputs` contract and what makes each input `UP`; `HUB-new` (same doc): an unmatched path answers 404. Changed: RES-012 ([docs/research/market-data.md](../docs/research/market-data.md#RES-012)), the price service's `GET /health` also reports `sessions_since_success`. STR-023 ([docs/strategy/runtime.md](../docs/strategy/runtime.md#STR-023)) goes from `divergent` to verified, citing the new tests; the "Known divergences" line about the `HEALTH_CHECK_BASE_URL` compose comment is dropped.

---

## Context

Written against `develop` @ `c471130`.

**The gap.** The strategy runtime polls `GET {CORE_HUB_URL}/api/v1/health/inputs` every `HEALTH_CHECK_INTERVAL_SECONDS` (`services/strategy/src/auspex_strategy/runtime/health.py`, `HttpInputHealthClient`) and expects `{"inputs": {"<input_source>": "UP" | "DOWN"}}`. No answer, or an input missing from the answer, counts as unhealthy, and a strategy declaring an unhealthy input is paused (STR-022). core-hub has no such route (STR-023, `divergent`; `## 2026-10-10 — Strategy runtime — FLAG — the live data channel is not fully served by core-hub yet`, item 1; fixed by its own spec per `## 2026-10-17 — Living docs — CHOICE — defects found while scoping`). So every `paper` strategy would stay paused forever.

**Seen on the stack machine.** The 2026-11-13 audit on the Mac found the runtime's poll failing once a minute since 2026-11-08: 1,432 `ERROR` lines a day in `auspex-strategy-runtime` and the same number in `auspex-core-hub`. core-hub answers the unknown path with 500 and logs `Unhandled exception` with a full stack trace, because `GlobalExceptionHandler` (`services/core-hub/src/main/java/dev/auspex/corehub/rest/GlobalExceptionHandler.java`) maps Spring's `NoResourceFoundException` to its catch-all 500 handler.

**The four inputs.** `InputSource` (`services/strategy/src/auspex_strategy/models.py`) has `corroboration_store`, `price_data`, `graph_query` and `extraction_model`. Every strategy today (H1, H4, H5, H6, H7) declares `corroboration_store` and `price_data`; none declares the other two.

**What core-hub can already see.**
- Postgres (`signal_current`, `corroboration`): its own `DataSource`; Spring Boot's `db` health indicator already feeds `/actuator/health`.
- Neo4j: its own driver; the `neo4j` health indicator already feeds `/actuator/health`.
- Prices: core-hub has no link to them. The runtime reads the MinIO price snapshots that the price service (`services/backtesting/src/auspex_backtesting/api.py`, port 8001, `PRICE_API_URL=http://price-service:8001` in `.env.example`) refreshes nightly. The price service already computes how many NYSE sessions it has missed (`PriceRefreshMetrics.sessions_since_success()` in `price_metrics.py`, exported as the gauge `auspex_price_refresh_sessions_since_success`, read by the Price Refresh Stale rule against `ALERT_PRICE_REFRESH_MAX_MISSED_SESSIONS`). Its `GET /health` answers only `{"status": "ok"}` (RES-012).
- The extraction model (Ollama on the host, called by the scraper): core-hub has no link to it, and the scraper's `/health` does not check it.

## What this builds

1. **`GET /api/v1/health/inputs` on core-hub**, answering 200 with `{"inputs": {...}}`, one key per input that core-hub can judge:
   - `corroboration_store`: `UP` when the Postgres health indicator is `UP`.
   - `graph_query`: `UP` when the Neo4j health indicator is `UP`.
   - `price_data`: `UP` when the price service's `GET /health` answers 200 within the timeout and its `sessions_since_success` is at most `INPUT_HEALTH_PRICE_MAX_MISSED_SESSIONS` (a required `.env` value; `.env.example` sets it to 2, the same as `ALERT_PRICE_REFRESH_MAX_MISSED_SESSIONS`). Any other answer, a timeout or a missing field is `DOWN`.
   - `extraction_model` is left out of the answer. The runtime reads a missing input as unhealthy, which is right for an input nobody vouches for, and no strategy declares it.
   Each check runs on request, with its own timeout (`auspex.health.inputs.timeout-ms`, default 2000), so one slow dependency cannot hold the answer past the runtime's own timeout. A failing check is `DOWN`, never an error status for the whole answer. The endpoint is a GET under `/api`, so it needs no token (HUB-041).
2. **The price service's `GET /health`** answers `{"status": "ok", "sessions_since_success": <int>}`, the same count the gauge reports.
3. **An unmatched path on core-hub answers 404** with the usual JSON error body (HUB-049), logged at most at `DEBUG`, with no stack trace.
4. **Compose and `.env.example`.** core-hub gets `PRICE_API_URL` and `INPUT_HEALTH_PRICE_MAX_MISSED_SESSIONS`; the `HEALTH_CHECK_BASE_URL` compose comment stays true. `SETUP.md` is unchanged (no credential or manual step).

## Out of scope

- An `extraction_model` check (Ollama reachability, model loaded). It needs a scraper or Ollama probe and has no consumer yet; a strategy that declares it gets its own spec first.
- Freshness of the corroboration store (age of the newest corroboration). A quiet week is not an outage; Source Silence (OPS-058) already alerts on silent sources.
- STR-024 (ticker and source types on the live corroboration record), the other half of the 2026-10-10 FLAG.
- Changing the runtime's client, its poll interval or what it does with the answer (STR-022 stays as it is).
- Any change to `/actuator/health` or the compose health checks.

## Constraints

- STR-022 and STR-023 ([docs/strategy/runtime.md](../docs/strategy/runtime.md)): the answer shape is fixed by the runtime's client; key names are the `InputSource` values exactly.
- HUB-041 (GET needs no token), HUB-049 (JSON error body, no stack trace), HUB-051 (actuator stays as it is) in [docs/core-hub/http-api.md](../docs/core-hub/http-api.md).
- RES-012 changes as stated under Docs impact; RES-011 and the metric catalogue in [docs/operations/observability.md](../docs/operations/observability.md) do not.
- INV-2: the endpoint only reads. INV-15: test-first.
- core-hub must not read MinIO or the price snapshots for this: the price service already owns the session count, and a second implementation of the NYSE calendar in Java would drift.
- The 404 handler must not swallow other errors: any other unhandled exception still answers 500 and is still logged at `ERROR`.
- Trap: the price check must not block on the price service's refresh. `POST /prices/refresh` can run for minutes and holds one of the price service's two gunicorn threads (`services/backtesting/config/gunicorn.conf.py`); `GET /health` answers on the other, so the check must call only `GET /health` and keep to its timeout.

## Required tests

Write these first and watch each fail for the right reason (ENG-001).

core-hub, unit (`services/core-hub/src/test/java/dev/auspex/corehub/health/InputHealthServiceTest.java`):
- `reportsCorroborationStoreUpWhenPostgresIsUp` and `reportsCorroborationStoreDownWhenPostgresIsDown` (HUB-new)
- `reportsGraphQueryDownWhenNeo4jIsDown` (HUB-new)
- `reportsPriceDataUpWithinTheMissedSessionLimit` and `reportsPriceDataDownPastTheMissedSessionLimit`, the limit itself counting as `UP` (HUB-new)
- `reportsPriceDataDownWhenThePriceServiceTimesOutOrAnswersNon200` (HUB-new)
- `reportsPriceDataDownWhenSessionsSinceSuccessIsMissing` (HUB-new)
- `leavesExtractionModelOutOfTheAnswer` (HUB-new)
- `oneFailingCheckDoesNotFailTheOthers` (HUB-new)

core-hub, integration (`services/core-hub/src/integrationTest/java/dev/auspex/corehub/rest/InputHealthIT.java`, Testcontainers Postgres and Neo4j, the price service stubbed):
- `test_input_health_answers_the_shape_the_strategy_runtime_reads` — 200, `{"inputs": {...}}` with exactly the keys `corroboration_store`, `graph_query`, `price_data`, values `UP` or `DOWN` (STR-023, HUB-new)
- `test_input_health_needs_no_token` (HUB-041)
- `test_unknown_path_answers_404_json_without_stack_trace` — body has message and status 404, no `stack_trace`, no `ERROR` log line (HUB-new, HUB-049)
- `test_unhandled_exception_still_answers_500` — the catch-all keeps working (HUB-049)

Price service, unit (`services/backtesting/tests/unit/test_price_api.py`):
- `test_health_reports_sessions_since_success` — equals `PriceRefreshMetrics.sessions_since_success()` for the same clock (RES-012)

Cross-service contract (`services/strategy/tests/unit/test_runtime_components.py`):
- `test_runtime_reads_core_hub_input_health_fixture` — a JSON fixture of core-hub's answer, the same file the core-hub IT asserts against (`services/core-hub/src/integrationTest/resources/input-health-sample.json`, read by path from the strategy test), parsed by `HttpInputHealthClient` gives `corroboration_store` and `price_data` healthy and `extraction_model` unhealthy (STR-022, STR-023)

## Definition of done

```bash
(cd services/core-hub && ./gradlew test --tests '*InputHealthServiceTest' --rerun-tasks) && grep -h -o 'tests="[0-9]*"' services/core-hub/build/test-results/test/TEST-*InputHealthServiceTest.xml
(cd services/backtesting && uv run pytest tests/unit/test_price_api.py -q | tail -1)
(cd services/strategy && uv run pytest tests/unit/test_runtime_components.py -q -k input_health | tail -1)
python3 -m tools.docs_check
```

Expected: `tests="9"`; `N passed` with 0 failed for both pytest runs; docs check clean. `InputHealthIT` (4 tests) needs Docker and is proven in CI on the PR (cloud sessions have no Docker). On the stack machine after deploy: `curl -s localhost:8080/api/v1/health/inputs` answers the three keys; `curl -s -o /dev/null -w '%{http_code}' localhost:8080/no-such-path` prints `404`; `docker logs --since 10m auspex-strategy-runtime 2>&1 | grep -c 'input health check'` prints `0`.

## Compatibility

- The runtime needs no change and no restart: its next poll gets an answer.
- With the endpoint live, a `paper` strategy pauses only while Postgres is down or prices have missed more than the limit; today none is `paper`, so nothing trades differently.
- The price service's `/health` keeps `status: ok`, so the compose health check (`curl -sf`) and any reader of `status` are unaffected.
- A client that relied on a 500 for unknown paths gets 404; core-hub's only callers in the repo are the dashboard server layer (`services/dashboard/src/lib/bff.ts`) and the strategy runtime, and both call known routes.

## Rollback

Revert the PR. The runtime goes back to logging one error a minute and treating every input as unhealthy, as before.

## Notes

- Why `price_data` asks the price service instead of reading the snapshots: the price service already owns the session count, and Price Refresh Stale alerts on the same number, so the runtime pauses on the same condition the owner is alerted on.
- `sessions_since_success` counts from the price service's start until its first success after a restart, so a fresh price service reports 0 and `UP`. That matches the gauge and is accepted: a restart does not make prices stale.
- Defaults recorded here (owner may change at review): the limit equals the alert's 2 sessions; `extraction_model` is omitted rather than reported `DOWN`; the per-check timeout is 2 s, below the runtime's own.
