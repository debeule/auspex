import io

from minio import Minio

from ..models import RawDocument


def minio_key(doc: RawDocument) -> str:
    ts = doc.retrieved_at.strftime("%Y%m%dT%H%M%S") + "Z"
    return f"raw/{doc.source_type}/{doc.external_id}/{ts}-{doc.content_sha256[:8]}.json"


class MinioArchive:
    def __init__(self, client: Minio, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(self, doc: RawDocument) -> str:
        key = minio_key(doc)
        data = doc.model_dump_json().encode()
        self._client.put_object(
            self._bucket,
            key,
            io.BytesIO(data),
            len(data),
            content_type="application/json",
        )
        return key
