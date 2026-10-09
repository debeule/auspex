import urllib.error
from datetime import date

import pytest

from auspex_backtesting.universe import CompanyRecord, Filing
from auspex_backtesting.universe.listing import ListingHistory
from auspex_backtesting.universe.sec_index import InstanceDocuments, instance_document

_EXCHANGES = frozenset({"NYSE", "Nasdaq"})
_ARCHIVES = "https://archives.example/edgar/data"

# Trimmed from a 2014 10-K index page: the XBRL instance sits in the second ("Data Files") table.
_INDEX_2014 = """
<table class="tableFile" summary="Document Format Files">
<tr><th scope="col">Seq</th><th scope="col">Description</th><th scope="col">Document</th>
<th scope="col">Type</th><th scope="col">Size</th></tr>
<tr><td scope="row">1</td><td scope="row">FORM 10-K</td>
<td scope="row"><a href="/Archives/edgar/data/1234567/000119312514012345/d650123d10k.htm">d650123d10k.htm</a></td>
<td scope="row">10-K</td><td scope="row">1234567</td></tr>
</table>
<table class="tableFile" summary="Data Files">
<tr><th scope="col">Seq</th><th scope="col">Description</th><th scope="col">Document</th>
<th scope="col">Type</th><th scope="col">Size</th></tr>
<tr class="evenRow"><td scope="row">6</td><td scope="row">XBRL INSTANCE DOCUMENT</td>
<td scope="row"><a href="/Archives/edgar/data/1234567/000119312514012345/oldx-20131231.xml">oldx-20131231.xml</a></td>
<td scope="row">EX-101.INS</td><td scope="row">2345678</td></tr>
<tr><td scope="row">7</td><td scope="row">XBRL TAXONOMY EXTENSION SCHEMA</td>
<td scope="row"><a href="/Archives/edgar/data/1234567/000119312514012345/oldx-20131231.xsd">oldx-20131231.xsd</a></td>
<td scope="row">EX-101.SCH</td><td scope="row">34567</td></tr>
</table>
"""


def _company(cik: str, filings: list[Filing], tickers: tuple[str, ...] = ()) -> CompanyRecord:
    return CompanyRecord(cik, f"Company {cik}", "2834", (), tickers, tuple(filings))


def _delisted_2015(cik: str, *, xbrl: bool = True, document: str = "d650123d10k.htm") -> CompanyRecord:
    return _company(cik, [
        Filing("8-A12B", date(2010, 5, 1)),
        Filing("10-K", date(2013, 3, 1), (), "d500001d10k.htm", "0001193125-13-000001", xbrl),
        Filing("10-K", date(2014, 3, 3), (), document, "0001193125-14-012345", xbrl),
        Filing("8-K", date(2014, 6, 2), ("8.01",), "d700001d8k.htm", "0001193125-14-020000"),
        Filing("25-NSE", date(2015, 2, 10)),
    ])


class _Sec:
    def __init__(self, pages: dict[str, str] | None = None, refuse_after: int | None = None) -> None:
        self.pages = pages or {}
        self.requested: list[tuple[str, str]] = []
        self.refuse_after = refuse_after

    def __call__(self, url: str, user_agent: str) -> str:
        self.requested.append((url, user_agent))
        if self.refuse_after is not None and len(self.requested) > self.refuse_after:
            raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)  # type: ignore[arg-type]
        if url not in self.pages:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)  # type: ignore[arg-type]
        return self.pages[url]


def _index_url(cik: str, accession: str) -> str:
    return f"{_ARCHIVES}/{int(cik)}/{accession.replace('-', '')}/{accession}-index.htm"


def test_filing_index_yields_the_xbrl_instance_document_name() -> None:
    assert instance_document(_INDEX_2014) == "oldx-20131231.xml"
    without_xbrl = _INDEX_2014.replace("EX-101.INS", "EX-101.LAB")
    assert instance_document(without_xbrl) is None


