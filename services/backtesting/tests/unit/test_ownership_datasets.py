import io
import itertools
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Self

import pandas as pd
import pytest
from ownership_fakes import FakeMinio, FakeSec, FixedMarketCaps, make_zip, tsv

from auspex_backtesting.ownership import (
    DatasetFile,
    Form13FDatasetStore,
    HoldingsPanel,
    InsiderPanel,
    InsiderTransactionStore,
    Issuer,
    IssuerDirectory,
    OwnershipStore,
    SecClient,
    ShareCountPanel,
    SpecialistClassifier,
)

ISSUER = "0000001001"
OTHER_ISSUER = "0000001002"
FUND = "0000009001"
_UA = "Auspex research ops@example.com"
_ACCESSIONS = itertools.count(1)


# --- fakes and builders ------------------------------------------------------------------------


def _at(day: date, hour: int = 21) -> pd.Timestamp:
    return pd.Timestamp(datetime(day.year, day.month, day.day, hour, tzinfo=UTC))


def _filing(
    accession: str,
    period: date,
    accepted: date,
    *,
    filer: str = FUND,
    total: float = 500e6,
    healthcare: float = 400e6,
    amendment_type: str | None = None,
) -> dict[str, Any]:
    return {
        "accession_number": accession,
        "filer_cik": filer,
        "period_of_report": period,
        "filing_accepted_at": _at(accepted),
        "is_amendment": amendment_type is not None,
        "amendment_type": amendment_type,
        "total_value_usd": total,
        "healthcare_value_usd": healthcare,
    }


def _holding(accession: str, shares: float, issuer: str = ISSUER) -> dict[str, Any]:
    return {"accession_number": accession, "issuer_cik": issuer, "cusip": "00000A101",
            "shares": shares, "value_usd": shares * 10.0}


def _shares(*counts: tuple[float, date]) -> ShareCountPanel:
    return ShareCountPanel(pd.DataFrame([
        {"cik": ISSUER, "value": value, "end": filed, "filed": filed} for value, filed in counts
    ]))


def _holdings_panel(
    filings: list[dict[str, Any]],
    holdings: list[dict[str, Any]],
    shares: ShareCountPanel | None = None,
    *,
    min_aum_usd: float = 100e6,
) -> HoldingsPanel:
    classifier = SpecialistClassifier(
        pd.DataFrame(filings), healthcare_share=0.5, min_aum_usd=min_aum_usd
    )
    return HoldingsPanel(
        pd.DataFrame(filings),
        pd.DataFrame(holdings),
        classifier,
        shares or _shares((10_000_000, date(2023, 11, 1))),
    )


def _trade(
    code: str,
    shares: float,
    price: float,
    traded: date,
    accepted: date,
    *,
    plan: bool = False,
    accession: str | None = None,
    issuer: str = ISSUER,
) -> dict[str, Any]:
    return {
        "accession_number": accession or f"0000000000-24-{next(_ACCESSIONS):06d}",
        "issuer_cik": issuer,
        "owner_cik": "0000005001",
        "role": "officer",
        "transaction_code": code,
        "acquired_disposed": "A" if code == "P" else "D",
        "shares": shares,
        "price": price,
        "transaction_date": traded,
        "filing_date": accepted,
        "filing_accepted_at": _at(accepted),
        "is_10b5_1": plan,
    }


def _offering(form: str, filed: date, issuer: str = ISSUER) -> dict[str, Any]:
    return {"issuer_cik": issuer, "form": form, "filing_date": filed,
            "accession_number": f"0000000000-24-9{filed:%m%d}"}


def _insider_panel(
    trades: list[dict[str, Any]],
    offerings: list[dict[str, Any]] | None = None,
    market_cap: float = 100e6,
) -> InsiderPanel:
    return InsiderPanel(
        pd.DataFrame(trades),
        pd.DataFrame(),
        pd.DataFrame(offerings or []),
        FixedMarketCaps({ISSUER: market_cap}),
    )


