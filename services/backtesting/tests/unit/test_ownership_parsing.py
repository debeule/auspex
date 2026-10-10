import json
import urllib.error
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Self

import pandas as pd
import pytest
from ownership_fakes import (
    FakeMinio,
    FakeSec,
    FixedMarketCaps,
    h9_with_thresholds,
    make_zip,
    register_h9,
    tsv,
)

from auspex_backtesting.hypothesis import (
    HypothesisModifiedError,
    HypothesisNotRegisteredError,
    register_hypothesis,
)
from auspex_backtesting.ownership import (
    DatasetFile,
    InsiderPanel,
    InsiderTransactionStore,
    Issuer,
    IssuerDirectory,
    OwnershipStore,
    PanelExistsError,
    SecBlockedError,
    SecClient,
    SecNotFoundError,
    ShareCountPanel,
    SpecialistClassifier,
    UniverseMarketCaps,
    list_dataset_files,
    read_issuer_directory,
)
from auspex_backtesting.ownership.datasets import instant, latest_acceptance
from auspex_backtesting.ownership.form13f import parse_13f_dataset, specialists_key
from auspex_backtesting.ownership.insider import (
    parse_form4_submission,
    parse_form_index,
    parse_insider_dataset,
)
from auspex_backtesting.ownership.issuers import normalize_name
from auspex_backtesting.ownership.job import (
    OwnershipBackfill,
    OwnershipConfig,
    OwnershipConfigError,
)
from auspex_backtesting.ownership.panels import HoldingsPanel
from auspex_backtesting.ownership.specialists import SpecialistThresholdsError, report_accessions
from auspex_backtesting.universe import UniverseMember, UniverseSnapshot, UniverseStore

ISSUER = "0000001001"
OTHER = "0000001002"


def _member(cik: str, market_cap: float | None = 100e6) -> UniverseMember:
    return UniverseMember(
        cik=cik, ticker="ALPH", ticker_source="current", name="Alpha Therapeutics, Inc.",
        sic="2836", exchange="Nasdaq", market_cap_usd=market_cap, median_dollar_volume_20d=1e6,
        entered_on=date(2015, 1, 1), exited_on=None, exit_reason=None, price_coverage="complete",
        coverage_note="",
    )


# --- data set listings and time ----------------------------------------------------------------


def test_dataset_page_lists_quarter_and_window_files_with_absolute_urls_oldest_first() -> None:
    page = """
    <a href="/files/datastandardsinnovation/data/form-13f-data-sets/01jun2026-31aug2026_form13f.zip">x</a>
    <a href="https://www.sec.gov/files/structureddata/data/form-13f-data-sets/2023q4_form13f.zip">y</a>
    <a href='/files/structureddata/data/form-13f-data-sets/01jan2024-29feb2024_form13f.zip'>z</a>
    <a href="/files/form_13f_readme.pdf">readme</a>
    <a href="/files/structureddata/data/insider-transactions-data-sets/2023q4_form345.zip">i</a>
    """

    files = list_dataset_files(page, "https://www.sec.gov/data-research/13f", "_form13f.zip")

    assert files == [
        DatasetFile("2023q4", "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
                    "2023q4_form13f.zip", date(2023, 10, 1), date(2023, 12, 31)),
        DatasetFile("01jan2024-29feb2024", "https://www.sec.gov/files/structureddata/data/"
                    "form-13f-data-sets/01jan2024-29feb2024_form13f.zip",
                    date(2024, 1, 1), date(2024, 2, 29)),
        DatasetFile("01jun2026-31aug2026", "https://www.sec.gov/files/datastandardsinnovation/"
                    "data/form-13f-data-sets/01jun2026-31aug2026_form13f.zip",
                    date(2026, 6, 1), date(2026, 8, 31)),
    ]


def test_data_set_filing_date_stands_for_its_latest_possible_acceptance_in_utc() -> None:
    assert latest_acceptance(date(2024, 5, 14)) == pd.Timestamp("2024-05-15T02:00:00Z")
    assert latest_acceptance(date(2024, 2, 10)) == pd.Timestamp("2024-02-11T03:00:00Z")


def test_as_of_date_is_its_first_utc_moment_and_naive_datetimes_are_refused() -> None:
    assert instant(date(2024, 5, 14)) == pd.Timestamp("2024-05-14T00:00:00Z")
    assert instant(datetime(2024, 5, 14, 15, tzinfo=UTC)) == pd.Timestamp("2024-05-14T15:00Z")
    with pytest.raises(ValueError, match="timezone-aware"):
        instant(datetime(2024, 5, 14, 15))  # noqa: DTZ001


# --- issuer names ------------------------------------------------------------------------------


def test_issuer_names_normalize_across_punctuation_suffixes_and_abbreviations() -> None:
    assert normalize_name("Alpha Therapeutics, Inc.") == normalize_name("ALPHA THERAPEUTCS INC")
    assert normalize_name("Beta Pharmaceuticals Corp /DE/") == normalize_name("BETA PHARMA CORP")
    assert normalize_name("The Gamma & Delta Co") == "GAMMA AND DELTA"
    assert normalize_name("Alpha Therapeutics") != normalize_name("Alpha Biosciences")


