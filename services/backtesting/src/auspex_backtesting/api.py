"""HTTP API that Airflow calls to keep price snapshots current."""

import os
from dataclasses import asdict
from datetime import date

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue
from minio import Minio

from auspex_backtesting.prices.price_refresher import (
    PriceDataUnavailableError,
    PriceRefresher,
    RefreshResult,
    SnapshotDiscontinuityError,
    price_universe,
)


def create_app(refresher: PriceRefresher | None = None, tickers: list[str] | None = None) -> Flask:
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
        payload = {"results": [asdict(r) for r in results], "failed": failed}
        return jsonify(payload), 502 if failed else 200

    return app


def refresher_from_env() -> PriceRefresher:
    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    return PriceRefresher(
        client, history_start=date.fromisoformat(os.environ["PRICE_HISTORY_START"])
    )
