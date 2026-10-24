# Auspex

Local biotech signal research pipeline. Convergence of evidence across sources is the signal — no single document is.

Requirements, by domain and with their owners: [docs/README.md](docs/README.md).

---

## Architecture

Public sources feed `ingestion-scraper` (Python), which archives raw documents to MinIO and publishes extracted signals to Kafka. `core-hub` (Java/Spring) consumes them, keeps the signal state, the signal graph and the corroborations, and serves a REST API. `price-service` and the backtesting jobs keep price snapshots and research panels in MinIO. `strategy-runtime` runs the registered strategies on corroborations into virtual books. The `dashboard` (Next.js) is the interface: the browser talks only to the dashboard's own server, which forwards to the backend services. Airflow schedules the ingestion, price, universe, backup and health DAGs. The full picture is [docs/system/overview.md](docs/system/overview.md); the rules every component keeps are the invariants in [docs/system/invariants.md](docs/system/invariants.md).

---

## Services

| Service | Directory | Role |
|---|---|---|
| ingestion-scraper | [`services/ingestion-scraper/`](services/ingestion-scraper/README.md) | Fetch, archive, pre-filter, extract and publish, over an HTTP API the ingestion DAGs call |
| core-hub | [`services/core-hub/`](services/core-hub/README.md) | Kafka consumer, signal store and graph, corroboration, REST API |
| price-service and backtesting | [`services/backtesting/`](services/backtesting/README.md) | Price snapshots, universe and research panels; backtests and the evaluation protocol |
| strategy-runtime | [`services/strategy/`](services/strategy/README.md) | Strategy framework, runtime, risk layer and decision traces |
| backup | [`services/backup/`](services/backup/README.md) | Nightly backup of Postgres, Neo4j and MinIO; restore into empty stores |
| dashboard | [`services/dashboard/`](services/dashboard/README.md) | Control and research UI behind a single-user login |
| Airflow DAGs | `services/*/dags/`, see [orchestration/README.md](orchestration/README.md) | Ingestion per source, price refresh, universe build, backup, daily health summary |

The stack around them (Kafka, Postgres, Neo4j, MinIO, Airflow, logging and metrics) is described in [docker/README.md](docker/README.md); pinned versions are in [VERSIONS.md](VERSIONS.md).

---

## Quick start

```bash
cp .env.example .env          # fill in secrets and API keys — see SETUP.md
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --build --wait
```

[SETUP.md](SETUP.md) lists the manual steps in order. The dashboard is then at `http://localhost:3001` (`DASHBOARD_PORT` in `.env`).

---

## Stack commands

| Purpose | Command |
|---|---|
| Bring up infra only | `docker compose -f docker/docker-compose.yml --env-file .env up -d --wait` |
| Bring up the full stack | `docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --wait` |
| Tear down (keep volumes) | `docker compose -f docker/docker-compose.yml --env-file .env down` |
| Tear down and wipe volumes (destroys all data: price history, the pinned universe, the raw archive and every signal) | `docker compose -f docker/docker-compose.yml --env-file .env down -v` |
| Restore one nightly backup into empty stores ([docs/backup-restore.md](docs/backup-restore.md)) | `docker compose --profile restore -f docker/docker-compose.yml --env-file .env run --rm restore --date YYYY-MM-DD` |
| core-hub REST smoke check: two REST requests, not proof that the pipeline works | `./verify_pipeline.sh` |
| Grafana provisioning check: dashboards, alert rules, contact point, scrape targets and probes | `GRAFANA_ADMIN_PASSWORD=... sh docker/grafana/test_provisioning.sh` |

Stop all strategies: the kill switch in [`services/strategy/AGENTS.md`](services/strategy/AGENTS.md).

Service commands: the `AGENTS.md` in each service directory.

---

## Project structure

```
auspex/
├── services/
│   ├── ingestion-scraper/   Python scraper: fetch, archive, extract, publish
│   ├── core-hub/            Java Spring Boot: signal store, graph, corroboration, REST
│   ├── backtesting/         price-service, universe, panels, backtests, evaluation
│   ├── strategy/            strategy framework, strategy-runtime, risk, traces
│   ├── backup/              nightly backup and restore
│   └── dashboard/           Next.js control and research UI
├── config/                  hypotheses, universe rules, models, strategies, themes
├── docker/                  Docker Compose stack, startup one-shots, monitoring
├── orchestration/           pointer to the DAGs (they live with their services)
├── docs/                    requirements by domain, runbooks, history
├── specs/                   proposed changes; specs/done/ is history
├── tools/                   docs checker
├── .github/                 CI workflows and scripts
├── AGENTS.md                agent instructions (CLAUDE.md imports it)
├── SETUP.md                 the manual steps, in order; everything else fills itself on `up`
├── TODO.md                  spec index and session log
├── VERSIONS.md              pinned versions
└── DECISIONS.md             append-only log of flags, choices and decisions
```

---

## Watched tickers

The watched tickers are `WATCHED_TICKERS` in [.env.example](.env.example).
