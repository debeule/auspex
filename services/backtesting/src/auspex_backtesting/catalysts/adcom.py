"""FDA advisory committee meetings from Federal Register notices.

FDA must publish a meeting notice at least 15 days ahead (21 CFR 14.20). The notice's agenda
names the application, product and sponsor; the sponsor is matched to universe company names,
and a notice that matches none, or more than one, is kept with no CIK rather than guessed.
"""

import json
import logging
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from auspex_backtesting.catalysts.fetch import (
    DocumentCache,
    DocumentNotFoundError,
    HttpSource,
    SourceBlockedError,
)
from auspex_backtesting.catalysts.model import Catalyst, ExtractionResult
from auspex_backtesting.catalysts.phrases import (
    date_mentions,
    name_tokens,
    normalize_alias,
    paragraphs,
    product_aliases,
)
from auspex_backtesting.catalysts.press_releases import quarters
from auspex_backtesting.universe.model import UniverseMember

log = logging.getLogger("auspex_backtesting.catalysts")

_FIELDS = ("document_number", "title", "type", "publication_date", "dates", "html_url", "raw_text_url")
_PAGE_SIZE = 1000
_MEETING_NOTICE = re.compile(r"advisory\s+committee.*notice\s+of\s+meeting", re.IGNORECASE)
_WITHDRAWN = re.compile(r"cancel|postpone", re.IGNORECASE)
_AGENDA = re.compile(r"\bAgenda:\s*(.{1,2000}?)(?=\s+(?:Procedure|FDA intends|Persons attending)\b|$)")
_DATES_SECTION = re.compile(r"\bDATES:\s*(.{1,500})")
_SPONSOR = re.compile(
    r"\b(?:submitted|sponsored)\s+by\s+(.+?)(?:,\s+(?:for|to|in|and)\b|;|\.\s|\.?\s*$)"
)
_EASTERN = ZoneInfo("America/New_York")
# federalregister.gov puts each day's issue online at 06:00 Eastern.
_PUBLICATION_TIME = time(6, 0)
_MIN_NAME_LENGTH = 4


def _utc_today() -> date:
    return datetime.now(UTC).date()


