"""HTTP API that Airflow calls to keep price snapshots and the stock universe current."""

import os
from collections.abc import Callable
from dataclasses import asdict
from datetime import date
from pathlib import Path

from flask import Flask, Response, jsonify, request
from flask.typing import ResponseReturnValue
from minio import Minio
from prometheus_client import CollectorRegistry, generate_latest

from auspex_backtesting.catalysts import (
    AdvisoryCommitteeNotices,
    CatalystPanel,
    DocumentCache,
    HttpSource,
    PressReleaseCatalystExtractor,
)
from auspex_backtesting.catalysts.job import CatalystPanelBuild, universe_members
from auspex_backtesting.price_metrics import PriceRefreshMetrics
from auspex_backtesting.prices.price_refresher import (
    PriceDataUnavailableError,
    PriceRefresher,
    RefreshResult,
    SnapshotDiscontinuityError,
    price_universe,
)
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore
from auspex_backtesting.prices.splits import SplitStore
from auspex_backtesting.universe.job import (
    SecBulkSource,
    SnapshotPrices,
    UniverseBuildJob,
    UniverseConfigError,
)
from auspex_backtesting.universe.rules import load_rules
from auspex_backtesting.universe.sec_index import InstanceDocuments
from auspex_backtesting.universe.store import RulesVersionError, UniverseStore


def create_app(
    refresher: PriceRefresher | None = None,
    tickers: list[str] | None = None,
    universe_job: Callable[[], UniverseBuildJob] | None = None,
    metrics: PriceRefreshMetrics | None = None,
) -> Flask:
    if metrics is None:
        metrics = PriceRefreshMetrics(CollectorRegistry())
    if refresher is None:
        refresher = refresher_from_env()
    if tickers is None:
        tickers = price_universe(os.environ.get("WATCHED_TICKERS", ""))
    configured = tickers

    app = Flask(__name__)

    @app.get("/health")
    def health() -> ResponseReturnValue:
        return jsonify(status="ok")

    @app.post("/prices/refresh")
    def refresh() -> ResponseReturnValue:
        body = request.get_json(silent=True) or {}
        results: list[RefreshResult] = []
        failed: dict[str, str] = {}
        for ticker in body.get("tickers") or configured:
            try:
                results.append(refresher.refresh(ticker))
            except (PriceDataUnavailableError, SnapshotDiscontinuityError) as exc:
                failed[ticker] = str(exc)
        metrics.record_run(refreshed=len(results), failed=len(failed))
        payload = {"results": [asdict(r) for r in results], "failed": failed}
        return jsonify(payload), 502 if failed else 200

    @app.post("/universe/build")
    def build_universe() -> ResponseReturnValue:
        job = (universe_job or universe_job_from_env)()
        try:
            summary = job.run()
        except (RulesVersionError, UniverseConfigError) as exc:
            return jsonify(error=str(exc)), 409
        except OSError as exc:
            # SEC or MinIO unreachable; the next scheduled run retries.
            return jsonify(error=str(exc)), 502
        return jsonify(summary.as_dict()), 200

    @app.get("/metrics")
    def prometheus_metrics() -> ResponseReturnValue:
        return Response(generate_latest(metrics.registry), mimetype="text/plain; version=0.0.4")

    return app


def refresher_from_env() -> PriceRefresher:
    return PriceRefresher(
        _minio_from_env(), history_start=date.fromisoformat(os.environ["PRICE_HISTORY_START"])
    )


def universe_job_from_env() -> UniverseBuildJob:
    client = _minio_from_env()
    return UniverseBuildJob(
        UniverseStore(client),
        Path(os.environ["UNIVERSE_RULES_PATH"]),
        SecBulkSource(
            os.environ["SEC_SUBMISSIONS_BULK_URL"],
            os.environ["SEC_COMPANYFACTS_BULK_URL"],
            os.environ["SEC_USER_AGENT"],
            InstanceDocuments(os.environ["SEC_ARCHIVES_URL"], os.environ["SEC_USER_AGENT"]),
        ),
        SnapshotPrices(refresher_from_env(), PriceSnapshotStore(client), SplitStore(client)),
        backfill_start=date.fromisoformat(os.environ["BACKFILL_SCOPE_START"]),
        price_history_start=date.fromisoformat(os.environ["PRICE_HISTORY_START"]),
    )


# SEC allows 10 requests per second across its hosts; the panel build stays at half that.
_SEC_INTERVAL_S = 0.2
_FEDERAL_REGISTER_INTERVAL_S = 1.0


def catalyst_build_from_env() -> CatalystPanelBuild:
    client = _minio_from_env()
    cache = DocumentCache(client)
    user_agent = os.environ["SEC_USER_AGENT"]
    rules_version = load_rules(Path(os.environ["UNIVERSE_RULES_PATH"])).version
    store = UniverseStore(client)
    return CatalystPanelBuild(
        CatalystPanel(client),
        PressReleaseCatalystExtractor(
            os.environ["SEC_FULL_INDEX_URL"],
            os.environ["SEC_ARCHIVES_URL"],
            HttpSource(user_agent, _SEC_INTERVAL_S),
            cache,
        ),
        AdvisoryCommitteeNotices(
            os.environ["FEDERAL_REGISTER_API_URL"],
            HttpSource(user_agent, _FEDERAL_REGISTER_INTERVAL_S),
            cache,
        ),
        lambda: universe_members(store, rules_version),
    )


def _minio_from_env() -> Minio:
    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
