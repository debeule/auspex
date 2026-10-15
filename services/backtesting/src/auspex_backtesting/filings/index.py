"""10-K and 10-Q filings per calendar quarter, from EDGAR's quarterly full index."""

import io
import json
from collections.abc import Callable
from datetime import UTC, date, datetime

from minio import Minio
from minio.error import S3Error

from auspex_backtesting.catalysts.fetch import DocumentCache, DocumentNotFoundError, HttpSource
from auspex_backtesting.catalysts.press_releases import IndexEntry, parse_master_index, quarters
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET

ANNUAL_AND_QUARTERLY_FORMS = frozenset(
    f + suffix for f in ("10-K", "10-K405", "10-KT", "10-Q") for suffix in ("", "/A")
)


def _utc_today() -> date:
    return datetime.now(UTC).date()


class FilingIndex:
    """Every 10-K, 10-K405, 10-KT and 10-Q filing of a quarter, amendments included, from any
    filer. A finished quarter's rows are stored once under `filings/index/` in the prices
    bucket; the quarter in progress is read again each time, since its index still grows."""

    def __init__(
        self,
        minio_client: Minio,
        full_index_url: str,
        sec: HttpSource,
        cache: DocumentCache,
        *,
        bucket: str = PRICES_BUCKET,
        today: Callable[[], date] = _utc_today,
    ) -> None:
        """`cache` holds any quarterly index another panel already kept, so it is not read
        from SEC twice; this index keeps only its own rows, never the raw file."""
        self._minio = minio_client
        self._full_index_url = full_index_url.rstrip("/")
        self._sec = sec
        self._cache = cache
        self._bucket = bucket
        self._today = today

    def quarter(self, year: int, quarter: int) -> list[IndexEntry]:
        key = f"filings/index/{year}-q{quarter}.json"
        stored = self._get(key)
        if stored is not None:
            return [_entry(row) for row in json.loads(stored)]
        try:
            raw = self._cache.fetch(
                f"edgar/full-index/{year}-q{quarter}/master.idx",
                f"{self._full_index_url}/{year}/QTR{quarter}/master.idx",
                self._sec,
                keep=False,
            )
        except DocumentNotFoundError:
            return []
        rows = sorted(
            (e for e in parse_master_index(raw.decode("latin-1"))
             if e.form in ANNUAL_AND_QUARTERLY_FORMS),
            key=lambda e: (e.filed, e.cik, e.accession),
        )
        _, _, _, last = next(quarters(date(year, 3 * quarter - 2, 1), date(year, 3 * quarter, 1)))
        if last < self._today():
            data = json.dumps([_row(e) for e in rows]).encode()
            self._minio.put_object(
                self._bucket, key, io.BytesIO(data), len(data), content_type="application/json"
            )
        return rows

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


def _row(e: IndexEntry) -> dict[str, str]:
    return {"cik": e.cik, "form": e.form, "filed": e.filed.isoformat(), "accession": e.accession}


def _entry(row: dict[str, str]) -> IndexEntry:
    return IndexEntry(row["cik"], row["form"], date.fromisoformat(row["filed"]), row["accession"])
