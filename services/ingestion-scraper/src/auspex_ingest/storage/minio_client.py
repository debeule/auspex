import hashlib
import io
import json
from collections.abc import Iterator
from typing import Any

from minio import Minio
from minio.error import S3Error

from ..models import RawDocument


def minio_key(doc: RawDocument) -> str:
    ts = doc.retrieved_at.strftime("%Y%m%dT%H%M%S") + "Z"
    return f"raw/{doc.source_type}/{doc.external_id}/{ts}-{doc.content_sha256[:8]}.json"


class MinioArchive:
    def __init__(self, client: Minio, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(self, doc: RawDocument) -> tuple[str, bool]:
        key = minio_key(doc)

        is_new = True
        try:
            self._client.stat_object(self._bucket, key)
            is_new = False
        except S3Error as e:
            if e.code != "NoSuchKey":
                raise

        payload = {**json.loads(doc.model_dump_json()), "raw_content": doc.raw_content}
        data = json.dumps(payload).encode()
        self._client.put_object(
            self._bucket,
            key,
            io.BytesIO(data),
            len(data),
            content_type="application/json",
        )
        return key, is_new

    def get_canonical_marker(self, canonical_id: str) -> dict[str, Any] | None:
        key = f"dedup/canonical/{hashlib.sha256(canonical_id.encode()).hexdigest()}.json"
        try:
            response = self._client.get_object(self._bucket, key)
            return dict(json.loads(response.read()))
        except S3Error as e:
            if e.code in ("NoSuchKey", "NoSuchObject"):
                return None
            raise

    def put_canonical_marker(self, canonical_id: str, data: dict[str, Any]) -> None:
        key = f"dedup/canonical/{hashlib.sha256(canonical_id.encode()).hexdigest()}.json"
        payload = json.dumps(data).encode()
        self._client.put_object(
            self._bucket,
            key,
            io.BytesIO(payload),
            len(payload),
            content_type="application/json",
        )

    def list_raw_keys(self, source_type_prefix: str | None) -> Iterator[str]:
        prefix = f"raw/{source_type_prefix}/" if source_type_prefix else "raw/"
        for obj in self._client.list_objects(self._bucket, prefix=prefix, recursive=True):
            yield obj.object_name

    def get_raw(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        return response.read()
