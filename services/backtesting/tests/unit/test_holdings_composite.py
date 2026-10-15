from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from holdings_support import (
    CONFIG_DIR,
    MAY_15,
    MAY_31,
    REBALANCE,
    RULES_VERSION,
    FakeUniverse,
    TableHoldings,
    accepted,
    h9,
    insiders,
    member,
    opens,
    score,
    short_interest,
    snapshot,
    trade,
    with_cap,
)
from ownership_fakes import FakeMinio

from auspex_backtesting.ownership import OwnershipStore
from auspex_backtesting.ownership.reference import SHARES_OUTSTANDING_KEY, counts_frame
from auspex_backtesting.portfolio.scores import ScoreSnapshotExistsError, ScoreStore
from auspex_backtesting.scores.holdings_composite import (
    HoldingsScoreBuild,
    component_variant,
    score_version,
)
from auspex_backtesting.scores.job import holdings_score_build
from auspex_backtesting.short_interest import FinraCalendar, ShortInterestRecord, ShortInterestStore
from auspex_backtesting.universe import ShareCount, UniverseMember, UniverseStore

A, B, C = "0000000001", "0000000002", "0000000003"
CAPS = {A: 1e9, B: 1e9, C: 1e9}
TICKERS = {A: "TA", B: "TB", C: "TC"}
FINRA_CALENDAR = Path(__file__).resolve().parents[4] / "config" / "short_interest" / "finra_calendar.csv"


def _member(cik: str) -> UniverseMember:
    return member(cik, TICKERS[cik])


def _rows(frame: pd.DataFrame) -> dict[str, dict[str, object]]:
    return {str(r["cik"]): r for r in frame.to_dict("records")}


def test_name_below_h9_tradable_floor_is_not_scored_unless_no_floor_variant() -> None:
    members = [
        _member(A),
        with_cap(_member(B), 400e6),
        with_cap(_member(C), 1e9, volume=1.5e6),
    ]
    holdings = TableHoldings({c: (0.1, accepted(date(2024, 5, 15))) for c in (A, B, C)})
    short = short_interest({TICKERS[c]: {MAY_15: 2.0} for c in (A, B, C)})

    floored = score(members, holdings=holdings, short=short).compute(REBALANCE)
    unfloored = score(members, holdings=holdings, short=short, floor=False).compute(REBALANCE)

    assert set(floored.snapshot.rows["cik"]) == {A}
    assert floored.below_floor == (B, C)
    assert set(unfloored.snapshot.rows["cik"]) == {A, B, C}
    assert unfloored.below_floor == ()
    assert floored.snapshot.version == "1"
    assert unfloored.snapshot.version == "1-no_floor"


def test_short_interest_published_after_rebalance_is_not_used() -> None:
    # FINRA publishes the 31 May period on the rebalance date itself: not known before the open.
    finra = FinraCalendar({MAY_15: date(2024, 5, 24), MAY_31: REBALANCE})
    short = short_interest({"TA": {MAY_15: 2.0, MAY_31: 9.0}}, finra)
    holdings = TableHoldings({A: (0.1, accepted(date(2024, 5, 15)))})

    month = score([_member(A)], holdings=holdings, short=short, finra=finra).compute(REBALANCE)

    row = _rows(month.snapshot.rows)[A]
    assert row["days_to_cover"] == pytest.approx(2.0)
    assert row["days_to_cover_settlement"] == MAY_15


def test_lower_days_to_cover_ranks_higher() -> None:
    holdings = TableHoldings({c: (0.1, accepted(date(2024, 5, 15))) for c in (A, B, C)})
    short = short_interest({"TA": {MAY_15: 8.0}, "TB": {MAY_15: 1.0}, "TC": {MAY_15: 4.0}})

    month = score([_member(A), _member(B), _member(C)], holdings=holdings, short=short).compute(
        REBALANCE
    )

    rows = _rows(month.snapshot.rows)
    assert rows[B]["days_to_cover_rank"] > rows[C]["days_to_cover_rank"] > rows[A][
        "days_to_cover_rank"
    ]
    assert rows[B]["days_to_cover_rank"] == pytest.approx(1.0)