def test_name_shared_by_two_companies_resolves_to_neither() -> None:
    directory = IssuerDirectory([
        Issuer("0000000001", "2834", ("ACME INC",)),
        Issuer("0000000002", "6770", ("Acme Inc.",)),
        Issuer("0000000003", "2836", ("ZETA BIO INC", "OLD ZETA CORP")),
    ])

    assert directory.resolve("ACME INC") is None
    assert directory.resolve("OLD ZETA CORP") == "0000000003"
    assert directory.sic("0000000003") == "2836"


def test_issuer_directory_reads_current_and_former_names_of_filers_with_a_sic_code(
    tmp_path: Path,
) -> None:
    def company(sic: str, name: str, former: list[str]) -> bytes:
        return json.dumps({
            "cik": "1", "entityType": "operating", "sic": sic, "name": name,
            "formerNames": [{"name": f, "from": "2010-01-01", "to": "2015-01-01"} for f in former],
            "filings": {"recent": {}, "files": []},
        }).encode()

    long_history = json.dumps({
        "cik": "3", "sic": "2834", "name": "Long Filer Inc",
        "description": "x" * 20_000,
        "formerNames": [{"name": "Long Filer Old Name Inc"}],
        "filings": {"recent": {}},
    }).encode()
    archive = tmp_path / "submissions.zip"
    archive.write_bytes(make_zip({
        "CIK0000000001.json": company("2836", "Alpha Therapeutics, Inc.", ["Alpha Bio Corp"]),
        "CIK0000000002.json": company("", "Some Fund LP", []),
        "CIK0000000003.json": long_history,
        "CIK0000000001-submissions-001.json": b"{}",
    }))

    directory = read_issuer_directory(archive)

    assert directory.resolve("ALPHA BIO CORP") == "0000000001"
    assert directory.resolve("ALPHA THERAPEUTICS INC") == "0000000001"
    assert directory.resolve("SOME FUND LP") is None
    assert directory.resolve("LONG FILER OLD NAME INC") == "0000000003"


# --- 13F data set parsing ----------------------------------------------------------------------


def _13f_archive(tmp_path: Path, submissions: list[dict[str, Any]], cover: list[dict[str, Any]],
                 info: list[dict[str, Any]]) -> Path:
    path = tmp_path / "13f.zip"
    path.write_bytes(make_zip({
        "SUBMISSION.tsv": tsv(submissions), "COVERPAGE.tsv": tsv(cover), "INFOTABLE.tsv": tsv(info),
    }))
    return path


def _submission(accession: str, filed: str, form: str = "13F-HR", cik: str = "9001") -> dict[str, Any]:
    return {"ACCESSION_NUMBER": accession, "FILING_DATE": filed, "SUBMISSIONTYPE": form,
            "CIK": cik, "PERIODOFREPORT": "30-SEP-2022"}


def _cover(accession: str, amendment: str = "N", kind: str = "",
           report: str = "13F HOLDINGS REPORT") -> dict[str, Any]:
    return {"ACCESSION_NUMBER": accession, "ISAMENDMENT": amendment, "AMENDMENTTYPE": kind,
            "REPORTTYPE": report}


def _row(accession: str, name: str, cusip: str, value: int, shares: int,
         kind: str = "SH", putcall: str = "") -> dict[str, Any]:
    return {"ACCESSION_NUMBER": accession, "NAMEOFISSUER": name, "CUSIP": cusip, "VALUE": value,
            "SSHPRNAMT": shares, "SSHPRNAMTTYPE": kind, "PUTCALL": putcall}


_DIRECTORY = IssuerDirectory([
    Issuer(ISSUER, "2836", ("ALPHA THERAPEUTICS INC",)),
    Issuer("0000003001", "3841", ("DEVICE CO",)),
    Issuer("0000002002", "3571", ("BIG COMPUTER CORP",)),
])


def test_13f_values_before_2023_are_thousands_and_options_and_principal_rows_are_excluded(
    tmp_path: Path,
) -> None:
    archive = _13f_archive(
        tmp_path,
        [_submission("A", "14-NOV-2022"), _submission("B", "13-FEB-2023", cik="9002")],
        [_cover("A"), _cover("B")],
        [
            _row("A", "ALPHA THERAPEUTICS INC", "02079K107", 3_000, 100_000),
            _row("A", "ALPHA THERAPEUTICS INC", "02079K107", 500, 0, putcall="Call"),
            _row("A", "ALPHA THERAPEUTICS INC", "02079KAB1", 900, 1_000_000, kind="PRN"),
            _row("A", "DEVICE CO", "25179M103", 1_000, 10_000),
            _row("A", "BIG COMPUTER CORP", "037833100", 6_000, 50_000),
            _row("B", "ALPHA THERAPEUTICS INC", "02079K107", 3_000_000, 100_000),
        ],
    )

    filings, holdings, report = parse_13f_dataset(archive, "2022q4", _DIRECTORY, {ISSUER})

    by_accession = filings.set_index("accession_number")
    assert by_accession.loc["A", "total_value_usd"] == 10_000_000
    assert by_accession.loc["A", "healthcare_value_usd"] == 4_000_000
    assert by_accession.loc["B", "total_value_usd"] == 3_000_000
    assert by_accession.loc["A", "filer_cik"] == "0000009001"
    assert by_accession.loc["A", "filing_accepted_at"] == latest_acceptance(date(2022, 11, 14))
    assert holdings[["accession_number", "issuer_cik", "shares", "value_usd"]].to_dict("records") == [
        {"accession_number": "A", "issuer_cik": ISSUER, "shares": 100_000, "value_usd": 3_000_000},
        {"accession_number": "B", "issuer_cik": ISSUER, "shares": 100_000, "value_usd": 3_000_000},
    ]
    assert report.unmapped_cusips == 0
    assert report.universe_issuers_held == 1


