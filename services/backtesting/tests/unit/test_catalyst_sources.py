import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from catalyst_support import (
    ACCEPTANCE_RELEASE,
    ACME,
    BETA,
    EXTENSION_RELEASE,
    FR_API,
    FULL_INDEX,
    HALF_YEAR_RELEASE,
    MEMBERS,
    TODAY,
    USER_AGENT,
    FakeMinio,
    FakeWeb,
    accession,
    adcom_notices,
    exhibit_url,
    fr_notice,
    fr_text,
    member,
    panel_from,
    press_releases,
    sec_web,
)

from auspex_backtesting.catalysts import (
    Catalyst,
    CatalystPanel,
    ExtractionResult,
    HttpSource,
)
from auspex_backtesting.catalysts.job import (
    CatalystPanelBuild,
    UniverseNotBuiltError,
    universe_members,
)
from auspex_backtesting.catalysts.panel import partition_key
from auspex_backtesting.catalysts.phrases import (
    date_mentions,
    name_tokens,
    pdufa_date,
    pdufa_hits,
    product_aliases,
    sentences,
)
from auspex_backtesting.universe.store import UniverseStore

_Q1 = (date(2024, 1, 1), date(2024, 3, 31))


def _acceptance(n: int = 10, cik: str = ACME, accepted: str = "2024-02-05 16:31:07"
                ) -> tuple[str, str, str, str]:
    return (cik, accession(cik, n), accepted, ACCEPTANCE_RELEASE)


# --- phrase rules ------------------------------------------------------------------------------


@pytest.mark.parametrize(("sentence", "precision", "start", "end"), [
    ("The PDUFA target action date is March 2027.", "month", date(2027, 3, 1), date(2027, 3, 31)),
    ("The PDUFA date falls in Q3 2027.", "quarter", date(2027, 7, 1), date(2027, 9, 30)),
    ("A PDUFA goal date in the third quarter of 2027 is expected.", "quarter",
     date(2027, 7, 1), date(2027, 9, 30)),
    ("The company anticipates a PDUFA date in 1H 2026.", "half", date(2026, 1, 1), date(2026, 6, 30)),
    ("The FDA set a goal date of 15 March 2027.", "day", date(2027, 3, 15), date(2027, 3, 15)),
    ("The FDA set a target action date of Sept. 3, 2027.", "day", date(2027, 9, 3), date(2027, 9, 3)),
])
def test_phrase_rules_keep_the_precision_the_date_was_written_at(
    sentence: str, precision: str, start: date, end: date
) -> None:
    when = pdufa_date(sentence)

    assert when is not None
    assert (when.precision, when.period_start, when.period_end) == (precision, start, end)


def test_date_written_just_before_the_phrase_is_taken_when_none_follows() -> None:
    when = pdufa_date("The NDA has a March 15, 2027 PDUFA date.")

    assert when is not None and when.period_start == date(2027, 3, 15)
    assert pdufa_date("On March 15, 2027 the company announced many things about the PDUFA.") is None


def test_revision_takes_the_date_after_to() -> None:
    when = pdufa_date("FDA moved the PDUFA date from March 15, 2027 to June 15, 2027.")

    assert when is not None and when.period_start == date(2027, 6, 15)


def test_impossible_day_is_not_a_date_and_day_spans_are_not_reread_as_months() -> None:
    assert date_mentions("February 30, 2027") == []
    (only,) = date_mentions("on March 15, 2027")
    assert only.precision == "day"


def test_sentences_do_not_break_after_us_or_inc() -> None:
    text = "<p>ACME Bio, Inc. said the U.S. Food and Drug Administration accepted it. Next one.</p>"

    assert sentences(text) == [
        "ACME Bio, Inc. said the U.S. Food and Drug Administration accepted it.", "Next one."]


def test_plain_text_documents_split_at_blank_lines() -> None:
    text = "First paragraph wraps\nonto a second line.\n\nThe PDUFA date is June 1, 2027."

    assert sentences(text) == ["First paragraph wraps onto a second line.",
                               "The PDUFA date is June 1, 2027."]


