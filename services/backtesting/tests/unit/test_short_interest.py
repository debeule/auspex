from collections.abc import Mapping
from datetime import date
from typing import Any

import pytest
from ownership_fakes import FakeMinio
from short_interest_fakes import FixedShares

from auspex_backtesting.short_interest import (
    FinraCalendar,
    PeriodExistsError,
    ShortInterestFetcher,
    ShortInterestRecord,
    ShortInterestStore,
)

# --- fakes and builders ------------------------------------------------------------------------


class FakeFinra:
    """Serves FINRA API rows per settlement date and records every period asked for."""

    def __init__(self, periods: Mapping[date, list[dict[str, Any]]]) -> None:
        self.periods = dict(periods)
        self.requested: list[date] = []

    def records(self, settlement_date: date) -> list[dict[str, Any]]:
        self.requested.append(settlement_date)
        return self.periods.get(settlement_date, [])


def _row(symbol: str, settlement: date, short: int, adv: int) -> dict[str, Any]:
    return {
        "symbolCode": symbol,
        "settlementDate": settlement.isoformat(),
        "currentShortPositionQuantity": short,
        "averageDailyVolumeQuantity": adv,
        "daysToCoverQuantity": 1.0,
    }


def _record(
    settlement: date,
    publication: date,
    short: int | None = 1_000_000,
    adv: int | None = 250_000,
) -> ShortInterestRecord:
    return ShortInterestRecord.from_counts(
        "ACME", settlement, publication, short_interest_shares=short, average_daily_volume=adv
    )


def _store() -> tuple[ShortInterestStore, FakeMinio]:
    minio = FakeMinio()
    return ShortInterestStore(minio), minio  # type: ignore[arg-type]


# Two settlement periods with FINRA's published dates: the 7th business day after settlement.
JAN_15, JAN_24 = date(2025, 1, 15), date(2025, 1, 24)
JAN_31, FEB_11 = date(2025, 1, 31), date(2025, 2, 11)
CALENDAR = FinraCalendar(published={JAN_15: JAN_24, JAN_31: FEB_11})


# --- required tests ----------------------------------------------------------------------------


def test_as_of_returns_nothing_before_publication_date() -> None:
    store, _ = _store()
    dec_31 = date(2024, 12, 31)
    store.append("ACME", [
        _record(dec_31, date(2025, 1, 10), short=900_000),
        _record(JAN_15, JAN_24, short=1_000_000),
    ])

    on_23rd = store.as_of("ACME", date(2025, 1, 23))
    assert on_23rd is not None
    assert on_23rd.settlement_date == dec_31
    assert on_23rd.short_interest_shares == 900_000
    assert store.as_of("ACME", date(2025, 1, 9)) is None


def test_as_of_returns_the_latest_published_period() -> None:
    store, _ = _store()
    store.append("ACME", [_record(JAN_15, JAN_24, short=1_000_000)])
    store.append("ACME", [_record(JAN_31, FEB_11, short=1_200_000)])

    on_publication = store.as_of("ACME", JAN_24)
    later = store.as_of("ACME", date(2025, 3, 1))
    assert on_publication is not None and on_publication.settlement_date == JAN_15
    assert later is not None and later.settlement_date == JAN_31
    assert later.short_interest_shares == 1_200_000


def test_days_to_cover_is_short_interest_over_average_daily_volume() -> None:
    finra = FakeFinra({JAN_15: [_row("ACME", JAN_15, 1_000_000, 400_000)]})
    store, _ = _store()
    ShortInterestFetcher(store, finra, CALENDAR).fetch(["ACME"], JAN_15, date(2025, 1, 25))

    record = store.as_of("ACME", JAN_24)
    assert record is not None
    # FINRA's own figure is rounded and floored at 1.00; the stored one is the exact ratio.
    assert record.days_to_cover == pytest.approx(2.5)
    assert _record(JAN_15, JAN_24, short=1_000, adv=0).days_to_cover is None


