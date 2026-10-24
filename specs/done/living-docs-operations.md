# Living docs: operations

> Archived. Not authoritative: current behaviour is in docs/ (see docs/README.md).

**Status:** done
**Blocked by:** `docs-check-tooling` and `living-docs-system-and-contracts`, both merged into `feature/living-docs-integration` (INV IDs, `docs/system/contracts.md` and `docs/README.md` must exist before this spec links to them). Decisions: `## 2026-10-15 — Living docs — PENDING — restore exception to invariant 2` (only the wording of INV-2 that `backup.md` links to) and `## 2026-10-15 — Living docs — PENDING — rollout branch model`. The ratification batch this spec appends (`## <date> — Living docs — PENDING — operations ratification batch`, dated the day it is appended) does not block the merge into the integration branch; it blocks the cutover gate.
**Branch:** `feature/living-docs-operations` (from and into `feature/living-docs-integration`)
**Docs impact:** creates `docs/operations/topology.md`, `docs/operations/orchestration.md`, `docs/operations/observability.md` and `docs/operations/backup.md` (namespace OPS, all new IDs). Changes `docs/backup-restore.md` (one link line), `specs/soak-test-run.md` and `specs/first-run-on-stack-machine.md` (Docs impact field, restated rules replaced by IDs), `DECISIONS.md` (one PENDING ratification entry), the `ID` cells of the OPS rows and the `IDs` cells of 19 decisions rows in `specs/living-docs-cutover-matrix.md`, and the `planned_domains` line of `docs-check.toml`. Retires nothing. READMEs, `SETUP.md` and `docs/PREREQUISITES.md` are trimmed later by `legacy-docs-retirement`, not here.

---

## Context

Written against `develop` @ `e51f742`. The rollout design is `specs/living-docs-cutover-design.md`; everything this spec needs from it is restated here.

**Target model.** After cutover, `docs/` is the only prose authority for what the system must do. One file owns each subject. Values stay in machine-readable files; a doc names the file and states only what the file cannot say. Each living doc has this shape:
- first line under the title: `Domain: OPS · Code: <paths> · Last reviewed against: develop @ <sha>`, where the SHA is a commit on `develop`;
- H2 sections in this order: `## Scope`, `## Requirements`, `## Machine-readable authorities`, `## Verification`, `## Known traps`, `## Rationale`, `## Retired requirements` (the checker requires Scope, Requirements, Verification and Retired requirements; the others are used here because operations has traps and authorities);
- every requirement is a list item that starts `<a id="OPS-NNN"></a>**OPS-NNN** — `;
- the `## Verification` table has the columns `| ID | Source | Verified by | Status |`, one row per ID. Status is one of `tested` (Verified by is `path::test_name`), `enforced` (a checker or CI rule), `untested`, `divergent` (the code disagrees with the approved rule; cites a DECISIONS heading) or `pending-decision` (cites a PENDING DECISIONS heading).

The checker (`python3 -m tools.docs_check`, checks A–M, configured in `docs-check.toml`) is defined by `specs/docs-check-tooling.md`.

**Where operations rules live today (all at e51f742):**

| Subject | Where it is stated now | Code and tests that implement it |
|---|---|---|
| Compose services, profiles, ports, one-shots, volumes, limits | `docker/README.md:7-78,113-136`, `docker/CLAUDE.md:13-64`, `SETUP.md:5-30` | `docker/docker-compose.yml` (881 lines: profiles `app` at `:430,480,524,567`, `restore` at `:266`, named volumes `:870-881`); `.env.example`; tests `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py`, `test_stack_observability_config.py`, `test_stack_backup_config.py`, `test_repo_scaffolding.py`, `test_dashboard_stack_config.py`; `services/backtesting/tests/unit/test_stack_bootstrap.py` |
| Build and runtime glue | nowhere | 6 Dockerfiles (`services/{ingestion-scraper,core-hub,backtesting,strategy,backup,dashboard}/Dockerfile`); 3 `gunicorn.conf.py` (`services/{ingestion-scraper,backtesting,backup}/config/`), each `workers = 1`; `test_metrics.py::test_gunicorn_serves_from_one_process_so_metrics_are_not_split_across_workers` covers the scraper only |
| SEC request budget across containers | DECISIONS `## 2026-10-09 — Soak-test readiness — CHOICE — SEC request budget across containers`; `docs/requirements.md` §6.5 says "Configure 5 req/s" | EDGAR `rate_limit_rps: 4.0` in `services/ingestion-scraper/config/sources.yaml:94`; universe lookups `services/backtesting/tests/unit/test_universe_sec_index.py::test_filing_index_lookups_run_at_most_five_per_second`; ownership, filing-panel and catalyst clients are host scripts. No test asserts the sum |
| Airflow DAGs, schedules, pool, retries, cursor storage, Fernet | `docs/requirements.md` §0.2, §5; `orchestration/README.md` (stale: `:3`, `:17`, `:37`); `docker/CLAUDE.md:44-50` | `services/ingestion-scraper/dags/{auspex_dags,daily_health,health_summary}.py`, `services/backtesting/dags/{price_refresh,universe_build}.py`, `services/backup/dags/backup.py`; tests `test_ingestion_dag.py` (14), `test_daily_health_summary.py` (7), `services/backup/tests/unit/test_backup_dag.py`. No test covers the price, universe or backup DAG schedules or their `is_paused_upon_creation=False` |
| Logs, metrics, alerts, health summary | `docs/requirements.md` §3.3 (second sentence), §12; `docker/README.md:148-194`; DECISIONS 2026-10-09/10 Infrastructure observability and Pipeline alerting gaps CHOICEs | `docker/grafana/provisioning/alerting/{rules,infrastructure,contactpoints,policies}.yaml` (22 rules), `docker/prometheus/prometheus.yml`, `docker/elasticsearch/ilm_policy.json`, `docker/statsd-exporter/mapping.yml`; tests `test_stack_alert_expressions.py` (promtool), `test_stack_observability_config.py`, `test_logging.py` |
| Metric emitters | `docker/README.md:192` (a partial list) | `services/ingestion-scraper/src/auspex_ingest/metrics.py`; `services/backtesting/src/auspex_backtesting/price_metrics.py`; core-hub `config/KafkaConfig.java`, `kafka/CountingDeadLetterRecoverer.java`, `kafka/SignalListener.java`, `health/HealthReporter.java`, `corroboration/ScheduledCorroborationService.java` (Micrometer, dotted names such as `auspex.dlt.depth`); `services/strategy/src/auspex_strategy/runtime/main.py`; `docker/volume-usage/collect.sh` (`auspex_volume_bytes`); statsd mapping |
| Backup and retention | `docs/backup-restore.md`, `services/backup/README.md`, DECISIONS `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac` and `## 2026-10-10 — Stack backup — CHOICE — client tools from the server image, memory and restore semantics`; `specs/done/stack-backup.md` | `services/backup/src/auspex_backup/{api,backup,restore,graph,minio_mirror,postgres,prune}.py`; compose `:221-290` (`BACKUP_DATABASES` `:240`, `BACKUP_BUCKETS` `:247`); 20 unit tests under `services/backup/tests/unit/`, 3 integration round trips (CI) |

