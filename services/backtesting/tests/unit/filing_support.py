"""Fixture filings and fakes shared by the filing text change tests.

The filing index pages follow EDGAR's `-index.htm` layout as `catalyst_support.py` builds it,
with the "Period of Report" field 10-K and 10-Q index pages carry.
"""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from catalyst_support import FakeMinio, FakeWeb, master_index
from minio.error import S3Error

from auspex_backtesting.catalysts import DocumentCache, HttpSource
from auspex_backtesting.filings import (
    ArchivedSection,
    FilingIndex,
    FilingSectionArchive,
    IndexEntry,
)
from auspex_backtesting.universe import UniverseMember, UniverseSnapshot, UniverseStore

FIXTURES = Path(__file__).parent / "fixtures" / "filings"
ARCHIVES = "https://archives.example/edgar/data"
FULL_INDEX = "https://archives.example/edgar/full-index"
USER_AGENT = "Auspex research a@b.c"
TODAY = date(2026, 10, 9)

ACME = "0001234567"
BETA = "0007654321"


class StoreMinio(FakeMinio):
    """`FakeMinio` with the existence check the universe store makes before writing."""

    def stat_object(self, bucket: str, key: str) -> object:
        if key not in self.objects:
            raise S3Error(MagicMock(), "NoSuchKey", "missing", "/", "", "")
        return object()


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def index_url(cik: str, acc: str) -> str:
    return f"{ARCHIVES}/{int(cik)}/{acc.replace('-', '')}/{acc}-index.htm"


def document_url(cik: str, acc: str) -> str:
    return f"https://archives.example/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/doc.htm"


def filing_index_page(cik: str, acc: str, form: str, accepted: str, period: str) -> str:
    folder = f"/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}"
    return f"""
<div class="formGrouping">
<div class="infoHead">Filing Date</div><div class="info">{accepted[:10]}</div>
<div class="infoHead">Accepted</div><div class="info">{accepted}</div>
</div>
<div class="formGrouping">
<div class="infoHead">Period of Report</div>
<div class="info">{period}</div>
</div>
<table class="tableFile" summary="Document Format Files">
<tr><th scope="col">Seq</th><th scope="col">Description</th><th scope="col">Document</th>
<th scope="col">Type</th><th scope="col">Size</th></tr>
<tr><td scope="row">1</td><td scope="row">{form}</td>
<td scope="row"><a href="/ix?doc={folder}/doc.htm">doc.htm</a></td>
<td scope="row">{form}</td><td scope="row">23456</td></tr>
<tr><td scope="row">2</td><td scope="row">EXHIBIT 31.1</td>
<td scope="row"><a href="{folder}/ex31-1.htm">ex31-1.htm</a></td>
<td scope="row">EX-31.1</td><td scope="row">1234</td></tr>
</table>
"""


def filing_pages(
    cik: str, acc: str, form: str, accepted: str, period: str, document: str
) -> dict[str, str]:
    """The index page and primary document of one filing; `accepted` is EDGAR's Eastern time."""
    return {
        index_url(cik, acc): filing_index_page(cik, acc, form, accepted, period),
        document_url(cik, acc): document,
    }


def risk_document(form: str, *paragraphs: str) -> str:
    """A minimal 10-K or 10-Q whose Item 1A holds `paragraphs`."""
    end = "Item 1B. Unresolved Staff Comments" if form.startswith("10-K") else "Item 2. Other"
    part = "<div><b>PART II. OTHER INFORMATION</b></div>" if form.startswith("10-Q") else ""
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    return (
        f"<html><body><div><b>FORM {form}</b></div>{part}"
        f"<div><b>Item 1A. Risk Factors</b></div>{body}<div><b>{end}</b></div>"
        "<p>None.</p></body></html>"
    )


def entry(cik: str, form: str, filed: str, acc: str) -> IndexEntry:
    return IndexEntry(cik, form, date.fromisoformat(filed), acc)


def archive(
    web: FakeWeb, minio: FakeMinio | None = None
) -> tuple[FilingSectionArchive, FakeMinio]:
    minio = minio or StoreMinio()
    sec = HttpSource(USER_AGENT, 0.0, fetch=web, sleep=lambda _: None)
    return FilingSectionArchive(minio, ARCHIVES, sec), minio  # type: ignore[arg-type]


def filing_index(web: FakeWeb, minio: FakeMinio) -> FilingIndex:
    sec = HttpSource(USER_AGENT, 0.0, fetch=web, sleep=lambda _: None)
    return FilingIndex(
        minio,  # type: ignore[arg-type]
        FULL_INDEX,
        sec,
        DocumentCache(minio),  # type: ignore[arg-type]
        today=lambda: TODAY,
    )


def quarter_index(rows: list[tuple[str, str, str, str]]) -> str:
    return master_index([(str(int(cik)), form, filed, acc) for cik, form, filed, acc in rows])


def section(
    cik: str,
    acc: str,
    form: str,
    period: str,
    accepted: datetime,
    text: str,
    status: Any = "cut",
) -> ArchivedSection:
    return ArchivedSection(
        cik=cik,
        accession=acc,
        form=form,
        filed=accepted.date(),
        period_of_report=date.fromisoformat(period),
        accepted_at=accepted,
        status=status,
        reason="",
        text=text,
    )


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def member(cik: str, ticker: str) -> UniverseMember:
    return UniverseMember(cik, ticker, "current", f"{ticker} Inc", "2834", "Nasdaq", None, None,
                          date(2014, 1, 2), None, None, "complete", "")


def universe_with(minio: FakeMinio, month: str, rebalance: date, *ciks: str) -> UniverseStore:
    store = UniverseStore(minio)  # type: ignore[arg-type]
    members = tuple(member(c, f"T{c[-2:]}") for c in sorted(ciks))
    store.write(UniverseSnapshot(1, month, rebalance, members))
    return store
