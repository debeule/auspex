import hashlib
import os
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import pytest
from minio import Minio
from testcontainers.core.container import DockerContainer

from auspex_ingest.identity import compute_event_id, compute_extraction_id
from auspex_ingest.models import RawDocument, ResearchSignalEvent
from auspex_ingest.reextract import ReextractionRunner
from auspex_ingest.storage.minio_client import MinioArchive

_UTC = UTC
_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=_UTC)
_BUCKET = "auspex-test"
_LOCALSTACK_IMAGE = "localstack/localstack:4.9.2"
_SCHEMA_VERSION = "1.0"
_PROMPT_VERSION = "v1"
_PREFILTER_VERSION = "v1"
_MODEL = "gpt-4o"
_CONTENT = "CRISPR base editing of BCL11A corrects sickle cell anemia"


@pytest.fixture(scope="module")
def minio_client():
    container = (
        DockerContainer(_LOCALSTACK_IMAGE)
        .with_exposed_ports(4566)
        .with_env("SERVICES", "s3")
    )
    with container:
        for _ in range(30):
            try:
                port = container.get_exposed_port(4566)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            pytest.fail("LocalStack port never became available")

        host = container.get_container_host_ip()
        client = Minio(
            f"{host}:{port}",
            access_key="test",
            secret_key="test",
            secure=False,
        )

        for _ in range(30):
            try:
                client.list_buckets()
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            pytest.fail("LocalStack never became ready")

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


def _make_doc(
    *,
    external_id: str = "ext-001",
    source_type: str = "biorxiv",
    canonical_id: str | None = "doi:10.1101/2024.06.01.001",
) -> RawDocument:
    sha = hashlib.sha256(_CONTENT.encode()).hexdigest()
    return RawDocument(
        schema_version=_SCHEMA_VERSION,
        external_id=external_id,
        canonical_id=canonical_id,
        source_type=source_type,
        source_url="https://example.com/doc/1",
        published_date=_T0,
        raw_content=_CONTENT,
        content_sha256=sha,
        retrieved_at=_T0,
    )


def _stub_extractor(doc: RawDocument, prefilter_version: str, raw_object_key: str) -> ResearchSignalEvent:
    event_id = compute_event_id(doc.canonical_id, doc.source_type, doc.external_id)
    extraction_id = compute_extraction_id(
        event_id, _SCHEMA_VERSION, _PROMPT_VERSION, prefilter_version, _MODEL
    )
    return ResearchSignalEvent(
        schema_version=_SCHEMA_VERSION,
        event_id=event_id,
        extraction_id=extraction_id,
        external_id=doc.external_id,
        canonical_id=doc.canonical_id,
        raw_object_key=raw_object_key,
        source_type=doc.source_type,
        source_url=doc.source_url,
        published_date=doc.published_date,
        published_date_field="published_date",
        ingested_at=_T0,
        title="CRISPR BCL11A editing",
        raw_text_snippet="BCL11A base editing results...",
        gene_targets=["BCL11A"],
        mechanisms=["base editing"],
        companies_mentioned=[],
        summary="BCL11A editing for sickle cell anemia",
        directionality="positive",
        confidence_score=0.9,
        prompt_version=_PROMPT_VERSION,
        prefilter_version=prefilter_version,
        extraction_model=_MODEL,
    )


@pytest.mark.integration
def test_reextraction_round_trip_publishes_valid_signal(archive: MinioArchive) -> None:
    doc = _make_doc()
    archive.put(doc)

    extractor = MagicMock()
    extractor.extract.side_effect = _stub_extractor

    producer = MagicMock()

    runner = ReextractionRunner(archive=archive, extractor=extractor, producer=producer)
    result = runner.run(
        source_type="biorxiv",
        prompt_version=_PROMPT_VERSION,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    assert result["scanned"] == 1
    assert result["published"] == 1
    assert result["failed"] == 0

    producer.publish_signal.assert_called_once()
    published: ResearchSignalEvent = producer.publish_signal.call_args[0][0]

    expected_event_id = compute_event_id(doc.canonical_id, doc.source_type, doc.external_id)
    assert published.event_id == expected_event_id
    assert isinstance(published, ResearchSignalEvent)
    producer.flush.assert_called_once()