**Known defects and gaps this spec records but does not fix** (the rollout changes no application code; each is listed in `## 2026-10-15 — Living docs — PENDING — defects found while scoping`):
- **Bucket lists out of step.** `auspex-strategy` is backed up (compose `:247`), but `docker/README.md:23`, `SETUP.md:16` and `VERSIONS.md:18` say two buckets. Worse, nothing ties `BACKUP_BUCKETS` to `stack_bootstrap.stack_buckets()` (`services/backtesting/src/auspex_backtesting/stack_bootstrap.py:35`), so a fourth bucket would silently go unbacked-up. The README and SETUP text is fixed by `legacy-docs-retirement`; here the requirement is written with status `untested`.
- `POST /backup` answers 409 during a run (`services/backup/src/auspex_backup/api.py:33`); no test.
- No alert or summary line fires on a stale backup beyond the generic DAG-failure rule (`specs/done/stack-backup.md:38` deferred it; nothing picked it up).
- Restore pairs dated Postgres and Neo4j copies with the latest, undated MinIO mirror (`docs/backup-restore.md:26-28`). Whether newer processed markers or strategy checkpoints can then suppress work is unanalysed.
- `verify_pipeline.sh` checks two core-hub REST responses (`:9-17`), not the pipeline.
- Nothing in the stack has run on the Mac yet (`specs/first-run-on-stack-machine.md` is blocked). Every OPS status is about tests in CI, never about the stack.

**Runbooks keep their paths.** `docs/backup-restore.md` is cited by `services/backup/src/auspex_backup/restore.py:2`; `docs/local-model-runbook.md` is cited from specs and DECISIONS. Both stay where they are and stay procedures, not requirements.

**Tests that read docs.** `test_stack_persistence_config.py:152` (`test_docs_never_offer_down_v_as_a_fix`) reads `README.md`, `CLAUDE.md`, `SETUP.md`, `docker/README.md`, `docker/CLAUDE.md`. `:159` (`test_new_secrets_are_documented_in_setup`) reads `SETUP.md` and the one line of `specs/first-run-on-stack-machine.md` that starts with `test -f .env && for k in` (`:73`), and asserts ` AIRFLOW_FERNET_KEY `, ` AIRFLOW_JWT_SECRET ` and ` AIRFLOW_SECRET_KEY ` (each with a space on both sides) are in it.

## What this builds

Four living docs under `docs/operations/`, each in the shape given in Context. Links to another domain's doc are file links without an anchor (`docs/ingestion/pipeline.md`, not `…#ING-0NN`), so nothing is left to fill in after the other domains merge.

1. **`docs/operations/topology.md`** owns:
   - the host: one Mac, Docker Desktop's VM capped by `SETUP.md` step 2, the model server on the host reached at `host.docker.internal` through `extra_hosts`, `config/models/` mounted read-only into the scraper;
   - profiles: default (stores, monitoring, price-service, backup, Airflow, one-shots), `app` (scraper, core-hub, strategy-runtime, dashboard), `restore` (restore only);
   - published ports on `127.0.0.1` only; exporters and backup publish none;
   - the configuration surface: compose gives no default to a variable `.env.example` defines; the Airflow secrets and `BACKUP_HOST_DIR` are required `:?` references; credentials are empty in `.env.example`; `.env.example` also configures host scripts (so "every variable is in compose" is not the rule);
   - startup data: each one-shot (`kafka-init`, `minio-init`, `price-bootstrap`, `elasticsearch-setup`, `airflow-db-role`, `airflow-state-init`, `postgres-monitor-role`) is a no-op when its data exists; data that must stay current is a DAG calling a service endpoint; `minio-init` creates every bucket `stack_buckets()` lists. Topic provisioning is not restated: one sentence links the CON requirement in `docs/system/contracts.md` (topics only from `docker/topics.yaml` through `kafka-init`);
   - Postgres: two databases in one container, Airflow's with its own role and no cross-grants;
   - memory: every service has a `mem_limit` from `.env`; the long-running limits sum to at most the VM less 512 MB; one-shots are not counted; Airflow one API worker and a bounded task count; Neo4j heap plus page cache within its limit;
   - disk: every store on the VM disk has a setting that bounds it or an alert and panel that watch it;
   - persistence: every stateful path on a declared named volume, mounted into `volume-usage`; Kafka cluster ID pinned and offsets kept longer than the longest topic retention; project name `auspex`; `down -v` destroys all data and is never a fix;
   - build glue: each image is built from its service directory (6 Dockerfiles); backup's on the Postgres server image so `pg_dump` matches the server major; the scraper, price-service and backup each serve from one gunicorn process with threads;
   - **the combined SEC request budget**: every client that sends requests to a `*.sec.gov` host and can run at the same time as another stays, in sum, under SEC's per-IP limit, with each client's own rate owned elsewhere (EDGAR in `docs/ingestion/connectors.md`; the universe, ownership, filing and catalyst clients in `docs/research/`). The requirement names each client module and the scheduling rule (ownership pulls never overlap EDGAR ingestion);
   - Known traps: Docker Hub anonymous limits and publisher registries in compose (the CI half is in `docs/engineering/verification.md`); Docker Desktop on macOS has no Metal, so the model server runs on the host (owned here only; `docs/ingestion/extraction.md` links it); the Airflow healthcheck takes about a minute; gunicorn metrics are per process.
2. **`docs/operations/orchestration.md`** owns:
   - the DAG catalogue: every DAG (`auspex_<source_type>` per `sources.yaml` entry, `auspex_price_refresh`, `auspex_universe_build`, `auspex_backup`, `auspex_daily_health`), its file, the endpoint it posts to (or Prometheus and the contact point, for the summary), and the owner doc of that endpoint. Schedules are named by file and never copied;
   - rules for every DAG: no logic beyond the call (INV-3); `catchup=False`; `max_active_runs=1`; UTC schedules; which DAGs are active at creation and that ingestion DAGs are paused until a gated model exists;
   - ingestion rules: one DAG per `sources.yaml` entry with no source-specific branching (INV-4); a schedule-less source is never scheduled; live sources start at distinct, spaced times; one-slot `ingestion` pool created before the scheduler starts; retries and their spacing; the HTTP request shares the task timeout;
   - **the DAG side of the cursor**: read `cursor:{source_type}`, defaulting to `initial_lookback` days before now in UTC; post it; on a completed run write the returned `next_cursor` (never "now"), then fail the task if any document failed; on a failed request leave the Variable untouched; the cursor is visible in the Airflow UI. What `next_cursor` is links to `docs/ingestion/pipeline.md`. The rule that a backfill never writes the live cursor is not written here or linked: no living doc holds it yet, and it arrives with `specs/historical-backfill.md` when that spec is built;
   - Fernet: `AIRFLOW_FERNET_KEY`, `AIRFLOW_JWT_SECRET`, `AIRFLOW_SECRET_KEY` are required from `.env`; the same Fernet key is needed after a restore; the admin password file is on the `airflow_state` volume; no Airflow 2 `webserver.*` options;
   - Known traps: Airflow 3 `schedule` rename and Task SDK access; Airflow generates a Fernet key when none is set.
