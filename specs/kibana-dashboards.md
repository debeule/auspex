# Kibana Operational Dashboards

**Status:** ready
**Blocked by:** [Centralised logging](centralised-logging.md) — Elasticsearch must be populated with ECS-structured logs before dashboards are meaningful
**Branch:** `feature/kibana-dashboards`

---

## Context

Kibana is already in the compose stack from the logging spec. The logging spec scopes only: ILM policy, basic index pattern, and verifying that log events arrive. It explicitly defers dashboards and alerting. This spec delivers the operational UI.

ELK (Elasticsearch + Filebeat + Kibana) is the canonical enterprise Java logging stack — the setup a new hire would recognise immediately at Netflix, Booking.com, or any large Java shop. The operational workflow is: Discover for ad-hoc queries, Dashboards for monitoring, Alerting for automated notification. That is what this spec builds.

Everything here is delivered as version-controlled Kibana saved objects (NDJSON files in `docker/kibana/objects/`), imported automatically by an extended `docker/kibana/setup.sh`. A fresh `docker compose up` followed by `setup.sh` gives a fully configured Kibana with no manual steps.

The fields this spec depends on are defined in the logging spec:
- `@timestamp`, `log.level`, `service.name`, `message` — ECS standard
- `auspex.source_type`, `auspex.event_id`, `auspex.external_id`, `auspex.run_id` — custom namespace
- `auspex.run.fetched`, `auspex.run.published`, `auspex.run.failed`, `auspex.run.not_signal`, `auspex.run.prefiltered_out`, `auspex.run.max_published_date` — emitted by `IngestionPipeline` on run completion
- `auspex.topic` — bound when logging DLT routing events in core-hub

## What this builds

### 1. Saved searches

Five saved searches in `docker/kibana/objects/saved-searches.ndjson`, usable from Discover and embeddable in dashboards:

| Name | Query | Purpose |
|---|---|---|
| `auspex: DLT events` | `auspex.topic: *.dlt` | All dead-letter events — the first thing to check on a bad run |
| `auspex: pipeline run summaries` | `auspex.event_type: run_summary` | One log event per source per run; carries all `RunResult` counters |
| `auspex: extraction errors` | `service.name: ingestion-scraper AND log.level: ERROR` | Connector failures, LLM errors, publish failures |
| `auspex: signal consumer errors` | `service.name: core-hub AND log.level: ERROR` | Deserialization failures, store write failures, schema version mismatches |
| `auspex: rate limit events` | `auspex.event_type: rate_limit_hit` | When `RateLimitedClient` sleeps — signals connector is at capacity |

### 2. Lens visualizations

Six visualizations in `docker/kibana/objects/visualizations.ndjson`:

| Name | Type | Data |
|---|---|---|
| `auspex: signals published by source` | Stacked bar (time) | `auspex.run.published` sum, split by `auspex.source_type`, last 7 days |
| `auspex: extraction failure rate` | Line (time) | `auspex.run.failed / auspex.run.fetched` ratio per source, last 7 days |
| `auspex: DLT events by topic` | Bar (time) | Count of DLT log events grouped by `auspex.topic`, last 24h |
| `auspex: published vs not_signal` | Donut | `auspex.run.published` vs `auspex.run.not_signal` totals, last 7 days |
| `auspex: per-source last run` | Data table | Max `@timestamp` grouped by `auspex.source_type`, filtered to `run_summary` events |
| `auspex: error log count by service` | Metric | Count of `log.level: ERROR` events per service, last 1 hour |

### 3. Dashboards

**"Auspex Operations"** (`docker/kibana/objects/dashboard-operations.ndjson`)

Three panels, top to bottom:

**Row 1 — Current state (last 24 h)**
- Signals published total (metric)
- DLT events total (metric, red if > 0)
- Error log count (metric, red if > 0)
- Per-source last run table

**Row 2 — Pipeline volume (last 7 days)**
- Signals published by source (stacked bar)
- Extraction failure rate (line)

**Row 3 — Error detail**
- DLT events by topic (bar)
- Error log count by service (metric)

Links from the dashboard to the relevant saved searches (Kibana's "Inspect" → opens Discover filtered to the panel's query).

**"Auspex Error Drill-Down"** (`docker/kibana/objects/dashboard-errors.ndjson`)

Focused view for incident investigation:
- DLT events table (full columns: `@timestamp`, `auspex.topic`, `auspex.event_id`, `auspex.source_type`, `message`)
- Extraction errors table (`@timestamp`, `auspex.source_type`, `auspex.external_id`, `message`, `error.type`)
- Signal consumer errors table (`@timestamp`, `auspex.event_id`, `log.logger`, `message`, `error.type`)

### 4. Alert rules

Three rules in `docker/kibana/objects/alert-rules.ndjson`. All use the **Kibana Server Log** action connector (built-in, requires no external configuration). Notifications via email or Slack belong in the watchlist-alerts spec.

| Rule | Condition | Check interval |
|---|---|---|
| `auspex: DLT backlog` | Any `auspex.topic: *.dlt` log event in the last 60 minutes | Every 15 min |
| `auspex: source silence` | No `auspex.event_type: run_summary` for a given `auspex.source_type` in the last 6 hours | Every 30 min |
| `auspex: error spike` | More than 10 `log.level: ERROR` events in any 5-minute window | Every 5 min |

These are operational alerts — pipeline health, not signal quality. User-facing signal alerts are out of scope (watchlist-alerts spec).

### 5. `docker/kibana/setup.sh` extension

The logging spec creates `setup.sh` for the ILM policy. This spec extends it to also import all saved objects:

