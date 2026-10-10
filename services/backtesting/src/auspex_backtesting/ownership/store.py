"""Ownership panels in MinIO, under `ownership/` in the prices bucket.

A panel file covers one data set or one day and is written once: the SEC data it came from
does not change, and a later correction arrives in a later file. Only reference tables that
are rebuilt whole (`shares_outstanding.parquet`, specialist classifications) are replaced.
"""

import io
import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error

from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET

PREFIX = "ownership/"
_META_KEY = b"auspex"


class PanelExistsError(Exception):
    """A panel file is written once; this key is already stored."""


class OwnershipStore:
    def __init__(self, minio_client: Minio, bucket: str = PRICES_BUCKET) -> None:
        self._minio = minio_client
        self._bucket = bucket

    def exists(self, key: str) -> bool:
        try:
            self._minio.stat_object(self._bucket, PREFIX + key)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise
        return True

    def write(self, key: str, frame: pd.DataFrame, meta: dict[str, object] | None = None) -> None:
        if self.exists(key):
            raise PanelExistsError(PREFIX + key)
        self.replace(key, frame, meta)

    def replace(self, key: str, frame: pd.DataFrame, meta: dict[str, object] | None = None) -> None:
        table = pa.Table.from_pandas(frame, preserve_index=False)
        schema_meta = dict(table.schema.metadata or {})
        schema_meta[_META_KEY] = json.dumps(meta or {}, sort_keys=True).encode()
        buf = io.BytesIO()
        pq.write_table(table.replace_schema_metadata(schema_meta), buf)
        content = buf.getvalue()
        self._minio.put_object(
            self._bucket, PREFIX + key, io.BytesIO(content), len(content),
            content_type="application/octet-stream",
        )

    def read(self, key: str) -> tuple[pd.DataFrame, dict[str, object]] | None:
        try:
            resp = self._minio.get_object(self._bucket, PREFIX + key)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise
        try:
            data = bytes(resp.read())
        finally:
            resp.close()
            resp.release_conn()
        table = pq.read_table(io.BytesIO(data))
        meta = json.loads((table.schema.metadata or {}).get(_META_KEY, b"{}"))
        return table.to_pandas(), meta

    def keys(self, prefix: str) -> list[str]:
        """Stored keys under `prefix` (relative to `ownership/`), sorted; not recursive."""
        objects = self._minio.list_objects(self._bucket, prefix=PREFIX + prefix)
        return sorted(
            name[len(PREFIX):]
            for o in objects
            if (name := o.object_name or "") and not name.endswith("/")
            and "/" not in name[len(PREFIX + prefix):]
        )

    def read_all(self, prefix: str, suffix: str = ".parquet") -> list[tuple[str, pd.DataFrame]]:
        result = []
        for key in self.keys(prefix):
            if not key.endswith(suffix):
                continue
            stored = self.read(key)
            if stored is not None:
                result.append((key, stored[0]))
        return result