3. **`docs/operations/observability.md`** owns:
   - **the single metric-name catalogue**, under `## Metric catalogue`, one table with the exact header `| Exported name | Name in code | Type | Emitter | Consumers |`. It lists every metric an alert rule, a provisioned dashboard or the daily summary reads, with the file that emits it (path) and the rules, dashboards and summary queries that consume it. Each domain doc links here instead of listing names. A rename changes the catalogue, the consumers and the emitter in one PR;
   - **the log contract, the one owner of logging for the whole system**: structured JSON lines with ECS field names; `source_type`, and `external_id` or `event_id` where applicable; credentials and full `raw_content` are never logged (Source: requirements §3.3, second sentence, and §12); the shared rotating `json-file` driver (not `local`); every service labelled for log shipping; healthcheck access lines dropped; log indices deleted by `ilm_policy.json`. Ingestion and core-hub docs link this contract and state only fields they add; Python and Java logging code conventions that are not behaviour belong to `docs/engineering/conventions.md`;
   - what is watched: every service with a healthcheck is scraped or probed; VM metrics read through PID 1 without host mounts; volume sizes from `volume-usage`; the Mac's own exporter optional, its absence one info alert; Airflow statsd mapped to DAG outcomes; exporters use a read-only monitoring role; Prometheus retention bounded by time and by size; Grafana for stack health, the dashboard for using the application;
   - **alert intent**: one row per provisioned rule title saying what failure it detects. No thresholds or durations: those are in the rule YAML and `.env.example`. Every rule has a promtool firing case and quiet case; alert files reference only variables Grafana receives; one contact point from `ALERT_CONTACT_TYPE`;
   - **the health summary**: `auspex_daily_health` lists every `sources.yaml` source, marks one with no recent run, lists one with no run in 30 days once, reports DLT, lag, price refresh, restarts, disk, swap and alerts, and is delivered through the alert contact settings. Its absence is the signal that the stack or the Mac is down;
   - Known traps: Grafana `$` expansion (write `$$`); `make_metrics()` cached per registry (owned here only; other docs link it); Source Silence must read the run gauge over a lookback because the gauge dies with the scraper process.
   - Links, not text: the scraper's run summary (`docs/ingestion/pipeline.md`), core-hub's health reporter (`docs/core-hub/http-api.md`), INV-11, and dead-letter naming and headers (`docs/system/contracts.md`).
4. **`docs/operations/backup.md`** owns:
   - what is backed up: both Postgres databases in custom format with the password only in the environment, the whole Neo4j graph in one read transaction, an additive mirror of every MinIO bucket the stack creates; what is not, and why (Elasticsearch, Prometheus, Grafana, Kafka);
   - how a run behaves: the nightly DAG posts once and fails on any HTTP error; every store runs even if one failed; `last_success.json` written last and only when all succeeded; 500 naming the failed stores; 409 during a run; the backup only reads the stores; labels allow-listed before they reach Cypher; the mirror refuses a key that escapes its bucket folder;
   - retention: dated Postgres and Neo4j folders strictly older than `BACKUP_KEEP_DAYS` are pruned and the newest never is; the mirror is never pruned and keeps objects deleted from MinIO;
   - **the bucket requirement** ("the mirror covers every bucket `minio-init` creates") with status `untested` and a verification note naming `BACKUP_BUCKETS` (compose `:247`) and `stack_buckets()` (`stack_bootstrap.py:35`) as two lists no test ties together;
   - restore: one sentence and a link to INV-2 in `docs/system/invariants.md` for the approved exception, and a link to the runbook `docs/backup-restore.md`. The exception's conditions (empty stores, app stopped) are not restated;
   - Known traps: the MinIO mirror is undated, so a restore pairs a dated database with the latest mirror.