```bash
# Import saved objects (idempotent: --overwrite replaces existing)
curl -sf -X POST "http://localhost:5601/api/saved_objects/_import?overwrite=true" \
  -H "kbn-xsrf: true" \
  --form file=@docker/kibana/objects/saved-searches.ndjson
# ... repeat for each NDJSON file
```

The script waits for Kibana's health endpoint before importing (`until curl -sf http://localhost:5601/api/status`).

### 6. `docker/kibana/setup.sh` as a compose init container

Add a short-lived `kibana-setup` service to docker-compose that runs `setup.sh` and exits:

```yaml
kibana-setup:
  image: curlimages/curl:latest
  depends_on:
    kibana:
      condition: service_healthy
  volumes:
    - ./kibana:/kibana:ro
  command: /kibana/setup.sh
  restart: "no"
```

This removes the need to run `setup.sh` manually after first `up`.

## Out of scope

- Metrics (CPU, memory, JVM heap) — requires Metricbeat or Spring Boot Actuator + Prometheus. Separate concern.
- Distributed tracing — requires OpenTelemetry. Separate concern.
- User-facing signal alerts (email/Slack when a corroborated signal appears) — watchlist-alerts spec.
- Kibana security / user accounts / role-based access — not needed for local prod-sim.
- Custom index templates or mappings — ECS with dynamic mapping is sufficient; `auspex.*` fields are indexed automatically.

## Constraints

- Saved objects are tied to the Kibana version. The NDJSON export must be done against the pinned `ELASTIC_VERSION`. If `ELASTIC_VERSION` is bumped, re-export all saved objects and commit the updated NDJSON files.
- Saved objects must be built in Kibana first (manually), then exported via `Stack Management → Saved Objects → Export`, and committed. Do not hand-craft NDJSON — Kibana's internal format has undocumented fields that must be present.
- `docker/kibana/setup.sh` must be idempotent. Running it twice against a live Kibana must not error or duplicate objects (`?overwrite=true` handles this).
- Alert rules use **Kibana Server Log connector** only. No external connectors (email, Slack, PagerDuty) — those require credentials and are a deployment concern.
- The `auspex.event_type: run_summary` field must be emitted by the logging spec's `IngestionPipeline` log event. Verify this field name matches exactly before building the saved searches — a mismatch produces a saved search that returns no results silently.
- All time ranges in dashboards default to "Last 7 days". Do not pin to absolute dates — saved objects with absolute dates break immediately.

## Required tests

These are integration smoke tests against a running compose stack, not unit tests. Application logic is tested in each service's own suite; this spec tests the Kibana layer.

**`docker/kibana/test_setup.sh`** — shell assertions run after `setup.sh`:

- Assert HTTP 200 from `GET /api/saved_objects/_find?type=dashboard` and confirm `"auspex: operations"` in response
- Assert HTTP 200 from `GET /api/saved_objects/_find?type=search` and confirm all 5 saved search titles present
- Assert HTTP 200 from `GET /api/alerting/rules/_find` and confirm 3 rule names present

**`tests/integration/test_kibana_dashboards.py`** — Python integration test using `elasticsearch-py` client:

- `test_auspex_logs_index_exists_after_pipeline_run` — after running one source via `scripts/run_pipeline.py`, the `auspex-logs-*` index exists and has > 0 documents
- `test_run_summary_event_has_required_fields` — query for `auspex.event_type: run_summary`; assert `auspex.source_type`, `auspex.run.published`, `auspex.run.fetched` are present on at least one document
- `test_no_sensitive_fields_in_any_log_document` — query 100 most recent documents; assert none contain `raw_content`, `api_key`, `access_key`, `secret_key` at any path

## Definition of done

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d --wait
# kibana-setup container runs automatically and exits 0
docker compose logs kibana-setup | grep "Setup complete"
```

Then manually:
1. Open `http://localhost:5601` → Dashboards → "Auspex Operations". Dashboard loads with no errors.
2. Run one source: `cd services/ingestion-scraper && uv run python scripts/run_pipeline.py --sources biorxiv --days 1`
3. Refresh dashboard. "Per-source last run" table shows `biorxiv` with a recent timestamp. "Signals published by source" bar chart shows at least one bar.
4. Open Discover → select `auspex: pipeline run summaries` saved search → at least one document appears.
5. Open Stack Management → Alerts → three alert rules are present and enabled.

```bash
cd services/ingestion-scraper && uv run pytest tests/integration/test_kibana_dashboards.py -v -m integration
```

All pass.

## Notes

- **Build the dashboards manually first, then export.** The correct workflow: bring up the compose stack, run the pipeline for a few sources to populate data, build the saved searches and visualizations in Kibana's UI, then export via Stack Management → Saved Objects → Export all. Commit the NDJSON. This is not optional — hand-crafted NDJSON is fragile and undocumented.
- `curlimages/curl` for the init container is minimal (no shell beyond what curl needs). If `setup.sh` uses bash features, use a different base image (`alpine` with `curl` and `bash` installed). Keep it simple.
- The `auspex: per-source last run` table is the most operationally valuable visualization — it immediately shows whether a source has stopped running. Build this first. If it works, the rest of the dashboard is supporting context.
- Kibana's **Lens** editor (not the legacy Visualize) is the correct tool for all visualizations. Lens saved objects are forward-compatible; legacy visualizations are deprecated.
- `elasticsearch-py` is the official Elasticsearch Python client. Add it to `pyproject.toml` under `[project.optional-dependencies]` dev/test group, not the main dependencies. The scraper service does not use Elasticsearch at runtime.
- Alert rule for source silence is slightly tricky: it needs to check per-`auspex.source_type`, not globally. Use Kibana's "group by" alert condition grouped on `auspex.source_type`. Verify this is available in the pinned Kibana version before committing.
