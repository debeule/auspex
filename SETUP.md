# Setup — the steps a person has to do

Everything the stack can do for itself happens on `docker compose up`. This file lists only what it cannot: secrets you own, things installed on the host, and decisions that are yours to sign off. Do them in order; each step says what it unblocks.

## What starts by itself

One command brings up the stack and fills everything it needs:

```bash
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --build --wait
```

| On every `up` | How | When it is a no-op |
|---|---|---|
| Kafka topics from `docker/topics.yaml` | `kafka-init` one-shot | topic already exists |
| MinIO buckets `auspex-raw`, `auspex-prices` | `minio-init` one-shot | bucket already exists |
| Price history for the watchlist, `XBI` and `EURUSD=X` from `PRICE_HISTORY_START` | `price-bootstrap` one-shot | snapshot is current |
| Postgres databases and roles | `postgres-init/` | volume already initialised |
| Postgres schema | Flyway on `core-hub` start | migrations applied |
| Log retention, Grafana dashboards and alerts | `elasticsearch-setup`, Grafana provisioning | already applied |
| Read-only Postgres role for monitoring | `postgres-monitor-role` one-shot | role exists; its password is reset to `.env`'s |

| On a schedule | How |
|---|---|
| New daily bars for the same tickers, Mon–Fri 22:30 UTC | Airflow DAG `auspex_price_refresh`, active from the first start |
| Point-in-time stock universe (`config/universe/rules.yaml`), first week of each month 06:00 UTC and on the first start | Airflow DAG `auspex_universe_build`, active from the first start. The first run downloads SEC's bulk archives (a few GB, deleted afterwards) and every member's price history, so it takes a while; later runs only add the new month. |
| Source ingestion | Airflow DAGs `auspex_<source>`, paused until step 5 |

`up --wait` fails if a ticker has no price data at all after `price-bootstrap` (`docker logs auspex-price-bootstrap` names it). Yahoo rate limits are the usual cause; run the same `up` again later. A ticker added to `WATCHED_TICKERS` is filled on the next `up`.

## 1. Create `.env` (once)

```bash
cp .env.example .env
```

Fill in what only you have:

| Variable | Notes |
|---|---|
| `POSTGRES_PASSWORD`, `AIRFLOW_DB_PASSWORD`, `NEO4J_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `GRAFANA_ADMIN_PASSWORD`, `AIRFLOW_SECRET_KEY`, `AIRFLOW_JWT_SECRET` | Any strong values, e.g. `openssl rand -hex 24`. To change one later, follow "Changing a password in place" in `docker/README.md`; `down -v` destroys all data. |
| `AIRFLOW_FERNET_KEY` | `openssl rand -base64 32 \| tr '+/' '-_'`. Encrypts Airflow's stored Variables, including the ingestion cursors; keep it for the life of the stack. **If the stack already ran without it**, copy the key Airflow generated before you recreate the container: `docker exec auspex-airflow airflow config get-value core fernet_key`. |
| `SEC_USER_AGENT` | `Name email@example.com`; SEC returns 403 without it. |
| `NCBI_API_KEY`, `OPENFDA_API_KEY`, `EPO_OPS_KEY`, `EPO_OPS_SECRET` | From each provider's developer portal (EPO: `developers.epo.org`). |
| `OPENAI_API_KEY` | Only for the API fallback model. |
| `DASHBOARD_USERNAME` | The dashboard's one login. |
| `DASHBOARD_PASSWORD_HASH` | Print it with `docker compose --profile app -f docker/docker-compose.yml --env-file .env run --rm --no-deps dashboard node scripts/hash-password.mjs` (it asks for the password without echoing it) and paste the printed line as is: the single quotes keep compose from reading the `$` signs in the hash. |
| `DASHBOARD_SESSION_SECRET`, `CORE_HUB_WRITE_TOKEN` | Any strong values, e.g. `openssl rand -hex 32`. Changing the session secret signs everyone out; changing the write token needs both `core-hub` and `dashboard` restarted. |
| `POSTGRES_MONITOR_PASSWORD` | Any strong value; the read-only role Prometheus's Postgres exporter uses. Created or updated on every `up`. |
| `ALERT_CONTACT_TYPE`, `ALERT_EMAIL_ADDRESSES`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_ADDRESS` | Where Grafana sends alerts. `email` (the default) needs the address list and an SMTP account, e.g. `smtp.gmail.com:587` with an app password. For a webhook instead, set `ALERT_CONTACT_TYPE=webhook` and `ALERT_WEBHOOK_URL`. Grafana does not start without one of the two. |

