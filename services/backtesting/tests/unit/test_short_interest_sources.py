import base64
import io
import json
import urllib.error
import urllib.request
from datetime import date
from email.message import Message
from pathlib import Path
from typing import Any, Self

import pandas as pd
import pytest
from ownership_fakes import FakeMinio

from auspex_backtesting.ownership import ShareCountPanel
from auspex_backtesting.short_interest import (
    FinraAuthError,
    FinraCalendar,
    FinraClient,
    ShortInterestFetcher,
    ShortInterestStore,
)
from auspex_backtesting.short_interest.job import ShortInterestConfig, UniverseShareCounts
from auspex_backtesting.universe.model import UniverseMember

_CALENDAR_CSV = Path(__file__).resolve().parents[4] / "config" / "short_interest" / "finra_calendar.csv"
_DATA_URL = "https://finra.example/data/group/otcMarket/name/consolidatedShortInterest"
_TOKEN_URL = "https://fip.example/oauth2/access_token?grant_type=client_credentials"


# --- calendar ----------------------------------------------------------------------------------


def test_rule_reproduces_every_publication_date_finra_published() -> None:
    calendar = FinraCalendar.from_csv(_CALENDAR_CSV)

    assert calendar.published
    for settlement, publication in calendar.published.items():
        assert calendar.rule_publication_date(settlement) == publication


def test_settlement_dates_are_the_15th_and_month_end_moved_back_to_a_session() -> None:
    calendar = FinraCalendar()

    # 2025-03-15 is a Saturday; 2025-05-31 is a Saturday; 2024-03-29 is Good Friday.
    assert calendar.settlement_dates(date(2025, 3, 1), date(2025, 3, 31)) == [
        date(2025, 3, 14), date(2025, 3, 31),
    ]
    assert calendar.settlement_dates(date(2025, 5, 1), date(2025, 5, 31))[-1] == date(2025, 5, 30)
    assert calendar.settlement_dates(date(2024, 3, 1), date(2024, 3, 31))[-1] == date(2024, 3, 28)


def test_published_schedule_replaces_the_rule_for_its_month() -> None:
    calendar = FinraCalendar(published={date(2025, 1, 14): date(2025, 1, 27)})

    assert calendar.settlement_dates(date(2025, 1, 1), date(2025, 1, 31)) == [date(2025, 1, 14)]
    assert calendar.publication_date(date(2025, 1, 14)) == date(2025, 1, 27)


def test_periods_published_after_the_cutoff_are_left_out() -> None:
    calendar = FinraCalendar()
    # Settles 2025-11-14, published 2025-11-25.
    assert calendar.periods(date(2025, 11, 1), date(2025, 11, 24)) == []
    assert [p.settlement_date for p in calendar.periods(date(2025, 11, 1), date(2025, 11, 25))] == [
        date(2025, 11, 14)
    ]


# --- FINRA client ------------------------------------------------------------------------------


class _Response(io.BytesIO):
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class FakeOpener:
    """Answers token requests with a numbered token and data requests from `pages`."""

    def __init__(self, pages: list[list[dict[str, Any]]], reject_data_with: list[int] | None = None):
        self.pages = pages
        self.reject = list(reject_data_with or [])
        self.requests: list[urllib.request.Request] = []
        self.tokens = 0

    def __call__(self, request: urllib.request.Request, timeout: float) -> _Response:
        self.requests.append(request)
        if request.full_url == _TOKEN_URL:
            self.tokens += 1
            return _Response(json.dumps({"access_token": f"t{self.tokens}"}).encode())
        if self.reject:
            raise urllib.error.HTTPError(request.full_url, self.reject.pop(0), "no", Message(), None)
        return _Response(json.dumps(self.pages.pop(0)).encode() if self.pages else b"")


def _client(opener: FakeOpener) -> FinraClient:
    return FinraClient(_DATA_URL, _TOKEN_URL, "id", "secret", opener=opener, sleep=lambda _: None)


def _bodies(opener: FakeOpener) -> list[dict[str, Any]]:
    return [
        json.loads(r.data)  # type: ignore[arg-type]
        for r in opener.requests if r.full_url == _DATA_URL
    ]


