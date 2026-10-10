# orchestration/

Airflow 3.3 schedules ingestion. `services/ingestion-scraper/dags/auspex_dags.py` defines one DAG per entry in `services/ingestion-scraper/config/sources.yaml`. Each DAG's single task reads the source's cursor from an Airflow Variable, posts it to the scraper's `POST /ingest/<source_type>`, and writes back `max_published_date_processed` only when the call succeeds and processed something. The DAG holds no ingestion logic (Invariant 3).

---

## Price refresh

`auspex_price_refresh` (`services/backtesting/dags/price_refresh.py`) runs Mon–Fri 22:30 UTC and calls the price service's `POST /prices/refresh`, which appends each new daily bar for the watchlist, `XBI` and `EURUSD=X`. It is active from the first start; the ingestion DAGs are paused until a gated extraction model exists (`SETUP.md` step 5).

Compose mounts the ingestion DAGs at `/opt/airflow/dags/ingestion` and the price DAG at `/opt/airflow/dags/prices`.

---

## Cursor ownership

The cursor belongs to Airflow, not to the scraper. `ingestion-scraper` is stateless with respect to it. Airflow Variables are the cursor store. A failed run leaves the cursor unchanged; the next run reprocesses the same window.

---

## DAG entry point

`services/ingestion-scraper/dags/auspex_dags.py`, tested by `services/ingestion-scraper/tests/unit/test_ingestion_dag.py` against stand-in Airflow modules.

---

## Adding a source

Add an entry to `services/ingestion-scraper/config/sources.yaml`. The DAG file picks it up on the next DAG parse. No Airflow code changes needed.

---

## Airflow 3 notes

- `schedule`, not `schedule_interval` — the old name was removed.
- Task code cannot access the metadata DB directly; use Airflow Variables and Connections.
- API keys are Airflow Connections, not environment variables. Set them via the Airflow UI or CLI before running a DAG for the first time.
- Airflow runs at `http://localhost:8082` (see `docker/README.md` for port details).