def test_store_appends_new_periods_without_rewriting_existing_ones() -> None:
    store, _ = _store()
    store.append("ACME", [_record(JAN_15, JAN_24, short=1_000_000)])
    before = store.read("ACME")

    store.append("ACME", [_record(JAN_31, FEB_11, short=1_200_000)])
    after = store.read("ACME")

    assert len(after) == 2
    assert after.iloc[:1].reset_index(drop=True).equals(before.reset_index(drop=True))
    with pytest.raises(PeriodExistsError):
        store.append("ACME", [_record(JAN_15, JAN_24, short=5)])
    assert store.read("ACME").equals(after)


def test_missing_ticker_in_a_period_is_recorded_as_absent_not_zero() -> None:
    finra = FakeFinra({JAN_15: [_row("OTHR", JAN_15, 500, 100)]})
    store, _ = _store()
    ShortInterestFetcher(store, finra, CALENDAR).fetch(["ACME", "OTHR"], JAN_15, JAN_24)

    record = store.as_of("ACME", JAN_24)
    assert record is not None
    assert record.reported is False
    assert record.short_interest_shares is None
    assert record.average_daily_volume is None
    assert record.days_to_cover is None


def test_short_interest_pct_of_shares_is_null_when_shares_outstanding_unknown() -> None:
    store, _ = _store()
    store.append("ACME", [
        _record(JAN_15, JAN_24, short=1_000_000),
        _record(JAN_31, FEB_11, short=1_500_000),
    ])

    unknown = store.features("ACME", FEB_11, FixedShares({}))
    without_source = store.features("ACME", FEB_11, None)
    known = store.features("ACME", FEB_11, FixedShares({"ACME": 20_000_000}))

    assert unknown is not None and unknown.short_interest_pct_of_shares is None
    assert without_source is not None and without_source.short_interest_pct_of_shares is None
    assert known is not None and known.short_interest_pct_of_shares == pytest.approx(7.5)
    assert known.change_since_previous_shares == 500_000
    assert unknown.short_interest_pct_missing == "no_share_count"
    # Without split factors a change across periods cannot be ruled free of a split.
    assert without_source.change_since_previous_shares is None
    assert known.short_interest_pct_missing is None


def test_fetcher_stores_publication_date_from_the_finra_calendar_not_settlement_date() -> None:
    finra = FakeFinra({JAN_15: [_row("ACME", JAN_15, 1_000, 100)]})
    store, _ = _store()
    ShortInterestFetcher(store, finra, CALENDAR).fetch(["ACME"], JAN_15, JAN_24)

    stored = store.read("ACME")
    assert list(stored["settlement_date"]) == [JAN_15]
    assert list(stored["publication_date"]) == [JAN_24]
    assert store.as_of("ACME", date(2025, 1, 23)) is None


def test_period_already_stored_is_not_refetched() -> None:
    finra = FakeFinra({
        JAN_15: [_row("ACME", JAN_15, 1_000, 100)],
        JAN_31: [_row("ACME", JAN_31, 1_100, 100)],
    })
    store, _ = _store()
    fetcher = ShortInterestFetcher(store, finra, CALENDAR)
    fetcher.fetch(["ACME"], JAN_15, JAN_24)
    fetcher.fetch(["ACME"], JAN_15, FEB_11)

    assert finra.requested == [JAN_15, JAN_31]
    assert list(store.read("ACME")["settlement_date"]) == [JAN_15, JAN_31]


def test_coverage_report_states_first_available_settlement_date() -> None:
    # FINRA has nothing for the first calendar period (before its history starts).
    feb_14 = date(2025, 2, 14)
    finra = FakeFinra({
        JAN_31: [_row("ACME", JAN_31, 1_100, 100)],
        feb_14: [_row("ACME", feb_14, 1_200, 100)],
    })
    store, _ = _store()

    report = ShortInterestFetcher(store, finra, CALENDAR).fetch(
        ["ACME", "OTHR"], JAN_15, date(2025, 2, 27)
    )

    assert report.first_available_settlement_date == JAN_31
    assert report.last_settlement_date == feb_14
    assert report.unavailable_periods == [JAN_15]
    assert report.periods_stored == 2
    assert report.tickers_never_reported == ["OTHR"]
    assert report.as_dict()["first_available_settlement_date"] == "2025-01-31"