def test_offering_participation_purchase_is_excluded_from_insider_buying() -> None:
    bought = trade(A, date(2024, 4, 10), shares=10_000, price=10.0, traded=date(2024, 4, 9))
    offering = {"issuer_cik": A, "form": "424B5", "filing_date": date(2024, 4, 10),
                "accession_number": "OFFER"}
    holdings = TableHoldings({A: (0.1, accepted(date(2024, 5, 15)))})

    with_offering = score(
        [_member(A)], holdings=holdings, insider_panel=insiders([bought], CAPS, [offering])
    ).compute(REBALANCE)
    without = score(
        [_member(A)], holdings=holdings, insider_panel=insiders([bought], CAPS)
    ).compute(REBALANCE)

    assert _rows(with_offering.snapshot.rows)[A]["net_insider_buying"] == 0.0
    assert _rows(without.snapshot.rows)[A]["net_insider_buying"] == pytest.approx(100_000 / 1e9)


def test_no_insider_activity_scores_zero_not_missing() -> None:
    holdings = TableHoldings({A: (0.1, accepted(date(2024, 5, 15)))})

    month = score([_member(A)], holdings=holdings, insider_panel=insiders([], CAPS)).compute(
        REBALANCE
    )

    row = _rows(month.snapshot.rows)[A]
    assert row["net_insider_buying"] == 0.0
    assert row["components"] == 2
    assert month.left_out == ()


def test_missing_short_interest_is_missing_not_zero() -> None:
    holdings = TableHoldings({c: (0.1, accepted(date(2024, 5, 15))) for c in (A, B, C)})
    # A is absent from the latest published period, B has no record at all and C only one
    # from an earlier period: none is carried forward.
    short = short_interest({"TA": {date(2024, 4, 30): 3.0, MAY_15: None},
                            "TC": {date(2024, 4, 30): 3.0}})

    month = score(
        [_member(A), _member(B), _member(C)],
        holdings=holdings, insider_panel=insiders([], CAPS), short=short,
    ).compute(REBALANCE)

    rows = _rows(month.snapshot.rows)
    for cik in (A, B, C):
        assert pd.isna(rows[cik]["days_to_cover"])
        assert pd.isna(rows[cik]["days_to_cover_rank"])
        assert rows[cik]["days_to_cover_settlement"] is None
        assert rows[cik]["components"] == 2
        assert pd.Timestamp(rows[cik]["known_at_max"]) == accepted(date(2024, 5, 15))


def test_name_with_fewer_than_two_components_is_left_out_and_counted() -> None:
    # B has no share count, market cap or short interest record; C has insider buying only.
    holdings = TableHoldings({A: (0.1, accepted(date(2024, 5, 15)))})
    caps = {A: 1e9, C: 1e9}

    month = score(
        [_member(A), _member(B), _member(C)], holdings=holdings, insider_panel=insiders([], caps)
    ).compute(REBALANCE)

    assert list(month.snapshot.rows["cik"]) == [A]
    assert month.left_out == (B, C)
    assert month.members == 3


def test_score_is_mean_of_available_component_percentile_ranks() -> None:
    holdings = TableHoldings({
        A: (0.30, accepted(date(2024, 5, 15))),
        B: (0.20, accepted(date(2024, 5, 15))),
        C: (0.10, accepted(date(2024, 5, 15))),
    })
    trades = [trade(B, date(2024, 5, 1), shares=1_000), trade(C, date(2024, 5, 1), shares=9_000)]
    short = short_interest({"TA": {MAY_15: 5.0}, "TB": {MAY_15: 1.0}, "TC": {MAY_15: 3.0}})

    month = score(
        [_member(A), _member(B), _member(C)],
        holdings=holdings, insider_panel=insiders(trades, CAPS), short=short,
    ).compute(REBALANCE)

    frame = month.snapshot.rows
    assert list(frame["cik"]) == [B, C, A]
    rows = _rows(frame)
    assert rows[A]["score"] == pytest.approx((1 + 1 / 3 + 1 / 3) / 3)
    assert rows[B]["score"] == pytest.approx((2 / 3 + 2 / 3 + 1) / 3)
    assert rows[C]["score"] == pytest.approx((1 / 3 + 1 + 2 / 3) / 3)