class AdvisoryCommitteeNotices:
    def __init__(
        self,
        api_url: str,
        federal_register: HttpSource,
        cache: DocumentCache,
        *,
        today: Callable[[], date] = _utc_today,
    ) -> None:
        self._api_url = api_url
        self._fr = federal_register
        self._cache = cache
        self._today = today

    def collect(
        self, members: Sequence[UniverseMember], since: date, until: date
    ) -> ExtractionResult:
        """Meetings from FDA advisory committee notices published from `since` to `until`,
        each known at its publication date. Unmatched notices are rows with `cik` None, counted
        in `stats["unmatched"]`."""
        names = _UniverseNames(members)
        rows: list[Catalyst] = []
        stats: Counter[str] = Counter()
        try:
            for year, quarter, first, last in quarters(since, until):
                for notice in self._notices(year, quarter, first, last):
                    published = date.fromisoformat(notice["publication_date"])
                    if not since <= published <= until:
                        continue
                    title = str(notice.get("title") or "")
                    if not _MEETING_NOTICE.search(title):
                        continue
                    if _WITHDRAWN.search(title):
                        stats["withdrawals_skipped"] += 1
                        continue
                    row = self._row(notice, title, published, names, stats)
                    if row is not None:
                        rows.append(row)
        except SourceBlockedError as exc:
            log.warning("Federal Register refused %s: stopping this run", exc)
            stats["blocked"] = 1
        return ExtractionResult(tuple(rows), dict(stats))

    def _notices(self, year: int, quarter: int, first: date, last: date) -> list[dict[str, Any]]:
        notices: list[dict[str, Any]] = []
        page, pages = 1, 1
        while page <= pages:
            query = [
                ("conditions[agencies][]", "food-and-drug-administration"),
                ("conditions[type][]", "NOTICE"),
                ("conditions[publication_date][gte]", first.isoformat()),
                ("conditions[publication_date][lte]", last.isoformat()),
                ("order", "oldest"),
                ("per_page", str(_PAGE_SIZE)),
                ("page", str(page)),
                *(("fields[]", f) for f in _FIELDS),
            ]
            body = self._cache.fetch(
                f"federal_register/listing/{year}-q{quarter}/page-{page}.json",
                f"{self._api_url}?{urlencode(query)}",
                self._fr,
                keep=last < self._today(),
            )
            data = json.loads(body)
            notices.extend(data.get("results") or [])
            pages = int(data.get("total_pages") or 0)
            page += 1
        return notices

    def _row(
        self,
        notice: dict[str, Any],
        title: str,
        published: date,
        names: _UniverseNames,
        stats: Counter[str],
    ) -> Catalyst | None:
        number = str(notice["document_number"])
        try:
            text = self._cache.fetch(
                f"federal_register/{number}.txt", str(notice["raw_text_url"]), self._fr
            ).decode("utf-8", errors="replace")
        except DocumentNotFoundError as exc:
            log.info("no notice text: %s", exc)
            stats["missing_documents"] += 1
            return None
        flat = " ".join(paragraphs(text))
        meeting = _meeting_date(str(notice.get("dates") or ""), flat)
        if meeting is None:
            stats["without_meeting_date"] += 1
            return None
        agenda = m.group(1) if (m := _AGENDA.search(flat)) else flat
        sponsor = m.group(1).strip() if (m := _SPONSOR.search(agenda)) else ""
        cik = names.match(sponsor, agenda)
        stats["matched" if cik else "unmatched"] += 1
        committee = title.split(";")[0].strip()
        aliases = product_aliases(agenda) or (
            normalize_alias(committee) + meeting.isoformat().replace("-", ""),
        )
        return Catalyst(
            source="federal_register",
            catalyst_type="adcom",
            cik=cik,
            subject=aliases[0],
            aliases=aliases,
            precision="day",
            period_start=meeting,
            period_end=meeting,
            known_at=datetime.combine(published, _PUBLICATION_TIME, tzinfo=_EASTERN).astimezone(UTC),
            document_id=number,
            document_url=str(notice.get("html_url") or notice["raw_text_url"]),
            evidence=agenda[:1000],
            committee=committee,
            company_name=sponsor,
        )


def _meeting_date(dates_field: str, text: str) -> date | None:
    """The first day-precise date of the notice's DATES section."""
    sources = [dates_field]
    if (m := _DATES_SECTION.search(text)) is not None:
        sources.append(m.group(1))
    for source in sources:
        days = [d for d in date_mentions(source) if d.precision == "day"]
        if days:
            return days[0].period_start
    return None


class _UniverseNames:
    """Universe companies by name tokens, for matching a notice's sponsor."""

    def __init__(self, members: Sequence[UniverseMember]) -> None:
        self._by_tokens: dict[frozenset[str], set[str]] = defaultdict(set)
        self._by_phrase: dict[str, set[str]] = defaultdict(set)
        for m in members:
            if tokens := name_tokens(m.name):
                self._by_tokens[frozenset(tokens)].add(m.cik)
                self._by_phrase[" ".join(tokens)].add(m.cik)

    def match(self, sponsor: str, agenda: str) -> str | None:
        """The one universe CIK the sponsor names (same words in any order, as in SEC's
        "LILLY ELI & CO"), or, when the agenda names no sponsor, the one company whose whole
        name it contains. None when nothing or more than one company matches."""
        if sponsor:
            found = self._by_tokens.get(frozenset(name_tokens(sponsor)), set())
        else:
            text = f" {' '.join(name_tokens(agenda))} "
            found = {
                cik
                for phrase, ciks in self._by_phrase.items()
                # Short names ("ab") would match stray words.
                if len(phrase) >= _MIN_NAME_LENGTH and f" {phrase} " in text
                for cik in ciks
            }
        return next(iter(found)) if len(found) == 1 else None
