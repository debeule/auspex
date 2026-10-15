import math
from datetime import date, timedelta

import pytest
from catalyst_support import FakeWeb
from filing_support import (
    ACME,
    BETA,
    FULL_INDEX,
    USER_AGENT,
    StoreMinio,
    archive,
    entry,
    filing_index,
    filing_pages,
    fixture,
    quarter_index,
    risk_document,
    section,
    universe_with,
    utc,
)

from auspex_backtesting.filings import (
    ArchivedSection,
    RiskFactorChangeScore,
    TextChangeScore,
    cut_item_1a,
    filing_to_text,
)
from auspex_backtesting.market_sim.calendar import MarketCalendar

_CAL = MarketCalendar()
_NO_CHANGE = (
    "There have been no material changes to the risk factors disclosed in Part I, Item 1A of our "
    "Annual Report on Form 10-K for the year ended December 31, 2023."
)


# --- section cutting ---------------------------------------------------------------------------


def test_item_1a_is_cut_from_a_10k_fixture_matching_golden_text() -> None:
    cut = cut_item_1a(filing_to_text(fixture("10k.htm")), "10-K")

    assert cut.status == "cut"
    assert cut.text == fixture("10k.item1a.txt").strip()


def test_item_1a_is_cut_from_a_10q_part_ii_fixture() -> None:
    cut = cut_item_1a(filing_to_text(fixture("10q.htm")), "10-Q")

    assert cut.status == "cut"
    assert cut.text == fixture("10q.item1a.txt").strip()


def test_section_that_cannot_be_cut_is_recorded_missing_with_reason() -> None:
    no_heading = "<html><body><div>Item 1. Business</div><p>We make drugs.</p></body></html>"
    no_end = "<html><body><div>Item 1A. Risk Factors</div><p>Trials may fail.</p></body></html>"
    acc = f"{ACME}-24-000001"
    web = FakeWeb(filing_pages(ACME, acc, "10-K", "2024-03-01 16:05:00", "2023-12-31", no_heading))
    store, minio = archive(web)

    stored = store.get(entry(ACME, "10-K", "2024-03-01", acc))

    assert (stored.status, stored.reason, stored.text) == ("section_missing", "no_item_1a_heading", "")
    assert store.get(entry(ACME, "10-K", "2024-03-01", acc)) == stored
    assert cut_item_1a(filing_to_text(no_end), "10-K").reason == "no_end_heading"
    late = f"{ACME}-24-000002"
    page = filing_pages(ACME, late, "10-K", "2024-03-01 16:05:00", "2023-12-31", no_end)
    page[next(iter(page))] = page[next(iter(page))].replace("Accepted", "Received")
    unaccepted, _ = archive(FakeWeb(page))
    assert unaccepted.get(entry(ACME, "10-K", "2024-03-01", late)).reason == "no_acceptance_time"
    assert any(k.startswith(f"filings/item1a/{ACME}/{acc}") for k in minio.objects)


def test_no_material_changes_statement_scores_zero_change() -> None:
    cut = cut_item_1a(filing_to_text(risk_document("10-Q", _NO_CHANGE)), "10-Q")
    earlier = section(BETA, "b-1", "10-Q", "2023-06-30", utc("2023-08-05T20:00:00"),
                      "Our trials may fail. We need capital.")
    later = section(BETA, "b-2", "10-Q", "2024-06-30", utc("2024-08-06T20:00:00"), cut.text,
                    status=cut.status)

    (score,) = TextChangeScore().score([earlier, later]).scores

    assert cut.status == "no_change_statement"
    assert (score.accession, score.change, score.jaccard) == ("b-2", 0.0, 1.0)


# --- the score ---------------------------------------------------------------------------------


def test_identical_sections_score_zero_change() -> None:
    text = "Our clinical trials may fail. We depend on a single manufacturer."
    earlier = section(ACME, "a-1", "10-K", "2022-12-31", utc("2023-03-01T21:00:00"), text)
    later = section(ACME, "a-2", "10-K", "2023-12-31", utc("2024-03-01T21:00:00"), text)

    (score,) = TextChangeScore().score([earlier, later]).scores

    assert score.change == pytest.approx(0.0, abs=1e-12)
    assert score.jaccard == 1.0


