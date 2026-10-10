from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, Metric
from prometheus_client.registry import Collector

from auspex_strategy.runtime.streaming import StreamingRuntime


class _RuntimeCollector(Collector):
    def __init__(self, runtime: StreamingRuntime) -> None:
        self._runtime = runtime

    def collect(self) -> Iterator[Metric]:
        failures = CounterMetricFamily(
            "auspex_strategy_decide_failures",
            "decide() calls that crashed, timed out or returned invalid intents",
            labels=["strategy"],
        )
        paused = GaugeMetricFamily(
            "auspex_strategy_paused",
            "1 while the strategy is paused by an unhealthy declared input",
            labels=["strategy"],
        )
        counts = self._runtime.failure_counts
        for slot in self._runtime.slots:
            failures.add_metric([slot.name], counts.get(slot.name, 0))
            paused.add_metric([slot.name], 1.0 if self._runtime.is_paused(slot.name) else 0.0)
        rejected = CounterMetricFamily(
            "auspex_strategy_rejected_events", "corroborated events that could not be read"
        )
        rejected.add_metric([], self._runtime.rejected_events)
        yield failures
        yield paused
        yield rejected


class HealthEndpoint:
    """`/health` (liveness plus per-strategy failures and pauses) and `/metrics`."""

    def __init__(self, runtime: StreamingRuntime) -> None:
        self._runtime = runtime
        self._registry = CollectorRegistry()
        self._registry.register(_RuntimeCollector(runtime))

    def handle(self, path: str) -> tuple[int, str, bytes]:
        if path == "/health":
            counts = self._runtime.failure_counts
            body = {
                "status": "ok",
                "strategies": {
                    slot.name: {
                        "failures": counts.get(slot.name, 0),
                        "paused": self._runtime.is_paused(slot.name),
                    }
                    for slot in self._runtime.slots
                },
            }
            return 200, "application/json", json.dumps(body).encode("utf-8")
        if path == "/metrics":
            return 200, "text/plain; version=0.0.4", generate_latest(self._registry)
        return 404, "text/plain", b"not found"


def serve(endpoint: HealthEndpoint, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            status, content_type, body = endpoint.handle(self.path.split("?", 1)[0])
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass  # healthchecks every few seconds would drown the log

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, name="health-http", daemon=True).start()
    return server
