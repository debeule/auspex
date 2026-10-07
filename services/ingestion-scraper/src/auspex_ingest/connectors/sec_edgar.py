"""SEC EDGAR 8-K connector (EFTS full-text search endpoint).

EFTS is undocumented: no published parameter list or schema commitment, so the hit
mapping stays thin. Only 8-Ks carrying a press-release item (`_PRESS_RELEASE_ITEMS`)
are kept. Trial readouts, CRLs and clinical holds are usually furnished as Exhibit 99.1
rather than written into the cover document, so each filing's index page is read for the
cover, the exhibit and the acceptance time; the exhibit text leads `raw_content` so it
falls inside the extractor's input window.
"""

import hashlib
import logging
import os
import re
import time
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from datetime import time as dt_time
from html.parser import HTMLParser
from typing import Any, cast
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import httpx

from ..models import RawDocument
from .base import SourceConnector
from .rate_limited_client import RateLimitedClient

_USER_AGENT: str = os.environ.get("SEC_USER_AGENT", "")

_log = logging.getLogger(__name__)

_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
_FORMS = "8-K,8-K/A"
# Results of operations, Regulation FD and other events: the items press releases are filed under.
_PRESS_RELEASE_ITEMS = frozenset({"2.02", "7.01", "8.01"})
_PRESS_RELEASE_EXHIBIT = re.compile(r"EX-99\.0?1", re.IGNORECASE)
_EDGAR_TZ = ZoneInfo("America/New_York")
# EDGAR assigns the next business day's file date to anything accepted after 17:30 ET,
# so a filing is known to be public by this time on its file date.
_FILING_DATE_CUTOFF = dt_time(17, 30)
_PAGE_SIZE = 20
# SEC blocks by IP for ~10 minutes on rate limit; back off conservatively.
_BLOCK_BACKOFF = 60.0


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self._parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


class _FilingIndexParser(HTMLParser):
    """Reads the acceptance time and the "Document Format Files" table of a `-index.htm` page."""

    def __init__(self) -> None:
        super().__init__()
        self.accepted: str | None = None
        self.header: list[str] = []
        self.rows: list[list[tuple[str, str | None]]] = []
        self._div_class: str | None = None
        self._div_text: list[str] = []
        self._last_info_head: str | None = None
        self._in_documents_table = False
        self._documents_table_done = False
        self._row: list[tuple[str, str | None]] | None = None
        self._cell_text: list[str] | None = None
        self._cell_href: str | None = None
        self._cell_is_header = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "div":
            self._div_class = attr.get("class")
            self._div_text = []
        elif tag == "table" and "tableFile" in (attr.get("class") or ""):
            # The first file table lists the filed documents; a later one holds XBRL data files.
            self._in_documents_table = not self._documents_table_done
        elif not self._in_documents_table:
            return
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell_text = []
            self._cell_href = None
            self._cell_is_header = tag == "th"
        elif tag == "a" and self._cell_text is not None and self._cell_href is None:
            self._cell_href = attr.get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self._div_class is not None:
            text = " ".join(self._div_text).strip()
            if self._div_class == "infoHead":
                self._last_info_head = text
            elif self._div_class == "info" and self._last_info_head == "Accepted":
                self.accepted = text
            self._div_class = None
        elif tag == "table" and self._in_documents_table:
            self._in_documents_table = False
            self._documents_table_done = True
        elif tag in ("td", "th") and self._cell_text is not None:
            text = " ".join(self._cell_text).strip()
            if self._cell_is_header:
                self.header.append(text)
            elif self._row is not None:
                self._row.append((text, self._cell_href))
            self._cell_text = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if not stripped:
            return
        if self._div_class is not None:
            self._div_text.append(stripped)
        if self._cell_text is not None:
            self._cell_text.append(stripped)


class _FilingIndex:
    def __init__(self, accepted_at: datetime | None, documents: dict[str, str]) -> None:
        self.accepted_at = accepted_at
        # document type (e.g. "8-K", "EX-99.1") -> absolute URL; first occurrence wins
        self.documents = documents

    @classmethod
    def parse(cls, html: str) -> _FilingIndex:
        parser = _FilingIndexParser()
        parser.feed(html)
        try:
            doc_col = parser.header.index("Document")
            type_col = parser.header.index("Type")
        except ValueError:
            doc_col, type_col = 2, 3
        documents: dict[str, str] = {}
        for row in parser.rows:
            if len(row) <= max(doc_col, type_col):
                continue
            doc_type = row[type_col][0].upper()
            href = row[doc_col][1]
            if not doc_type or not href:
                continue
            # Inline XBRL documents link through the viewer: /ix?doc=/Archives/...
            href = href.removeprefix("/ix?doc=")
            documents.setdefault(doc_type, urljoin("https://www.sec.gov/", href))
        return cls(_parse_acceptance(parser.accepted), documents)

    def primary_document(self, form_type: str) -> str | None:
        return self.documents.get(form_type.upper()) or self.documents.get("8-K") or self.documents.get("8-K/A")

    def press_release_exhibit(self) -> str | None:
        return next(
            (url for doc_type, url in self.documents.items() if _PRESS_RELEASE_EXHIBIT.fullmatch(doc_type)),
            None,
        )


def _parse_acceptance(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_EDGAR_TZ).astimezone(UTC)
    except ValueError:
        return None