def test_product_aliases_prefer_application_numbers_and_skip_years() -> None:
    aliases = product_aliases(
        "the NDA 214567 for ABC-123 (Brandix®, acmetinib) presented at ASCO 2024 under sBLA 761001")

    assert aliases == ("nda214567", "bla761001", "abc123", "brandix", "acmetinib")


def test_hit_without_a_product_borrows_one_from_the_sentences_before() -> None:
    (hit,) = pdufa_hits(ACCEPTANCE_RELEASE)

    assert hit.aliases == ("acmetinib",)


def test_company_names_compare_without_suffixes_or_punctuation() -> None:
    assert name_tokens("ACME BIO, INC.") == name_tokens("Acme Bio Inc") == ("acme", "bio")
    assert name_tokens("LILLY ELI & CO") == ("lilly", "eli")


# --- EDGAR press releases ----------------------------------------------------------------------


def test_only_item_7_01_or_8_01_filings_have_their_exhibit_read() -> None:
    acc = accession(ACME, 10)
    web = sec_web([_acceptance()], items={acc: ("2.02", "9.01")})

    result = press_releases(web, FakeMinio()).collect({ACME}, *_Q1)

    assert result.rows == ()
    assert result.stats["other_items"] == 1
    assert exhibit_url(ACME, acc) not in web.requested


def test_filing_index_without_items_is_counted_not_read_further() -> None:
    acc = accession(ACME, 10)
    web = sec_web([_acceptance()], items={acc: ()})

    result = press_releases(web, FakeMinio()).collect({ACME}, *_Q1)

    assert result.stats["without_items"] == 1
    assert exhibit_url(ACME, acc) not in web.requested


def test_filings_outside_the_range_or_universe_are_not_fetched() -> None:
    web = sec_web([_acceptance(), _acceptance(11, accepted="2024-03-20 09:00:00"),
                   (BETA, accession(BETA, 3), "2024-03-04 07:00:00", HALF_YEAR_RELEASE)])

    result = press_releases(web, FakeMinio()).collect({ACME}, date(2024, 1, 1), date(2024, 3, 1))

    assert result.stats["filings"] == 1
    assert [r.document_id for r in result.rows] == [accession(ACME, 10)]
    assert not any(str(int(BETA)) in u and "index.htm" in u for u in web.requested)


def test_sec_refusal_stops_the_run_without_retrying() -> None:
    web = sec_web([_acceptance(10), _acceptance(11, accepted="2024-02-06 09:00:00")], refuse_after=3)

    result = press_releases(web, FakeMinio()).collect({ACME}, *_Q1)

    # master index, first filing index and exhibit, then one refused request and nothing more.
    assert len(web.requested) == 4
    assert result.stats["blocked"] == 1
    assert [r.document_id for r in result.rows] == [accession(ACME, 10)]


def test_requests_to_sec_are_paced_at_five_per_second_and_carry_the_user_agent() -> None:
    sleeps: list[float] = []
    web = sec_web([_acceptance()])

    press_releases(web, FakeMinio(), sleeps).collect({ACME}, *_Q1)

    assert len(web.requested) == 3
    assert sleeps == [0.2, 0.2]
    assert web.user_agents == {USER_AGENT}


def test_pacing_waits_only_for_what_remains_of_the_interval() -> None:
    now = [0.0]
    sleeps: list[float] = []
    source = HttpSource(USER_AGENT, 0.2, fetch=lambda u, a: b"", clock=lambda: now[0],
                        sleep=sleeps.append)

    source.get("https://a.example/1")
    now[0] = 0.15
    source.get("https://a.example/2")
    now[0] = 1.0
    source.get("https://a.example/3")

    assert sleeps == [pytest.approx(0.05)]


def test_user_agent_is_required() -> None:
    with pytest.raises(ValueError, match="User-Agent"):
        HttpSource("  ", 0.2, fetch=lambda u, a: b"")