def test_fixture_pair_scores_within_0_001_of_hand_computed_value() -> None:
    # Term counts: earlier the=2 drug=1 may=1 fail=1 trial=1, later the=1 drug=1 may=1 fail=1
    # approval=1. Cosine = 5 / sqrt(8 * 5) = 0.79057, so change = 0.20943; Jaccard = 4 / 6.
    earlier = section(ACME, "a-1", "10-K", "2022-12-31", utc("2023-03-01T21:00:00"),
                      "The drug may fail the trial.")
    later = section(ACME, "a-2", "10-K", "2023-12-31", utc("2024-03-01T21:00:00"),
                    "THE drug may fail approval!")

    (score,) = TextChangeScore().score([earlier, later]).scores

    assert score.change == pytest.approx(1 - 5 / math.sqrt(40), abs=0.001)
    assert score.change == pytest.approx(0.20943, abs=0.001)
    assert score.jaccard == pytest.approx(4 / 6, abs=0.001)


def test_comparison_filing_is_same_form_and_fiscal_period_one_year_earlier() -> None:
    def s(acc: str, form: str, period: str, accepted: str, text: str = "trials may fail") -> ArchivedSection:
        return section(ACME, acc, form, period, utc(accepted), text)

    sections = [
        s("k22", "10-K", "2022-12-31", "2023-03-01T21:00:00"),
        s("q2-22", "10-Q", "2022-06-30", "2022-08-08T20:00:00"),
        s("q3-22", "10-Q", "2022-09-30", "2022-11-07T21:00:00"),
        s("q2-23", "10-Q", "2023-06-30", "2023-08-07T20:00:00"),
        s("q3-23", "10-Q", "2023-09-30", "2023-11-06T21:00:00"),
        s("k23", "10-K", "2023-12-31", "2024-02-28T21:00:00"),
        section(BETA, "beta-k22", "10-K", "2022-12-31", utc("2024-05-01T21:00:00"), "x"),
        section(BETA, "beta-k23", "10-K", "2023-12-31", utc("2024-03-01T21:00:00"), "x"),
    ]

    result = TextChangeScore().score(sections)
    compared = {sc.accession: sc.comparison_accession for sc in result.scores}

    assert compared == {"q2-23": "q2-22", "q3-23": "q3-22", "k23": "k22"}
    assert result.unscored["no_comparison"] == 5


def test_score_known_at_is_later_filing_acceptance_time_not_filing_date() -> None:
    # Accepted at 18:05 New York time on 2024-02-29: EDGAR dates the filing the next day.
    acc = f"{ACME}-24-000010"
    web = FakeWeb(filing_pages(ACME, acc, "10-K", "2024-02-29 18:05:00", "2023-12-31",
                               risk_document("10-K", "Our trials may fail approval.")))
    store, _ = archive(web)
    later = store.get(entry(ACME, "10-K", "2024-03-01", acc))
    earlier = section(ACME, "a-1", "10-K", "2022-12-31", utc("2023-03-01T21:00:00"),
                      "Our trials may fail.")

    (score,) = TextChangeScore().score([earlier, later]).scores

    assert later.accepted_at == utc("2024-02-29T23:05:00")
    assert score.known_at == utc("2024-02-29T23:05:00")
    assert score.known_at.date() != later.filed


def test_score_accepted_after_rebalance_open_is_not_used() -> None:
    rebalance = date(2024, 3, 1)
    opens = _CAL.session_open(rebalance)
    minio = StoreMinio()
    universe = universe_with(minio, "2024-03", rebalance, ACME)
    sections = [
        section(ACME, "k22", "10-K", "2022-12-31", utc("2023-02-27T21:00:00"), "trials may fail"),
        section(ACME, "q3-22", "10-Q", "2022-09-30", utc("2022-11-07T21:00:00"), "trials fail"),
        section(ACME, "q3-23", "10-Q", "2023-09-30", utc("2023-11-06T21:00:00"), "trials fail"),
        section(ACME, "k23", "10-K", "2023-12-31", opens, "trials may fail badly"),
    ]
    scores = TextChangeScore().score(sections).scores

    month = RiskFactorChangeScore(scores, universe, 1, "h10", "1").compute(rebalance)

    assert month.snapshot.rows["accession"].tolist() == ["q3-23"]
    month.snapshot.validate(_CAL)


