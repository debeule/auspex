"""PDUFA dates from 8-K press releases (Exhibit 99.1), found through EDGAR's quarterly full index.

The quarterly `master.idx` lists every filing with its company CIK, so one request per quarter
finds a universe company's 8-Ks. Each 8-K's filing index then gives its items, its acceptance
time and its Exhibit 99.1, selected as the scraper's EDGAR connector selects it.
"""

import logging
import re
from collections import Counter
from collections.abc import Callable, Collection, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from auspex_backtesting.catalysts.fetch import (
    DocumentCache,
    DocumentNotFoundError,
    HttpSource,
    SourceBlockedError,
)
from auspex_backtesting.catalysts.model import Catalyst, ExtractionResult
from auspex_backtesting.catalysts.phrases import pdufa_hits

log = logging.getLogger("auspex_backtesting.catalysts")

_FORMS = frozenset({"8-K", "8-K/A"})
# Regulation FD and other events: the items PDUFA announcements are filed under.
_PRESS_RELEASE_ITEMS = frozenset({"7.01", "8.01"})
_PRESS_RELEASE_EXHIBIT = re.compile(r"EX-99\.0?1", re.IGNORECASE)
_EDGAR_TZ = ZoneInfo("America/New_York")

_ACCEPTED = re.compile(
    r'<div class="infoHead">\s*Accepted\s*</div>\s*<div class="info">\s*([^<]+?)\s*</div>',
    re.IGNORECASE,
)
_ITEMS = re.compile(
    r'<div class="infoHead">\s*Items\s*</div>\s*<div class="info">(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
_ITEM_NUMBER = re.compile(r"Item\s+(\d+\.\d+)", re.IGNORECASE)
_FILE_TABLE = re.compile(r'<table[^>]*class="tableFile"[^>]*>(.*?)</table>', re.IGNORECASE | re.DOTALL)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_HREF = re.compile(r'href="([^"]+)"', re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class FilingIndex:
    accepted_at: datetime | None
    items: frozenset[str]
    documents: dict[str, str]

    def press_release_exhibit(self) -> str | None:
        return next(
            (url for kind, url in self.documents.items() if _PRESS_RELEASE_EXHIBIT.fullmatch(kind)),
            None,
        )


def parse_filing_index(html: str, base_url: str) -> FilingIndex:
    """Acceptance time (UTC), 8-K item numbers and document URLs by type from a `-index.htm`
    page. The first file table lists the filed documents: Seq, Description, Document, Type."""
    accepted_at = None
    if (m := _ACCEPTED.search(html)) is not None:
        try:
            accepted_at = (
                datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                .replace(tzinfo=_EDGAR_TZ)
                .astimezone(UTC)
            )
        except ValueError:
            accepted_at = None
    items = frozenset(_ITEM_NUMBER.findall(m.group(1))) if (m := _ITEMS.search(html)) else frozenset()
    documents: dict[str, str] = {}
    if (table := _FILE_TABLE.search(html)) is not None:
        for row in _ROW.findall(table.group(1)):
            cells = _CELL.findall(row)
            if len(cells) < 4 or (href := _HREF.search(cells[2])) is None:
                continue
            kind = _TAG.sub("", cells[3]).strip().upper()
            # Inline XBRL documents link through the viewer: /ix?doc=/Archives/...
            url = urljoin(base_url, href.group(1).removeprefix("/ix?doc="))
            if kind:
                documents.setdefault(kind, url)
    return FilingIndex(accepted_at, items, documents)


@dataclass(frozen=True)
class IndexEntry:
    cik: str
    form: str
    filed: date
    accession: str


def parse_master_index(text: str) -> Iterator[IndexEntry]:
    """Rows of a quarterly `master.idx` (`CIK|Company Name|Form Type|Date Filed|Filename`);
    the CIK is zero-padded to ten digits as the universe stores it."""
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) != 5 or not parts[0].strip().isdigit():
            continue
        cik, _, form, filed, filename = (p.strip() for p in parts)
        try:
            filed_on = date.fromisoformat(filed)
        except ValueError:
            continue
        accession = filename.rsplit("/", 1)[-1].removesuffix(".txt")
        yield IndexEntry(cik.zfill(10), form, filed_on, accession)


def quarters(since: date, until: date) -> Iterator[tuple[int, int, date, date]]:
    """(year, quarter, first day, last day) for every calendar quarter touching the range."""
    year, quarter = since.year, (since.month - 1) // 3 + 1
    while (year, quarter) <= (until.year, (until.month - 1) // 3 + 1):
        first = date(year, 3 * quarter - 2, 1)
        following = date(year + 1, 1, 1) if quarter == 4 else date(year, 3 * quarter + 1, 1)
        yield year, quarter, first, following - timedelta(days=1)
        year, quarter = (year + 1, 1) if quarter == 4 else (year, quarter + 1)


def _utc_today() -> date:
    return datetime.now(UTC).date()


class PressReleaseCatalystExtractor:
    def __init__(
        self,
        full_index_url: str,
        archives_url: str,
        sec: HttpSource,
        cache: DocumentCache,
        *,
        today: Callable[[], date] = _utc_today,
    ) -> None:
        """`sec` paces every request this extractor makes to SEC, index and exhibits alike."""
        self._full_index_url = full_index_url.rstrip("/")
        self._archives_url = archives_url.rstrip("/")
        self._sec = sec
        self._cache = cache
        self._today = today

    def collect(self, ciks: Collection[str], since: date, until: date) -> ExtractionResult:
        """PDUFA dates from the 8-Ks that companies in `ciks` filed from `since` to `until`.
        A refusal from SEC ends the run with what was read so far (`stats["blocked"]`); every
        document read is kept, so the next run starts where this one stopped."""
        wanted = {c.zfill(10) for c in ciks}
        rows: list[Catalyst] = []
        stats: Counter[str] = Counter()
        try:
            for year, quarter, _, last in quarters(since, until):
                try:
                    index = self._cache.fetch(
                        f"edgar/full-index/{year}-q{quarter}/master.idx",
                        f"{self._full_index_url}/{year}/QTR{quarter}/master.idx",
                        self._sec,
                        keep=last < self._today(),
                    )
                except DocumentNotFoundError as exc:
                    log.info("no full index: %s", exc)
                    stats["missing_documents"] += 1
                    continue
                for entry in parse_master_index(index.decode("latin-1")):
                    if entry.form in _FORMS and entry.cik in wanted and since <= entry.filed <= until:
                        stats["filings"] += 1
                        rows.extend(self._filing(entry, stats))
        except SourceBlockedError as exc:
            log.warning("SEC refused %s: stopping this run, no retry during a block", exc)
            stats["blocked"] = 1
        return ExtractionResult(tuple(rows), dict(stats))

    def _filing(self, entry: IndexEntry, stats: Counter[str]) -> list[Catalyst]:
        folder = f"{self._archives_url}/{int(entry.cik)}/{entry.accession.replace('-', '')}"
        try:
            page = self._cache.fetch(
                f"edgar/{entry.accession}/index.htm",
                f"{folder}/{entry.accession}-index.htm",
                self._sec,
            )
        except DocumentNotFoundError as exc:
            log.info("no filing index: %s", exc)
            stats["missing_documents"] += 1
            return []
        index = parse_filing_index(page.decode("utf-8", errors="replace"), self._archives_url + "/")
        if not index.items:
            stats["without_items"] += 1
            return []
        if not index.items & _PRESS_RELEASE_ITEMS:
            stats["other_items"] += 1
            return []
        exhibit_url = index.press_release_exhibit()
        if exhibit_url is None:
            stats["without_exhibit"] += 1
            return []
        if index.accepted_at is None:
            stats["without_acceptance_time"] += 1
            return []
        try:
            exhibit = self._cache.fetch(f"edgar/{entry.accession}/ex-99.1", exhibit_url, self._sec)
        except DocumentNotFoundError as exc:
            log.info("no exhibit: %s", exc)
            stats["missing_documents"] += 1
            return []
        stats["exhibits_read"] += 1
        rows = []
        for hit in pdufa_hits(exhibit.decode("utf-8", errors="replace")):
            stats[f"hits_{hit.when.precision}"] += 1
            rows.append(Catalyst(
                source="edgar",
                catalyst_type="pdufa",
                cik=entry.cik,
                subject=hit.aliases[0] if hit.aliases else "",
                aliases=hit.aliases,
                precision=hit.when.precision,
                period_start=hit.when.period_start,
                period_end=hit.when.period_end,
                known_at=index.accepted_at,
                document_id=entry.accession,
                document_url=exhibit_url,
                evidence=hit.sentence,
            ))
        return rows