def test_13f_notices_are_skipped_and_amendment_kind_is_kept(tmp_path: Path) -> None:
    archive = _13f_archive(
        tmp_path,
        [_submission("A", "14-FEB-2024"), _submission("N", "14-FEB-2024", "13F-NT", "9003"),
         _submission("R", "01-MAR-2024", "13F-HR/A"), _submission("H", "02-MAR-2024", "13F-HR/A"),
         _submission("X", "02-MAR-2024", "13F-HR", "9004")],
        [_cover("A"), _cover("N", report="13F NOTICE"), _cover("R", "Y", "RESTATEMENT"),
         _cover("H", "Y", "NEW HOLDINGS"), _cover("X", report="13F NOTICE REPORT")],
        [_row("A", "ALPHA THERAPEUTICS INC", "02079K107", 1, 1)],
    )

    filings, _, _ = parse_13f_dataset(archive, "2024q1", _DIRECTORY, {ISSUER})

    filings = filings.assign(amendment_type=filings["amendment_type"].fillna(""))
    assert filings[["accession_number", "is_amendment", "amendment_type"]].to_dict("records") == [
        {"accession_number": "A", "is_amendment": False, "amendment_type": ""},
        {"accession_number": "R", "is_amendment": True, "amendment_type": "RESTATEMENT"},
        {"accession_number": "H", "is_amendment": True, "amendment_type": "NEW HOLDINGS"},
    ]


def test_cusip_resolves_by_majority_of_names_and_by_shared_issuer_prefix(tmp_path: Path) -> None:
    archive = _13f_archive(
        tmp_path,
        [_submission("A", "14-FEB-2024")],
        [_cover("A")],
        [
            _row("A", "ALPHA THERAPEUTICS INC", "02079K107", 1, 10),
            _row("A", "ALPHA THERAPEUTCS", "02079K107", 1, 10),
            _row("A", "DEVICE CO", "02079K107", 1, 10),
            _row("A", "ALPHA TH CL B", "02079K305", 1, 5),
            _row("A", "ALPHA THERAPEUTICS INC", "99999X101", 1, 7),
            _row("A", "DEVICE CO", "99999X101", 1, 7),
        ],
    )

    _, holdings, report = parse_13f_dataset(archive, "2024q1", _DIRECTORY, {ISSUER})

    assert dict(zip(holdings["cusip"], holdings["shares"], strict=True)) == {
        "02079K107": 30, "02079K305": 5,
    }
    assert report.unmapped_cusips == 1


# --- which filings make up a report ------------------------------------------------------------


def _filing(accession: str, accepted: date, kind: str | None = None) -> dict[str, Any]:
    return {"accession_number": accession, "filer_cik": "F", "period_of_report": date(2024, 3, 31),
            "filing_accepted_at": latest_acceptance(accepted), "is_amendment": kind is not None,
            "amendment_type": kind, "total_value_usd": 1.0, "healthcare_value_usd": 1.0}


def test_report_is_latest_restatement_plus_new_holdings_accepted_after_it() -> None:
    filings = pd.DataFrame([
        _filing("O", date(2024, 5, 10)),
        _filing("H1", date(2024, 5, 20), "NEW HOLDINGS"),
        _filing("R", date(2024, 6, 1), "RESTATEMENT"),
        _filing("H2", date(2024, 6, 10), "NEW HOLDINGS"),
    ])

    def parts(on: date) -> set[str]:
        return set(report_accessions(filings, instant(on))["accession_number"])

    assert parts(date(2024, 5, 15)) == {"O"}
    assert parts(date(2024, 5, 25)) == {"O", "H1"}
    assert parts(date(2024, 6, 5)) == {"R"}
    assert parts(date(2024, 6, 15)) == {"R", "H2"}


def test_specialist_holding_comes_from_its_latest_report_only() -> None:
    filings = pd.DataFrame([
        {**_filing("Q4", date(2024, 2, 10)), "period_of_report": date(2023, 12, 31)},
        {**_filing("Q1", date(2024, 5, 10)), "period_of_report": date(2024, 3, 31)},
    ])
    # Sold out in Q1: the Q1 report lists another issuer only.
    holdings = pd.DataFrame([
        {"accession_number": "Q4", "issuer_cik": ISSUER, "shares": 1_000_000.0},
        {"accession_number": "Q1", "issuer_cik": OTHER, "shares": 5.0},
    ])
    classifier = SpecialistClassifier(filings, healthcare_share=0.5, min_aum_usd=0.5)
    shares = ShareCountPanel(pd.DataFrame([
        {"cik": ISSUER, "value": 10e6, "end": date(2023, 1, 1), "filed": date(2023, 1, 1)}
    ]))
    panel = HoldingsPanel(filings, holdings, classifier, shares)

    assert panel.specialist_ownership(ISSUER, date(2024, 4, 1)) == pytest.approx(0.1)
    assert panel.specialist_ownership(ISSUER, date(2024, 6, 1)) == 0.0
    assert panel.specialist_ownership(OTHER, date(2024, 6, 1)) is None