def test_client_reads_a_period_page_by_page_with_a_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("auspex_backtesting.short_interest.finra_client.PAGE_SIZE", 2)
    rows = [{"symbolCode": s} for s in ("A", "B", "C")]
    opener = FakeOpener([rows[:2], rows[2:]])

    assert _client(opener).records(date(2025, 11, 14)) == rows

    token_request = opener.requests[0]
    assert token_request.get_header("Authorization") == (
        "Basic " + base64.b64encode(b"id:secret").decode()
    )
    assert [b["offset"] for b in _bodies(opener)] == [0, 2]
    assert _bodies(opener)[0]["compareFilters"] == [{
        "compareType": "EQUAL", "fieldName": "settlementDate", "fieldValue": "2025-11-14",
    }]
    assert all(
        r.get_header("Authorization") == "Bearer t1"
        for r in opener.requests if r.full_url == _DATA_URL
    )


def test_client_returns_no_rows_for_an_empty_response() -> None:
    assert _client(FakeOpener([])).records(date(2014, 1, 15)) == []


def test_client_fetches_a_new_token_once_when_the_old_one_expires() -> None:
    opener = FakeOpener([[{"symbolCode": "A"}]], reject_data_with=[401])

    assert _client(opener).records(date(2025, 11, 14)) == [{"symbolCode": "A"}]
    assert opener.tokens == 2

    refused = FakeOpener([], reject_data_with=[401, 401])
    with pytest.raises(FinraAuthError):
        _client(refused).records(date(2025, 11, 14))


def test_client_refuses_to_start_without_a_credential() -> None:
    with pytest.raises(FinraAuthError):
        FinraClient(_DATA_URL, _TOKEN_URL, "", "secret")


def test_config_reads_every_setting_from_the_environment() -> None:
    config = ShortInterestConfig.from_env({
        "FINRA_SHORT_INTEREST_URL": _DATA_URL,
        "FINRA_TOKEN_URL": _TOKEN_URL,
        "FINRA_API_CLIENT_ID": "id",
        "FINRA_API_CLIENT_SECRET": "secret",
        "SHORT_INTEREST_HISTORY_START": "2021-06-01",
    })
    assert config.start == date(2021, 6, 1)
    with pytest.raises(KeyError):
        ShortInterestConfig.from_env({})


# --- shares outstanding by ticker --------------------------------------------------------------


def _member(cik: str, ticker: str | None) -> UniverseMember:
    return UniverseMember(
        cik=cik, ticker=ticker, ticker_source="current", name=cik, sic="2836",
        exchange="Nasdaq", market_cap_usd=None, median_dollar_volume_20d=None,
        entered_on=date(2014, 1, 31), exited_on=None, exit_reason=None,
        price_coverage="complete", coverage_note="",
    )


def test_share_counts_by_ticker_go_through_the_universe_company_and_skip_reused_tickers() -> None:
    counts = ShareCountPanel(pd.DataFrame([
        {"cik": "1", "value": 10e6, "end": date(2024, 12, 31), "filed": date(2025, 2, 1)},
        {"cik": "2", "value": 20e6, "end": date(2024, 12, 31), "filed": date(2025, 2, 1)},
        {"cik": "3", "value": 30e6, "end": date(2024, 12, 31), "filed": date(2025, 2, 1)},
    ]))
    shares = UniverseShareCounts(
        [_member("1", "acme"), _member("2", "REUSED"), _member("3", "REUSED"), _member("4", None)],
        counts,
    )

    assert shares.shares_outstanding("ACME", date(2025, 3, 1)) == 10e6
    assert shares.shares_outstanding("ACME", date(2025, 2, 1)) is None
    assert shares.shares_outstanding("REUSED", date(2025, 3, 1)) is None
    assert shares.shares_outstanding("NONE", date(2025, 3, 1)) is None


# --- coverage ----------------------------------------------------------------------------------


def test_coverage_lists_a_period_missing_between_stored_ones_as_a_gap() -> None:
    jan_31, feb_14, feb_28 = date(2025, 1, 31), date(2025, 2, 14), date(2025, 2, 28)

    class Finra:
        def records(self, settlement_date: date) -> list[dict[str, Any]]:
            if settlement_date in (jan_31, feb_28):
                return [{"symbolCode": "ACME", "currentShortPositionQuantity": 10,
                         "averageDailyVolumeQuantity": 5}]
            return []

    store = ShortInterestStore(FakeMinio())  # type: ignore[arg-type]
    report = ShortInterestFetcher(store, Finra(), FinraCalendar()).fetch(
        ["ACME"], jan_31, date(2025, 3, 12)
    )

    assert report.gaps == [feb_14]
    assert report.unavailable_periods == [feb_14]
    assert (report.first_available_settlement_date, report.last_settlement_date) == (jan_31, feb_28)
