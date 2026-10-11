from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from auspex_strategy.metrics.summary import MetricsService
from auspex_strategy.runtime.book import BookMode

log = logging.getLogger(__name__)

PREFIX = "/api/v1/metrics"

Response = tuple[int, str, bytes]


class MetricsApi:
    """`GET /api/v1/metrics/strategies`, `/strategies/<name>/<version>` (one summary per mode
    the version has a book in) and `/correlation?mode=<mode>` (default `paper`).

    Responses carry computed metrics only, never book rows.
    """

    def __init__(self, service: MetricsService) -> None:
        self._service = service

    def handle(self, path: str) -> Response:
        url = urlsplit(path)
        parts = [unquote(p) for p in url.path.removeprefix(PREFIX).split("/") if p]
        try:
            match parts:
                case ["strategies"]:
                    return _json(200, [s.to_dict() for s in self._service.summaries()])
                case ["strategies", name, version]:
                    found = self._service.version_summaries(name, version)
                    if not found:
                        return _json(404, {"error": f"no book for {name} version {version}"})
                    return _json(200, [s.to_dict() for s in found])
                case ["correlation"]:
                    return self._correlation(parse_qs(url.query).get("mode", ["paper"])[0])
        except Exception as exc:
            log.exception("metrics request %s failed", path)
            return _json(500, {"error": str(exc)})
        return _json(404, {"error": "not found"})

    def _correlation(self, mode_name: str) -> Response:
        try:
            mode = BookMode(mode_name)
        except ValueError:
            return _json(400, {"error": f"unknown mode {mode_name!r}"})
        matrix = self._service.correlation(mode)
        labels = [str(label) for label in matrix.index]
        return _json(200, {
            "mode": mode.value,
            "strategy_versions": labels,
            "matrix": [[float(v) for v in row] for row in matrix.to_numpy()],
        })


def _json(status: int, body: Any) -> Response:
    return status, "application/json", json.dumps(body, allow_nan=False).encode("utf-8")
