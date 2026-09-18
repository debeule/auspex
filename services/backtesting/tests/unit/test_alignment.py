from datetime import UTC, date, datetime

import pandas as pd
import pytest

from auspex_backtesting.alignment.aligner import (
    CorroborationRef,
    SignalRef,
    align,
    align_corroboration,
    align_signal,
)


def _prices(dates: list[str]) -> pd.DataFrame:
    idx = pd.DatetimeIndex(dates, tz="UTC", name="date")
    return pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 50000.0},
        index=idx,
    )


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=UTC)


def test_signal_excluded_from_price_window_predating_disclosure():
    signal = SignalRef(event_id="e1", published_date=_dt("2023-01-11T10:00:00"))
    prices = _prices(["2023-01-09", "2023-01-10", "2023-01-11", "2023-01-12"])
    result = align_signal(signal, prices)
    dates = [idx.date() for idx in result.index]
    assert date(2023, 1, 9) not in dates
    assert date(2023, 1, 10) not in dates
    assert date(2023, 1, 11) in dates


def test_corroboration_aligns_to_corroborated_at_not_first_detected_at():
    ref = CorroborationRef(
        entity_key="BCL11A",
        corroborated_at=_dt("2023-01-10T10:00:00"),
        first_detected_at=_dt("2023-01-12T09:00:00"),
    )
    prices = _prices(["2023-01-09", "2023-01-10", "2023-01-11", "2023-01-12"])
    result = align_corroboration(ref, prices)
    dates = [idx.date() for idx in result.index]
    assert date(2023, 1, 9) not in dates
    assert date(2023, 1, 10) in dates


def test_superseded_corroboration_uses_its_own_participant_set_not_the_latest():
    superseded = CorroborationRef(
        entity_key="BCL11A",
        corroborated_at=_dt("2023-01-10T10:00:00"),
        first_detected_at=_dt("2023-01-11T09:00:00"),
        superseded_by="newer_hash",
    )
    superseding = CorroborationRef(
        entity_key="BCL11A",
        corroborated_at=_dt("2023-02-15T10:00:00"),
        first_detected_at=_dt("2023-02-16T09:00:00"),
    )
    prices = _prices(["2023-01-09", "2023-01-10", "2023-02-14", "2023-02-15"])
    assert align_corroboration(superseded, prices).index[0].date() == date(2023, 1, 10)
    assert align_corroboration(superseding, prices).index[0].date() == date(2023, 2, 15)


def test_patent_aligns_to_publication_date_not_filing_date():
    # US patent: filed Jan 2022, A1 published July 2023 (~18-month gap)
    signal = SignalRef(event_id="epo-001", published_date=_dt("2023-07-12T10:00:00"))
    prices = _prices(["2022-01-12", "2023-07-12", "2023-07-13"])
    result = align_signal(signal, prices)
    dates = [idx.date() for idx in result.index]
    assert date(2022, 1, 12) not in dates
    assert date(2023, 7, 12) in dates


def test_trial_aligns_to_post_date_not_submission_date():
    signal = SignalRef(event_id="nct-001", published_date=_dt("2023-03-15T10:00:00"))
    prices = _prices(["2022-09-07", "2023-03-15", "2023-03-16"])
    result = align_signal(signal, prices)
    dates = [idx.date() for idx in result.index]
    assert date(2022, 9, 7) not in dates
    assert date(2023, 3, 15) in dates


def test_retrieved_at_far_later_than_published_date_uses_published_date():
    signal = SignalRef(event_id="e1", published_date=_dt("2022-03-09T10:00:00"))
    prices = _prices(["2022-03-08", "2022-03-09", "2022-03-10", "2023-07-05"])
    result = align_signal(signal, prices)
    assert result.index[0].date() == date(2022, 3, 9)


def test_backfilled_document_does_not_leak_into_an_earlier_window():
    signal = SignalRef(event_id="e1", published_date=_dt("2022-06-01T10:00:00"))
    prices = _prices(["2022-05-31", "2022-06-01", "2022-06-02"])
    result = align_signal(signal, prices)
    assert all(idx.date() >= date(2022, 6, 1) for idx in result.index)


def test_join_attempt_using_ingested_at_raises():
    with pytest.raises(ValueError, match="ingested_at"):
        align(_dt("2023-01-11T10:00:00"), "ingested_at", _prices(["2023-01-11"]))


def test_signal_published_after_market_close_aligns_to_next_session():
    # 2023-01-04 22:00 UTC = 17:00 EST — one hour after NYSE close
    signal = SignalRef(event_id="e1", published_date=_dt("2023-01-04T22:00:00"))
    prices = _prices(["2023-01-04", "2023-01-05", "2023-01-06"])
    result = align_signal(signal, prices)
    assert result.index[0].date() == date(2023, 1, 5)


def test_signal_on_market_holiday_aligns_to_next_trading_day():
    # 2023-01-16 is Martin Luther King Jr. Day — NYSE closed
    signal = SignalRef(event_id="e1", published_date=_dt("2023-01-16T10:00:00"))
    prices = _prices(["2023-01-17", "2023-01-18"])
    result = align_signal(signal, prices)
    assert result.index[0].date() == date(2023, 1, 17)
