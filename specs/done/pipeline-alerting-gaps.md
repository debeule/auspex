# Pipeline alerting gaps

**Status:** done
**Branch:** `feature/pipeline-alerting-gaps`

---

## Context

Grafana alert rules are provisioned from `docker/grafana/provisioning/alerting/` (`rules.yaml` for the pipeline, `infrastructure.yaml` for hosts and containers). Infrastructure observability adds a contact point (email or webhook from `.env`), a notification policy that re-sends a firing alert every 4 hours, exporters for Kafka, Postgres, Elasticsearch, cAdvisor, node and blackbox probes, Airflow statsd metrics, and tests that evaluate alert expressions (`services/ingestion-scraper/tests/unit/test_stack_alert_expressions.py`). It already alerts on disk, VM and Mac memory, container restarts, failed DAG runs, stale prices and the model server being down during extraction.

The scraper exports `auspex_pipeline_documents_fetched_total`, `_documents_failed_total`, `_signals_published_total`, `auspex_llm_extraction_calls_total`, `auspex_llm_extraction_duration_seconds` and the gauge `auspex_pipeline_run_last_timestamp`, all per `source_type` (`services/ingestion-scraper/src/auspex_ingest/metrics.py`). core-hub exports `auspex_dlt_events_total` and the Kafka client metrics.

Requirements: `docs/requirements.md` §3 rule 12 (DLT depth and per-source signal age are reported), §12 (a `@Scheduled` health reporter in core-hub logs DLT depth per topic and per-source age of the latest signal; "a connector that silently started returning empty result sets is otherwise indistinguishable from a quiet week").

Found by the soak-test readiness audit (2026-10-09):
1. `Source Silence` fires when a source hasn't run for 6 hours, but every source runs once a day, so it is true about 18 hours a day for every source. The 4-hour repeat turns that into several emails a day. The gauge it reads lives only in the scraper process; after a restart it is absent and `noDataState: OK` hides a source that has stopped.
2. The §12 health reporter doesn't exist.
3. No alert sees: a run that completed with failed documents; a source publishing nothing for days; extraction getting slower; lag on `auspex.raw.ingested`; Elasticsearch red or its indices read-only (the blackbox probe gets HTTP 200 either way); the corroboration scan throwing; the month's universe not built by day 7; or the whole stack being down (Grafana itself sends alerts, so nothing is sent).

## What this builds