def _13f_dataset(holdings: list[tuple[str, str, int, int]]) -> bytes:
    """One 13F-HR filed 14-MAY-2024 for the quarter ending 31-MAR-2024; holdings are
    (issuer name, cusip, value in dollars, shares)."""
    accession = "0000950123-24-005555"
    return make_zip({
        "SUBMISSION.tsv": tsv([{
            "ACCESSION_NUMBER": accession, "FILING_DATE": "14-MAY-2024",
            "SUBMISSIONTYPE": "13F-HR", "CIK": "9001", "PERIODOFREPORT": "31-MAR-2024",
        }]),
        "COVERPAGE.tsv": tsv([{
            "ACCESSION_NUMBER": accession, "REPORTCALENDARORQUARTER": "31-MAR-2024",
            "ISAMENDMENT": "N", "AMENDMENTNO": None, "AMENDMENTTYPE": None,
            "FILINGMANAGER_NAME": "Example Healthcare Partners", "REPORTTYPE": "13F HOLDINGS REPORT",
        }]),
        "INFOTABLE.tsv": tsv([
            {"ACCESSION_NUMBER": accession, "INFOTABLE_SK": i, "NAMEOFISSUER": name,
             "TITLEOFCLASS": "COM", "CUSIP": cusip, "FIGI": None, "VALUE": value,
             "SSHPRNAMT": shares, "SSHPRNAMTTYPE": "SH", "PUTCALL": None,
             "INVESTMENTDISCRETION": "SOLE", "OTHERMANAGER": None,
             "VOTING_AUTH_SOLE": shares, "VOTING_AUTH_SHARED": 0, "VOTING_AUTH_NONE": 0}
            for i, (name, cusip, value, shares) in enumerate(holdings, 1)
        ]),
    })


_13F_PAGE_URL = "https://sec.example/form-13f-data-sets"
_13F_URL = "https://sec.example/files/2024q2_form13f.zip"
_13F_DATASET = DatasetFile("2024q2", _13F_URL, date(2024, 4, 1), date(2024, 6, 30))
_INSIDER_URL = "https://sec.example/files/2024q3_form345.zip"
_INSIDER_DATASET = DatasetFile("2024q3", _INSIDER_URL, date(2024, 7, 1), date(2024, 9, 30))
_DAILY_INDEX = "https://sec.example/Archives/edgar/daily-index"
_FULL_INDEX = "https://sec.example/Archives/edgar/full-index"
_ARCHIVES = "https://sec.example/Archives/edgar/data"


def _directory() -> IssuerDirectory:
    return IssuerDirectory([
        Issuer(ISSUER, "2836", ("ALPHA THERAPEUTICS, INC.",)),
        Issuer("0000002002", "3571", ("BIG COMPUTER CORP",)),
    ])


def _13f_store(minio: FakeMinio, sec: FakeSec) -> Form13FDatasetStore:
    return Form13FDatasetStore(OwnershipStore(minio), sec, lambda: _directory(), {ISSUER})


def _insider_store(minio: FakeMinio, sec: FakeSec) -> InsiderTransactionStore:
    return InsiderTransactionStore(
        OwnershipStore(minio), sec, {ISSUER},
        daily_index_url=_DAILY_INDEX, full_index_url=_FULL_INDEX, archives_url=_ARCHIVES,
    )


def _insider_dataset(accession: str, shares: int) -> bytes:
    return make_zip({
        "SUBMISSION.tsv": tsv([{
            "ACCESSION_NUMBER": accession, "FILING_DATE": "16-SEP-2024",
            "PERIOD_OF_REPORT": "12-SEP-2024", "DATE_OF_ORIG_SUB": None, "DOCUMENT_TYPE": "4",
            "ISSUERCIK": "1001", "ISSUERNAME": "Alpha Therapeutics, Inc.",
            "ISSUERTRADINGSYMBOL": "ALPH", "REMARKS": None, "AFF10B5ONE": "0",
        }]),
        "REPORTINGOWNER.tsv": tsv([{
            "ACCESSION_NUMBER": accession, "RPTOWNERCIK": "5001", "RPTOWNERNAME": "Doe Jane",
            "RPTOWNER_RELATIONSHIP": "Director", "RPTOWNER_TITLE": None,
        }]),
        "NONDERIV_TRANS.tsv": tsv([{
            "ACCESSION_NUMBER": accession, "NONDERIV_TRANS_SK": 1,
            "SECURITY_TITLE": "Common Stock", "TRANS_DATE": "12-SEP-2024", "TRANS_CODE": "P",
            "TRANS_SHARES": shares, "TRANS_PRICEPERSHARE": "10.00",
            "TRANS_ACQUIRED_DISP_CD": "A", "TRANS_CODE_FN": None, "TRANS_SHARES_FN": None,
        }]),
        "FOOTNOTES.tsv": tsv([{"ACCESSION_NUMBER": accession, "FOOTNOTE_ID": "F1",
                                "FOOTNOTE_TXT": "Weighted average price."}]),
    })


