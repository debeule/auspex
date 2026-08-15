import io
import json

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
