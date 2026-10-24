# Observability

Domain: OPS · Code: `docker/grafana/provisioning/`, `docker/prometheus/prometheus.yml`, `docker/elasticsearch/ilm_policy.json`, `docker/filebeat/`, `docker/statsd-exporter/mapping.yml`, `docker/volume-usage/collect.sh`, `services/ingestion-scraper/dags/health_summary.py`, the metric emitters in the catalogue · Last reviewed against: develop @ `b7582c3`

## Scope

How the stack tells its owner it is unwell: the log contract for every service, what is scraped and probed, the one catalogue of metric names, what each alert detects, and the daily health summary.

This file is the only owner of logging for the whole system: what a log line carries and what it must never carry. Other docs link here and state only the fields they add. Logging code conventions that are not behaviour (configure once, at app creation) are in [conventions.md](../engineering/conventions.md).

Not here:
- the scraper's run summary log: [pipeline.md](../ingestion/pipeline.md); core-hub's health reporter (DLT depth and signal age): [http-api.md](../core-hub/http-api.md);
- that nothing may die silently: INV-11; dead-letter naming and headers: [contracts.md](../system/contracts.md);
- thresholds, durations and retention values: the rule YAML and `.env.example`;
- the Grafana panels: the dashboard JSON files; the application's own interface: [dashboard.md](../dashboard.md).

## Requirements

