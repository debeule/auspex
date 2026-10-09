from datetime import UTC, date, datetime, timedelta

from catalyst_support import (
    ACCEPTANCE_RELEASE,
    ACME,
    BETA,
    EXTENSION_RELEASE,
    FR_API,
    HALF_YEAR_RELEASE,
    MEMBERS,
    RESULTS_RELEASE,
    FakeMinio,
    FakeWeb,
    accession,
    adcom_notices,
    fr_notice,
    fr_text,
    panel_from,
    press_releases,
    sec_web,
)

from auspex_backtesting.catalysts import Catalyst, CatalystPanel

# 16:31:07 Eastern on 2024-02-05 (EST, UTC-5).
_ACCEPTED_UTC = datetime(2024, 2, 5, 21, 31, 7, tzinfo=UTC)
_ACCEPTANCE = (ACME, accession(ACME, 10), "2024-02-05 16:31:07", ACCEPTANCE_RELEASE)
# 08:02:00 Eastern on 2024-07-01 (EDT, UTC-4).
_EXTENSION = (ACME, accession(ACME, 20), "2024-07-01 08:02:00", EXTENSION_RELEASE)


def _panel(filings: list[tuple[str, str, str, str | None]], minio: FakeMinio | None = None
           ) -> CatalystPanel:
    minio = minio or FakeMinio()
    result = press_releases(sec_web(filings), minio).collect(
        {ACME, BETA}, date(2024, 1, 1), date(2024, 9, 30))
    panel = panel_from(minio)
    panel.append(result.rows)
    return panel


def _dates(rows: list[Catalyst]) -> list[date]:
    return [r.period_start for r in rows]


def test_pdufa_date_with_day_precision_is_extracted_from_press_release_fixture() -> None:
    result = press_releases(sec_web([_ACCEPTANCE]), FakeMinio()).collect(
        {ACME}, date(2024, 1, 1), date(2024, 3, 31))

    (row,) = result.rows
    assert row.catalyst_type == "pdufa"
    assert row.cik == ACME
    assert row.precision == "day"
    assert (row.period_start, row.period_end) == (date(2024, 10, 15), date(2024, 10, 15))
    assert row.known_at == _ACCEPTED_UTC
    assert row.document_id == accession(ACME, 10)
    assert "target action date of October 15, 2024" in row.evidence
    assert "acmetinib" in row.aliases


def test_half_year_pdufa_guidance_keeps_half_precision() -> None:
    filing = (BETA, accession(BETA, 3), "2024-03-04 07:00:00", HALF_YEAR_RELEASE)
    result = press_releases(sec_web([filing]), FakeMinio()).collect(
        {BETA}, date(2024, 1, 1), date(2024, 3, 31))

    (row,) = result.rows
    assert row.precision == "half"
    assert (row.period_start, row.period_end) == (date(2025, 7, 1), date(2025, 12, 31))
    assert "btx401" in row.aliases


def test_catalyst_is_invisible_before_its_8k_acceptance_time() -> None:
    panel = _panel([_ACCEPTANCE])

    assert panel.as_of(ACME, _ACCEPTED_UTC - timedelta(seconds=1)) == []
    assert _dates(panel.as_of(ACME, _ACCEPTED_UTC)) == [date(2024, 10, 15)]


def test_extension_appends_a_row_and_later_as_of_returns_the_new_date() -> None:
    panel = _panel([_ACCEPTANCE, _EXTENSION])

    assert len([r for r in panel.rows() if r.cik == ACME]) == 2
    effective = panel.as_of(ACME, datetime(2024, 7, 2, tzinfo=UTC))
    assert _dates(effective) == [date(2025, 1, 15)]
    assert effective[0].document_id == accession(ACME, 20)


def test_earlier_as_of_still_returns_the_original_date_after_extension() -> None:
    minio = FakeMinio()
    panel = _panel([_ACCEPTANCE, _EXTENSION], minio)

    assert _dates(panel.as_of(ACME, datetime(2024, 6, 30, tzinfo=UTC))) == [date(2024, 10, 15)]
    # Read back from storage, the panel answers the same for that date.
    reread = panel_from(minio)
    assert _dates(reread.as_of(ACME, datetime(2024, 6, 30, tzinfo=UTC))) == [date(2024, 10, 15)]