def test_holdings_of_filers_that_are_not_specialists_do_not_count() -> None:
    filings = pd.DataFrame([
        {**_filing("S", date(2024, 2, 10)), "period_of_report": date(2023, 12, 31)},
        {**_filing("G", date(2024, 2, 10)), "filer_cik": "GENERALIST",
         "period_of_report": date(2023, 12, 31), "healthcare_value_usd": 0.1},
    ])
    holdings = pd.DataFrame([
        {"accession_number": "S", "issuer_cik": ISSUER, "shares": 1_000_000.0},
        {"accession_number": "G", "issuer_cik": ISSUER, "shares": 4_000_000.0},
    ])
    classifier = SpecialistClassifier(filings, healthcare_share=0.5, min_aum_usd=0.5)
    shares = ShareCountPanel(pd.DataFrame([
        {"cik": ISSUER, "value": 10e6, "end": date(2023, 1, 1), "filed": date(2023, 1, 1)}
    ]))

    panel = HoldingsPanel(filings, holdings, classifier, shares)

    assert panel.specialist_ownership(ISSUER, date(2024, 3, 1)) == pytest.approx(0.1)


def test_offering_filed_after_as_of_does_not_flag_an_earlier_read() -> None:
    trade = {"accession_number": "T", "issuer_cik": ISSUER, "owner_cik": "", "role": "",
             "transaction_code": "P", "acquired_disposed": "A", "shares": 100.0, "price": 10.0,
             "transaction_date": date(2024, 3, 4), "filing_date": date(2024, 3, 5),
             "filing_accepted_at": latest_acceptance(date(2024, 3, 5)), "is_10b5_1": False}
    offering = {"issuer_cik": ISSUER, "form": "424B4", "filing_date": date(2024, 3, 6),
                "accession_number": "O"}
    panel = InsiderPanel(pd.DataFrame([trade]), pd.DataFrame(), pd.DataFrame([offering]),
                         FixedMarketCaps({ISSUER: 1e6}))

    assert panel.transactions(ISSUER, date(2024, 3, 8))["offering_participation"].tolist() == [True]
    assert panel.transactions(ISSUER, date(2024, 3, 7))["offering_participation"].tolist() == [False]


def test_specialist_thresholds_come_from_the_registered_h9(tmp_path: Path) -> None:
    registry = register_h9(tmp_path, healthcare_share=0.7, min_aum_usd=250e6)

    classifier = SpecialistClassifier.from_hypothesis(
        pd.DataFrame(), config_dir=tmp_path, registry_path=registry
    )

    assert (classifier.healthcare_share, classifier.min_aum_usd) == (0.7, 250e6)


def test_specialist_thresholds_read_from_the_repository_h9() -> None:
    hypotheses = Path(__file__).resolve().parents[4] / "config" / "hypotheses"

    classifier = SpecialistClassifier.from_hypothesis(
        pd.DataFrame(), config_dir=hypotheses, registry_path=hypotheses / "registry.jsonl"
    )

    assert (classifier.healthcare_share, classifier.min_aum_usd) == (0.5, 100e6)


def test_specialist_thresholds_refuse_an_edited_h9(tmp_path: Path) -> None:
    registry = register_h9(tmp_path, healthcare_share=0.7, min_aum_usd=250e6)
    h9 = tmp_path / "h9.yaml"
    h9.write_text(h9.read_text().replace("0.7", "0.4"))

    with pytest.raises(HypothesisModifiedError):
        SpecialistClassifier.from_hypothesis(
            pd.DataFrame(), config_dir=tmp_path, registry_path=registry
        )


def test_specialist_thresholds_refuse_an_unregistered_h9(tmp_path: Path) -> None:
    (tmp_path / "h9.yaml").write_text("id: h9\n")

    with pytest.raises(HypothesisNotRegisteredError):
        SpecialistClassifier.from_hypothesis(
            pd.DataFrame(), config_dir=tmp_path, registry_path=tmp_path / "registry.jsonl"
        )


def test_specialist_thresholds_refuse_an_h9_without_them(tmp_path: Path) -> None:
    registry = tmp_path / "registry.jsonl"
    without = h9_with_thresholds(0.5, 100e6).replace("SPECIALIST_MIN_AUM_USD: 100000000", "")
    register_hypothesis("h9", without, config_dir=tmp_path, registry_path=registry)

    with pytest.raises(SpecialistThresholdsError):
        SpecialistClassifier.from_hypothesis(
            pd.DataFrame(), config_dir=tmp_path, registry_path=registry
        )


# --- insider data sets, indexes and Form 4 -----------------------------------------------------