- **Source Silence** fires when a source has had no completed run for 30 hours, and also when the gauge has been missing for 30 hours (no data counts as alerting after the pending period), so a scraper restart is fine but a stopped source is not.
- **core-hub health reporter (§12)**: a `@Scheduled` job (every 5 minutes) that logs and exports `auspex_dlt_depth{topic}` (end offset minus the replay group's committed offset, or minus the earliest retained offset when the replay group has none) and `auspex_source_latest_signal_age_seconds{source_type}` read from Postgres, so the age survives restarts of any service.
- **New rules**, each with a threshold from `.env` where it is a judgement call:
  - `Documents Failed`: any increase of `auspex_pipeline_documents_failed_total` for a source over 24 hours.
  - `Source Quiet`: `auspex_source_latest_signal_age_seconds` above `ALERT_SOURCE_QUIET_DAYS` (default 5).
  - `Extraction Slow`: p95 of `auspex_llm_extraction_duration_seconds` over 1 hour above `ALERT_EXTRACTION_P95_SECONDS`.
  - `Raw Topic Lag`: consumer lag on `auspex.raw.ingested` above 1,000 for 15 minutes.
  - `DLT Not Empty`: `auspex_dlt_depth` above 0 for 1 hour (alongside the existing increase-based `DLT Backlog`).
  - `Elasticsearch Unhealthy`: cluster status red, or any index with a read-only block.
  - `Corroboration Scan Failing`: increase of a new `auspex_corroboration_scan_failures_total` counter.
  - `Universe Month Missing`: on day 8 or later of a month, the price-service metric for the latest stored universe month is not the current month.
- **Daily health summary**: an Airflow DAG `auspex_daily_health` (07:00 UTC) asks Prometheus' HTTP API for the numbers below and sends one email or webhook through the same contact settings as Grafana: per source the last successful run, documents fetched, published and failed in 24 hours; DLT depth; consumer lag; price refresh state; container restarts; VM disk free and growth since yesterday; Mac swap; alerts fired and still open. When it doesn't arrive, the stack or the Mac is down.

## Out of scope

- Fixing the failures these rules detect (`specs/ingestion-run-reliability.md`, `specs/done/dead-letter-recovery.md`).
- Paging, on-call routing or a second contact point.
- Dashboard panels beyond adding the new metrics to the existing pipeline dashboard.

## Constraints

- Invariant 2: the health reporter only reads Postgres and Kafka offsets.
- Invariant 3: the summary DAG calls HTTP APIs (Prometheus) and formats the result; it reads no service's database. Its formatting lives in a module tested without Airflow.
- Invariant 6: thresholds, SMTP and webhook settings come from `.env`, added to `.env.example` in its existing grouping.
- Invariant 12: the health reporter's queries are parameterized (ArchUnit).
- Every rule has a test that evaluates its expression against sample series: one that fires and one that stays quiet.

## Required tests

Alert expressions (`services/ingestion-scraper/tests/unit/test_stack_alert_expressions.py`):
- `test_source_silence_stays_quiet_within_a_day_of_the_last_run`
- `test_source_silence_fires_after_thirty_hours_without_a_run`
- `test_source_silence_fires_when_the_run_gauge_has_been_missing_for_thirty_hours`
- `test_documents_failed_fires_on_any_failed_document_in_a_day`
- `test_source_quiet_fires_after_the_configured_days_without_a_signal`
- `test_extraction_slow_fires_above_the_configured_p95`
- `test_raw_topic_lag_fires_above_one_thousand`
- `test_dlt_not_empty_fires_after_an_hour_of_depth`
- `test_elasticsearch_unhealthy_fires_on_red_or_read_only`
- `test_corroboration_scan_failing_fires_on_any_failure`
- `test_universe_month_missing_fires_from_day_eight`

core-hub unit (`./gradlew test`):
- `healthReporterExportsDltDepthPerTopic`
- `healthReporterExportsSignalAgePerSourceFromPostgres`
- `corroborationScanFailureIncrementsTheCounter`

core-hub integration (`./gradlew integrationTest`):
- `signalAgeIsReadFromTheSignalTableAfterARestart`

price-service unit (`services/backtesting/tests/unit/`):
- `test_metrics_report_the_latest_stored_universe_month`

Daily summary (`services/ingestion-scraper/tests/unit/`):
- `test_daily_summary_lists_every_live_source_with_its_counts`
- `test_daily_summary_marks_a_source_without_a_run_in_twenty_six_hours`
- `test_daily_summary_dag_runs_once_a_day_at_seven_utc`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit -q --strict-markers && uv run ruff check . && uv run mypy src && cd ../..
cd services/backtesting && uv run pytest tests/unit -q --strict-markers && cd ../..
cd services/core-hub && ./gradlew test --rerun-tasks && ./gradlew integrationTest --rerun-tasks
bash docker/grafana/test_provisioning.sh
```

Expected: every suite passes with the 19 new tests among them; the Grafana provisioning test passes; CI green on the PR (integration tests run in CI only). On the stack (picked up by `specs/first-run-on-stack-machine.md` step 8): Grafana lists every new rule as normal, and the first `auspex_daily_health` run delivers its message.

## Notes

- A rule that fires every day is worse than no rule: it teaches the reader to ignore the inbox. Each rule's quiet test uses a normal day's series.
- `DLT Backlog` (increase over 1 hour) stays: it says something just failed; `DLT Not Empty` says something failed and nobody replayed it.
