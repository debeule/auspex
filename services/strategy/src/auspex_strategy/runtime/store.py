from __future__ import annotations

import io
from typing import Protocol

from minio import Minio
from minio.error import S3Error

# Runtime state (virtual books, pauses, latency, offsets) lives here, not in Postgres: core-hub is
# the sole writer to the application database.
STRATEGY_BUCKET = "auspex-strategy"


class ObjectStore(Protocol):
    def get(self, key: str) -> bytes | None: ...

    def put(self, key: str, data: bytes) -> None: ...


def append_line(store: ObjectStore, key: str, line: str) -> None:
    """Append one line to a JSONL object. The runtime is the only writer of its keys, so a
    read-then-write is not racing anyone."""
    existing = store.get(key) or b""
    store.put(key, existing + line.encode("utf-8") + b"\n")


class MinioObjectStore:
    def __init__(self, minio: Minio, bucket: str = STRATEGY_BUCKET) -> None:
        self._minio = minio
        self._bucket = bucket

    def get(self, key: str) -> bytes | None:
        try:
            response = self._minio.get_object(self._bucket, key)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def put(self, key: str, data: bytes) -> None:
        self._minio.put_object(self._bucket, key, io.BytesIO(data), length=len(data))
