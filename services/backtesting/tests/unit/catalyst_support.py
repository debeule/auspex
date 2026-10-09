"""Fixture documents and fakes shared by the catalyst panel tests.

The EDGAR and Federal Register documents are trimmed to the parts the extractors read; the
filing index layout follows the one `test_universe_sec_index.py` uses.
"""

import io
import json
import urllib.error
import urllib.parse
from collections.abc import Callable
from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from minio.error import S3Error

from auspex_backtesting.catalysts import (
    AdvisoryCommitteeNotices,
    CatalystPanel,
    DocumentCache,
    HttpSource,
    PressReleaseCatalystExtractor,
)
from auspex_backtesting.universe import UniverseMember

ARCHIVES = "https://archives.example/edgar/data"
FULL_INDEX = "https://archives.example/edgar/full-index"
FR_API = "https://fr.example/api/v1/documents.json"
USER_AGENT = "Auspex research a@b.c"
TODAY = date(2026, 10, 9)

ACME = "0001234567"
BETA = "0007654321"


class FakeMinio:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, bucket: str, key: str, data: io.BytesIO, length: int, **_: object) -> None:
        self.objects[key] = data.read(length)

    def get_object(self, bucket: str, key: str) -> MagicMock:
        if key not in self.objects:
            raise S3Error(MagicMock(), "NoSuchKey", "missing", "/", "", "")
        response = MagicMock()
        response.read.return_value = self.objects[key]
        return response

    def list_objects(self, bucket: str, prefix: str = "", recursive: bool = False) -> list[Any]:
        return [SimpleNamespace(object_name=k) for k in sorted(self.objects) if k.startswith(prefix)]


class FakeWeb:
    """Serves `pages` by exact URL and Federal Register listings by publication quarter."""

    def __init__(self, pages: dict[str, str] | None = None,
                 listings: dict[str, list[dict[str, Any]]] | None = None,
                 refuse_after: int | None = None) -> None:
        self.pages = dict(pages or {})
        self.listings = listings or {}
        self.requested: list[str] = []
        self.user_agents: set[str] = set()
        self.refuse_after = refuse_after

    def __call__(self, url: str, user_agent: str) -> bytes:
        self.requested.append(url)
        self.user_agents.add(user_agent)
        if self.refuse_after is not None and len(self.requested) > self.refuse_after:
            raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)  # type: ignore[arg-type]
        if url.startswith(FR_API + "?"):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            start = query["conditions[publication_date][gte]"][0]
            results = self.listings.get(start, [])
            return json.dumps({"count": len(results), "total_pages": 1 if results else 0,
                               "results": results}).encode()
        if url not in self.pages:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)  # type: ignore[arg-type]
        return self.pages[url].encode()


def member(cik: str, name: str, ticker: str | None = None) -> UniverseMember:
    return UniverseMember(cik, ticker, "current", name, "2834", "Nasdaq", None, None,
                          date(2014, 1, 2), None, None, "complete", "")


MEMBERS = (member(ACME, "ACME BIO, INC.", "ACME"), member(BETA, "Beta Therapeutics Inc", "BETA"))


def master_index(rows: list[tuple[str, str, str, str]]) -> str:
    """A quarterly `master.idx`; rows are (cik, form, date filed, accession)."""
    names = {ACME.lstrip("0"): "ACME BIO, INC.", BETA.lstrip("0"): "BETA THERAPEUTICS INC"}
    lines = [
        "Description:           Master Index of EDGAR Dissemination Feed",
        "Last Data Received:    March 31, 2024",
        "Comments:              webmaster@sec.gov",
        "Anonymous FTP:         ftp://ftp.sec.gov/edgar/",
        "Cloud HTTP:            https://www.sec.gov/Archives/",
        "",
        "",
        "",
        "",
        "CIK|Company Name|Form Type|Date Filed|Filename",
        "-" * 80,
    ]
    for cik, form, filed, accession in rows:
        lines.append(f"{cik}|{names.get(cik, 'OTHER CO')}|{form}|{filed}|"
                     f"edgar/data/{cik}/{accession}.txt")
    return "\n".join(lines) + "\n"