def _insider_archive(tmp_path: Path) -> Path:
    submissions = [
        {"ACCESSION_NUMBER": a, "FILING_DATE": "05-MAR-2024", "PERIOD_OF_REPORT": "01-MAR-2024",
         "DOCUMENT_TYPE": doc, "ISSUERCIK": cik, "REMARKS": remarks, "AFF10B5ONE": aff}
        for a, doc, cik, remarks, aff in [
            ("J", "4", "1001", "", "0"),
            ("PLANREMARK", "4", "1001", "Sales under a Rule 10b5-1 trading plan.", ""),
            ("PLANBOX", "4", "1001", "", "1"),
            ("AMEND", "4/A", "1001", "", ""),
            ("INITIAL", "3", "1001", "", ""),
            ("ELSEWHERE", "4", "7777", "", ""),
        ]
    ]
    owners = [
        {"ACCESSION_NUMBER": "J", "RPTOWNERCIK": "6002", "RPTOWNER_RELATIONSHIP": "TenPercentOwner"},
        {"ACCESSION_NUMBER": "J", "RPTOWNERCIK": "6001", "RPTOWNER_RELATIONSHIP": "Director,Other"},
    ]
    transactions = [
        {"ACCESSION_NUMBER": a, "TRANS_DATE": "01-MAR-2024", "TRANS_CODE": code,
         "TRANS_SHARES": "100", "TRANS_PRICEPERSHARE": price, "TRANS_ACQUIRED_DISP_CD": "A",
         "TRANS_CODE_FN": fn, "TRANS_SHARES_FN": ""}
        for a, code, price, fn in [
            ("J", "P", "5.00", ""), ("J", "S", "5.10", "F1, F2"), ("PLANREMARK", "S", "", ""),
            ("PLANBOX", "S", "6", ""), ("AMEND", "P", "5", ""), ("INITIAL", "P", "5", ""),
            ("ELSEWHERE", "P", "5", ""),
        ]
    ]
    footnotes = [
        {"ACCESSION_NUMBER": "J", "FOOTNOTE_ID": "F2", "FOOTNOTE_TXT": "Sold under a 10b5-1 plan."},
        {"ACCESSION_NUMBER": "J", "FOOTNOTE_ID": "F1", "FOOTNOTE_TXT": "Weighted average."},
    ]
    path = tmp_path / "insider.zip"
    path.write_bytes(make_zip({
        "SUBMISSION.tsv": tsv(submissions), "REPORTINGOWNER.tsv": tsv(owners),
        "NONDERIV_TRANS.tsv": tsv(transactions), "FOOTNOTES.tsv": tsv(footnotes),
    }))
    return path


def test_insider_data_set_keeps_original_forms_4_and_5_of_universe_issuers(tmp_path: Path) -> None:
    rows = parse_insider_dataset(_insider_archive(tmp_path), {ISSUER})

    assert rows[["accession_number", "transaction_code", "is_10b5_1"]].to_dict("records") == [
        {"accession_number": "J", "transaction_code": "P", "is_10b5_1": False},
        {"accession_number": "J", "transaction_code": "S", "is_10b5_1": True},
        {"accession_number": "PLANREMARK", "transaction_code": "S", "is_10b5_1": True},
        {"accession_number": "PLANBOX", "transaction_code": "S", "is_10b5_1": True},
    ]
    joint = rows.iloc[0]
    assert (joint["owner_cik"], joint["role"]) == ("0000006001", "director,other,ten_percent_owner")
    assert (joint["shares"], joint["price"]) == (100.0, 5.0)
    assert joint["filing_accepted_at"] == latest_acceptance(date(2024, 3, 5))
    assert pd.isna(rows.iloc[2]["price"])


def test_form_index_is_cut_at_header_positions_in_daily_and_quarterly_layouts() -> None:
    header = (
        "Description:           Master Index\n\n"
        "Form Type   Company Name                                                  CIK         "
        "Date Filed  File Name\n" + "-" * 120 + "\n"
    )
    line = "{:<12}{:<62}{:<12}{:<12}{}\n"
    text = header + line.format("SC 13G/A", "Alpha Therapeutics, Inc.", "1001", "2024-03-05",
                                "edgar/data/1001/0000950123-24-000001.txt") \
        + line.format("424B5", "Alpha Therapeutics, Inc.", "1001", "20240306",
                      "edgar/data/1001/0001193125-24-000002.txt")

    first, second = parse_form_index(text)

    assert (first.form, first.company, first.cik, first.filing_date) == (
        "SC 13G/A", "Alpha Therapeutics, Inc.", ISSUER, date(2024, 3, 5)
    )
    assert (second.form, second.filing_date, second.accession_number) == (
        "424B5", date(2024, 3, 6), "0001193125-24-000002"
    )
    with pytest.raises(ValueError, match="Form Type"):
        parse_form_index("<html>Access denied</html>")


_FORM4 = """<SEC-DOCUMENT>
<ACCEPTANCE-DATETIME>20240110171500
ACCESSION NUMBER:\t\t0001001001-24-000009
</SEC-HEADER>
<XML>
<?xml version="1.0"?>
<ownershipDocument>
  <documentType>{doc}</documentType>
  <issuer><issuerCik>{issuer}</issuerCik></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>0000005002</rptOwnerCik></reportingOwnerId>
    <reportingOwnerRelationship><isOfficer>true</isOfficer></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2024-01-08</value></transactionDate>
      <transactionCoding><transactionCode>S</transactionCode><footnoteId id="F1"/></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>500</value></transactionShares>
        <transactionPricePerShare><value>7.25</value><footnoteId id="F2"/></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2024-01-09</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>100</value></transactionShares>
        <transactionPricePerShare><value>7.00</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <footnotes>
    <footnote id="F1">Effected pursuant to a Rule 10b5-1 trading plan adopted May 2023.</footnote>
    <footnote id="F2">Weighted average price.</footnote>
  </footnotes>
</ownershipDocument>
</XML>
"""


