"""Prometheus metrics for the price service's refresh endpoint."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

from prometheus_client import CollectorRegistry, Counter
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

from auspex_backtesting.market_sim.calendar import MarketCalendar


class PriceRefreshMetrics:
    """Counters for each `/prices/refresh` call and how many NYSE sessions it has fallen behind.

    A run succeeds only when every ticker refreshed. `auspex_price_refresh_sessions_since_success`
    counts the sessions strictly between the last success (or the service's start, before any
    success) and today, both as UTC dates: the nightly run for a session lands after its close, so
    today's session is not missed yet.
    """

    def __init__(
        self,
        registry: CollectorRegistry,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        calendar: MarketCalendar | None = None,
    ) -> None:
        self.registry = registry
        self._now = now
        self._calendar = calendar or MarketCalendar()
        self._baseline = now()
        self._runs = Counter(
            "auspex_price_refresh_runs_total",
            "Price refresh requests by outcome; failed means at least one ticker failed",
            ["outcome"],
            registry=registry,
        )
        self._refreshed = Counter(
            "auspex_price_tickers_refreshed_total",
            "Tickers whose snapshot refreshed",
            registry=registry,
        )
        self._failed = Counter(
            "auspex_price_tickers_failed_total",
            "Tickers that raised during a refresh",
            registry=registry,
        )
        self.last_success: datetime | None = None
        registry.register(_SinceSuccess(self))

    def record_run(self, *, refreshed: int, failed: int) -> None:
        self._refreshed.inc(refreshed)
        self._failed.inc(failed)
        if failed:
            self._runs.labels(outcome="failed").inc()
            return
        self._runs.labels(outcome="success").inc()
        self._baseline = self.last_success = self._now()

    def sessions_since_success(self) -> int:
        start = self._baseline.astimezone(UTC).date() + timedelta(days=1)
        end = self._now().astimezone(UTC).date() - timedelta(days=1)
        if start > end:
            return 0
        return self._calendar.trading_days_in(start, end)


class _SinceSuccess(Collector):
    """Computed at scrape time, so the session count advances while nothing calls the service."""

    def __init__(self, metrics: PriceRefreshMetrics) -> None:
        self._metrics = metrics

    def collect(self) -> Iterator[GaugeMetricFamily]:
        # Absent until the first success: a zero timestamp would read as 1970.
        if self._metrics.last_success is not None:
            yield GaugeMetricFamily(
                "auspex_price_refresh_last_success_timestamp_seconds",
                "Unix time of the last refresh in which every ticker refreshed",
                value=self._metrics.last_success.timestamp(),
            )
        yield GaugeMetricFamily(
            "auspex_price_refresh_sessions_since_success",
            "NYSE sessions since the last fully successful refresh, or since the service started",
            value=self._metrics.sessions_since_success(),
        )