def filing_index(cik: str, accession: str, accepted: str, items: tuple[str, ...] = ("8.01", "9.01"),
                 exhibit: bool = True) -> str:
    folder = f"/Archives/edgar/data/{cik}/{accession.replace('-', '')}"
    item_names = {"2.02": "Results of Operations and Financial Condition",
                  "7.01": "Regulation FD Disclosure", "8.01": "Other Events",
                  "9.01": "Financial Statements and Exhibits"}
    item_html = "<br />".join(f"Item {i}: {item_names[i]}" for i in items)
    exhibit_row = (
        f'<tr><td scope="row">2</td><td scope="row">PRESS RELEASE</td>'
        f'<td scope="row"><a href="{folder}/ex99-1.htm">ex99-1.htm</a></td>'
        f'<td scope="row">EX-99.1</td><td scope="row">12345</td></tr>'
    ) if exhibit else ""
    return f"""
<div class="formGrouping">
<div class="infoHead">Filing Date</div><div class="info">{accepted[:10]}</div>
<div class="infoHead">Accepted</div><div class="info">{accepted}</div>
</div>
<div class="formGrouping">
<div class="infoHead">Items</div>
<div class="info">{item_html}</div>
</div>
<table class="tableFile" summary="Document Format Files">
<tr><th scope="col">Seq</th><th scope="col">Description</th><th scope="col">Document</th>
<th scope="col">Type</th><th scope="col">Size</th></tr>
<tr><td scope="row">1</td><td scope="row">8-K</td>
<td scope="row"><a href="/ix?doc={folder}/acme-8k.htm">acme-8k.htm</a></td>
<td scope="row">8-K</td><td scope="row">23456</td></tr>
{exhibit_row}
</table>
"""


ACCEPTANCE_RELEASE = """<html><body>
<p style="text-align:center"><b>ACME Bio Announces FDA Acceptance of New Drug Application for
Zorvexa&#8482; (acmetinib)</b></p>
<p>BOSTON, Feb. 5, 2024 -- ACME Bio, Inc. (Nasdaq: ACME) today announced that the U.S. Food and
Drug Administration (FDA) has accepted its New Drug Application (NDA) for Zorvexa (acmetinib) for
the treatment of adults with relapsed solid tumors. The FDA has assigned a Prescription Drug User
Fee Act (PDUFA) target action date of October&nbsp;15, 2024.</p>
<p>About ACME Bio<br />ACME Bio develops kinase inhibitors. Its revenue for the year ended
December 31, 2023 was $4.1 million.</p>
</body></html>"""

EXTENSION_RELEASE = """<html><body>
<p><b>ACME Bio Announces Extension of PDUFA Date for Zorvexa&#8482;</b></p>
<p>BOSTON, July 1, 2024 -- ACME Bio, Inc. (Nasdaq: ACME) today announced that the FDA has
extended the PDUFA target action date for acmetinib by three months from October 15, 2024 to
January 15, 2025, to review a major amendment to the application.</p>
</body></html>"""

HALF_YEAR_RELEASE = """<html><body>
<p>CAMBRIDGE, Mass., March 4, 2024 -- Beta Therapeutics Inc. (Nasdaq: BETA) today reported that
it completed the rolling submission of its Biologics License Application (BLA) for BTX-401. Beta
expects a PDUFA goal date in the second half of 2025, subject to FDA acceptance.</p>
</body></html>"""

RESULTS_RELEASE = """<html><body>
<p>CAMBRIDGE, Mass., March 14, 2024 -- Beta Therapeutics Inc. (Nasdaq: BETA) today reported
fourth quarter and full year 2023 financial results. Cash was $210 million as of
December 31, 2023. The company will host a conference call on March 15, 2024.</p>
</body></html>"""