_FORM_INDEX_HEADER = (
    "Description:           Daily Index of EDGAR Dissemination Feed by Form Type\n"
    "Last Data Received:    {received}\n"
    "Comments:              webmaster@sec.gov\n"
    "Anonymous FTP:         ftp://ftp.sec.gov/edgar/\n"
    " \n \n \n"
    "Form Type   Company Name                                                  CIK         Date Filed  File Name\n"
    + "-" * 140 + "\n"
)


def _index_line(form: str, company: str, cik: str, filed: str, path: str) -> str:
    return f"{form:<12}{company:<62}{cik:<12}{filed:<12}{path}\n"


def _form4_submission(accession: str, accepted: str, shares: int, traded: str) -> bytes:
    return f"""<SEC-DOCUMENT>{accession}.txt : {accepted[:8]}
<SEC-HEADER>{accession}.hdr.sgml : {accepted[:8]}
<ACCEPTANCE-DATETIME>{accepted}
ACCESSION NUMBER:\t\t{accession}
CONFORMED SUBMISSION TYPE:\t4
</SEC-HEADER>
<DOCUMENT>
<TYPE>4
<SEQUENCE>1
<FILENAME>form4.xml
<TEXT>
<XML>
<?xml version="1.0"?>
<ownershipDocument>
    <schemaVersion>X0508</schemaVersion>
    <documentType>4</documentType>
    <periodOfReport>{traded}</periodOfReport>
    <issuer>
        <issuerCik>0000001001</issuerCik>
        <issuerName>Alpha Therapeutics, Inc.</issuerName>
        <issuerTradingSymbol>ALPH</issuerTradingSymbol>
    </issuer>
    <reportingOwner>
        <reportingOwnerId>
            <rptOwnerCik>0000005001</rptOwnerCik>
            <rptOwnerName>Doe Jane</rptOwnerName>
        </reportingOwnerId>
        <reportingOwnerRelationship>
            <isDirector>1</isDirector>
            <isOfficer>0</isOfficer>
        </reportingOwnerRelationship>
    </reportingOwner>
    <aff10b5One>0</aff10b5One>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <securityTitle><value>Common Stock</value></securityTitle>
            <transactionDate><value>{traded}</value></transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>P</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares><value>{shares}</value></transactionShares>
                <transactionPricePerShare><value>10.00</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
</ownershipDocument>
</XML>
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>
""".encode()


def _daily_sec(day: date, accession: str, accepted: str, shares: int) -> FakeSec:
    cik_path = f"edgar/data/1001/{accession}.txt"
    index = _FORM_INDEX_HEADER.format(received=f"{day:%B %d, %Y}") + "".join([
        _index_line("4", "Alpha Therapeutics, Inc.", "1001", f"{day:%Y%m%d}", cik_path),
        _index_line("4", "Doe Jane", "5001", f"{day:%Y%m%d}", cik_path),
        _index_line("4", "Unrelated Corp", "7777", f"{day:%Y%m%d}", "edgar/data/7777/x.txt"),
    ])
    quarter = (day.month - 1) // 3 + 1
    return FakeSec({
        f"{_DAILY_INDEX}/{day.year}/QTR{quarter}/form.{day:%Y%m%d}.idx": index.encode(),
        f"{_ARCHIVES}/1001/{accession}.txt": _form4_submission(
            accession, accepted, shares, day.isoformat()
        ),
    })


# --- 13F holdings ------------------------------------------------------------------------------


def test_13f_holding_is_invisible_before_its_filing_acceptance_time() -> None:
    panel = _holdings_panel(
        [_filing("Q4", date(2023, 12, 31), date(2024, 2, 10)),
         _filing("Q1", date(2024, 3, 31), date(2024, 5, 14))],
        [_holding("Q4", 1_000_000), _holding("Q1", 3_000_000)],
    )

    assert panel.specialist_ownership(ISSUER, date(2024, 5, 13)) == pytest.approx(0.1)
    assert panel.specialist_ownership(ISSUER, date(2024, 5, 16)) == pytest.approx(0.3)


def test_13f_amendment_accepted_later_does_not_change_earlier_as_of_reads() -> None:
    panel = _holdings_panel(
        [_filing("Q1", date(2024, 3, 31), date(2024, 5, 14)),
         _filing("Q1A", date(2024, 3, 31), date(2024, 8, 1), amendment_type="RESTATEMENT")],
        [_holding("Q1", 3_000_000), _holding("Q1A", 5_000_000)],
    )

    assert panel.specialist_ownership(ISSUER, date(2024, 7, 1)) == pytest.approx(0.3)
    assert panel.specialist_ownership(ISSUER, date(2024, 8, 5)) == pytest.approx(0.5)