def test_member_without_score_in_last_120_days_is_left_out_and_counted() -> None:
    rebalance = date(2024, 3, 1)
    opens = _CAL.session_open(rebalance)
    minio = StoreMinio()
    universe = universe_with(minio, "2024-03", rebalance, ACME, BETA)
    stale = opens - timedelta(days=120, seconds=1)
    sections = [
        section(ACME, "a22", "10-K", "2022-12-31", utc("2023-02-27T21:00:00"), "trials fail"),
        section(ACME, "a23", "10-K", "2023-12-31", utc("2024-02-27T21:00:00"), "trials fail"),
        section(BETA, "b22", "10-Q", "2022-09-30", stale - timedelta(days=365), "trials fail"),
        section(BETA, "b23", "10-Q", "2023-09-30", stale, "trials fail"),
    ]
    scores = TextChangeScore().score(sections).scores

    month = RiskFactorChangeScore(scores, universe, 1, "h10", "1").compute(rebalance)

    assert month.snapshot.rows["cik"].tolist() == [ACME]
    assert month.members == 2
    assert month.left_out == (BETA,)


def test_least_changed_filer_ranks_highest() -> None:
    rebalance = date(2024, 3, 1)
    minio = StoreMinio()
    universe = universe_with(minio, "2024-03", rebalance, ACME, BETA)
    sections = [
        section(ACME, "a22", "10-K", "2022-12-31", utc("2023-02-27T21:00:00"),
                "trials may fail and we need capital"),
        section(ACME, "a23", "10-K", "2023-12-31", utc("2024-02-27T21:00:00"),
                "pandemic disruption cyber attack tariffs litigation"),
        section(BETA, "b22", "10-K", "2022-12-31", utc("2023-02-27T21:00:00"),
                "trials may fail and we need capital"),
        section(BETA, "b23", "10-K", "2023-12-31", utc("2024-02-26T21:00:00"),
                "trials may fail and we need more capital"),
    ]
    scores = TextChangeScore().score(sections).scores

    rows = RiskFactorChangeScore(scores, universe, 1, "h10", "1").compute(rebalance).snapshot.rows

    assert rows["cik"].tolist() == [BETA, ACME]
    assert rows["score"].tolist() == sorted(rows["score"], reverse=True)
    assert (rows["score"] == -rows["change"]).all()


# --- fetching ----------------------------------------------------------------------------------


def test_filing_already_archived_is_not_refetched() -> None:
    acc = f"{ACME}-24-000001"
    pages = filing_pages(ACME, acc, "10-K", "2024-03-01 16:05:00", "2023-12-31",
                         risk_document("10-K", "Our trials may fail."))
    pages[f"{FULL_INDEX}/2024/QTR1/master.idx"] = quarter_index(
        [(ACME, "10-K", "2024-03-01", acc), (BETA, "8-K", "2024-03-02", f"{BETA}-24-000002")]
    )
    web = FakeWeb(pages)
    store, minio = archive(web)
    index = filing_index(web, minio)

    for _ in range(2):
        for e in index.quarter(2024, 1):
            store.get(e)

    assert sorted(web.requested) == sorted(pages)
    assert [e.accession for e in index.quarter(2024, 1)] == [acc]
    assert store.get(entry(ACME, "10-K", "2024-03-01", acc)).status == "cut"


def test_requests_carry_the_configured_user_agent() -> None:
    acc = f"{ACME}-24-000001"
    pages = filing_pages(ACME, acc, "10-K", "2024-03-01 16:05:00", "2023-12-31",
                         risk_document("10-K", "Our trials may fail."))
    pages[f"{FULL_INDEX}/2024/QTR1/master.idx"] = quarter_index([(ACME, "10-K", "2024-03-01", acc)])
    web = FakeWeb(pages)
    store, minio = archive(web)

    for e in filing_index(web, minio).quarter(2024, 1):
        store.get(e)

    assert len(web.requested) == 3
    assert web.user_agents == {USER_AGENT}