def test_company_delisted_before_inline_xbrl_takes_its_ticker_from_the_xbrl_instance_document() -> None:
    gone = _delisted_2015("0001234567")
    sec = _Sec({_index_url("0001234567", "0001193125-14-012345"): _INDEX_2014})

    (resolved,) = InstanceDocuments(_ARCHIVES, "Auspex research a@b.c", fetch=sec, sleep=lambda _: None
                                    ).attach([gone], _EXCHANGES, since=date(2013, 11, 17))

    history = ListingHistory.from_record(resolved, _EXCHANGES)
    assert (history.ticker, history.ticker_source) == ("OLDX", "filing")
    assert sec.requested == [
        (_index_url("0001234567", "0001193125-14-012345"), "Auspex research a@b.c")
    ]


def test_instance_lookup_reads_only_unresolved_companies_listed_in_the_window() -> None:
    current = _company("0000000001", [Filing("8-A12B", date(2010, 5, 1))], tickers=("CURR",))
    inline = _delisted_2015("0000000002", document="inln-20131231.htm")
    before_window = _company("0000000003", [
        Filing("8-A12B", date(2005, 5, 1)),
        Filing("10-K", date(2011, 3, 1), (), "d1d10k.htm", "0001193125-11-000001", True),
        Filing("25-NSE", date(2012, 2, 10)),
    ])
    no_xbrl = _delisted_2015("0000000004", xbrl=False)
    wanted = _delisted_2015("0000000005")
    sec = _Sec({_index_url("0000000005", "0001193125-14-012345"): _INDEX_2014})

    records = InstanceDocuments(_ARCHIVES, "ua", fetch=sec, sleep=lambda _: None).attach(
        [current, inline, before_window, no_xbrl, wanted], _EXCHANGES, since=date(2013, 11, 17)
    )

    assert [url for url, _ in sec.requested] == [_index_url("0000000005", "0001193125-14-012345")]
    assert records[:4] == [current, inline, before_window, no_xbrl]


def test_instance_lookups_are_paced_under_sec_request_limit() -> None:
    companies = [_delisted_2015(f"000000000{i}") for i in range(1, 4)]
    sec = _Sec({_index_url(c.cik, "0001193125-14-012345"): _INDEX_2014 for c in companies})
    pauses: list[float] = []

    InstanceDocuments(_ARCHIVES, "ua", fetch=sec, sleep=pauses.append).attach(
        companies, _EXCHANGES, since=date(2013, 11, 17)
    )

    assert len(sec.requested) == 3
    assert len(pauses) == 2
    assert all(p >= 0.1 for p in pauses)


def test_instance_lookups_stop_once_sec_refuses_requests() -> None:
    companies = [_delisted_2015(f"000000000{i}") for i in range(1, 5)]
    sec = _Sec({_index_url(c.cik, "0001193125-14-012345"): _INDEX_2014 for c in companies},
               refuse_after=1)

    records = InstanceDocuments(_ARCHIVES, "ua", fetch=sec, sleep=lambda _: None).attach(
        companies, _EXCHANGES, since=date(2013, 11, 17)
    )

    # Retrying while SEC blocks the address only extends the block.
    assert len(sec.requested) == 2
    tickers = [ListingHistory.from_record(r, _EXCHANGES).ticker for r in records]
    assert tickers == ["OLDX", None, None, None]


def test_missing_filing_index_leaves_that_company_unresolved_and_continues() -> None:
    first, second = _delisted_2015("0000000001"), _delisted_2015("0000000002")
    sec = _Sec({_index_url("0000000002", "0001193125-14-012345"): _INDEX_2014})

    records = InstanceDocuments(_ARCHIVES, "ua", fetch=sec, sleep=lambda _: None).attach(
        [first, second], _EXCHANGES, since=date(2013, 11, 17)
    )

    assert [ListingHistory.from_record(r, _EXCHANGES).ticker for r in records] == [None, "OLDX"]


@pytest.mark.parametrize("name", ["oldx-20131231_htm.xml", "oldx_20131231.xml", "toolongx-20131231.xml"])
def test_instance_documents_not_named_after_a_symbol_give_no_ticker(name: str) -> None:
    gone = _delisted_2015("0001234567")
    page = _INDEX_2014.replace("oldx-20131231.xml", name)
    sec = _Sec({_index_url("0001234567", "0001193125-14-012345"): page})

    (resolved,) = InstanceDocuments(_ARCHIVES, "ua", fetch=sec, sleep=lambda _: None).attach(
        [gone], _EXCHANGES, since=date(2013, 11, 17)
    )

    assert ListingHistory.from_record(resolved, _EXCHANGES).ticker_source == "unresolved"