def accession(cik: str, n: int) -> str:
    return f"{cik}-24-{n:06d}"


def index_url(cik: str, acc: str) -> str:
    return f"{ARCHIVES}/{int(cik)}/{acc.replace('-', '')}/{acc}-index.htm"


def exhibit_url(cik: str, acc: str) -> str:
    return f"https://archives.example/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/ex99-1.htm"


def filing_pages(cik: str, acc: str, accepted: str, release: str | None,
                 items: tuple[str, ...] = ("8.01", "9.01")) -> dict[str, str]:
    pages = {index_url(cik, acc): filing_index(str(int(cik)), acc, accepted, items,
                                               exhibit=release is not None)}
    if release is not None:
        pages[exhibit_url(cik, acc)] = release
    return pages


def sec_web(filings: list[tuple[str, str, str, str | None]], *,
            items: dict[str, tuple[str, ...]] | None = None,
            refuse_after: int | None = None) -> FakeWeb:
    """A fake SEC serving `filings` as (cik, accession, accepted ET, release or None), each
    listed in the master index of the quarter it was accepted in."""
    pages: dict[str, str] = {}
    by_quarter: dict[str, list[tuple[str, str, str, str]]] = {}
    for cik, acc, accepted, release in filings:
        pages.update(filing_pages(cik, acc, accepted, release, (items or {}).get(acc, ("8.01", "9.01"))))
        filed = date.fromisoformat(accepted[:10])
        quarter = f"{FULL_INDEX}/{filed.year}/QTR{(filed.month - 1) // 3 + 1}/master.idx"
        by_quarter.setdefault(quarter, []).append((str(int(cik)), "8-K", accepted[:10], acc))
    for url, rows in by_quarter.items():
        pages[url] = master_index(rows)
    return FakeWeb(pages, refuse_after=refuse_after)


def no_sleep(_: float) -> None:
    return None


def press_releases(web: Callable[[str, str], bytes], minio: FakeMinio,
                   sleeps: list[float] | None = None) -> PressReleaseCatalystExtractor:
    sec = HttpSource(USER_AGENT, 0.2, fetch=web, clock=lambda: 0.0,
                     sleep=sleeps.append if sleeps is not None else no_sleep)
    return PressReleaseCatalystExtractor(FULL_INDEX, ARCHIVES, sec, DocumentCache(minio),
                                         today=lambda: TODAY)


def adcom_notices(web: Callable[[str, str], bytes], minio: FakeMinio) -> AdvisoryCommitteeNotices:
    fr = HttpSource(USER_AGENT, 1.0, fetch=web, clock=lambda: 0.0, sleep=no_sleep)
    return AdvisoryCommitteeNotices(FR_API, fr, DocumentCache(minio), today=lambda: TODAY)


def panel_from(minio: FakeMinio) -> CatalystPanel:
    return CatalystPanel(minio)  # type: ignore[arg-type]


def fr_notice(number: str, title: str, published: str, dates: str) -> dict[str, Any]:
    return {
        "document_number": number,
        "title": title,
        "type": "Notice",
        "publication_date": published,
        "dates": dates,
        "html_url": f"https://fr.example/documents/{number}",
        "raw_text_url": f"https://fr.example/documents/full_text/text/{number}.txt",
    }


def fr_text(agenda: str) -> str:
    return (
        "DEPARTMENT OF HEALTH AND HUMAN SERVICES\nFood and Drug Administration\n"
        "AGENCY: Food and Drug Administration, HHS.\nACTION: Notice.\n"
        "SUMMARY: The Food and Drug Administration (FDA) announces a forthcoming public advisory "
        "committee meeting.\n"
        f"Agenda: {agenda}\n"
        "Procedure: Interested persons may present data, information, or views.\n"
    )