class SecEdgarConnector(SourceConnector):
    provides_canonical_id = True

    def __init__(
        self,
        *,
        client: RateLimitedClient,
        user_agent: str = _USER_AGENT,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = client
        self._user_agent = user_agent
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep: Callable[[float], None] = sleep or time.sleep
        self._max_retries = max_retries

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        start = cursor.strftime("%Y-%m-%d")
        end = self._now().strftime("%Y-%m-%d")
        retrieved_at = self._now()
        from_ = 0
        seen_accessions: set[str] = set()

        while True:
            params = {
                "q": "",
                "dateRange": "custom",
                "startdt": start,
                "enddt": end,
                "forms": _FORMS,
                "from": str(from_),
            }
            data = self._get_json(params)
            hits_wrapper = data.get("hits") or {}
            hits: list[dict[str, Any]] = hits_wrapper.get("hits") or []
            total: int = (hits_wrapper.get("total") or {}).get("value", 0)

            for hit in hits:
                source = hit.get("_source") or {}
                if not _PRESS_RELEASE_ITEMS.intersection(source.get("items") or []):
                    continue
                doc = self._map(source, retrieved_at)
                if doc is None:
                    continue
                # Full-text search can return a hit per filed document (cover, exhibits); the filing is the unit.
                accession_no = str(source["adsh"])
                if accession_no in seen_accessions:
                    continue
                seen_accessions.add(accession_no)
                yield self._with_filing_content(doc, source)

            from_ += len(hits)
            if from_ >= total or not hits:
                break

    def _map(self, source: dict[str, Any], retrieved_at: datetime) -> RawDocument | None:
        accession_no: str = str(source.get("adsh") or "")
        if not accession_no:
            return None

        file_date: str = str(source.get("file_date") or "")
        if not file_date:
            return None

        # ciks[0] is zero-padded; strip for the Archives URL path
        entity_id: str = str((source.get("ciks") or [""])[0]).lstrip("0")
        # display_names[0] may include " (TICKER)  (CIK XXXXXXXXXX)" suffix
        entity_name: str = str((source.get("display_names") or [""])[0]).split("(")[0].strip()
        form_type: str = str(source.get("form") or "")
        period: str = str(source.get("period_ending") or "")
        items: str = ", ".join(source.get("items") or [])

        # Until the index supplies the acceptance time: no filing is accepted later than this on its file date.
        published_date = datetime.combine(
            date.fromisoformat(file_date), _FILING_DATE_CUTOFF, tzinfo=_EDGAR_TZ
        ).astimezone(UTC)

        raw_content = (
            f"Accession: {accession_no}\n"
            f"Entity: {entity_name}\n"
            f"Form type: {form_type}\n"
            f"Filed: {file_date}\n"
            f"Period: {period}\n"
            f"Items: {items}"
        )
        sha = hashlib.sha256(raw_content.encode()).hexdigest()

        accession_nodash = accession_no.replace("-", "")
        source_url = (
            f"{_ARCHIVES_URL}/{entity_id}/{accession_nodash}/"
            if entity_id
            else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&accession={accession_nodash}"
        )

        return RawDocument(
            schema_version="1.0",
            external_id=f"edgar:{accession_no}",
            canonical_id=f"edgar:{accession_no}",
            source_type="edgar",
            source_url=source_url,
            published_date=published_date,
            raw_content=raw_content,
            content_sha256=sha,
            retrieved_at=retrieved_at,
        )

    def _with_filing_content(self, doc: RawDocument, source: dict[str, Any]) -> RawDocument:
        """Swap the metadata stub for the filing's text and acceptance time, where the archive has them."""
        accession_no = str(source["adsh"])
        # The company's CIK, not the accession prefix: that names whoever submitted the filing,
        # often a filing agent.
        cik = str((source.get("ciks") or [""])[0]).lstrip("0")
        if not cik:
            return doc
        index_url = f"{_ARCHIVES_URL}/{cik}/{accession_no.replace('-', '')}/{accession_no}-index.htm"
        index_html = self._get_text(index_url, accession_no, "filing index")
        if index_html is None:
            return doc
        index = _FilingIndex.parse(index_html)

        update: dict[str, Any] = {}
        if index.accepted_at is not None:
            update["published_date"] = index.accepted_at

        parts: list[str] = []
        exhibit_url = index.press_release_exhibit()
        if exhibit_url is not None:
            exhibit = self._get_text(exhibit_url, accession_no, "exhibit 99.1")
            if exhibit:
                parts.append(_strip_html(exhibit))
        primary_url = index.primary_document(str(source.get("form") or ""))
        if primary_url is not None:
            primary = self._get_text(primary_url, accession_no, "primary document")
            if primary:
                parts.append(_strip_html(primary))
        else:
            _log.warning("edgar filing index lists no primary document: accession=%s", accession_no)

        text = "\n\n".join(p for p in parts if p)
        if text:
            update["raw_content"] = text
            update["content_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        return doc.model_copy(update=update) if update else doc

    def _get_text(self, url: str, accession_no: str, what: str) -> str | None:
        try:
            resp = self._client.get(url, headers={"User-Agent": self._user_agent})
        except Exception as exc:  # noqa: BLE001
            _log.warning("edgar %s fetch error: accession=%s exc=%s", what, accession_no, exc)
            return None
        if resp.status_code >= 400:
            _log.warning(
                "edgar %s fetch failed: accession=%s status=%d", what, accession_no, resp.status_code
            )
            return None
        return resp.text

    def _get_json(self, params: dict[str, str]) -> dict[str, Any]:
        headers = {"User-Agent": self._user_agent}
        last_resp: httpx.Response | None = None
        for _ in range(self._max_retries):
            last_resp = self._client.get(_EFTS_URL, params=params, headers=headers)
            if last_resp.status_code == 403:
                self._sleep(_BLOCK_BACKOFF)
                continue
            last_resp.raise_for_status()
            return cast(dict[str, Any], last_resp.json())
        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError(f"Exhausted retries for {_EFTS_URL}")