def test_form4_submission_yields_transactions_with_eastern_acceptance_in_utc() -> None:
    sale, purchase = parse_form4_submission(_FORM4.format(doc="4", issuer=ISSUER), {ISSUER})

    assert sale == {
        "accession_number": "0001001001-24-000009", "issuer_cik": ISSUER,
        "owner_cik": "0000005002", "role": "officer", "transaction_code": "S",
        "acquired_disposed": "D", "shares": 500.0, "price": 7.25,
        "transaction_date": date(2024, 1, 8), "filing_date": date(2024, 1, 10),
        "filing_accepted_at": pd.Timestamp("2024-01-10T22:15:00Z"), "is_10b5_1": True,
    }
    assert purchase["is_10b5_1"] is False
    assert parse_form4_submission(_FORM4.format(doc="4/A", issuer=ISSUER), {ISSUER}) == []
    assert parse_form4_submission(_FORM4.format(doc="4", issuer="0000007777"), {ISSUER}) == []


_DAILY = "https://sec.example/daily-index"
_FULL = "https://sec.example/full-index"
_ARCHIVES = "https://sec.example/data"
_INDEX_HEADER = (
    "Form Type   Company Name                                                  CIK         "
    "Date Filed  File Name\n" + "-" * 120 + "\n"
)


def _index(*rows: tuple[str, str, str, str]) -> bytes:
    return (_INDEX_HEADER + "".join(
        f"{form:<12}{'Company':<62}{cik:<12}{filed:<12}{path}\n" for form, cik, filed, path in rows
    )).encode()


def _insider_store(minio: FakeMinio, sec: FakeSec) -> InsiderTransactionStore:
    return InsiderTransactionStore(OwnershipStore(minio), sec, {ISSUER}, daily_index_url=_DAILY,
                                   full_index_url=_FULL, archives_url=_ARCHIVES)


def test_day_without_index_is_not_stored_and_missing_form4_is_skipped() -> None:
    minio = FakeMinio()
    day = date(2024, 1, 10)
    sec = FakeSec({
        f"{_DAILY}/2024/QTR1/form.20240110.idx": _index(
            ("4", "1001", "20240110", "edgar/data/1001/0001001001-24-000008.txt"),
            ("4", "1001", "20240110", "edgar/data/1001/0001001001-24-000009.txt"),
            ("424B5", "1001", "20240110", "edgar/data/1001/0001193125-24-000002.txt"),
            ("424B3", "1001", "20240110", "edgar/data/1001/0001193125-24-000003.txt"),
        ),
        f"{_ARCHIVES}/1001/0001001001-24-000009.txt": _FORM4.format(doc="4", issuer=ISSUER).encode(),
    })
    store = _insider_store(minio, sec)

    assert store.fetch_day(date(2024, 1, 13)) is None
    assert store.fetch_day(day) == 2
    assert not any("2024-01-13" in k for k in minio.objects)
    panel = InsiderPanel.load(OwnershipStore(minio), FixedMarketCaps({ISSUER: 1e6}))
    flagged = panel.transactions(ISSUER, date(2024, 2, 1))
    assert flagged["offering_participation"].tolist() == [False, True]


def test_quarterly_offerings_keep_424b4_and_424b5_of_universe_issuers() -> None:
    minio = FakeMinio()
    sec = FakeSec({f"{_FULL}/2024/QTR1/form.idx": _index(
        ("424B4", "1001", "2024-02-01", "edgar/data/1001/a-1.txt"),
        ("424B5", "7777", "2024-02-01", "edgar/data/7777/b-1.txt"),
        ("424B2", "1001", "2024-02-01", "edgar/data/1001/c-1.txt"),
    )})

    assert _insider_store(minio, sec).fetch_offerings(2024, 1) == 1
    assert _insider_store(minio, FakeSec()).fetch_offerings(2024, 1) == 1


def test_disagreements_name_filings_missing_from_either_side_for_days_covered() -> None:
    def trade(accession: str, filed: date, shares: float = 100.0) -> dict[str, Any]:
        return {"accession_number": accession, "issuer_cik": ISSUER, "owner_cik": "",
                "role": "", "transaction_code": "P", "acquired_disposed": "A", "shares": shares,
                "price": float("nan"), "transaction_date": filed, "filing_date": filed,
                "filing_accepted_at": latest_acceptance(filed), "is_10b5_1": False}

    quarterly = pd.DataFrame([trade("SAME", date(2024, 9, 3)), trade("ONLYQ", date(2024, 9, 3)),
                              trade("UNCOVERED", date(2024, 9, 4))])
    daily = pd.DataFrame([trade("SAME", date(2024, 9, 3)), trade("ONLYD", date(2024, 9, 3))])

    panel = InsiderPanel(quarterly, daily, pd.DataFrame(), FixedMarketCaps({}),
                         quarterly_labels={"2024q3"}, daily_days={date(2024, 9, 3)})

    assert [(d.accession_number, d.kind) for d in panel.disagreements()] == [
        ("ONLYD", "missing_from_dataset"), ("ONLYQ", "missing_from_daily"),
    ]
    assert panel.net_insider_buying(ISSUER, date(2024, 10, 1)) is None


