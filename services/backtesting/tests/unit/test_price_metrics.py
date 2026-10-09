from datetime import UTC, datetime
from unittest.mock import MagicMock

from prometheus_client import CollectorRegistry

from auspex_backtesting.api import create_app
from auspex_backtesting.price_metrics import PriceRefreshMetrics
from auspex_backtesting.prices.price_refresher import PriceDataUnavailableError, RefreshResult


def _sample(registry: CollectorRegistry, name: str, **labels: str) -> float | None:
    return registry.get_sample_value(name, labels or None)


def _app(refresher: MagicMock, metrics: PriceRefreshMetrics, tickers: list[str]):  # type: ignore[no-untyped-def]
    return create_app(refresher=refresher, tickers=tickers, metrics=metrics).test_client()


def _metrics(now: datetime, registry: CollectorRegistry | None = None) -> PriceRefreshMetrics:
    return PriceRefreshMetrics(registry or CollectorRegistry(), now=lambda: now)


def test_metrics_endpoint_exposes_refresh_counters_and_last_success_timestamp() -> None:
    registry = CollectorRegistry()
    now = datetime(2026, 10, 7, 22, 31, tzinfo=UTC)
    refresher = MagicMock()
    refresher.refresh.side_effect = lambda t: RefreshResult(t, 1, "2026-10-07")
    client = _app(refresher, _metrics(now, registry), ["SRPT", "XBI"])

    assert client.post("/prices/refresh").status_code == 200
    body = client.get("/metrics").get_data(as_text=True)

    assert "auspex_price_refresh_runs_total" in body
    assert _sample(registry, "auspex_price_refresh_runs_total", outcome="success") == 1
    assert _sample(registry, "auspex_price_refresh_runs_total", outcome="failed") is None
    assert _sample(registry, "auspex_price_tickers_refreshed_total") == 2
    assert _sample(registry, "auspex_price_tickers_failed_total") == 0
    assert _sample(registry, "auspex_price_refresh_last_success_timestamp_seconds") == (
        now.timestamp()
    )
    assert "auspex_price_refresh_last_success_timestamp_seconds" in body


def test_failed_ticker_increments_failure_counter_without_raising_from_metrics() -> None:
    registry = CollectorRegistry()
    now = datetime(2026, 10, 7, 22, 31, tzinfo=UTC)

    def refresh(ticker: str) -> RefreshResult:
        if ticker == "SRPT":
            raise PriceDataUnavailableError("SRPT: no data from Yahoo or Stooq")
        return RefreshResult(ticker, 0, "2026-10-07")

    refresher = MagicMock()
    refresher.refresh.side_effect = refresh
    client = _app(refresher, _metrics(now, registry), ["SRPT", "XBI"])

    resp = client.post("/prices/refresh", json={})

    assert resp.status_code == 502
    assert resp.get_json()["failed"] == {"SRPT": "SRPT: no data from Yahoo or Stooq"}
    assert _sample(registry, "auspex_price_tickers_failed_total") == 1
    assert _sample(registry, "auspex_price_tickers_refreshed_total") == 1
    assert _sample(registry, "auspex_price_refresh_runs_total", outcome="failed") == 1
    # A run with any failed ticker is not a successful refresh.
    assert _sample(registry, "auspex_price_refresh_last_success_timestamp_seconds") is None
    assert client.get("/metrics").status_code == 200


def test_sessions_since_success_counts_nyse_sessions_strictly_between() -> None:
    registry = CollectorRegistry()
    clock = {"now": datetime(2026, 10, 5, 22, 31, tzinfo=UTC)}  # Monday
    metrics = PriceRefreshMetrics(registry, now=lambda: clock["now"])
    metrics.record_run(refreshed=2, failed=0)

    def sessions_at(now: datetime) -> float | None:
        clock["now"] = now
        return _sample(registry, "auspex_price_refresh_sessions_since_success")

    assert sessions_at(datetime(2026, 10, 6, 23, 0, tzinfo=UTC)) == 0  # Tuesday's run pending
    assert sessions_at(datetime(2026, 10, 7, 9, 0, tzinfo=UTC)) == 1  # Tuesday missed
    assert sessions_at(datetime(2026, 10, 8, 1, 0, tzinfo=UTC)) == 2  # Tuesday and Wednesday


def test_sessions_since_success_skips_weekends_and_nyse_holidays() -> None:
    registry = CollectorRegistry()
    clock = {"now": datetime(2026, 11, 25, 22, 31, tzinfo=UTC)}  # Wednesday before Thanksgiving
    metrics = PriceRefreshMetrics(registry, now=lambda: clock["now"])
    metrics.record_run(refreshed=1, failed=0)

    clock["now"] = datetime(2026, 11, 30, 9, 0, tzinfo=UTC)  # Monday
    # Thursday 26th is closed; Friday 27th is the only session before Monday.
    assert _sample(registry, "auspex_price_refresh_sessions_since_success") == 1


def test_sessions_count_from_service_start_until_the_first_success() -> None:
    registry = CollectorRegistry()
    clock = {"now": datetime(2026, 10, 5, 12, 0, tzinfo=UTC)}  # Monday, service starts
    PriceRefreshMetrics(registry, now=lambda: clock["now"])

    clock["now"] = datetime(2026, 10, 8, 1, 0, tzinfo=UTC)  # Thursday, no refresh has worked
    assert _sample(registry, "auspex_price_refresh_sessions_since_success") == 2


def test_each_app_gets_its_own_metrics_registry_by_default() -> None:
    # Two apps in one process (the test suite, or a reload) must not collide on collector names.
    first = create_app(refresher=MagicMock(), tickers=[]).test_client()
    second = create_app(refresher=MagicMock(), tickers=[]).test_client()

    assert first.get("/metrics").status_code == 200
    assert second.get("/metrics").status_code == 200