def test_adcom_notice_known_at_publication_date_not_meeting_date() -> None:
    notice = fr_notice("2024-04411", "Oncologic Drugs Advisory Committee; Notice of Meeting",
                       "2024-03-01", "The meeting will be held on April 18, 2024, from 9 a.m. "
                       "to 5 p.m. Eastern Time.")
    web = FakeWeb(
        {notice["raw_text_url"]: fr_text(
            "On April 18, 2024, the committee will discuss new drug application (NDA) 218765, "
            "for acmetinib tablets, submitted by ACME Bio, Inc., for the proposed treatment of "
            "adults with relapsed solid tumors.")},
        {"2024-01-01": [notice]},
    )
    minio = FakeMinio()
    result = adcom_notices(web, minio).collect(MEMBERS, date(2024, 1, 1), date(2024, 3, 31))

    (row,) = result.rows
    assert row.catalyst_type == "adcom"
    assert row.cik == ACME
    assert row.committee == "Oncologic Drugs Advisory Committee"
    assert (row.period_start, row.precision) == (date(2024, 4, 18), "day")
    assert row.known_at.date() == date(2024, 3, 1)
    panel = panel_from(minio)
    panel.append(result.rows)
    assert panel.as_of(ACME, datetime(2024, 2, 29, 23, 59, tzinfo=UTC)) == []
    assert _dates(panel.as_of(ACME, datetime(2024, 3, 1, 15, 0, tzinfo=UTC))) == [date(2024, 4, 18)]


def test_unmatched_adcom_notice_is_kept_and_counted() -> None:
    notice = fr_notice("2024-05522",
                       "Circulatory System Devices Panel of the Medical Devices Advisory Committee; "
                       "Notice of Meeting", "2024-02-12", "The meeting will be held on March 20, 2024.")
    web = FakeWeb(
        {notice["raw_text_url"]: fr_text(
            "The committee will discuss and make recommendations on the premarket approval "
            "application for the Vela transcatheter valve, submitted by Gamma Medical Corp.")},
        {"2024-01-01": [notice]},
    )
    minio = FakeMinio()
    result = adcom_notices(web, minio).collect(MEMBERS, date(2024, 1, 1), date(2024, 3, 31))

    (row,) = result.rows
    assert row.cik is None
    assert row.company_name == "Gamma Medical Corp"
    assert result.stats["unmatched"] == 1
    panel = panel_from(minio)
    panel.append(result.rows)
    assert [r.document_id for r in panel.rows()] == ["2024-05522"]
    assert panel.coverage(MEMBERS)["unmatched_adcom_notices"] == 1


def test_binaries_between_returns_only_catalysts_known_as_of_the_trade_date() -> None:
    # BETA's half-year guidance is known in March; ACME's July extension is not yet known on
    # the trade date, so ACME still shows the October date.
    panel = _panel([
        _ACCEPTANCE,
        _EXTENSION,
        (BETA, accession(BETA, 3), "2024-03-04 07:00:00", HALF_YEAR_RELEASE),
    ])
    trade = datetime(2024, 6, 3, 13, 30, tzinfo=UTC)

    assert _dates(panel.binaries_between(ACME, date(2024, 6, 3), date(2024, 12, 31), trade)) == [
        date(2024, 10, 15)]
    assert panel.binaries_between(ACME, date(2024, 11, 1), date(2025, 3, 31), trade) == []
    assert _dates(panel.binaries_between(ACME, date(2024, 11, 1), date(2025, 3, 31),
                                         datetime(2024, 7, 2, tzinfo=UTC))) == [date(2025, 1, 15)]
    assert _dates(panel.binaries_between(BETA, date(2025, 9, 1), date(2025, 9, 30), trade)) == [
        date(2025, 7, 1)]


def test_press_release_without_catalyst_phrase_yields_nothing() -> None:
    filing = (BETA, accession(BETA, 4), "2024-03-14 16:05:00", RESULTS_RELEASE)
    result = press_releases(sec_web([filing], items={accession(BETA, 4): ("8.01", "9.01")}),
                            FakeMinio()).collect({BETA}, date(2024, 1, 1), date(2024, 3, 31))

    assert result.rows == ()
    assert result.stats["exhibits_read"] == 1


def test_document_already_fetched_is_not_refetched() -> None:
    web = sec_web([_ACCEPTANCE, (BETA, accession(BETA, 4), "2024-03-14 16:05:00", RESULTS_RELEASE)])
    minio = FakeMinio()
    first = press_releases(web, minio).collect({ACME, BETA}, date(2024, 1, 1), date(2024, 3, 31))
    fetched = len(web.requested)

    second = press_releases(web, minio).collect({ACME, BETA}, date(2024, 1, 1), date(2024, 3, 31))

    # master index, two filing indexes and two exhibits, each once.
    assert fetched == 5
    assert len(web.requested) == fetched
    assert second.rows == first.rows
    assert not any(FR_API in u for u in web.requested)
