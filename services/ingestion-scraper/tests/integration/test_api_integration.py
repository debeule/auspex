"""Integration test — ingest round-trip via the Flask API with real MinIO + Kafka containers."""

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from confluent_kafka import Consumer
from confluent_kafka import Producer as ConfluentProducer
from confluent_kafka.admin import AdminClient, NewTopic
from minio import Minio
from testcontainers.community.kafka import KafkaContainer
from testcontainers.core.container import DockerContainer

from auspex_ingest.api import create_app
from auspex_ingest.identity import compute_event_id, compute_extraction_id
from auspex_ingest.messaging import KafkaProducerClient
from auspex_ingest.models import RawDocument, ResearchSignalEvent
from auspex_ingest.normalizer import IdentityNormalizer
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter
from auspex_ingest.sources import SourceEntry, SourcesConfig
from auspex_ingest.storage.minio_client import MinioArchive

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

_MINIO_IMAGE = "quay.io/minio/minio:RELEASE.2022-12-02T19-19-22Z"
_BUCKET = "auspex-test-api"
_RAW_TOPIC = "auspex.raw.ingested"
_SIG_TOPIC = "auspex.signals.extracted"
_T0 = datetime(2023, 1, 10, 12, 0, 0, tzinfo=UTC)


def _make_signal(external_id: str) -> ResearchSignalEvent:
    event_id = compute_event_id(None, "biorxiv", external_id)
    extraction_id = compute_extraction_id(event_id, "1.0", "v1", "v1", "gpt-4o")
    content = f"gene therapy {external_id}"
    sha8 = hashlib.sha256(content.encode()).hexdigest()[:8]
    return ResearchSignalEvent(
        schema_version="1.0",
        event_id=event_id,
        extraction_id=extraction_id,
        external_id=external_id,
        canonical_id=None,
        raw_object_key=f"raw/biorxiv/{external_id}/20230110T120000Z-{sha8}.json",
        source_type="biorxiv",
        source_url=f"https://biorxiv.org/{external_id}",
        published_date=_T0,
        published_date_field="published_date",
        ingested_at=_T0,
        title="Gene therapy progress",
        raw_text_snippet="significant improvement in gene editing",
        gene_targets=["BRCA1"],
        mechanisms=["inhibition"],
        companies_mentioned=["BEAM"],
        summary="Gene therapy progress",
        directionality="positive",
        confidence_score=0.9,
        prompt_version="v1",
        prefilter_version="v1",
        extraction_model="gpt-4o",
    )


def _drain(bootstrap: str, topic: str, timeout_s: float = 15.0) -> list:
    c = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": f"test-drain-{uuid4()}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    c.subscribe([topic])
    msgs = []
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        msg = c.poll(0.5)
        if msg and not msg.error():
            msgs.append(json.loads(msg.value().decode()))
            break
    c.close()
    return msgs


@pytest.mark.integration
def test_ingest_round_trip_publishes_signal_to_kafka():
    minio_container = (
        DockerContainer(_MINIO_IMAGE)
        .with_exposed_ports(9000)
        .with_env("MINIO_ROOT_USER", "minioadmin")
        .with_env("MINIO_ROOT_PASSWORD", "minioadmin")
        .with_command("server /data --address :9000")
    )

    with minio_container as minio_ctr, KafkaContainer().with_kraft() as kafka:
        for _ in range(30):
            try:
                minio_port = minio_ctr.get_exposed_port(9000)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)

        minio_host = minio_ctr.get_container_host_ip()
        minio_client = Minio(
            f"{minio_host}:{minio_port}",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False,
        )
        for _ in range(30):
            try:
                minio_client.list_buckets()
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        if not minio_client.bucket_exists(_BUCKET):
            minio_client.make_bucket(_BUCKET)

        bootstrap = kafka.get_bootstrap_server()
        admin = AdminClient({"bootstrap.servers": bootstrap})
        admin.create_topics([
            NewTopic(_RAW_TOPIC, num_partitions=1, replication_factor=1),
            NewTopic(_SIG_TOPIC, num_partitions=1, replication_factor=1),
        ])

        archive = MinioArchive(client=minio_client, bucket=_BUCKET)
        kafka_prod = KafkaProducerClient(
            ConfluentProducer({"bootstrap.servers": bootstrap}),
            raw_topic=_RAW_TOPIC,
            signals_topic=_SIG_TOPIC,
        )

        external_id = "biorxiv-api-test"
        stub_doc = RawDocument(
            schema_version="1.0",
            external_id=external_id,
            source_type="biorxiv",
            source_url=f"https://biorxiv.org/{external_id}",
            published_date=_T0,
            raw_content="gene therapy content",
            content_sha256=hashlib.sha256(b"gene therapy content").hexdigest(),
            retrieved_at=_T0,
        )

        mock_connector = MagicMock()
        mock_connector.fetch_since.return_value = [stub_doc]
        mock_connector.provides_canonical_id = False

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = _make_signal(external_id)

        pipeline = IngestionPipeline(
            connector=mock_connector,
            archive=archive,
            extractor=mock_extractor,
            producer=kafka_prod,
            prefilter=Prefilter.from_vocab({"gene therapy"}),
            normalizer=IdentityNormalizer(),
            now=lambda: datetime.now(UTC),
        )

        sources_config = SourcesConfig(sources=[
            SourceEntry(
                source_type="biorxiv",
                schedule="@daily",
                rate_limit_rps=3.0,
                initial_lookback=7,
                max_documents_per_run=100,
                prefilter_vocabulary=["gene therapy"],
                source_config={},
            )
        ])

        app = create_app(
            pipeline_for_source=lambda _st: pipeline,
            sources_config=sources_config,
        )
        flask_client = app.test_client()

        resp = flask_client.post("/ingest/biorxiv", json={"cursor": "2023-01-01T00:00:00+00:00"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["published"] >= 1

        msgs = _drain(bootstrap, _SIG_TOPIC)
        assert msgs, "No message appeared on auspex.signals.extracted"
        assert "event_id" in msgs[0]