def test_index_of_a_quarter_in_progress_is_read_again_on_the_next_run() -> None:
    filing = (ACME, accession(ACME, 30), "2026-08-03 08:00:00", EXTENSION_RELEASE)
    web = sec_web([filing])
    minio = FakeMinio()
    current = f"{FULL_INDEX}/2026/QTR3/master.idx"
    in_progress = f"{FULL_INDEX}/2026/QTR4/master.idx"
    web.pages[in_progress] = web.pages[current]

    for _ in range(2):
        press_releases(web, minio).collect({ACME}, date(2026, 7, 1), TODAY)

    assert web.requested.count(current) == 1
    assert web.requested.count(in_progress) == 2


# --- Federal Register notices ------------------------------------------------------------------


def _notice_web(agenda: str, title: str = "Oncologic Drugs Advisory Committee; Notice of Meeting",
                published: str = "2024-03-01", number: str = "2024-04411") -> FakeWeb:
    notice = fr_notice(number, title, published, "The meeting will be held on April 18, 2024.")
    return FakeWeb({notice["raw_text_url"]: fr_text(agenda)}, {"2024-01-01": [notice]})


def test_sponsor_matches_universe_name_with_words_in_any_order() -> None:
    web = _notice_web("The committee will discuss BLA 761234 for donanemab, submitted by Eli Lilly "
                      "and Company, for the treatment of early Alzheimer's disease.")
    lilly = member("0000059478", "LILLY ELI & CO", "LLY")

    (row,) = adcom_notices(web, FakeMinio()).collect([lilly], *_Q1).rows

    assert row.cik == "0000059478"
    assert row.aliases == ("bla761234", "donanemab")


def test_sponsor_matching_two_universe_companies_is_left_unmatched() -> None:
    web = _notice_web("NDA 218765 for acmetinib, submitted by ACME Bio, Inc., for solid tumors.")
    twins = [member(ACME, "ACME BIO, INC."), member("0001111111", "Acme Bio Inc")]

    result = adcom_notices(web, FakeMinio()).collect(twins, *_Q1)

    assert [r.cik for r in result.rows] == [None]
    assert result.stats["unmatched"] == 1


def test_notice_without_a_sponsor_phrase_matches_a_company_named_in_its_agenda() -> None:
    web = _notice_web("The committee will discuss the application from Beta Therapeutics for "
                      "BTX-401 in adults.")

    (row,) = adcom_notices(web, FakeMinio()).collect(MEMBERS, *_Q1).rows

    assert row.cik == BETA


def test_cancelled_meeting_notice_is_skipped_and_counted() -> None:
    web = _notice_web("NDA 218765 for acmetinib, submitted by ACME Bio, Inc., for solid tumors.",
                      title="Oncologic Drugs Advisory Committee; Notice of Meeting; Cancellation")

    result = adcom_notices(web, FakeMinio()).collect(MEMBERS, *_Q1)

    assert result.rows == ()
    assert result.stats["withdrawals_skipped"] == 1


def test_other_fda_notices_and_notices_outside_the_range_are_ignored() -> None:
    other = fr_notice("2024-00001", "Agency Information Collection Activities; Proposed Collection",
                      "2024-02-01", "")
    late = fr_notice("2024-00002", "Oncologic Drugs Advisory Committee; Notice of Meeting",
                     "2024-03-28", "The meeting will be held on May 2, 2024.")
    web = FakeWeb({}, {"2024-01-01": [other, late]})

    result = adcom_notices(web, FakeMinio()).collect(MEMBERS, date(2024, 1, 1), date(2024, 3, 15))

    assert result.rows == ()
    assert web.requested == [u for u in web.requested if u.startswith(FR_API)]


def test_listing_pages_are_all_read() -> None:
    pages = {1: [fr_notice("2024-00001", "Oncologic Drugs Advisory Committee; Notice of Meeting",
                           "2024-01-10", "The meeting will be held on February 20, 2024.")],
             2: [fr_notice("2024-00002", "Oncologic Drugs Advisory Committee; Notice of Meeting",
                           "2024-01-12", "The meeting will be held on March 5, 2024.")]}
    texts = {n["raw_text_url"]: fr_text("NDA 218765 for acmetinib, submitted by ACME Bio, Inc., "
                                        "for solid tumors.") for p in pages.values() for n in p}

    def web(url: str, user_agent: str) -> bytes:
        if url.startswith(FR_API):
            page = int(url.rsplit("page=", 1)[1].split("&", 1)[0])
            return json.dumps({"total_pages": 2, "results": pages[page]}).encode()
        return texts[url].encode()

    result = adcom_notices(web, FakeMinio()).collect(MEMBERS, *_Q1)

    assert [r.document_id for r in result.rows] == ["2024-00001", "2024-00002"]