def test_ties_are_broken_by_cik() -> None:
    holdings = TableHoldings({c: (0.1, accepted(date(2024, 5, 15))) for c in (B, A)})

    month = score(
        [_member(B), _member(A)], holdings=holdings, insider_panel=insiders([], CAPS)
    ).compute(REBALANCE)

    rows = _rows(month.snapshot.rows)
    assert rows[A]["specialist_13f_ownership_rank"] > rows[B]["specialist_13f_ownership_rank"]
    assert list(month.snapshot.rows["cik"]) == [A, B]


def test_known_at_max_is_latest_input_time_and_before_rebalance_open() -> None:
    holdings = TableHoldings({A: (0.1, accepted(date(2024, 5, 15)))})
    trades = [trade(A, date(2024, 5, 20)), trade(A, date(2024, 3, 20))]
    short = short_interest({"TA": {MAY_15: 2.0}})

    month = score(
        [_member(A)], holdings=holdings, insider_panel=insiders(trades, CAPS), short=short
    ).compute(REBALANCE)

    known = pd.Timestamp(_rows(month.snapshot.rows)[A]["known_at_max"])
    # 15 May's period is published 24 May; known by the end of that day, New York time.
    published = pd.Timestamp("2024-05-25", tz="America/New_York").tz_convert("UTC")
    assert known == published
    assert known < opens()
    assert holdings.asked == [opens().to_pydatetime()]
    month.snapshot.validate()

    without_short = score(
        [_member(A)], holdings=holdings, insider_panel=insiders(trades, CAPS)
    ).compute(REBALANCE)
    assert pd.Timestamp(_rows(without_short.snapshot.rows)[A]["known_at_max"]) == accepted(
        date(2024, 5, 20)
    )


def test_two_component_variant_is_chosen_by_short_interest_start_date_only() -> None:
    hypothesis = h9()

    assert component_variant(hypothesis, date(2021, 6, 15)) == "two_component"
    assert component_variant(hypothesis, None) == "two_component"
    assert component_variant(hypothesis, date(2014, 1, 2)) == "two_component"
    assert component_variant(hypothesis, date(2014, 1, 1)) == "three_component"
    assert component_variant(hypothesis, date(2013, 12, 31)) == "three_component"

    holdings = TableHoldings({A: (0.1, accepted(date(2024, 5, 15)))})
    short = short_interest({"TA": {MAY_15: 2.0}})
    month = score(
        [_member(A)], holdings=holdings, insider_panel=insiders([], CAPS), short=short,
        variant="two_component",
    ).compute(REBALANCE)
    row = _rows(month.snapshot.rows)[A]
    assert row["variant"] == "two_component"
    assert pd.isna(row["days_to_cover"])
    assert row["components"] == 2


def test_snapshot_for_a_rebalance_date_is_never_overwritten() -> None:
    minio = FakeMinio()
    store = ScoreStore(minio)  # type: ignore[arg-type]
    holdings = TableHoldings({A: (0.1, accepted(date(2024, 5, 15)))})
    universe = FakeUniverse([snapshot([_member(A)])])
    first = HoldingsScoreBuild(
        score([_member(A)], holdings=holdings, insider_panel=insiders([], CAPS)),
        universe, RULES_VERSION, store, today=lambda: date(2024, 7, 1),
    ).run()
    written = dict(minio.objects)

    changed = TableHoldings({A: (0.9, accepted(date(2024, 5, 15)))})
    second = HoldingsScoreBuild(
        score([_member(A)], holdings=changed, insider_panel=insiders([], CAPS)),
        universe, RULES_VERSION, store, today=lambda: date(2024, 7, 1),
    ).run()

    assert first["snapshots_written"] == 1
    assert second["snapshots_written"] == 0
    assert minio.objects == written
    month = score([_member(A)], holdings=changed, insider_panel=insiders([], CAPS)).compute(
        REBALANCE
    )
    with pytest.raises(ScoreSnapshotExistsError):
        store.write(month.snapshot)