def test_store_writes_a_panel_once() -> None:
    store = OwnershipStore(FakeMinio())
    store.write("insider/2024q1.parquet", pd.DataFrame({"a": [1]}))

    with pytest.raises(PanelExistsError):
        store.write("insider/2024q1.parquet", pd.DataFrame({"a": [2]}))


# --- HTTP pacing -------------------------------------------------------------------------------


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class _Ok:
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, *_: object) -> bytes:
        return b""


def test_sec_requests_are_spaced_to_five_per_second() -> None:
    clock = _Clock()
    client = SecClient("ua x@example.com", opener=lambda r, timeout: _Ok(), clock=clock,
                       sleep=clock.sleep)

    for _ in range(3):
        client.get("https://sec.example/x")

    assert clock.slept == [pytest.approx(0.2), pytest.approx(0.2)]


@pytest.mark.parametrize(("status", "error"), [(403, SecBlockedError), (429, SecBlockedError),
                                               (404, SecNotFoundError)])
def test_sec_refusal_and_absence_raise_without_retry(status: int, error: type[Exception]) -> None:
    calls: list[str] = []

    def opener(request: Any, timeout: float) -> Any:
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, "x", None, None)  # type: ignore[arg-type]

    with pytest.raises(error):
        SecClient("ua x@example.com", opener=opener, sleep=lambda _: None).get("https://s/x")
    assert len(calls) == 1


def test_sec_client_refuses_an_empty_user_agent() -> None:
    with pytest.raises(ValueError, match="User-Agent"):
        SecClient(" ")


# --- reference data ----------------------------------------------------------------------------


def test_market_cap_comes_from_the_latest_universe_month_on_or_before_the_date() -> None:
    minio = FakeMinio()
    universe = UniverseStore(minio)
    universe.write(UniverseSnapshot(1, "2024-02", date(2024, 2, 1), (_member(ISSUER, 100e6),)))
    universe.write(UniverseSnapshot(1, "2024-03", date(2024, 3, 1), (_member(ISSUER, 150e6),)))

    caps = UniverseMarketCaps(universe, 1)

    assert caps.market_cap_usd(ISSUER, date(2024, 1, 31)) is None
    assert caps.market_cap_usd(ISSUER, date(2024, 2, 29)) == 100e6
    assert caps.market_cap_usd(ISSUER, date(2024, 3, 1)) == 150e6
    assert caps.market_cap_usd(OTHER, date(2024, 3, 1)) is None


def test_share_count_is_known_only_after_its_filing_day() -> None:
    panel = ShareCountPanel(pd.DataFrame([
        {"cik": ISSUER, "value": 5.0, "end": date(2024, 3, 31), "filed": date(2024, 5, 10)},
    ]))

    assert panel.shares_outstanding(ISSUER, date(2024, 5, 10)) is None
    assert panel.shares_outstanding(ISSUER, date(2024, 5, 11)) == 5.0


# --- backfill ----------------------------------------------------------------------------------


_CONFIG = OwnershipConfig(
    form13f_page_url="https://sec.example/13f-page",
    insider_page_url="https://sec.example/insider-page",
    daily_index_url=_DAILY,
    full_index_url=_FULL,
    archives_url=_ARCHIVES,
    submissions_bulk_url="https://sec.example/submissions.zip",
    companyfacts_bulk_url="https://sec.example/companyfacts.zip",
    start=date(2024, 4, 1),
)


