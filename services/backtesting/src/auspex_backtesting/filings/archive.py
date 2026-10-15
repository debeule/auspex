"""Item 1A of each filing, cut once and kept under `filings/item1a/` in the prices bucket.

Each filing takes two requests, its `-index.htm` page (acceptance time, period of report and
the primary document by type) and the primary document; neither is kept, only the section.
A filing whose section cannot be cut is kept too, with the reason, so it is not fetched again.
"""

import gzip
import io
import json
import re
from datetime import date, datetime
from typing import Any

from minio import Minio
from minio.error import S3Error

from auspex_backtesting.catalysts.fetch import DocumentNotFoundError, HttpSource
from auspex_backtesting.catalysts.press_releases import IndexEntry, parse_filing_index
from auspex_backtesting.filings.model import ArchivedSection
from auspex_backtesting.filings.sections import cut_item_1a, filing_to_text
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET

PREFIX = "filings/item1a/"
_PERIOD = re.compile(
    r'<div class="infoHead">\s*Period of Report\s*</div>\s*<div class="info">\s*([^<]+?)\s*</div>',
    re.IGNORECASE,
)


class FilingSectionArchive:
    def __init__(
        self, minio_client: Minio, archives_url: str, sec: HttpSource, bucket: str = PRICES_BUCKET
    ) -> None:
        self._minio = minio_client
        self._archives_url = archives_url.rstrip("/")
        self._sec = sec
        self._bucket = bucket

    def get(self, entry: IndexEntry) -> ArchivedSection:
        """The archived section of `entry`, fetched and cut first if it is not archived yet.
        Raises `SourceBlockedError` when SEC refuses a request; nothing is kept for that
        filing."""
        key = f"{PREFIX}{entry.cik}/{entry.accession}.json.gz"
        stored = self._get(key)
        if stored is not None:
            return _decode(stored)
        section = self._fetch(entry)
        data = gzip.compress(json.dumps(_encode(section)).encode(), mtime=0)
        self._minio.put_object(
            self._bucket, key, io.BytesIO(data), len(data), content_type="application/gzip"
        )
        return section

    def _fetch(self, entry: IndexEntry) -> ArchivedSection:
        def missing(reason: str, **known: Any) -> ArchivedSection:
            return ArchivedSection(
                entry.cik, entry.accession, entry.form, entry.filed,
                known.get("period"), known.get("accepted_at"), "section_missing", reason, "",
            )

        folder = f"{self._archives_url}/{int(entry.cik)}/{entry.accession.replace('-', '')}"
        try:
            page = self._sec.get(f"{folder}/{entry.accession}-index.htm").decode(
                "utf-8", errors="replace"
            )
        except DocumentNotFoundError:
            return missing("filing_index_not_found")
        index = parse_filing_index(page, self._archives_url + "/")
        period = _period(page)
        accepted_at = index.accepted_at
        if accepted_at is None:
            return missing("no_acceptance_time", period=period)
        if period is None:
            return missing("no_period_of_report", accepted_at=accepted_at)
        url = index.documents.get(entry.form)
        if url is None:
            return missing("no_primary_document", period=period, accepted_at=accepted_at)
        try:
            document = self._sec.get(url).decode("utf-8", errors="replace")
        except DocumentNotFoundError:
            return missing("primary_document_not_found", period=period, accepted_at=accepted_at)
        cut = cut_item_1a(filing_to_text(document), entry.form)
        return ArchivedSection(
            entry.cik, entry.accession, entry.form, entry.filed, period, accepted_at,
            cut.status, cut.reason, cut.text,
        )

    def _get(self, key: str) -> bytes | None:
        try:
            resp = self._minio.get_object(self._bucket, key)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise
        try:
            return bytes(resp.read())
        finally:
            resp.close()
            resp.release_conn()


def _period(page: str) -> date | None:
    if (m := _PERIOD.search(page)) is None:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _encode(s: ArchivedSection) -> dict[str, Any]:
    return {
        "cik": s.cik,
        "accession": s.accession,
        "form": s.form,
        "filed": s.filed.isoformat(),
        "period_of_report": s.period_of_report.isoformat() if s.period_of_report else None,
        "accepted_at": s.accepted_at.isoformat() if s.accepted_at else None,
        "status": s.status,
        "reason": s.reason,
        "text": s.text,
    }


def _decode(data: bytes) -> ArchivedSection:
    raw = json.loads(gzip.decompress(data))
    return ArchivedSection(
        cik=raw["cik"],
        accession=raw["accession"],
        form=raw["form"],
        filed=date.fromisoformat(raw["filed"]),
        period_of_report=(
            date.fromisoformat(raw["period_of_report"]) if raw["period_of_report"] else None
        ),
        accepted_at=datetime.fromisoformat(raw["accepted_at"]) if raw["accepted_at"] else None,
        status=raw["status"],
        reason=raw["reason"],
        text=raw["text"],
    )