## 2. Host settings (once)

- **macOS:** Docker Desktop → Settings → Resources → Memory: **8 GB**, so a local model fits next to the stack on 24 GB.
- **macOS:** `brew install node_exporter && brew services start node_exporter`. Prometheus reads the Mac's own CPU, memory and disk from it at `host.docker.internal:9100`; inside Docker only the VM is visible, not Ollama's memory or the Mac's disk. Optional: without it the Mac panels on the Auspex Infrastructure dashboard stay empty and one info alert fires.
- **Docker Hub (optional):** `docker login` with a free Docker Hub account. The first `up` pulls about ten images, and Docker Hub limits anonymous pulls per IP.
- **Linux:** `sudo sysctl -w vm.max_map_count=262144` and persist it in `/etc/sysctl.d/99-elasticsearch.conf`; Elasticsearch will not start without it.

Then run the `up` command above. The dashboard is at `http://localhost:3001` (`DASHBOARD_PORT`). Airflow is at `http://localhost:8082`; its `admin` password is in `docker exec auspex-airflow cat /opt/airflow/state/simple_auth_manager_passwords.json`, and stays the same across recreates.

## 3. Install the local model (once, on the host)

Ollama runs natively because Docker on macOS cannot use the GPU. Follow `docs/local-model-runbook.md`: install Ollama, set its context length, pull the candidates, `register_local_model.py`, then `evaluate_model.py` and `score_extraction.py` per candidate.

**Your call:** pick the model from the printed precision and latency. It must reach 0.85 `is_signal` precision. Record the choice in `DECISIONS.md`. If no local model passes, the fallback is `gpt-4o-mini-2024-07-18` for the backfill only (budget in step 6).

## 4. Point the pipeline at the chosen model

Set `EXTRACTION_MODEL`, `EXTRACTION_BASE_URL`, `EXTRACTION_API_KEY` and `EXTRACTION_PROMPT_VERSION` in `.env` as the runbook's last section shows, then run the `up` command again. Commit the new `config/models/` registry entry, gate record and latency record.

## 5. Start live ingestion

Ingestion DAGs stay paused until a gated model exists, because every run calls it.

```bash
docker exec auspex-airflow airflow dags unpause -y --treat-dag-id-as-regex '^auspex_(?!price_refresh$|mock$)'
```

## 6. Historical backfill (once)

Runs on the host against the running stack (`scripts/run_backfill.py`, `specs/historical-backfill.md`).

**Your calls, before the live run:**
- Set `BACKFILL_TIME_CEILING_HOURS` (local model) or `BACKFILL_BUDGET_CEILING` (API fallback) in `.env` from the dry run's estimate plus about a third.
- Confirm the machine can stay on for the estimated duration (`caffeinate -i` keeps a Mac awake).
- Sign off the dry-run output (documents, LLM calls, hours, lineage overlap), then start the live run with its run id. It is checkpointed: re-running the same command resumes.

## 7. Before live trading

Each answer goes in `DECISIONS.md` before trading starts; details in `docs/PREREQUISITES.md`.

1. Belgian tax advisor: investment versus speculative income, and the effect of short-selling.
2. Interactive Brokers margin account opened and funded.
3. Borrow availability and fee per watchlist ticker on IBKR.
4. A source for the price history of any watchlist company delisted or acquired during the backfill window.