def _backfill_sec() -> FakeSec:
    accession = "0000950123-24-005555"
    form13f = make_zip({
        "SUBMISSION.tsv": tsv([{"ACCESSION_NUMBER": accession, "FILING_DATE": "14-MAY-2024",
                                "SUBMISSIONTYPE": "13F-HR", "CIK": "9001",
                                "PERIODOFREPORT": "31-MAR-2024"}]),
        "COVERPAGE.tsv": tsv([_cover(accession)]),
        "INFOTABLE.tsv": tsv([
            _row(accession, "ALPHA THERAPEUTICS INC", "02079K107", 30_000_000, 1_000_000),
            _row(accession, "BIG COMPUTER CORP", "037833100", 50_000_000, 200_000),
        ]),
    })
    insider = make_zip({
        "SUBMISSION.tsv": tsv([{"ACCESSION_NUMBER": "I1", "FILING_DATE": "05-AUG-2024",
                                "DOCUMENT_TYPE": "4", "ISSUERCIK": "1001", "REMARKS": ""}]),
        "REPORTINGOWNER.tsv": tsv([{"ACCESSION_NUMBER": "I1", "RPTOWNERCIK": "5001",
                                    "RPTOWNER_RELATIONSHIP": "Officer"}]),
        "NONDERIV_TRANS.tsv": tsv([{"ACCESSION_NUMBER": "I1", "TRANS_DATE": "01-AUG-2024",
                                    "TRANS_CODE": "P", "TRANS_SHARES": "1000",
                                    "TRANS_PRICEPERSHARE": "10", "TRANS_ACQUIRED_DISP_CD": "A"}]),
    })
    submissions = make_zip({
        "CIK0000001001.json": json.dumps({"sic": "2836", "name": "Alpha Therapeutics, Inc.",
                                          "filings": {}}).encode(),
        "CIK0000002002.json": json.dumps({"sic": "3571", "name": "Big Computer Corp",
                                          "filings": {}}).encode(),
    })
    facts = make_zip({"CIK0000001001.json": json.dumps({"facts": {"dei": {
        "EntityCommonStockSharesOutstanding": {"units": {"shares": [
            {"end": "2024-03-31", "val": 10_000_000, "filed": "2024-05-01"},
        ]}}}}}).encode()})
    return FakeSec({
        _CONFIG.form13f_page_url: b'<a href="/files/2023q4_form13f.zip">old</a>'
                                  b'<a href="/files/01mar2024-31may2024_form13f.zip">x</a>',
        "https://sec.example/files/01mar2024-31may2024_form13f.zip": form13f,
        _CONFIG.insider_page_url: b'<a href="/files/2024q3_form345.zip">x</a>',
        "https://sec.example/files/2024q3_form345.zip": insider,
        _CONFIG.submissions_bulk_url: submissions,
        _CONFIG.companyfacts_bulk_url: facts,
        f"{_FULL}/2024/QTR2/form.idx": _index(),
        f"{_FULL}/2024/QTR3/form.idx": _index(
            ("424B5", "1001", "2024-08-01", "edgar/data/1001/0001193125-24-000002.txt")),
        f"{_DAILY}/2024/QTR4/form.20241001.idx": _index(),
    })


def test_backfill_stores_every_panel_once_and_reports_coverage(tmp_path: Path) -> None:
    registry = register_h9(tmp_path, healthcare_share=0.3, min_aum_usd=1e6)
    h9 = {"hypotheses_dir": tmp_path, "hypothesis_registry": registry}
    minio = FakeMinio()
    UniverseStore(minio).write_listings(1, [_member(ISSUER)], date(2024, 10, 1))
    UniverseStore(minio).write(UniverseSnapshot(1, "2024-05", date(2024, 5, 1), (
        _member(ISSUER, 300e6), _member(OTHER, 100e6),
    )))
    store = OwnershipStore(minio)
    sec = _backfill_sec()

    summary = OwnershipBackfill(
        _CONFIG, store, UniverseStore(minio), 1, sec, date(2024, 10, 3), **h9
    ).run()

    assert summary.universe_issuers == 1
    (f13,) = summary.form13f
    assert (f13.label, f13.filings, f13.universe_issuers_held, f13.unmapped_cusips) == (
        "01mar2024-31may2024", 1, 1, 0
    )
    assert f13.universe_value_without_holder_share == pytest.approx(0.25)
    assert [(i.label, i.filings, i.transactions) for i in summary.insider] == [("2024q3", 1, 1)]
    assert (summary.offering_quarters, summary.offerings) == (2, 1)
    assert (summary.daily_days, summary.share_count_issuers) == (1, 1)
    specialists = store.read(specialists_key("01mar2024-31may2024"))
    assert specialists is not None
    assert specialists[0]["is_specialist"].tolist() == [True]
    holdings = HoldingsPanel.load(store, config_dir=tmp_path, registry_path=registry)
    assert holdings.specialist_ownership(ISSUER, date(2024, 6, 1)) == pytest.approx(0.1)
    insider = InsiderPanel.load(store, FixedMarketCaps({ISSUER: 100e6}))
    assert insider.transactions(ISSUER, date(2024, 9, 1))["offering_participation"].tolist() == [True]

    again = FakeSec(sec.bodies)
    OwnershipBackfill(
        _CONFIG, store, UniverseStore(minio), 1, again, date(2024, 10, 3), **h9
    ).run()
    assert set(again.requested) == {
        _CONFIG.form13f_page_url, _CONFIG.insider_page_url, _CONFIG.companyfacts_bulk_url,
        f"{_DAILY}/2024/QTR4/form.20241002.idx",
    }


def test_backfill_refuses_to_run_before_the_universe_is_built() -> None:
    minio = FakeMinio()

    with pytest.raises(OwnershipConfigError, match="build the universe first"):
        OwnershipBackfill(_CONFIG, OwnershipStore(minio), UniverseStore(minio), 1, FakeSec(),
                          date(2024, 10, 3)).run()


def test_config_reads_urls_and_history_start_from_the_environment() -> None:
    env = {
        "SEC_13F_DATASETS_URL": "a", "SEC_INSIDER_DATASETS_URL": "b", "SEC_DAILY_INDEX_URL": "c",
        "SEC_FULL_INDEX_URL": "d", "SEC_ARCHIVES_URL": "e", "SEC_SUBMISSIONS_BULK_URL": "f",
        "SEC_COMPANYFACTS_BULK_URL": "g", "OWNERSHIP_HISTORY_START": "2013-01-01",
    }

    assert OwnershipConfig.from_env(env) == OwnershipConfig("a", "b", "c", "d", "e", "f", "g",
                                                            date(2013, 1, 1))