# --- panel -------------------------------------------------------------------------------------


def _row(cik: str, aliases: tuple[str, ...], day: date, known: datetime, doc: str = "d1",
         kind: str = "pdufa") -> Catalyst:
    return Catalyst("edgar", kind, cik, aliases[0] if aliases else "", aliases,  # type: ignore[arg-type]
                    "day", day, day, known, doc, f"https://x.example/{doc}", "PDUFA ...")


def test_append_is_idempotent_and_partitions_by_source_and_disclosure_quarter() -> None:
    minio = FakeMinio()
    panel = panel_from(minio)
    rows = [_row(ACME, ("acmetinib",), date(2024, 10, 15), datetime(2024, 2, 5, tzinfo=UTC)),
            _row(ACME, ("acmetinib",), date(2025, 1, 15), datetime(2024, 7, 1, tzinfo=UTC), "d2")]

    assert panel.append(rows) == 2
    assert panel.append(rows) == 0
    assert sorted(minio.objects) == ["catalysts/edgar/2024q1.parquet", "catalysts/edgar/2024q3.parquet"]
    assert partition_key(rows[0]) == "catalysts/edgar/2024q1.parquet"
    assert panel_from(minio).rows() == rows


def test_as_of_requires_a_timezone_aware_time() -> None:
    with pytest.raises(ValueError, match="timezone"):
        panel_from(FakeMinio()).as_of(ACME, datetime(2024, 3, 1))  # noqa: DTZ001


def test_as_of_drops_past_catalysts_that_binaries_between_still_reports() -> None:
    panel = panel_from(FakeMinio())
    panel.append([_row(ACME, ("acmetinib",), date(2024, 3, 1), datetime(2024, 1, 5, tzinfo=UTC))])
    later = datetime(2024, 4, 1, tzinfo=UTC)

    assert panel.as_of(ACME, later) == []
    assert len(panel.binaries_between(ACME, date(2024, 2, 20), date(2024, 3, 10), later)) == 1


def test_different_products_of_one_company_are_separate_catalysts() -> None:
    panel = panel_from(FakeMinio())
    panel.append([
        _row(ACME, ("acmetinib",), date(2024, 10, 15), datetime(2024, 2, 5, tzinfo=UTC)),
        _row(ACME, ("btx401",), date(2024, 11, 20), datetime(2024, 3, 5, tzinfo=UTC), "d2"),
        _row(ACME, ("acmetinib",), date(2024, 12, 1), datetime(2024, 3, 6, tzinfo=UTC), "d3",
             kind="adcom"),
    ])

    effective = panel.as_of(ACME, datetime(2024, 4, 1, tzinfo=UTC))

    assert [(r.catalyst_type, r.period_start) for r in effective] == [
        ("pdufa", date(2024, 10, 15)), ("pdufa", date(2024, 11, 20)), ("adcom", date(2024, 12, 1))]


def test_rows_naming_no_product_revise_only_each_other() -> None:
    panel = panel_from(FakeMinio())
    panel.append([
        _row(ACME, (), date(2024, 10, 15), datetime(2024, 2, 5, tzinfo=UTC)),
        _row(ACME, ("btx401",), date(2024, 11, 20), datetime(2024, 3, 5, tzinfo=UTC), "d2"),
        _row(ACME, (), date(2025, 1, 15), datetime(2024, 3, 6, tzinfo=UTC), "d3"),
    ])

    effective = panel.as_of(ACME, datetime(2024, 4, 1, tzinfo=UTC))

    assert [r.period_start for r in effective] == [date(2024, 11, 20), date(2025, 1, 15)]