5. `docs/backup-restore.md` gains one line under its title: "Why and what is backed up: `[docs/operations/backup.md](operations/backup.md)`." (written as a link in the runbook, where the relative path resolves). Nothing else in it changes. `docs/local-model-runbook.md` is not edited.
6. **Active specs this spec owns** (each active spec has exactly one rollout owner; these two are operations'):
   - `specs/soak-test-run.md`: add `**Docs impact:** none — operational acceptance only; cites OPS IDs`; fix the four stale blocker paths (`:4`) to `specs/done/…`; replace restated rules with IDs: the schedule list (`:11`) becomes a reference to the orchestration catalogue ID; "7,680 MB" (`:13`, `:56`) becomes "the long-running memory budget (OPS-0NN; values in `.env.example`)"; the `down -v` ban (`:34`) cites the topology ID; "Invariant 9" (`:35`) becomes INV-9; the commit rule citing root `CLAUDE.md` (`:33`) points at root `AGENTS.md`. Its checks, steps and pass criteria do not change.
   - `specs/first-run-on-stack-machine.md`: add `**Docs impact:** none — operational acceptance only; cites OPS IDs`; "Invariant 6", "Invariant 9" (`:53-54`) become INV-6, INV-9; the commit-identity constraint (`:55`) points at root `AGENTS.md`; the 8 GB fact (`:20`) cites the topology host ID. **The preflight line at `:73` is not edited**, and neither is any other line starting with `test -f .env && for k in`.
   After this, neither spec contains `CLAUDE.md`, so `agent-instruction-hierarchy` has nothing left to change in them.
7. **Ratification batch.** Append to `DECISIONS.md`: `## <date> — Living docs — PENDING — operations ratification batch` (the date it is appended), listing each OPS ID whose only source is code, a README, a `CLAUDE.md` trap or a config comment, with its one-line text and that source. Expected members (matrix rows `M-OPS-114`, `-115`, `-116`, `-118`, `-121`, `-175`, and the `extra_hosts` half of `-081`):
   - non-ingestion DAGs retry and fail on any HTTP error (DAG files; only the backup DAG is tested);
   - the scraper serves from one gunicorn process (root `CLAUDE.md` trap, `gunicorn.conf.py` comment);
   - price-service and backup serve from one gunicorn process (code only);
   - `POST /backup` answers 409 during a run (code, `services/backup/README.md:8`);
   - a catalogued metric is renamed in one PR with its consumers (rollout rule);
   - `.env.example` configures compose and host scripts alike (`.env.example` header comment and the host scripts that read it);
   - the scraper reaches the host model server through `extra_hosts: host-gateway` (compose).
   Each row's Source cell cites, in backticks, the appended heading by its full dated text (so it contains `operations ratification batch`), and has status `pending-decision`. The spec author adds any further code-only rule found while writing and removes one whose source turns out to be an archived spec or a DECISIONS entry. The owner approves by appending `## <date> — Living docs — CHOICE — operations ratification batch`; once that CHOICE exists, `living-docs-cutover` (its decision-application step) flips these rows to their real status. This spec does neither.
8. **Matrix cells** in `specs/living-docs-cutover-matrix.md` (this spec edits only these cells):
   - the `ID` cell of every fragment row whose `NS` column is `OPS` and whose disposition is `move`, `ratify`, `divergent` or `retire`. Each OPS ID written there has a verification `Source` cell that contains that row's document-level source reference: the file path, `requirements §N`, or the DECISIONS heading in the row's Source column (line numbers are not compared; a row whose Source is only a scoping label needs only an existing ID). For a row that targets a `## Known traps` or `## Rationale` section, fill the cell in the form `specs/docs-check-tooling.md` accepts for such rows;
   - the `IDs` cell of each of the 19 decisions-table rows classified `binding` whose `Fragment rows` include an M-OPS row with `NS` `OPS` (fragments `M-OPS-252` … `M-OPS-254`, `-257` … `-260`, `-262` … `-273`). Write the OPS IDs that carry the rule, space-separated, after any IDs another domain already wrote. Each of those OPS IDs has a verification `Source` cell that contains the heading text. Decisions rows owned by another domain (for example `M-OPS-256` → ENG, `M-OPS-275` → STR) are not touched.
9. **Last step: `docs-check.toml`.** Remove `"operations"` from `[rollout] planned_domains`, and change nothing else in the file. From then on, broken links into `docs/operations/` and OPS placeholders are findings, not notices.
10. **Archive this spec in the same PR.** Set `**Status:** done`, move this file to `specs/done/living-docs-operations.md`, and update this spec's own `TODO.md` row (status `done`, link to `specs/done/…`). No other `TODO.md` row is touched.

## Out of scope

- Any change to application code, compose, `.env.example`, alert rules, DAGs or tests. In particular: the test tying `BACKUP_BUCKETS` to `stack_buckets()`, a backup staleness alert, DAG schedule tests and a stronger smoke test are follow-up specs (recommended in Notes, not created here).
- `docs/README.md`: `living-docs-system-and-contracts` writes it in full, including the links to the four operations files. This spec only checks that those links are there.
- Trimming `docker/README.md`, `orchestration/README.md`, `services/backup/README.md`, root `README.md`, `SETUP.md`, `docs/PREREQUISITES.md`, `VERSIONS.md`: `legacy-docs-retirement` does that after this spec merges.
- Extending `test_docs_never_offer_down_v_as_a_fix`: `legacy-docs-retirement`.
- `docker/AGENTS.md`, `docker/CLAUDE.md` and every other agent file: `agent-instruction-hierarchy`.
- The text of INV-2, INV-3, INV-6, INV-11 and their exceptions: `living-docs-system-and-contracts`. Dead-letter naming and headers: `docs/system/contracts.md`. Which failures dead-letter: `docs/core-hub/consumption.md`.
- What `next_cursor` is, the extraction cap and per-connector rates (`docs/ingestion/`); price-service endpoint behaviour and per-client SEC pacing (`docs/research/`); core-hub's health reporter (`docs/core-hub/http-api.md`); pin rules and logging code conventions (`docs/engineering/conventions.md`); CI images (`docs/engineering/verification.md`).
- Approving the ratification batch (the owner appends the CHOICE) and flipping its rows afterwards (`living-docs-cutover`).
- Restore-consistency analysis: recorded as a trap and a Note, not resolved.

## Constraints

- **Invariants.** Nothing here changes behaviour, so no invariant is touched. The docs cite INV-1, INV-2 (backup only reads; restore exception by link), INV-3 (DAGs), INV-4 (one DAG per source entry), INV-6 (secrets from `.env`), INV-9 (UTC schedules and folder names), INV-11 (alerts and summary), INV-12 (Cypher labels), INV-13 (archive) by ID. An exception to an invariant is stated only under the invariant in `docs/system/invariants.md`; `backup.md` links INV-2 and does not restate the restore conditions.
- **Where each requirement comes from.** Every OPS requirement carries a `Source`, in this order of preference: a `docs/requirements.md` § that is still true; a DECISIONS `CHOICE` heading (the binding ones are the decisions-table rows in item 8); an archived spec's requirement or test list; an invariant; an owner ratification. If the only source is code, a README, a `CLAUDE.md` trap or a config comment, the row's Source cell cites the operations ratification batch heading (it contains `operations ratification batch`), with status `pending-decision`. A source that contradicts the code is written as the approved version with status `divergent` and a DECISIONS heading; none is known in OPS at e51f742 (stale README text such as `orchestration/README.md:3,17,37` is not a source and is dropped).
- **Conflicts.** Compose, `.env.example`, alert YAML, `prometheus.yml`, `ilm_policy.json`, the statsd mapping, DAG files and `sources.yaml` win on values. Where a README disagrees with them, the README is wrong. Never edit a doc to match the code without a source from the list above.
- **No copied values.** The four docs name files and variable names, never their values: no memory sizes, thresholds, durations, retention, keep-days, cron strings or clock times. Two named checks below enforce this.
- **`down -v`.** Any line in `docs/operations/*.md` that contains `down -v` also contains `destroys all data`, because `legacy-docs-retirement` adds these files to the guard test.
- **Paths that do not move.** Do not move, rename or delete `SETUP.md`, `VERSIONS.md`, `README.md`, `CLAUDE.md`, `docker/README.md`, `docker/CLAUDE.md`, `docs/backup-restore.md`, `docs/strategy-research.md`, `docs/requirements.md`, `specs/first-run-on-stack-machine.md`, `specs/point-in-time-universe.md`, `specs/sec-ownership-datasets.md`, `specs/clinicaltrials-version-diffs.md`, `specs/catalyst-date-panel.md` (code, tests or hash-locked hypotheses cite them).
- **IDs.** Namespace OPS only. Numbers come from `python3 -m tools.docs_check --next OPS`, sequential in file order: `topology.md`, then `orchestration.md`, `observability.md`, `backup.md`. Each ID is defined once. A reference to another namespace is a file link (see What this builds) or an ID that is already defined on the integration branch; no `NS-?` placeholder is written. Decisions are cited by their full DECISIONS heading text; no decision register number appears in `docs/` or in this spec's edits.
- **`Last reviewed against`** names a commit on `develop` (the integration branch's recorded base), never a feature-branch SHA.
- **Citations in verification cells are in backticks**: paths, `requirements §N` and DECISIONS headings alike; a heading that itself contains backticks (such as the Startup data CHOICE) is cited inside a double-backtick span.
- Every `tested` verification row is `path::name` with a `def name` present in that file (check K). Rows for compose-reading tests point at `services/ingestion-scraper/tests/unit/test_stack_*.py`; these tests live in the scraper package for historical reasons, which the docs say once and do not change.
- **Mutations stay local.** Every deliberate break runs in a disposable worktree under `${TMPDIR:-/tmp}`; nothing broken is committed or pushed.

## Dependencies

- **Needs:** `docs-check-tooling` (checker, `docs-check.toml` with OPS in the namespaces and `operations` in `[rollout] planned_domains`, ownership globs mapping `docker/**`, `**/dags/**`, `services/backup/**`, `**/gunicorn.conf.py`, `**/Dockerfile`, `services/ingestion-scraper/tests/unit/test_stack_*.py` and the metric emitters to `operations`); `living-docs-system-and-contracts` (INV IDs, `docs/system/contracts.md`, `docs/README.md` with the four operations links). The migration matrix `specs/living-docs-cutover-matrix.md` (rows `M-OPS-*` and the decisions table) is on the integration branch.
- **Parallel:** `living-docs-ingestion`, `living-docs-core-hub`, `living-docs-research`, `living-docs-strategy-and-dashboard`, `living-docs-engineering-workflow` own the files this spec links to. Links to them are file links, valid once those specs merge; while their domain is still planned, the checker reports such a link as a notice.
- **Hands to:** `legacy-docs-retirement` (the README, SETUP and PREREQUISITES text becomes links to these four files; the `down -v` guard covers `docs/operations/*.md`); `agent-instruction-hierarchy` (`docker/AGENTS.md` lists OPS IDs and the trap pointers); `living-docs-cutover` (flipping the ratification batch rows once the owner's `CHOICE — operations ratification batch` exists).

## Affected files

| Path | Action |
|---|---|
| `docs/operations/topology.md` | create |
| `docs/operations/orchestration.md` | create |
| `docs/operations/observability.md` | create |
| `docs/operations/backup.md` | create |
| `docs/backup-restore.md` | modify (one link line) |
| `specs/soak-test-run.md` | modify (Docs impact, blocker paths, IDs, `CLAUDE.md` citation) |
| `specs/first-run-on-stack-machine.md` | modify (Docs impact, IDs, `CLAUDE.md` citation; preflight line `:73` untouched) |
| `DECISIONS.md` | modify (append the operations ratification batch) |
| `specs/living-docs-cutover-matrix.md` | modify (only the `ID` cells of `NS` = OPS fragment rows and the `IDs` cells of the 19 decisions rows in item 8) |
| `docs-check.toml` | modify (only the `[rollout] planned_domains` line: remove `"operations"`) |
| `specs/living-docs-operations.md` → `specs/done/living-docs-operations.md` | move, Status `done` |
| `TODO.md` | modify (this spec's row only) |
| `docs/README.md` | untouched (owned by `living-docs-system-and-contracts`; checked for the four links) |
| `docker/docker-compose.yml`, `.env.example`, `docker/grafana/provisioning/alerting/*.yaml`, `docker/prometheus/prometheus.yml`, `docker/elasticsearch/ilm_policy.json`, `docker/statsd-exporter/mapping.yml`, `docker/topics.yaml` | untouched but cited (machine authorities) |
| `services/*/dags/*.py`, `services/ingestion-scraper/config/sources.yaml`, `services/*/Dockerfile`, `services/*/config/gunicorn.conf.py` | untouched but cited |
| `services/backup/src/auspex_backup/*.py`, `services/backtesting/src/auspex_backtesting/stack_bootstrap.py`, metric emitters listed in Context | untouched but cited |
| `services/ingestion-scraper/tests/unit/test_stack_*.py`, `test_ingestion_dag.py`, `test_daily_health_summary.py`, `test_logging.py`, `test_metrics.py`, `test_repo_scaffolding.py`, `test_dashboard_stack_config.py`; `services/backup/tests/unit/*.py`; `services/backtesting/tests/unit/test_stack_bootstrap.py`, `test_universe_sec_index.py` | untouched but cited (Verified by) |
| `docker/README.md`, `docker/CLAUDE.md`, `orchestration/README.md`, `services/backup/README.md`, `SETUP.md`, `docs/PREREQUISITES.md`, `README.md`, `VERSIONS.md`, `docs/local-model-runbook.md` | untouched (later specs) |

## Required tests

All run from the repo root on the spec branch, after items 1–9 are done. Checker commands are created by `docs-check-tooling`; output lines have the form `CHECK path:line message`. `OWN` below is `docs/operations/**,docs/backup-restore.md,specs/soak-test-run.md,specs/first-run-on-stack-machine.md`: this spec's own files only.

Checker assertions:
- `operations_docs_have_no_checker_findings`: `python3 -m tools.docs_check --paths "$OWN"` prints nothing and exits 0. Fails on a broken link or anchor (A), a backticked path that does not exist (B), a duplicate ID (C), an unresolved ID, placeholder or DECISIONS heading (D), a missing required H2, a `Last reviewed against` SHA that is not an ancestor, or a spec without Docs impact (E), or a verification row that is missing, has an empty Source, or names a `path::name` that does not exist (K). Other domains' files are not scanned, because their specs may still be open.
- `matrix_rows_for_operations_all_have_assigned_ids`: `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain OPS` exits 0. Fails if a matrix row with `NS` OPS and disposition move, ratify, divergent or retire has no defined ID, or if the ID's verification Source does not contain the row's file path, `requirements §N` or DECISIONS heading.

Spec-specific checks (each is the script in the Definition of done under the same name):
- `four_operations_docs_exist`: `docs/operations/` holds exactly `backup.md`, `observability.md`, `orchestration.md`, `topology.md`. Fails before the work, so the checks below cannot pass on an empty directory.
- `no_env_example_value_copied_into_operations_docs`: for every `KEY=VALUE` in `.env.example` whose value is numeric with an optional unit (`^\d+(\.\d+)?[A-Za-z%]*$`), no line of `docs/operations/*.md` that names `KEY` also contains `VALUE` as a separate token. Fails, for example, on "`BACKUP_KEEP_DAYS` (14)".
- `no_schedule_value_in_operations_docs`: no five-field cron expression and no `HH:MM` clock time in `docs/operations/*.md`. Fails on "daily at 03:00 UTC".
- `metric_catalogue_covers_every_metric_alerts_and_summary_read`: every `auspex_*` name in `docker/grafana/provisioning/alerting/*.yaml` and `services/ingestion-scraper/dags/health_summary.py` (with a `_bucket`, `_sum` or `_count` suffix removed when the stripped name is catalogued) appears backticked in `docs/operations/observability.md`. Fails when an alert reads a metric the catalogue does not list.
- `catalogued_metric_names_exist_in_their_emitters`: the `## Metric catalogue` table has at least one row, and for each row the `Name in code` value occurs in the file named in `Emitter`. Fails on a typo or a renamed metric.
- `every_alert_rule_has_an_intent_row`: every `title:` value in `rules.yaml` and `infrastructure.yaml` appears in `docs/operations/observability.md`. Fails when a rule has no intent row.
- `backup_bucket_coverage_is_marked_untested`: `docs/operations/backup.md` has a verification row that contains `BACKUP_BUCKETS`, `stack_buckets` and `untested`. Fails if the bucket-list defect is hidden behind `tested`.
- `restore_exception_linked_not_restated`: `docs/operations/backup.md` contains `invariants.md#INV-2`, and no line in `docs/operations/*.md` matches `(?i)\brestore\b.*\b(non-)?empty\b`. Fails if the exception's conditions are copied.
- `sec_budget_names_every_sec_client`: every file matched by `grep -rlE 'SEC_(USER_AGENT|ARCHIVES_URL|FULL_INDEX_URL|DAILY_INDEX_URL|SUBMISSIONS_BULK_URL|COMPANYFACTS_BULK_URL|13F_DATASETS_URL|INSIDER_DATASETS_URL)' services/*/src` appears by its repo path in `docs/operations/topology.md` (at e51f742: `services/ingestion-scraper/src/auspex_ingest/connectors/sec_edgar.py`, `services/backtesting/src/auspex_backtesting/api.py`, which builds the universe, filing and catalyst clients, and `services/backtesting/src/auspex_backtesting/ownership/job.py`), and the file also names the `universe`, `filings` and `catalysts` packages. Fails when a client that reads SEC configuration is missing from the budget.
- `down_v_mentions_in_operations_docs_warn`: every line of `docs/operations/*.md` containing `down -v` contains `destroys all data`. Fails before `legacy-docs-retirement` would.
- `operations_ratification_batch_lists_every_pending_ops_id`: `DECISIONS.md` has exactly one heading matching `^## \d{4}-\d{2}-\d{2} — Living docs — PENDING — operations ratification batch$`; every verification row in `docs/operations/*.md` with status `pending-decision` cites that heading's full text, and every such ID appears in the body of that entry. Fails on a pending row outside the batch, a batch that omits one, or a missing or duplicated heading.
- `docs_readme_links_every_operations_doc`: `docs/README.md` links `operations/topology.md`, `operations/orchestration.md`, `operations/observability.md` and `operations/backup.md`. Fails if the index written by `living-docs-system-and-contracts` misses one.
- `runbook_gains_exactly_one_link_line`: against the integration base, `docs/backup-restore.md` has exactly one added line, it links `operations/backup.md`, and no line is removed. Fails if the runbook link is missing or the runbook was otherwise edited.
- `binding_decisions_rows_carry_ops_ids`: for each decisions-table row classified `binding` whose `Fragment rows` include an M-OPS row with `NS` OPS (20 at scoping), the `IDs` cell holds at least one `OPS-NNN` that is defined in `docs/operations/*.md`, and each such ID's verification Source contains the heading text (compared with backticks and the leading `## ` removed). Fails on an empty cell, an undefined ID, or an ID whose Source does not name the decision.
- `owned_specs_cite_no_claude_md_and_carry_docs_impact`: `specs/soak-test-run.md` and `specs/first-run-on-stack-machine.md` each contain `**Docs impact:**` and do not contain `CLAUDE.md`. Fails if either still cites a root `CLAUDE.md` section.
- `operations_is_no_longer_planned`: `[rollout] planned_domains` in `docs-check.toml` does not contain `operations`, and `git diff` of `docs-check.toml` against the integration base changes exactly one line. Fails if the domain was left planned or another setting changed.
- `first_run_preflight_line_unchanged`: `git diff "$(git merge-base HEAD origin/feature/living-docs-integration)" -- specs/first-run-on-stack-machine.md` has no added or removed line starting with `test -f .env && for k in`. Fails if the preflight line is touched.
- `doc_reading_tests_still_pass`: `cd services/ingestion-scraper && uv run pytest tests/unit/test_stack_persistence_config.py -q -k "down_v or new_secrets"` reports `2 passed`. Fails if an edit to `specs/first-run-on-stack-machine.md` broke the secrets test.
- `operations_spec_archived`: `specs/done/living-docs-operations.md` exists with `**Status:** done`, `specs/living-docs-operations.md` does not, and `TODO.md` links `specs/done/living-docs-operations.md`.

Mutation check, in a disposable worktree (`git worktree add "${TMPDIR:-/tmp}/ops-mutants" HEAD`, run the Definition of done there, then `git worktree remove --force "${TMPDIR:-/tmp}/ops-mutants"`; nothing is committed or pushed): for each spec-specific check, make one edit that breaks it (add "`BACKUP_KEEP_DAYS` (14)" to `backup.md`; add "03:00 UTC"; delete one catalogue row; flip the bucket row to `tested`; add "restore refuses non-empty stores"; drop `ownership` from topology; add a bare `down -v`; remove a pending ID from the batch body; empty one decisions-row `IDs` cell; put `CLAUDE.md` back into the soak spec; add `"operations"` back to `planned_domains`; edit the preflight line), and confirm the named check fails. List the mutations in the PR description.

## Definition of done

```bash
set -u
BASE=$(git merge-base HEAD origin/feature/living-docs-integration)
OWN='docs/operations/**,docs/backup-restore.md,specs/soak-test-run.md,specs/first-run-on-stack-machine.md'
echo "== operations_docs_have_no_checker_findings"
python3 -m tools.docs_check --paths "$OWN"; echo "exit=$?"
echo "== matrix_rows_for_operations_all_have_assigned_ids"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain OPS; echo "exit=$?"
python3 - "$BASE" <<'EOF'
import pathlib, re, subprocess, sys, tomllib
base = sys.argv[1]
fails = []
def check(name, bad):
    print(f"{name}: {'FAIL ' + '; '.join(map(str, bad[:5])) if bad else 'ok'}")
    fails.extend(bad)
def read(p):
    p = pathlib.Path(p)
    return p.read_text(encoding="utf-8") if p.is_file() else ""
ops = sorted(pathlib.Path("docs/operations").glob("*.md"))
check("four_operations_docs_exist", [] if [p.name for p in ops] == ["backup.md", "observability.md", "orchestration.md", "topology.md"] else [f"found {[p.name for p in ops]}"])
text = {p: p.read_text(encoding="utf-8") for p in ops}
lines = [(p, n, l) for p, t in text.items() for n, l in enumerate(t.splitlines(), 1)]
env = {}
for line in open(".env.example", encoding="utf-8"):
    m = re.match(r"([A-Z][A-Z0-9_]*)=(\S+)\s*$", line)
    if m and re.fullmatch(r"\d+(\.\d+)?[A-Za-z%]*", m[2]):
        env[m[1]] = m[2]
check("no_env_example_value_copied_into_operations_docs", [f"{p}:{n} {k}" for p, n, l in lines for k, v in env.items()
    if k in l and re.search(r"(?<![\w.\-])" + re.escape(v) + r"(?![\w.\-])", l.replace(k, ""))])
cron = re.compile(r"(?<!\S)([\d*/,\-]+\s+){4}[\d*/,\-]+(?!\S)|\b\d{1,2}:\d{2}\b")
check("no_schedule_value_in_operations_docs", [f"{p}:{n}" for p, n, l in lines if cron.search(l)])
obs = read("docs/operations/observability.md")
src = "".join(read(p) for p in [*pathlib.Path("docker/grafana/provisioning/alerting").glob("*.yaml"), "services/ingestion-scraper/dags/health_summary.py"])
used = set(re.findall(r"\bauspex_[a-z0-9_]+", src))
check("metric_catalogue_covers_every_metric_alerts_and_summary_read", sorted(
    u for u in used if f"`{u}`" not in obs and f"`{re.sub(r'_(bucket|sum|count)$', '', u)}`" not in obs))
cat = obs.split("## Metric catalogue", 1)[1].split("\n## ", 1)[0] if "## Metric catalogue" in obs else ""
rows = [[c.strip().strip("`") for c in l.strip().strip("|").split("|")] for l in cat.splitlines() if l.startswith("|") and not l.startswith("|---") and "Exported name" not in l]
check("catalogued_metric_names_exist_in_their_emitters", ["no catalogue rows"] if not rows else [
    r[0] for r in rows if len(r) < 5 or r[1] not in read(r[3])])
titles = re.findall(r"^\s*title:\s*['\"]?(.+?)['\"]?\s*$", read("docker/grafana/provisioning/alerting/rules.yaml") + read("docker/grafana/provisioning/alerting/infrastructure.yaml"), re.M)
check("every_alert_rule_has_an_intent_row", ["no titles read"] if not titles else [t for t in titles if t not in obs])
bk = read("docs/operations/backup.md")
check("backup_bucket_coverage_is_marked_untested", [] if any(all(s in l for s in ("BACKUP_BUCKETS", "stack_buckets", "untested")) for l in bk.splitlines()) else ["no untested bucket row"])
check("restore_exception_linked_not_restated", ([] if "invariants.md#INV-2" in bk else ["no INV-2 link"]) + [
    f"{p}:{n}" for p, n, l in lines if re.search(r"(?i)\brestore\b.*\b(non-)?empty\b", l)])
topo = read("docs/operations/topology.md")
hits = subprocess.run(["bash", "-c", "grep -rlE 'SEC_(USER_AGENT|ARCHIVES_URL|FULL_INDEX_URL|DAILY_INDEX_URL|SUBMISSIONS_BULK_URL|COMPANYFACTS_BULK_URL|13F_DATASETS_URL|INSIDER_DATASETS_URL)' services/*/src"], capture_output=True, text=True).stdout.split()
check("sec_budget_names_every_sec_client", ["grep found no SEC client"] if not hits else sorted(n for n in set(hits) | {"universe", "filings", "catalysts"} if n not in topo))
check("down_v_mentions_in_operations_docs_warn", [f"{p}:{n}" for p, n, l in lines if "down -v" in l and "destroys all data" not in l])
dec = read("DECISIONS.md")
heads = re.findall(r"(?m)^## \d{4}-\d{2}-\d{2} — Living docs — PENDING — operations ratification batch$", dec)
body = dec.split(heads[0], 1)[1].split("\n## ", 1)[0] if len(heads) == 1 else ""
pend = [l for p, n, l in lines if l.startswith("| OPS-") and "pending-decision" in l]
check("operations_ratification_batch_lists_every_pending_ops_id", ([] if len(heads) == 1 else [f"{len(heads)} batch headings"]) + [
    l.split("|")[1].strip() for l in pend if not heads or heads[0][3:] not in l or l.split("|")[1].strip() not in body])
idx = read("docs/README.md")
check("docs_readme_links_every_operations_doc", [f for f in ("topology", "orchestration", "observability", "backup") if f"operations/{f}.md" not in idx])
diff = subprocess.run(["git", "diff", "-U0", base, "--", "docs/backup-restore.md"], capture_output=True, text=True).stdout.splitlines()
added = [l for l in diff if l.startswith("+") and not l.startswith("+++")]
removed = [l for l in diff if l.startswith("-") and not l.startswith("---")]
check("runbook_gains_exactly_one_link_line", [] if len(added) == 1 and "operations/backup.md" in added[0] and not removed else [f"+{len(added)} -{len(removed)}"])
matrix = read("specs/living-docs-cutover-matrix.md").splitlines()
ns = {c[1].strip(): c[7].strip() for c in (l.split("|") for l in matrix if l.startswith("| M-")) if len(c) > 8}
verif = {l.split("|")[1].strip(): l.split("|")[2] for p, n, l in lines if re.match(r"\| OPS-\d{3} \|", l)}
norm = lambda s: s.replace("`", "").strip().removeprefix("## ").strip()
drows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in matrix if l.startswith("| `## ")]
mine = [r for r in drows if len(r) >= 4 and r[1] == "binding" and any(ns.get(f.strip()) == "OPS" for f in r[3].split(",") if f.strip().startswith("M-OPS-"))]
bad = ["no OPS decisions rows found"] if not mine else []
for r in mine:
    ids = re.findall(r"OPS-\d{3}", r[2])
    if not ids:
        bad.append(f"empty: {norm(r[0])[:50]}")
    bad += [f"{i} undefined or Source lacks heading" for i in ids if i not in verif or norm(r[0]) not in norm(verif[i])]
check("binding_decisions_rows_carry_ops_ids", bad)
print(f"  ({len(mine)} decisions rows)")
own = ["specs/soak-test-run.md", "specs/first-run-on-stack-machine.md"]
check("owned_specs_cite_no_claude_md_and_carry_docs_impact", [f"{s} cites CLAUDE.md" for s in own if "CLAUDE.md" in read(s)] + [f"{s} no Docs impact" for s in own if "**Docs impact:**" not in read(s)])
planned = tomllib.loads(read("docs-check.toml")).get("rollout", {}).get("planned_domains", [])
tdiff = subprocess.run(["git", "diff", "-U0", base, "--", "docs-check.toml"], capture_output=True, text=True).stdout.splitlines()
tchanged = [l for l in tdiff if l[:1] in "+-" and not l.startswith(("+++", "---"))]
check("operations_is_no_longer_planned", (["still planned"] if "operations" in planned else []) + ([] if len(tchanged) == 2 and all("planned_domains" in l for l in tchanged) else [f"{len(tchanged)} changed lines"]))
sys.exit(1 if fails else 0)
EOF
echo "exit=$?"
echo "== first_run_preflight_line_unchanged"
git diff "$BASE" -- specs/first-run-on-stack-machine.md | grep -cE '^[-+]test -f \.env && for k in'
echo "== doc_reading_tests_still_pass"
(cd services/ingestion-scraper && uv run pytest tests/unit/test_stack_persistence_config.py -q -k "down_v or new_secrets")
echo "== operations_spec_archived"
test ! -e specs/living-docs-operations.md && grep -q '^\*\*Status:\*\* done' specs/done/living-docs-operations.md && grep -q 'specs/done/living-docs-operations.md' TODO.md && echo archived
```

Expected output:
- nothing between the first header and `exit=0`;
- `exit=0` after the matrix check;
- sixteen lines `<name>: ok` plus `(19 decisions rows)`, then `exit=0`;
- `0` for the preflight diff count;
- `2 passed, … deselected` for the doc-reading tests;
- `archived`.

The PR into `feature/living-docs-integration` lists the mutations checked, the IDs created (first and last per file), and the ratification batch IDs.

## Compatibility

- **Readers.** Nothing that exists today is removed or moved by this spec. `docker/README.md`, `orchestration/README.md`, `SETUP.md` and the service READMEs keep their text until `legacy-docs-retirement` replaces it with links, so for the life of the integration branch a reader finds the same facts in the old place and the owned version in `docs/operations/`. Nothing reaches `develop` before the cutover PR.
- **Links.** The four new files are linked from `docs/README.md`, which `living-docs-system-and-contracts` writes; this spec only checks the links. `docs/backup-restore.md` keeps its path and gains one outbound link. Inbound citations from `specs/done/` and `DECISIONS.md` to `docs/requirements.md` §5 and §12 keep resolving through the index `legacy-docs-retirement` writes.
- **Agents.** Root `CLAUDE.md` and `docker/CLAUDE.md` are unchanged here, so sessions keep loading today's rules until `agent-instruction-hierarchy` merges.
- **Tests.** No test or test input changes. `test_new_secrets_are_documented_in_setup` keeps finding its preflight line; `test_docs_never_offer_down_v_as_a_fix` reads the same five files.
- **Specs.** `specs/soak-test-run.md` and `specs/first-run-on-stack-machine.md` keep every step, check and pass criterion; only cited wording changes.
- **Checker.** Removing `operations` from `planned_domains` turns OPS notices into findings for every file, including other specs that link `docs/operations/`. They link files that now exist, so no new finding appears.

## Rollback

On the integration branch, before `living-docs-cutover`, in one PR into `feature/living-docs-integration`, merged on the owner's word:
1. `git revert --no-commit <integration tip before this spec merged>..<integration tip after it merged>` (the range includes this spec's first commit).
2. `git checkout HEAD -- DECISIONS.md`, so no `DECISIONS.md` entry is deleted.
3. Append `## <date> — Living docs — FLAG — operations docs rolled back`, recording the range reverted and that the IDs listed in the operations ratification batch are withdrawn; if the batch has already been answered with a CHOICE, the CHOICE stays and the FLAG says its IDs no longer exist.
4. Commit once.

That removes `docs/operations/`, the runbook link, the edits to the two active specs, the matrix cells and the archive move, and puts `operations` back into `planned_domains`. Specs that merged after this one and link OPS IDs (`legacy-docs-retirement`, `agent-instruction-hierarchy`) then fail check D and must be reverted first or re-pointed. After cutover, rollback is the cutover spec's.

## Notes

- **Six Dockerfiles.** The tree has six (strategy and dashboard included). `topology.md` covers all six; an earlier count of five is wrong.
- **`docs/soak-test-report.md`.** `docs-check.toml` lists it as non-normative, so the soak spec's report under `docs/` needs no change here.
- **Follow-up specs recommended, not created:** a test that `BACKUP_BUCKETS` covers `stack_buckets()` (or one list derived from the other); a stale-backup alert or summary line from `last_success.json`; schedule and active-at-creation tests for the price, universe, backup and health DAGs; a `verify_pipeline.sh` that checks more than two REST calls, or a rename; a restore-consistency analysis (dated databases with the latest mirror); a soak check for backup success.
- **Root `CLAUDE.md` traps, each with one destination.** Airflow 3 rename and Fernet → `orchestration.md`; gunicorn, Docker Hub (compose half) and Docker Desktop/Metal → `topology.md`; Grafana `$$` and `make_metrics()` → `observability.md`. Ollama context and digest → `docs/ingestion/extraction.md`; LocalStack and the CI image prefix → `docs/engineering/verification.md`; bcrypt `$` → `docs/dashboard.md`.
- **One metric catalogue.** Each emitting domain could have owned its own metric names; the design (`specs/living-docs-cutover-design.md` §2) chose one catalogue here, because a rename must change emitter, alert and summary together. Domain docs state what a metric means for their component only by linking the catalogue row.
- **Logging has one owner.** The log contract in `observability.md` is the only place that says what a log line carries and what it must never carry. The system, ingestion and core-hub docs link it.
- **What schedules look like in the docs.** The orchestration catalogue says, for example, "schedule: `schedule=` in `services/backup/dags/backup.py`" and states the rule (UTC, staggered, spaced so the ingestion pool's single slot is not oversubscribed) without the cron string. `SETUP.md` keeps its human-readable times as a runbook (tolerated; noted in `legacy-docs-retirement`).
- **Status values.** Rows backed by compose-reading tests are `tested`; that proves the configuration, not that the stack has run. Do not use `enforced` for them. None of these rows may cite a Mac result until a DECISIONS `VERIFIED` entry exists.
- **As built.**
  - 71 IDs: `topology.md` OPS-001…OPS-023, `orchestration.md` OPS-024…OPS-039, `observability.md` OPS-040…OPS-059, `backup.md` OPS-060…OPS-071.
  - Ratification batch (`## 2026-10-22 — Living docs — PENDING — operations ratification batch`): OPS-002 (`extra_hosts`), OPS-007 (`.env.example` configures compose and host scripts), OPS-021 (scraper one gunicorn process), OPS-022 (price-service and backup one gunicorn process), OPS-031 (non-ingestion DAGs retry and fail on HTTP errors), OPS-053 (catalogue rename in one PR), OPS-068 (409 during a backup run). Exactly the seven expected members; none added or removed.
  - `Last reviewed against` is `develop @ b7582c3`, the integration branch's recorded base on `develop`, not `e51f742` (the scoping base): the checker requires an ancestor on `develop`, and b7582c3 is what the integration branch was cut from.
  - Three requirements beyond the list in What this builds, each carrying a matrix row: OPS-008 (Elastic images from the publisher registry, the binding Docker Hub decision), OPS-011 (`depends_on` conditions and `--wait`, matrix `M-SYS-141`), and the cursor-visible-in-the-UI rule as its own ID (OPS-033).
  - The strategy image builds from the `services/` context (it copies the backtesting package), not from its own directory; OPS-020 says so.
  - The strategy metrics' emitter in the catalogue is `services/strategy/src/auspex_strategy/runtime/http.py`, where the names are defined, not `runtime/main.py` as Context listed.
  - Third-party exporter metrics that alerts read (cAdvisor, node-exporter, Kafka, Postgres and Elasticsearch exporters) are listed in prose under the catalogue, not as catalogue rows: the catalogue's `Emitter` column must name a repository file containing the name, and these are emitted by pinned images.
  - Ports bound to `127.0.0.1` (OPS-005) and the profile split (OPS-004) are `untested`: the existing compose tests cover some services, not the rule as a whole.
  - The Startup data CHOICE heading contains backticks and the matrix spells it without them, so the Source cells cite it in a double-backtick span and also give the plain spelling in parentheses, which check M and `binding_decisions_rows_carry_ops_ids` both match.
  - Item 5 and item 9 quote a link and an ID placeholder that the checker read as a broken link and an unresolved placeholder once `operations` left `planned_domains`; both are written as code or prose here.
