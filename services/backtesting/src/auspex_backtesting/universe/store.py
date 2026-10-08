"""Universe snapshots in MinIO, under `universe/{rules_version}/` in the prices bucket.

`{yyyy-mm}.parquet` holds a month's members and is written once. `rules.yaml` is the rules file
the version was first built with; a different file under the same version is refused, so an
edited rule can never mix into snapshots built under the old one.
"""

import hashlib
import io
from dataclasses import asdict, fields
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error

from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET
from auspex_backtesting.universe.model import UniverseMember, UniverseSnapshot
from auspex_backtesting.universe.rules import UniverseRules, parse_rules

_SCHEMA = pa.schema([
    ("cik", pa.string()),
    ("ticker", pa.string()),
    ("ticker_source", pa.string()),
    ("name", pa.string()),
    ("sic", pa.string()),
    ("exchange", pa.string()),
    ("market_cap_usd", pa.float64()),
    ("median_dollar_volume_20d", pa.float64()),
    ("entered_on", pa.date32()),
    ("exited_on", pa.date32()),
    ("exit_reason", pa.string()),
    ("price_coverage", pa.string()),
    ("coverage_note", pa.string()),
])


class SnapshotExistsError(Exception):
    """A snapshot for this rules version and month is already stored."""


class RulesVersionError(Exception):
    """The rules file differs from the one its version was first built with."""


class UniverseStore:
    def __init__(self, minio_client: Minio, bucket: str = PRICES_BUCKET) -> None:
        self._minio = minio_client
        self._bucket = bucket

    def lock_rules(self, path: Path) -> UniverseRules:
        """Parses the rules file and pins it to its version on first use."""
        content = path.read_bytes()
        rules = parse_rules(content.decode("utf-8"))
        key = f"{_prefix(rules.version)}rules.yaml"
        stored = self._get(key)
        if stored is None:
            self._put(key, content, "application/yaml")
        elif _sha256(stored) != _sha256(content):
            raise RulesVersionError(
                f"{path} changed but is still version {rules.version}; snapshots under that "
                "version were built with the earlier rules. Bump `version` to build new ones."
            )
        return rules

    def exists(self, rules_version: int, month: str) -> bool:
        try:
            self._minio.stat_object(self._bucket, _snapshot_key(rules_version, month))
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise
        return True

    def write(self, snapshot: UniverseSnapshot) -> None:
        if self.exists(snapshot.rules_version, snapshot.month):
            raise SnapshotExistsError(
                f"universe {snapshot.month} under rules version {snapshot.rules_version}"
            )
        table = pa.Table.from_pylist(
            [asdict(m) for m in snapshot.members],
            schema=_SCHEMA.with_metadata({
                "rules_version": str(snapshot.rules_version),
                "month": snapshot.month,
                "rebalance_date": snapshot.rebalance_date.isoformat(),
            }),
        )
        buf = io.BytesIO()
        pq.write_table(table, buf)
        self._put(
            _snapshot_key(snapshot.rules_version, snapshot.month),
            buf.getvalue(),
            "application/octet-stream",
        )

    def read(self, rules_version: int, month: str) -> UniverseSnapshot | None:
        data = self._get(_snapshot_key(rules_version, month))
        if data is None:
            return None
        table = pq.read_table(io.BytesIO(data))
        meta = {k.decode(): v.decode() for k, v in (table.schema.metadata or {}).items()}
        names = {f.name for f in fields(UniverseMember)}
        members = tuple(
            UniverseMember(**{k: v for k, v in row.items() if k in names})
            for row in table.to_pylist()
        )
        return UniverseSnapshot(
            int(meta["rules_version"]),
            meta["month"],
            date.fromisoformat(meta["rebalance_date"]),
            members,
        )

    def put_report(self, rules_version: int, name: str, content: bytes, content_type: str) -> None:
        """Writes a derived report (coverage, backfill scope) next to the snapshots; reports
        are regenerated on every build and may be replaced."""
        self._put(f"{_prefix(rules_version)}{name}", content, content_type)

    def read_report(self, rules_version: int, name: str) -> bytes | None:
        return self._get(f"{_prefix(rules_version)}{name}")

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

    def _put(self, key: str, content: bytes, content_type: str) -> None:
        self._minio.put_object(
            self._bucket, key, io.BytesIO(content), len(content), content_type=content_type
        )


def _prefix(rules_version: int) -> str:
    return f"universe/{rules_version}/"


def _snapshot_key(rules_version: int, month: str) -> str:
    return f"{_prefix(rules_version)}{month}.parquet"


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