def test_coverage_counts_years_members_unmatched_notices_and_precision() -> None:
    panel = panel_from(FakeMinio())
    unmatched = Catalyst("federal_register", "adcom", None, "x", ("x",), "day", date(2024, 4, 1),
                         date(2024, 4, 1), datetime(2024, 3, 1, 11, tzinfo=UTC), "2024-1", "u", "...")
    panel.append([
        _row(ACME, ("acmetinib",), date(2024, 10, 15), datetime(2024, 2, 5, tzinfo=UTC)),
        _row(ACME, ("acmetinib",), date(2025, 1, 15), datetime(2024, 7, 1, tzinfo=UTC), "d2"),
        unmatched,
    ])

    assert panel.coverage(MEMBERS) == {
        "catalysts_per_year": {2024: {"pdufa": 1}, 2025: {"pdufa": 1}},
        "members": 2,
        "members_with_catalysts": 1,
        "member_share_with_catalysts": 0.5,
        "unmatched_adcom_notices": 1,
        "pdufa_hits_by_precision": {"day": 2},
    }


# --- build -------------------------------------------------------------------------------------


class _Source:
    def __init__(self, result: ExtractionResult) -> None:
        self.result = result
        self.calls: list[tuple[object, date, date]] = []

    def collect(self, who: object, since: date, until: date) -> ExtractionResult:
        self.calls.append((who, since, until))
        return self.result


def test_build_matches_universe_members_and_reports_an_incomplete_run() -> None:
    row = _row(ACME, ("acmetinib",), date(2024, 10, 15), datetime(2024, 2, 5, tzinfo=UTC))
    edgar = _Source(ExtractionResult((row,), {"filings": 1, "blocked": 1}))
    notices = _Source(ExtractionResult((), {}))
    panel = panel_from(FakeMinio())

    summary = CatalystPanelBuild(panel, edgar, notices, lambda: MEMBERS  # type: ignore[arg-type]
                                 ).run(*_Q1)

    assert edgar.calls == [({ACME, BETA}, *_Q1)]
    assert notices.calls == [(MEMBERS, *_Q1)]
    assert summary["complete"] is False
    assert summary["added"] == {"edgar": 1, "federal_register": 0}
    assert summary["coverage"]["members_with_catalysts"] == 1
    assert panel.rows() == [row]


def test_universe_members_are_listed_once_per_cik_and_require_a_built_universe() -> None:
    minio = FakeMinio()
    store = UniverseStore(minio)  # type: ignore[arg-type]
    with pytest.raises(UniverseNotBuiltError):
        universe_members(store, 1)

    store.write_listings(1, [MEMBERS[0], MEMBERS[0], MEMBERS[1]], TODAY)

    assert [m.cik for m in universe_members(store, 1)] == [ACME, BETA]


def test_panel_reads_ignore_cached_documents() -> None:
    minio = FakeMinio()
    press_releases(sec_web([_acceptance()]), minio).collect({ACME}, *_Q1)

    assert CatalystPanel(minio).rows() == []  # type: ignore[arg-type]
    assert any(k.startswith("catalyst-documents/") for k in minio.objects)



def test_catalyst_build_from_env_reads_urls_and_paces_sec_at_five_per_second(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from auspex_backtesting.api import catalyst_build_from_env

    rules = tmp_path / "rules.yaml"
    rules.write_text((Path(__file__).parents[4] / "config/universe/rules.yaml").read_text())
    for key, value in {
        "MINIO_ENDPOINT": "minio:9000", "MINIO_ACCESS_KEY": "k", "MINIO_SECRET_KEY": "s",
        "UNIVERSE_RULES_PATH": str(rules), "SEC_USER_AGENT": USER_AGENT,
        "SEC_FULL_INDEX_URL": "https://sec.example/full-index/",
        "SEC_ARCHIVES_URL": "https://sec.example/data/",
        "FEDERAL_REGISTER_API_URL": "https://fr.example/documents.json",
    }.items():
        monkeypatch.setenv(key, value)

    build = catalyst_build_from_env()

    edgar = build._press_releases
    assert edgar._full_index_url == "https://sec.example/full-index"
    assert edgar._archives_url == "https://sec.example/data"
    assert edgar._sec._interval == 0.2
    assert build._adcom_notices._api_url == "https://fr.example/documents.json"
    assert build._adcom_notices._fr._interval == 1.0