def test_specialist_classification_uses_only_filings_accepted_before_as_of() -> None:
    filings = [
        _filing("Q2", date(2023, 6, 30), date(2023, 8, 10), total=400e6, healthcare=240e6),
        _filing("Q3", date(2023, 9, 30), date(2023, 11, 10), total=400e6, healthcare=240e6),
        _filing("Q4", date(2023, 12, 31), date(2024, 2, 10), total=400e6, healthcare=240e6),
        # A large generalist quarter that is not public until 14 May.
        _filing("Q1", date(2024, 3, 31), date(2024, 5, 14), total=4_000e6, healthcare=0.0),
    ]
    classifier = SpecialistClassifier(pd.DataFrame(filings), healthcare_share=0.5, min_aum_usd=100e6)

    assert classifier.specialists(date(2024, 5, 13)) == {FUND}
    assert classifier.specialists(date(2024, 5, 16)) == frozenset()


def test_filer_below_healthcare_share_is_not_a_specialist() -> None:
    filings = [_filing("Q4", date(2023, 12, 31), date(2024, 2, 10), total=1e9, healthcare=0.49e9)]
    classifier = SpecialistClassifier(pd.DataFrame(filings), healthcare_share=0.5, min_aum_usd=100e6)

    assert classifier.specialists(date(2024, 3, 1)) == frozenset()


def test_filer_below_minimum_aum_is_not_a_specialist() -> None:
    filings = [_filing("Q4", date(2023, 12, 31), date(2024, 2, 10), total=99e6, healthcare=90e6)]
    classifier = SpecialistClassifier(pd.DataFrame(filings), healthcare_share=0.5, min_aum_usd=100e6)

    assert classifier.specialists(date(2024, 3, 1)) == frozenset()


def test_specialist_ownership_divides_by_shares_outstanding_as_of_date() -> None:
    panel = _holdings_panel(
        [_filing("Q4", date(2023, 12, 31), date(2024, 2, 10))],
        [_holding("Q4", 2_000_000)],
        _shares((10_000_000, date(2024, 2, 1)), (20_000_000, date(2024, 5, 10))),
    )

    assert panel.specialist_ownership(ISSUER, date(2024, 5, 5)) == pytest.approx(0.2)
    assert panel.specialist_ownership(ISSUER, date(2024, 5, 20)) == pytest.approx(0.1)


def test_unmapped_cusip_is_counted_not_dropped_silently() -> None:
    minio = FakeMinio()
    sec = FakeSec({_13F_URL: _13f_dataset([
        ("ALPHA THERAPEUTICS INC", "02079K107", 30_000_000, 1_000_000),
        ("BIG COMPUTER CORP", "037833100", 50_000_000, 200_000),
        ("MYSTERY HOLDINGS PLC", "G0000X109", 20_000_000, 400_000),
    ])})

    report = _13f_store(minio, sec).fetch(_13F_DATASET)

    assert report.unmapped_cusips == 1
    assert report.unmapped_value_usd == 20_000_000
    assert _13f_store(minio, FakeSec()).report("2024q2") == report


# --- insider transactions ----------------------------------------------------------------------


def test_insider_purchase_counts_only_code_p_and_sale_only_code_s() -> None:
    accepted = date(2024, 3, 5)
    panel = _insider_panel([
        _trade("P", 100_000, 10.0, date(2024, 3, 1), accepted),
        _trade("S", 20_000, 10.0, date(2024, 3, 1), accepted),
        _trade("A", 500_000, 0.0, date(2024, 3, 1), accepted),
        _trade("M", 300_000, 2.0, date(2024, 3, 1), accepted),
        _trade("F", 50_000, 10.0, date(2024, 3, 1), accepted),
        _trade("G", 40_000, 0.0, date(2024, 3, 1), accepted),
    ])

    assert panel.net_insider_buying(ISSUER, date(2024, 4, 1)) == pytest.approx(800_000 / 100e6)


def test_10b5_1_plan_trades_are_excluded_from_net_buying() -> None:
    accepted = date(2024, 3, 5)
    panel = _insider_panel([
        _trade("P", 10_000, 10.0, date(2024, 3, 1), accepted),
        _trade("S", 50_000, 10.0, date(2024, 3, 1), accepted, plan=True),
    ])

    assert panel.net_insider_buying(ISSUER, date(2024, 4, 1)) == pytest.approx(100_000 / 100e6)


