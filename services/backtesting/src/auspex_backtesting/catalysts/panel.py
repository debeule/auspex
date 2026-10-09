"""The point-in-time catalyst panel: Parquet in MinIO, one file per source and quarter of
disclosure, `catalysts/{source}/{yyyy}q{q}.parquet` in the prices bucket.

Rows are only ever added. A revised date (an extended PDUFA goal, a rescheduled meeting) is a new
row known at its own disclosure time, so a read as of an earlier moment never sees it.
"""

import io
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, astuple, fields
from datetime import UTC, date, datetime
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error

from auspex_backtesting.catalysts.model import Catalyst
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET
from auspex_backtesting.universe.model import UniverseMember

_PREFIX = "catalysts/"
_PARTITION = re.compile(r"catalysts/[a-z_]+/\d{4}q[1-4]\.parquet")
_SCHEMA = pa.schema([
    ("source", pa.string()),
    ("catalyst_type", pa.string()),
    ("cik", pa.string()),
    ("subject", pa.string()),
    ("aliases", pa.list_(pa.string())),
    ("precision", pa.string()),
    ("period_start", pa.date32()),
    ("period_end", pa.date32()),
    ("known_at", pa.timestamp("us", tz="UTC")),
    ("document_id", pa.string()),
    ("document_url", pa.string()),
    ("evidence", pa.string()),
    ("committee", pa.string()),
    ("company_name", pa.string()),
])


def partition_key(row: Catalyst) -> str:
    known = row.known_at.astimezone(UTC)
    return f"{_PREFIX}{row.source}/{known.year}q{(known.month - 1) // 3 + 1}.parquet"


class CatalystPanel:
    def __init__(self, minio_client: Minio, bucket: str = PRICES_BUCKET) -> None:
        self._minio = minio_client
        self._bucket = bucket
        self._rows: list[Catalyst] | None = None

    def append(self, rows: Iterable[Catalyst]) -> int:
        """Adds the rows not already stored; returns how many were added. Stored rows are
        never changed or removed, so appending the same extraction twice adds nothing."""
        by_key: dict[str, list[Catalyst]] = defaultdict(list)
        for row in rows:
            by_key[partition_key(row)].append(row)
        added = 0
        for key, new in by_key.items():
            stored = self._read(key)
            seen = {astuple(r) for r in stored}
            fresh = [r for r in dict.fromkeys(new) if astuple(r) not in seen]
            if fresh:
                self._write(key, stored + fresh)
                added += len(fresh)
        if added:
            self._rows = None
        return added

    def rows(self) -> list[Catalyst]:
        """Every stored row, in disclosure order."""
        if self._rows is None:
            keys = sorted(
                o.object_name
                for o in self._minio.list_objects(self._bucket, prefix=_PREFIX, recursive=True)
                if _PARTITION.fullmatch(o.object_name or "")
            )
            loaded = [r for k in keys for r in self._read(k)]
            self._rows = sorted(loaded, key=lambda r: r.known_at)
        return self._rows

    def as_of(self, cik: str, at: datetime) -> list[Catalyst]:
        """Upcoming catalysts for `cik` as known at `at`: for each catalyst, the latest row
        disclosed at or before `at`, kept while its period has not ended. Ordered by date."""
        today = _utc(at).date()
        return [r for r in self._effective(cik, at) if r.period_end >= today]

    def binaries_between(
        self, cik: str, start: date, end: date, as_of: datetime
    ) -> list[Catalyst]:
        """Catalysts for `cik`, as known at `as_of`, whose period overlaps `start`..`end`. An
        imprecise date ("Q3 2027") counts if any part of its period does."""
        return [
            r for r in self._effective(cik, as_of) if r.period_start <= end and r.period_end >= start
        ]

    def coverage(self, members: Sequence[UniverseMember]) -> dict[str, Any]:
        """Catalysts per year by type, the share of `members` with any catalyst, unmatched
        advisory committee notices and PDUFA phrase hits by precision."""
        rows = self.rows()
        matched = [r for r in rows if r.cik is not None]
        per_year: dict[int, Counter[str]] = defaultdict(Counter)
        for r in matched:
            per_year[r.period_start.year][r.catalyst_type] += 1
        member_ciks = {m.cik for m in members}
        with_catalysts = member_ciks & {r.cik for r in matched}
        return {
            "catalysts_per_year": {y: dict(c) for y, c in sorted(per_year.items())},
            "members": len(member_ciks),
            "members_with_catalysts": len(with_catalysts),
            "member_share_with_catalysts": (
                round(len(with_catalysts) / len(member_ciks), 4) if member_ciks else 0.0
            ),
            "unmatched_adcom_notices": sum(
                r.cik is None for r in rows if r.source == "federal_register"
            ),
            "pdufa_hits_by_precision": dict(
                Counter(r.precision for r in rows if r.catalyst_type == "pdufa")
            ),
        }

    def _effective(self, cik: str, at: datetime) -> list[Catalyst]:
        moment = _utc(at)
        effective: list[Catalyst] = []
        for row in self.rows():
            if row.known_at > moment:
                break
            if row.cik != cik:
                continue
            effective = [e for e in effective if not _same_catalyst(e, row)]
            effective.append(row)
        return sorted(effective, key=lambda r: (r.period_start, r.catalyst_type))

    def _read(self, key: str) -> list[Catalyst]:
        try:
            resp = self._minio.get_object(self._bucket, key)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return []
            raise
        try:
            data = bytes(resp.read())
        finally:
            resp.close()
            resp.release_conn()
        names = {f.name for f in fields(Catalyst)}
        return [
            Catalyst(**{
                **{k: v for k, v in row.items() if k in names},
                "aliases": tuple(row["aliases"] or ()),
                "known_at": row["known_at"].astimezone(UTC),
            })
            for row in pq.read_table(io.BytesIO(data)).to_pylist()
        ]

    def _write(self, key: str, rows: list[Catalyst]) -> None:
        records = [{**asdict(r), "aliases": list(r.aliases)} for r in rows]
        buf = io.BytesIO()
        pq.write_table(pa.Table.from_pylist(records, schema=_SCHEMA), buf)
        data = buf.getvalue()
        self._minio.put_object(
            self._bucket, key, io.BytesIO(data), len(data), content_type="application/octet-stream"
        )


def _same_catalyst(a: Catalyst, b: Catalyst) -> bool:
    """Rows of one company describe the same catalyst when they share an alias; rows that name
    no product only match each other."""
    if a.catalyst_type != b.catalyst_type:
        return False
    if a.aliases and b.aliases:
        return bool(set(a.aliases) & set(b.aliases))
    return not a.aliases and not b.aliases


def _utc(at: datetime) -> datetime:
    if at.tzinfo is None:
        raise ValueError("as-of times must be timezone-aware")
    return at.astimezone(UTC)
