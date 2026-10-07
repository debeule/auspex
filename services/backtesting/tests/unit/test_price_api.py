from unittest.mock import MagicMock

from auspex_backtesting.api import create_app
from auspex_backtesting.prices.price_refresher import PriceDataUnavailableError, RefreshResult


def _client(refresher: MagicMock, tickers: list[str]):  # type: ignore[no-untyped-def]
    return create_app(refresher=refresher, tickers=tickers).test_client()


def test_refresh_without_body_refreshes_the_configured_universe() -> None:
    refresher = MagicMock()
    refresher.refresh.side_effect = lambda t: RefreshResult(t, 1, "2026-10-07")

    resp = _client(refresher, ["SRPT", "XBI"]).post("/prices/refresh")

    assert resp.status_code == 200
    assert [c.args[0] for c in refresher.refresh.call_args_list] == ["SRPT", "XBI"]
    assert resp.get_json()["results"][0] == {
        "ticker": "SRPT",
        "rows_added": 1,
        "last_date": "2026-10-07",
    }


def test_one_failing_ticker_fails_the_request_but_the_rest_still_refresh() -> None:
    def refresh(ticker: str) -> RefreshResult:
        if ticker == "SRPT":
            raise PriceDataUnavailableError("SRPT: no data from Yahoo or Stooq")
        return RefreshResult(ticker, 0, "2026-10-07")

    refresher = MagicMock()
    refresher.refresh.side_effect = refresh

    resp = _client(refresher, ["SRPT", "XBI"]).post("/prices/refresh", json={})

    assert resp.status_code == 502
    body = resp.get_json()
    assert body["failed"] == {"SRPT": "SRPT: no data from Yahoo or Stooq"}
    assert [r["ticker"] for r in body["results"]] == ["XBI"]


def test_request_body_can_narrow_the_tickers() -> None:
    refresher = MagicMock()
    refresher.refresh.side_effect = lambda t: RefreshResult(t, 0, "2026-10-07")

    resp = _client(refresher, ["SRPT", "XBI"]).post("/prices/refresh", json={"tickers": ["XBI"]})

    assert resp.status_code == 200
    assert [c.args[0] for c in refresher.refresh.call_args_list] == ["XBI"]


def test_health() -> None:
    assert _client(MagicMock(), []).get("/health").status_code == 200