def test_coverage_report_includes_component_rank_correlations() -> None:
    june, july = REBALANCE, date(2024, 7, 1)
    members = [_member(A), _member(B), _member(C)]
    holdings = TableHoldings({
        A: (0.30, accepted(date(2024, 5, 15))),
        B: (0.20, accepted(date(2024, 5, 15))),
        C: (0.10, accepted(date(2024, 5, 15))),
    })
    trades = [trade(A, date(2024, 5, 1), shares=9_000), trade(B, date(2024, 5, 1), shares=1_000)]
    # July's latest published period is 14 June's, published 26 June.
    periods = (MAY_15, MAY_31, date(2024, 6, 14))
    short = short_interest({
        t: dict.fromkeys(periods, days) for t, days in (("TA", 5.0), ("TB", 1.0), ("TC", 3.0))
    })
    snapshots = [snapshot(members, june), snapshot(members, july)]
    composite = score(
        members, holdings=holdings, insider_panel=insiders(trades, CAPS), short=short,
        snapshots=snapshots,
    )

    report = HoldingsScoreBuild(
        composite, FakeUniverse(snapshots), RULES_VERSION, ScoreStore(FakeMinio()),  # type: ignore[arg-type]
        today=lambda: date(2024, 8, 1),
    ).run()

    assert report["variant"] == "three_component"
    assert [m["month"] for m in report["months"]] == ["2024-06", "2024-07"]
    assert report["months"][0] == {
        "month": "2024-06", "members": 3, "below_floor": 0, "scored": 3, "left_out": 0,
        "specialist_missing": {},
    }
    correlations = report["component_rank_correlations"]["2024"]
    # Ownership and insider ranks agree name for name; days to cover ranks B, C, A.
    assert correlations["specialist_13f_ownership~net_insider_buying"] == pytest.approx(1.0)
    assert correlations["specialist_13f_ownership~days_to_cover"] == pytest.approx(-0.5)
    assert correlations["net_insider_buying~days_to_cover"] == pytest.approx(-0.5)


def test_score_version_keeps_floor_variants_apart() -> None:
    assert score_version(1, floor=True) == "1"
    assert score_version(1, floor=False) == "1-no_floor"


def test_build_from_stores_reads_panels_and_chooses_variant_from_short_interest() -> None:
    minio = FakeMinio()
    UniverseStore(minio).write(snapshot([_member(A)]))  # type: ignore[arg-type]
    OwnershipStore(minio).write(  # type: ignore[arg-type]
        SHARES_OUTSTANDING_KEY,
        counts_frame({A: [ShareCount(10e6, date(2024, 3, 31), date(2024, 5, 10))]}),
    )
    store = ShortInterestStore(minio)  # type: ignore[arg-type]
    store.append("TA", [ShortInterestRecord.from_counts(
        "TA", MAY_15, date(2024, 5, 24), short_interest_shares=200_000,
        average_daily_volume=100_000,
    )])

    report = holdings_score_build(
        minio, RULES_VERSION, FINRA_CALENDAR, floor=True,  # type: ignore[arg-type]
        config_dir=CONFIG_DIR, registry_path=CONFIG_DIR / "registry.jsonl",
        today=date(2024, 7, 1),
    ).run()

    # Short interest starts in 2024, after H9's in-sample start: two components.
    assert report["variant"] == "two_component"
    assert report["snapshots_written"] == 1
    stored = ScoreStore(minio).read("h9", "1", REBALANCE)  # type: ignore[arg-type]
    assert stored is not None
    row = _rows(stored.rows)[A]
    assert row["specialist_13f_ownership"] == 0.0
    assert row["net_insider_buying"] == 0.0
    assert pd.Timestamp(row["known_at_max"]) == accepted(date(2024, 5, 10))
