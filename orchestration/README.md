# orchestration/

Airflow 3.3 schedules the stack's work. The DAG files live with the service each one calls:

| Directory | Files |
|---|---|
| `services/ingestion-scraper/dags/` | `auspex_dags.py` (one ingestion DAG per `sources.yaml` entry), `daily_health.py` and `health_summary.py` (the daily health summary) |
| `services/backtesting/dags/` | `price_refresh.py`, `universe_build.py` |
| `services/backup/dags/` | `backup.py` |

The DAGs, their schedules and the policy they follow are owned by [docs/operations/orchestration.md](../docs/operations/orchestration.md). The cursor rule, what a run returns and when the cursor moves, is owned by [docs/ingestion/pipeline.md](../docs/ingestion/pipeline.md).

## DAG entry point

`services/ingestion-scraper/dags/auspex_dags.py`, tested by `services/ingestion-scraper/tests/unit/test_ingestion_dag.py` against stand-in Airflow modules.
