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
from short_interest_fakes import FixedShares

from auspex_backtesting.ownership import ShareCountPanel
from auspex_backtesting.short_interest import (
    FinraAuthError,
    FinraCalendar,
    FinraClient,
    ShortInterestFetcher,
    ShortInterestRecord,
    ShortInterestStore,
)
from auspex_backtesting.short_interest.job import ShortInterestConfig, UniverseShareBasis
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


def test_share_basis_by_ticker_goes_through_the_universe_company_and_skips_reused_tickers() -> None:
    counts = ShareCountPanel(pd.DataFrame([
        {"cik": "1", "value": 10e6, "end": date(2024, 12, 31), "filed": date(2025, 2, 1)},
        {"cik": "2", "value": 20e6, "end": date(2024, 12, 31), "filed": date(2025, 2, 1)},
        {"cik": "3", "value": 30e6, "end": date(2024, 12, 31), "filed": date(2025, 2, 1)},
    ]))
    splits = RecordedSplits()
    shares = UniverseShareBasis(
        [_member("1", "acme"), _member("2", "REUSED"), _member("3", "REUSED"), _member("4", None)],
        counts,
        splits,
    )

    count = shares.share_count("ACME", date(2025, 3, 1))
    assert count is not None and count.value == 10e6 and count.end == date(2024, 12, 31)
    assert shares.share_count("ACME", date(2025, 2, 1)) is None
    assert shares.share_count("REUSED", date(2025, 3, 1)) is None
    assert shares.share_count("NONE", date(2025, 3, 1)) is None

    assert shares.factor("acme", date(2025, 1, 1), date(2025, 3, 1)) == 0.5
    assert splits.asked == [("1", date(2025, 1, 1), date(2025, 3, 1))]
    assert shares.factor("REUSED", date(2025, 1, 1), date(2025, 3, 1)) is None
    assert shares.missing_reason("REUSED", date(2025, 1, 1), date(2025, 3, 1)) == (
        "ticker_history_uncertain"
    )
    assert shares.missing_reason("ACME", date(2025, 1, 1), date(2025, 3, 1)) is None


class RecordedSplits:
    """A factor of 0.5 for every CIK, recording what was asked."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, date, date]] = []

    def factor(self, cik: str, after: date, through: date) -> float | None:
        self.asked.append((cik, after, through))
        return 0.5

    def missing_reason(self, cik: str, after: date, through: date) -> None:
        return None


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


# --- split basis -------------------------------------------------------------------------------


def _split_store() -> ShortInterestStore:
    store = ShortInterestStore(FakeMinio())  # type: ignore[arg-type]
    jan_15, jan_31 = date(2025, 1, 15), date(2025, 1, 31)
    store.append("ACME", [
        ShortInterestRecord.from_counts(
            "ACME", jan_15, date(2025, 1, 24), short_interest_shares=1_000_000,
            average_daily_volume=250_000,
        ),
        ShortInterestRecord.from_counts(
            "ACME", jan_31, date(2025, 2, 11), short_interest_shares=150_000,
            average_daily_volume=25_000,
        ),
    ])
    return store


def test_pct_of_shares_restates_short_interest_and_share_count_to_one_basis() -> None:
    # 20M shares counted on 2024-12-31, then a 1-for-10 reverse split on 2025-01-20: the
    # 2025-01-31 short interest of 150k is on the post-split basis, the count is not.
    basis = FixedShares(
        {"ACME": 20_000_000}, splits=[("ACME", date(2025, 1, 20), 0.1)],
        filed=date(2025, 2, 1),
    )

    features = _split_store().features("ACME", date(2025, 2, 11), basis)

    assert features is not None
    assert features.short_interest_pct_of_shares == pytest.approx(7.5)


def test_pct_of_shares_restates_a_short_count_settled_before_a_split_published_after_it() -> None:
    # Short interest of 1.5M settles 2025-01-31, the 1-for-10 split is on 2025-02-05, FINRA
    # publishes on 2025-02-11 and the 2M count is taken after the split.
    store = ShortInterestStore(FakeMinio())  # type: ignore[arg-type]
    store.append("ACME", [ShortInterestRecord.from_counts(
        "ACME", date(2025, 1, 31), date(2025, 2, 11), short_interest_shares=1_500_000,
        average_daily_volume=100_000,
    )])
    basis = FixedShares(
        {"ACME": 2_000_000}, splits=[("ACME", date(2025, 2, 5), 0.1)],
        counted_on=date(2025, 2, 10),
    )

    features = store.features("ACME", date(2025, 2, 11), basis)

    assert features is not None
    assert features.short_interest_pct_of_shares == pytest.approx(7.5)



def test_pct_of_shares_is_missing_when_either_count_has_no_known_split_factor() -> None:
    store = _split_store()
    # The count is from 2024-12-31 and the short count from 2025-01-31; each interval to the
    # read date is unknown in turn.
    short_unknown = FixedShares(
        {"ACME": 2_000_000}, unknown_splits=["ACME"], unknown_after=date(2025, 1, 1)
    )
    count_unknown = FixedShares(
        {"ACME": 2_000_000}, unknown_splits=["ACME"], unknown_before=date(2025, 1, 1)
    )

    for basis in (short_unknown, count_unknown):
        features = store.features("ACME", date(2025, 2, 11), basis)
        assert features is not None
        assert features.short_interest_pct_of_shares is None
        assert features.short_interest_pct_missing == "split_history_unavailable"


def test_change_since_previous_restates_the_previous_period_across_a_split() -> None:
    basis = FixedShares({"ACME": 20_000_000}, splits=[("ACME", date(2025, 1, 20), 0.1)])

    features = _split_store().features("ACME", date(2025, 2, 11), basis)

    # 1,000,000 before the 1-for-10 split is 100,000 after it.
    assert features is not None
    assert features.change_since_previous_shares == 50_000
    assert features.change_since_previous_missing is None


def test_pct_and_change_are_missing_with_the_reason_when_the_split_basis_is_unknown() -> None:
    basis = FixedShares({"ACME": 20_000_000}, unknown_splits=["ACME"])

    features = _split_store().features("ACME", date(2025, 2, 11), basis)

    assert features is not None
    assert features.short_interest_pct_of_shares is None
    assert features.short_interest_pct_missing == "split_history_unavailable"
    assert features.change_since_previous_shares is None
    assert features.change_since_previous_missing == "split_history_unavailable"
    # Days to cover divides two counts FINRA reports on the same basis; it needs no factor.
    assert features.record.days_to_cover == pytest.approx(6.0)


def test_change_since_previous_is_missing_when_either_period_is_unreported() -> None:
    store = ShortInterestStore(FakeMinio())  # type: ignore[arg-type]
    store.append("ACME", [
        ShortInterestRecord.absent("ACME", date(2025, 1, 15), date(2025, 1, 24)),
        ShortInterestRecord.from_counts(
            "ACME", date(2025, 1, 31), date(2025, 2, 11), short_interest_shares=10,
            average_daily_volume=5,
        ),
    ])

    features = store.features("ACME", date(2025, 2, 11), None)
    first = store.features("ACME", date(2025, 1, 24), FixedShares({"ACME": 1_000}))

    assert features is not None and features.change_since_previous_missing == "not_reported"
    assert first is not None and first.change_since_previous_missing == "not_reported"
    assert first.short_interest_pct_of_shares is None
    assert first.short_interest_pct_missing == "not_reported"
