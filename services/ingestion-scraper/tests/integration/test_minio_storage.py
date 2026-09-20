"""Integration tests — MinioArchive refetch behaviour against a real MinIO container."""

import hashlib
import os
import time
from datetime import UTC, datetime

import pytest
from minio import Minio
from testcontainers.core.container import DockerContainer

from auspex_ingest.models import RawDocument
from auspex_ingest.storage.minio_client import MinioArchive

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


_UTC = UTC
_T1 = datetime(2024, 6, 15, 10, 0, 0, tzinfo=_UTC)
_T2 = datetime(2024, 6, 15, 10, 0, 1, tzinfo=_UTC)
_BUCKET = "auspex-test"
_MINIO_IMAGE = "quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"


@pytest.fixture(scope="module")
def minio_client():
    container = (
        DockerContainer(_MINIO_IMAGE)
        .with_exposed_ports(9000)
        .with_env("MINIO_ROOT_USER", "minioadmin")
        .with_env("MINIO_ROOT_PASSWORD", "minioadmin")
        .with_command("server /data --address :9000")
    )
    with container:
        # Poll until Docker has finished binding the port
        for _ in range(30):
            try:
                port = container.get_exposed_port(9000)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            pytest.fail("MinIO port never became available")

        host = container.get_container_host_ip()
        client = Minio(
            f"{host}:{port}",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False,
        )

        # Poll until MinIO is accepting requests
        for _ in range(30):
            try:
                client.list_buckets()
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            pytest.fail("MinIO never became ready")

        client.make_bucket(_BUCKET)
        yield client


@pytest.fixture(autouse=True)
def _clean_bucket(minio_client: Minio):
    yield
    for obj in minio_client.list_objects(_BUCKET, recursive=True):
        minio_client.remove_object(_BUCKET, obj.object_name)


@pytest.fixture
def archive(minio_client: Minio) -> MinioArchive:
    return MinioArchive(client=minio_client, bucket=_BUCKET)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _make_doc(content: str, retrieved_at: datetime, **overrides) -> RawDocument:
    defaults: dict = {
        "schema_version": "1.0",
        "external_id": "test-ext-001",
        "source_type": "biorxiv",
        "source_url": "https://example.com/doc/1",
        "published_date": _T1,
        "raw_content": content,
        "content_sha256": _sha256(content),
        "retrieved_at": retrieved_at,
    }
    defaults.update(overrides)
    return RawDocument(**defaults)



@pytest.mark.integration
def test_refetch_with_changed_content_creates_second_object(archive: MinioArchive, minio_client: Minio):
    doc1 = _make_doc("version one", _T1)
    doc2 = _make_doc("version two", _T2)

    key1, _ = archive.put(doc1)
    key2, _ = archive.put(doc2)

    assert key1 != key2
    minio_client.stat_object(_BUCKET, key1)
    minio_client.stat_object(_BUCKET, key2)


@pytest.mark.integration
def test_same_second_refetch_of_identical_content_is_a_noop_not_an_error(archive: MinioArchive, minio_client: Minio):
    doc = _make_doc("same content", _T1)

    key1, _ = archive.put(doc)
    key2, _ = archive.put(doc)

    assert key1 == key2
    minio_client.stat_object(_BUCKET, key1)


@pytest.mark.integration
def test_same_second_refetch_of_different_content_creates_a_distinct_key(archive: MinioArchive):
    doc1 = _make_doc("content alpha", _T1)
    doc2 = _make_doc("content beta", _T1)  # same second, different content → different sha256

    key1, _ = archive.put(doc1)
    key2, _ = archive.put(doc2)

    assert key1 != key2