def test_purchase_within_two_days_of_issuer_offering_is_flagged_and_excluded() -> None:
    panel = _insider_panel(
        [_trade("P", 100_000, 10.0, date(2024, 3, 4), date(2024, 3, 6)),
         _trade("P", 10_000, 10.0, date(2024, 3, 20), date(2024, 3, 22))],
        [_offering("424B5", date(2024, 3, 6)), _offering("424B5", date(2024, 3, 20), OTHER_ISSUER)],
    )

    trades = panel.transactions(ISSUER, date(2024, 4, 1))
    flags = dict(zip(trades["transaction_date"], trades["offering_participation"], strict=True))
    assert flags == {date(2024, 3, 4): True, date(2024, 3, 20): False}
    assert panel.net_insider_buying(ISSUER, date(2024, 4, 1)) == pytest.approx(100_000 / 100e6)


def test_insider_window_is_by_filing_acceptance_not_transaction_date() -> None:
    panel = _insider_panel([
        # Traded before the 90-day window but accepted inside it: counted.
        _trade("P", 10_000, 10.0, date(2023, 12, 1), date(2024, 1, 5)),
        # Traded inside the window but accepted on the as-of date: not yet public.
        _trade("P", 50_000, 10.0, date(2024, 3, 28), date(2024, 4, 1)),
        # Accepted before the window opened.
        _trade("P", 70_000, 10.0, date(2023, 12, 29), date(2024, 1, 1)),
    ])

    assert panel.net_insider_buying(ISSUER, date(2024, 4, 1), days=90) == pytest.approx(
        100_000 / 100e6
    )


# --- storage -----------------------------------------------------------------------------------


def test_quarter_already_stored_is_not_refetched() -> None:
    minio = FakeMinio()
    sec = FakeSec({
        _13F_URL: _13f_dataset([("ALPHA THERAPEUTICS INC", "02079K107", 30_000_000, 1_000_000)]),
        _INSIDER_URL: _insider_dataset("0001001001-24-000001", 10_000),
    })
    _13f_store(minio, sec).fetch(_13F_DATASET)
    _insider_store(minio, sec).fetch_quarter(_INSIDER_DATASET)
    stored = dict(minio.objects)

    again = FakeSec()
    _13f_store(minio, again).fetch(_13F_DATASET)
    _insider_store(minio, again).fetch_quarter(_INSIDER_DATASET)

    assert again.requested == []
    assert minio.objects == stored


def test_daily_form4_rows_fill_the_quarter_before_its_dataset_exists() -> None:
    minio = FakeMinio()
    day = date(2024, 9, 16)
    sec = _daily_sec(day, "0001001001-24-000001", "20240916163012", 20_000)

    rows = _insider_store(minio, sec).fetch_day(day)
    panel = InsiderPanel.load(OwnershipStore(minio), FixedMarketCaps({ISSUER: 100e6}))

    assert rows == 1
    (trade,) = panel.transactions(ISSUER, date(2024, 10, 1)).to_dict("records")
    assert trade["filing_accepted_at"] == pd.Timestamp("2024-09-16T20:30:12Z")
    assert trade["transaction_date"] == day
    assert panel.net_insider_buying(ISSUER, date(2024, 10, 1)) == pytest.approx(200_000 / 100e6)


def test_quarterly_dataset_is_preferred_and_disagreement_is_reported() -> None:
    minio = FakeMinio()
    day = date(2024, 9, 16)
    _insider_store(minio, _daily_sec(day, "0001001001-24-000001", "20240916163012", 25_000)) \
        .fetch_day(day)
    _insider_store(minio, FakeSec({_INSIDER_URL: _insider_dataset("0001001001-24-000001", 20_000)})) \
        .fetch_quarter(_INSIDER_DATASET)

    panel = InsiderPanel.load(OwnershipStore(minio), FixedMarketCaps({ISSUER: 100e6}))

    assert panel.net_insider_buying(ISSUER, date(2024, 10, 1)) == pytest.approx(200_000 / 100e6)
    (disagreement,) = panel.disagreements()
    assert disagreement.quarter == "2024q3"
    assert disagreement.accession_number == "0001001001-24-000001"
    assert disagreement.kind == "different"


def test_requests_carry_the_configured_user_agent() -> None:
    seen: list[urllib.request.Request] = []

    class _Response(io.BytesIO):
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            self.close()

    def opener(request: urllib.request.Request, timeout: float) -> _Response:
        seen.append(request)
        return _Response(b"ok")

    client = SecClient(_UA, opener=opener, sleep=lambda _: None)
    client.get("https://sec.example/a")
    client.download("https://sec.example/b.zip", Path("/dev/null"))

    assert [r.get_header("User-agent") for r in seen] == [_UA, _UA]