- <a id="OPS-040"></a>**OPS-040** — Every service writes its logs as one JSON object per line with ECS field names (`@timestamp`, `log.level`, `message`). A line about a source document carries `source_type`, and `external_id` or `event_id` where the document has one.
- <a id="OPS-041"></a>**OPS-041** — No log line carries a credential or a document's full `raw_content`.
- <a id="OPS-042"></a>**OPS-042** — Every compose service, one-shots included, uses the one shared logging setting: the `json-file` driver with rotation (`LOG_MAX_SIZE`, `LOG_MAX_FILE`), not the `local` driver, so each container's log on disk has a fixed cap.
- <a id="OPS-043"></a>**OPS-043** — Every compose service carries the label that enables log shipping. Filebeat ships container logs to daily Elasticsearch indices and drops the access lines of healthchecks and probes; `ilm_policy.json` deletes old log indices.
- <a id="OPS-044"></a>**OPS-044** — Every compose service with a healthcheck is scraped by Prometheus or probed by the blackbox exporter.
- <a id="OPS-045"></a>**OPS-045** — The Docker VM is watched without host bind mounts: node-exporter reads the VM through PID 1, cAdvisor reports per-container metrics, and `volume-usage` measures each named volume and hands `auspex_volume_bytes` to node-exporter's textfile collector. Postgres, Kafka and Elasticsearch have their own exporters.
- <a id="OPS-046"></a>**OPS-046** — Prometheus scrapes the Mac's own node_exporter at `host.docker.internal` when it runs. It is optional: its absence raises one info-level alert and nothing else.
- <a id="OPS-047"></a>**OPS-047** — Airflow sends statsd metrics, which `docker/statsd-exporter/mapping.yml` turns into DAG run and task outcome metrics labelled by `dag_id`; everything else Airflow emits is dropped.
- <a id="OPS-048"></a>**OPS-048** — The Postgres exporter logs in as a read-only monitoring role (`POSTGRES_MONITOR_USER`), never as the application owner. MinIO's metrics are open on the compose network only.
- <a id="OPS-049"></a>**OPS-049** — The Elasticsearch exporter reports read-only indices, so a full disk that stops log storage is visible.
- <a id="OPS-050"></a>**OPS-050** — Prometheus' retention is bounded both by time and by size (`PROMETHEUS_RETENTION_TIME`, `PROMETHEUS_RETENTION_SIZE`).
- <a id="OPS-051"></a>**OPS-051** — Grafana is where the stack's technical health is read (services up, errors, CPU, memory, disk of the VM and the Mac); the dashboard service is the interface for using the application.
- <a id="OPS-052"></a>**OPS-052** — The [metric catalogue](#metric-catalogue) below lists every metric Auspex code or configuration names that an alert rule, a provisioned Grafana dashboard or the daily summary reads, with the file that emits it and the rules, dashboards and summary queries that consume it. Other docs link this catalogue instead of listing metric names.
- <a id="OPS-053"></a>**OPS-053** — Renaming a catalogued metric changes the catalogue row, the emitter and every consumer (rules, dashboards, summary queries) in one PR.
- <a id="OPS-054"></a>**OPS-054** — Alerts go to one contact point, `auspex-default`, through one default policy. Its type, email or webhook, comes from `ALERT_CONTACT_TYPE`, and every setting of it comes from `.env` placeholders.
- <a id="OPS-055"></a>**OPS-055** — The provisioned alert rules are exactly those in `## Alert intent` below, and each detects the failure its row names. Thresholds and durations live only in the rule YAML and `.env.example`.
- <a id="OPS-056"></a>**OPS-056** — Every alert rule's expression has a promtool case that makes it fire and a case that keeps it quiet.
- <a id="OPS-057"></a>**OPS-057** — The alerting files reference only environment variables that the Grafana container receives.
- <a id="OPS-058"></a>**OPS-058** — Source Silence reads the scraper's last-run gauge over a lookback window per source, so the last run before a scraper restart still counts, and it treats no data as firing.
- <a id="OPS-059"></a>**OPS-059** — The DAG `auspex_daily_health` sends one summary a day through the alert contact settings (email or webhook). It lists every source in `sources.yaml`: a source with a run in the last 30 days gets a line with its counts and is marked when its last run is older than `STALE_AFTER` in `health_summary.py`; a source with no run in 30 days is listed once as not run. It also reports dead-letter depth, consumer lag, how far the price refresh is behind, container restarts, VM disk, Mac swap, and alerts open now and at their peak.

## Metric catalogue

Exported name is what Prometheus stores; Name in code is the string in the emitter. A histogram's `_bucket`, `_sum` and `_count` series belong to its row.

| Exported name | Name in code | Type | Emitter | Consumers |
|---|---|---|---|---|
| `auspex_pipeline_documents_fetched_total` | `auspex_pipeline_documents_fetched_total` | counter | `services/ingestion-scraper/src/auspex_ingest/metrics.py` | dashboard `pipeline.json`; summary query `fetched` |
| `auspex_pipeline_documents_failed_total` | `auspex_pipeline_documents_failed_total` | counter | `services/ingestion-scraper/src/auspex_ingest/metrics.py` | rule Documents Failed; dashboard `pipeline.json`; summary query `failed` |
| `auspex_pipeline_signals_published_total` | `auspex_pipeline_signals_published_total` | counter | `services/ingestion-scraper/src/auspex_ingest/metrics.py` | dashboard `pipeline.json`; summary query `published` |
| `auspex_llm_extraction_calls_total` | `auspex_llm_extraction_calls_total` | counter | `services/ingestion-scraper/src/auspex_ingest/metrics.py` | rules LLM Extraction Errors, Ollama Down During Extraction; dashboard `pipeline.json` |
| `auspex_llm_extraction_duration_seconds` | `auspex_llm_extraction_duration_seconds` | histogram | `services/ingestion-scraper/src/auspex_ingest/metrics.py` | rule Extraction Slow; dashboard `pipeline.json` |
| `auspex_pipeline_run_duration_seconds` | `auspex_pipeline_run_duration_seconds` | histogram | `services/ingestion-scraper/src/auspex_ingest/metrics.py` | dashboard `pipeline.json` |
| `auspex_pipeline_run_last_timestamp` | `auspex_pipeline_run_last_timestamp` | gauge | `services/ingestion-scraper/src/auspex_ingest/metrics.py` | rule Source Silence; dashboard `pipeline.json`; summary query `last_run` |
| `auspex_dlt_depth` | `auspex.dlt.depth` | gauge | `services/core-hub/src/main/java/dev/auspex/corehub/health/HealthReporter.java` | rule DLT Not Empty; dashboard `pipeline.json`; summary query `dlt_depth` |
| `auspex_source_latest_signal_age_seconds` | `auspex.source.latest.signal.age` | gauge | `services/core-hub/src/main/java/dev/auspex/corehub/health/HealthReporter.java` | rule Source Quiet; dashboard `pipeline.json` |
| `auspex_dlt_events_total` | `auspex.dlt.events.total` | counter | `services/core-hub/src/main/java/dev/auspex/corehub/kafka/CountingDeadLetterRecoverer.java` | rule DLT Backlog; dashboards `errors.json`, `operations.json` |
| `auspex_signals_processed_total` | `auspex.signals.processed.total` | counter | `services/core-hub/src/main/java/dev/auspex/corehub/kafka/SignalListener.java` | dashboard `operations.json` |
| `auspex_corroboration_scan_failures_total` | `auspex.corroboration.scan.failures` | counter | `services/core-hub/src/main/java/dev/auspex/corehub/corroboration/ScheduledCorroborationService.java` | rule Corroboration Scan Failing; dashboard `pipeline.json` |
| `auspex_price_refresh_sessions_since_success` | `auspex_price_refresh_sessions_since_success` | gauge | `services/backtesting/src/auspex_backtesting/price_metrics.py` | rule Price Refresh Stale; dashboard `infrastructure.json`; summary query `price_sessions_behind` |
| `auspex_price_refresh_last_success_timestamp_seconds` | `auspex_price_refresh_last_success_timestamp_seconds` | gauge | `services/backtesting/src/auspex_backtesting/price_metrics.py` | none |
| `auspex_price_refresh_runs_total` | `auspex_price_refresh_runs_total` | counter | `services/backtesting/src/auspex_backtesting/price_metrics.py` | none |
| `auspex_price_tickers_refreshed_total` | `auspex_price_tickers_refreshed_total` | counter | `services/backtesting/src/auspex_backtesting/price_metrics.py` | none |
| `auspex_price_tickers_failed_total` | `auspex_price_tickers_failed_total` | counter | `services/backtesting/src/auspex_backtesting/price_metrics.py` | none |
| `auspex_universe_latest_month` | `auspex_universe_latest_month` | gauge | `services/backtesting/src/auspex_backtesting/price_metrics.py` | rule Universe Month Missing |
| `auspex_strategy_decide_failures_total` | `auspex_strategy_decide_failures` | counter | `services/strategy/src/auspex_strategy/runtime/http.py` | none |
| `auspex_strategy_paused` | `auspex_strategy_paused` | gauge | `services/strategy/src/auspex_strategy/runtime/http.py` | none |
| `auspex_strategy_rejected_events_total` | `auspex_strategy_rejected_events` | counter | `services/strategy/src/auspex_strategy/runtime/http.py` | none |
| `auspex_volume_bytes` | `auspex_volume_bytes` | gauge | `docker/volume-usage/collect.sh` | dashboard `infrastructure.json` |
| `airflow_dagrun_duration_seconds` | `airflow_dagrun_duration_seconds` | summary | `docker/statsd-exporter/mapping.yml` | rule Airflow DAG Run Failed; dashboard `infrastructure.json` |
| `airflow_task_start_total` | `airflow_task_start_total` | counter | `docker/statsd-exporter/mapping.yml` | rule Ollama Down During Extraction |
| `airflow_task_finish_total` | `airflow_task_finish_total` | counter | `docker/statsd-exporter/mapping.yml` | rule Ollama Down During Extraction |
| `airflow_task_failures_total` | `airflow_task_failures_total` | counter | `docker/statsd-exporter/mapping.yml` | none |

Metrics named by a third-party exporter or library keep their upstream names and are not catalogued: `up` and `probe_success` (Prometheus, blackbox exporter), `node_*` (node-exporter, VM and Mac), `container_*` (cAdvisor), `kafka_consumergroup_lag` (kafka-exporter), `kafka_consumer_fetch_manager_records_lag` (core-hub's Kafka client, through Micrometer), `elasticsearch_*` (elasticsearch-exporter) and `grafana_alerting_alerts` (Grafana).

## Alert intent

| Rule title | Detects |
|---|---|
| Probe Target Down | A probed service (HTTP or TCP) fails its health probe |
| Mac Host Exporter Down | The Mac's own exporter is unreachable, so Mac CPU, memory and disk are unwatched (info only) |
| Docker Disk Low | The VM disk that holds the volumes is running out of space |
| Mac Disk Low | The Mac's disk is running out of space |
| VM Memory High | The Docker VM is close to its memory cap |
| Container Restarting | A container keeps restarting, for example killed at its memory limit |
| Airflow DAG Run Failed | A DAG run failed, including a DAG's first failure |
| Price Refresh Stale | The price snapshots have missed NYSE sessions without a fully successful refresh |
| Ollama Down During Extraction | The host model server is unreachable while an extraction run is in progress |
| DLT Backlog | Records are being dead-lettered at a high rate |
| Source Silence | A source has had no completed ingestion run for too long, also across a scraper restart |
| Kafka Lag Critical | core-hub is falling behind on `auspex.signals.extracted` |
| Scrape Target Down | A Prometheus scrape job other than the Mac exporter and the probes cannot be scraped |
| LLM Extraction Errors | A large share of extraction calls fail |
| Documents Failed | A source had documents fail during archive, extraction or publish |
| Source Quiet | A source has stored no signal for too long, though its runs complete |
| Extraction Slow | The p95 extraction time is above its threshold |
| Raw Topic Lag | core-hub's raw audit is falling behind on `auspex.raw.ingested` |
| DLT Not Empty | A dead-letter topic holds records that were not replayed |
| Elasticsearch Unhealthy | Elasticsearch is red or has a read-only index, so logs are not stored |
| Corroboration Scan Failing | The scheduled corroboration scan failed |
| Universe Month Missing | This month's stock universe has not been built within the first week |

## Machine-readable authorities

| File | Governs | Notes |
|---|---|---|
| `docker/grafana/provisioning/alerting/rules.yaml`, `docker/grafana/provisioning/alerting/infrastructure.yaml` | Alert rules, expressions, durations | OPS-055 to OPS-058; thresholds from `.env.example` |
| `docker/grafana/provisioning/alerting/contactpoints.yaml`, `docker/grafana/provisioning/alerting/policies.yaml` | Contact point and policy | OPS-054 |
| `docker/grafana/provisioning/dashboards/` | The four Grafana dashboards | Consumers in the catalogue |
| `docker/prometheus/prometheus.yml` | Scrape jobs and probes | OPS-044, OPS-046 |
| `docker/elasticsearch/ilm_policy.json`, `docker/filebeat/` | Log index retention, shipping and drop rules | OPS-043 |
| `docker/statsd-exporter/mapping.yml` | Airflow metric names | OPS-047 |
| `.env.example` | Thresholds, retention, log rotation, contact settings | Values never copied here |

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| OPS-040 | requirements §12; `specs/done/centralised-logging.md` [`docker/README.md`] | `services/ingestion-scraper/tests/unit/test_logging.py::test_json_logs_use_ecs_level_and_message_fields`; `services/ingestion-scraper/tests/unit/test_logging.py::test_connector_error_log_includes_source_type_and_external_id`; `services/core-hub/src/test/java/dev/auspex/corehub/kafka/LoggingTest.java::test_signal_listener_mdc_contains_event_id_and_source_type` cover the scraper and core-hub; the backtesting, strategy and backup services are untested | untested |
| OPS-041 | requirements §3.3; requirements §12 | `services/ingestion-scraper/tests/unit/test_logging.py::test_sensitive_field_drop_removes_raw_content`; `services/ingestion-scraper/tests/unit/test_logging.py::test_sensitive_field_drop_removes_api_key_variants`; `services/core-hub/src/test/java/dev/auspex/corehub/kafka/LoggingTest.java::test_log_output_does_not_contain_raw_content_field` | tested |
| OPS-042 | `## 2026-10-10 — Container limits and log rotation — CHOICE — json-file log driver with rotation, not local`; `specs/done/container-limits-and-log-rotation.md` [`docker/CLAUDE.md`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_every_service_uses_the_shared_rotating_log_driver`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_log_rotation_caps_each_container_at_sixty_megabytes` | tested |
| OPS-043 | `specs/done/container-limits-and-log-rotation.md`; `specs/done/centralised-logging.md` [`ilm_policy.json`; `docker/README.md`; `docker/CLAUDE.md`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_every_service_is_labelled_for_log_shipping`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_filebeat_drops_healthcheck_access_lines`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_log_indices_are_deleted_after_thirty_days` | tested |
| OPS-044 | `specs/done/infrastructure-observability.md`; `## 2026-10-10 — Infrastructure observability — CHOICE — dashboard memory limit and health probe` [`docker/CLAUDE.md`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_every_compose_service_with_a_healthcheck_is_scraped_or_probed` | tested |
| OPS-045 | `## 2026-10-09 — Infrastructure observability — CHOICE — VM and volume metrics without host bind mounts`; `specs/done/infrastructure-observability.md` [`docker/README.md`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_volume_usage_reports_each_mounted_volume_in_bytes`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_volume_usage_mounts_every_named_volume` | tested |
| OPS-046 | `specs/done/infrastructure-observability.md` [`docker/README.md`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_mac_host_job_targets_host_docker_internal_node_exporter`; `services/ingestion-scraper/tests/unit/test_stack_alert_expressions.py::test_alert_expressions_fire_on_their_failure_and_stay_quiet_otherwise` | tested |
| OPS-047 | `specs/done/infrastructure-observability.md` [`services/ingestion-scraper/tests/unit/test_stack_observability_config.py`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_airflow_statsd_is_enabled_and_mapped_to_dag_outcome_metrics` | tested |
| OPS-048 | `## 2026-10-09 — Infrastructure observability — CHOICE — monitoring role from a one-shot, not an init script`; `specs/done/infrastructure-observability.md` [`services/ingestion-scraper/tests/unit/test_stack_observability_config.py`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_exporter_credentials_are_a_monitoring_role_not_the_app_owner`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_minio_metrics_are_public_on_the_internal_network_only` | tested |
| OPS-049 | `## 2026-10-10 — Pipeline alerting gaps — CHOICE — Elasticsearch read-only indices from the exporter` [`services/ingestion-scraper/tests/unit/test_stack_observability_config.py`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_elasticsearch_exporter_reports_read_only_indices` | tested |
| OPS-050 | `specs/done/container-limits-and-log-rotation.md`; `specs/done/infrastructure-observability.md` [`docker/README.md`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_prometheus_retention_is_bounded_by_time_and_size` | tested |
| OPS-051 | `## 2026-10-08 — Control-surface scoping — CHOICE — Grafana for technical health, dashboard for using the application` | a division of roles; nothing to test | untested |
| OPS-052 | `specs/done/metrics.md`; `specs/done/pipeline-alerting-gaps.md` [`docker/README.md`; design §2] | the `metric_catalogue_covers_every_metric_alerts_and_summary_read` and `catalogued_metric_names_exist_in_their_emitters` scripts in the operations spec's definition of done; not in CI | untested |
| OPS-053 | `## 2026-10-22 — Living docs — PENDING — operations ratification batch`, approved by `## 2026-10-24 — Living docs — CHOICE — operations ratification batch` [design §2] | — | untested |
| OPS-054 | `specs/done/infrastructure-observability.md` [`contactpoints.yaml`, `policies.yaml`; `docker/README.md`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_contact_point_and_default_policy_are_provisioned`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_contact_point_settings_come_from_env_placeholders` | tested |
| OPS-055 | `## 2026-10-09 — Infrastructure observability — CHOICE — alert definitions the spec left open`; `specs/done/infrastructure-observability.md`; `specs/done/pipeline-alerting-gaps.md` [`rules.yaml`, `infrastructure.yaml`; `docker/README.md`] | each rule's firing and quiet cases in `services/ingestion-scraper/tests/unit/test_stack_alert_expressions.py::test_alert_expressions_fire_on_their_failure_and_stay_quiet_otherwise`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_alert_rules_exist_for_target_down_disk_memory_restarts_dag_failure_and_price_refresh` | tested |
| OPS-056 | `specs/done/infrastructure-observability.md`; `specs/done/pipeline-alerting-gaps.md` [`docker/CLAUDE.md`; `services/ingestion-scraper/tests/unit/test_stack_alert_expressions.py`] | `services/ingestion-scraper/tests/unit/test_stack_alert_expressions.py::test_every_new_alert_has_a_promtool_case`; `services/ingestion-scraper/tests/unit/test_stack_alert_expressions.py::test_alert_expressions_fire_on_their_failure_and_stay_quiet_otherwise` | tested |
| OPS-057 | `specs/done/infrastructure-observability.md`; `## 2026-10-09 — Infrastructure observability — VERIFIED — Grafana expands environment variables in alert provisioning` [`services/ingestion-scraper/tests/unit/test_stack_observability_config.py`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_alert_expressions_reference_only_env_vars_grafana_receives` | tested |
| OPS-058 | `## 2026-10-10 — Pipeline alerting gaps — CHOICE — Source Silence reads the last run over 7 days, and no data alerts` | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_source_silence_counts_missing_data_as_alerting`; `services/ingestion-scraper/tests/unit/test_stack_alert_expressions.py::test_source_silence_fires_when_the_run_gauge_has_been_missing_for_thirty_hours` | tested |
| OPS-059 | `## 2026-10-10 — Pipeline alerting gaps — CHOICE — which sources the daily summary lists`; `specs/done/pipeline-alerting-gaps.md`; requirements §12 [`health_summary.py`; `docker/README.md`] | `services/ingestion-scraper/tests/unit/test_daily_health_summary.py::test_daily_summary_lists_every_live_source_with_its_counts`; `services/ingestion-scraper/tests/unit/test_daily_health_summary.py::test_daily_summary_marks_a_source_without_a_run_in_twenty_six_hours`; `services/ingestion-scraper/tests/unit/test_daily_health_summary.py::test_summary_is_emailed_to_every_address`; `services/ingestion-scraper/tests/unit/test_daily_health_summary.py::test_summary_is_posted_to_the_webhook`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_daily_health_summary_reaches_prometheus_and_the_alert_contact` | tested |

"design §2" is a section of `specs/done/living-docs-cutover-design.md`. A bracketed Source part is where the text came from; the part before it is the approval.

## Known traps

- Grafana expands `$VAR` in provisioned alerting files (rules, annotations, contact points) after splitting on `$$`. A literal `$`, as in `{{ $labels.x }}` or a PromQL `$1`, must be written `$$`, or it silently becomes empty (OPS-057). (from `CLAUDE.md`, Known traps; `docker/CLAUDE.md`; `## 2026-10-09 — Infrastructure observability — VERIFIED — Grafana expands environment variables in alert provisioning`)
- `make_metrics()` in the scraper is cached per registry: the API builds a pipeline per request, and registering the collectors twice on one registry raises `DuplicateTimeseries`. Other docs link this item. (from `CLAUDE.md`, Known traps)
- The scraper's run gauge lives only in the scraper process and vanishes on a restart, so an alert or summary that reads it directly forgets every source that has not run since. Source Silence and the summary read it over a lookback window (OPS-058, OPS-059).

## Rationale

- The failure mode to watch for is fewer or wrong corroborations while every container stays green; health checks alone do not see it. (requirements §12)
- A connector that returns empty result sets looks like a quiet week, which is why Source Silence (no runs) and Source Quiet (runs, but no signals) are separate rules. (requirements §12)
- The daily summary arriving is itself the check: when it does not come, the stack or the Mac is down, which no alert running on that stack can report. (from `docker/README.md`)
- One metric catalogue rather than one per emitting domain, because a rename must change emitter, alerts, dashboards and summary together (design §2).

## Retired requirements

None.
