import hashlib
import os
import time
from datetime import UTC, datetime

import pytest
from confluent_kafka import Consumer, KafkaError
from confluent_kafka import Producer as ConfluentProducer
from confluent_kafka.admin import AdminClient, NewTopic
from testcontainers.community.kafka import KafkaContainer

from auspex_ingest.connectors.mock import MockConnector
from auspex_ingest.identity import compute_event_id, compute_extraction_id
from auspex_ingest.messaging import KafkaProducerClient
from auspex_ingest.models import RawDocument, ResearchSignalEvent
from auspex_ingest.normalizer import IdentityNormalizer
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter
from auspex_ingest.storage.minio_client import minio_key

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

_KAFKA_IMAGE = "confluentinc/cp-kafka:7.6.0"
_UTC = UTC
_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=_UTC)
_SCHEMA = "1.0"
_PROMPT = "v1"
_PREFILTER_VER = "v1"
_MODEL = "gpt-4o"
_RAW_TOPIC = "auspex.raw.ingested"
_SIG_TOPIC = "auspex.signals.extracted"


def _make_signal(external_id: str, source_type: str = "mock") -> ResearchSignalEvent:
    event_id = compute_event_id(None, source_type, external_id)
    extraction_id = compute_extraction_id(event_id, _SCHEMA, _PROMPT, _PREFILTER_VER, _MODEL)
    content = f"CRISPR base editing of BCL11A for {external_id}"
    sha8 = hashlib.sha256(content.encode()).hexdigest()[:8]
    return ResearchSignalEvent(
        schema_version=_SCHEMA,
        event_id=event_id,
        extraction_id=extraction_id,
        external_id=external_id,
        raw_object_key=f"raw/{source_type}/{external_id}/20240615T120000Z-{sha8}.json",
        source_type=source_type,
        source_url=f"https://mock.example.com/{external_id}",
        published_date=_T0,
        published_date_field="date",
        ingested_at=_T0,
        title=f"CRISPR BCL11A editing {external_id}",
        raw_text_snippet="BCL11A base editing results",
        gene_targets=["BCL11A"],
        mechanisms=["base editing"],
        companies_mentioned=["Beam Therapeutics"],
        summary="BCL11A editing for sickle cell",
        directionality="positive",
        confidence_score=0.85,
        prompt_version=_PROMPT,
        prefilter_version=_PREFILTER_VER,
        extraction_model=_MODEL,
    )


class _FakeArchive:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def put(self, doc: RawDocument) -> tuple[str, bool]:
        key = minio_key(doc)
        is_new = key not in self._seen
        self._seen.add(key)
        return key, is_new


class _FixedExtractor:
    def extract(
        self, doc: RawDocument, prefilter_version: str, raw_object_key: str
    ) -> ResearchSignalEvent | None:
        return _make_signal(doc.external_id, doc.source_type)


def _drain(bootstrap: str, topic: str, expected: int, timeout_s: float = 15.0) -> list:
    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": f"test-drain-{topic}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([topic])
    messages = []
    deadline = time.monotonic() + timeout_s
    while len(messages) < expected and time.monotonic() < deadline:
        msg = consumer.poll(0.5)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            raise RuntimeError(f"Kafka consumer error: {msg.error()}")
        messages.append(msg)
    consumer.close()
    return messages



@pytest.mark.integration
def test_pipeline_publishes_correct_message_count_to_each_topic():
    with KafkaContainer(_KAFKA_IMAGE).with_kraft() as kafka:
        bootstrap = kafka.get_bootstrap_server()

        admin = AdminClient({"bootstrap.servers": bootstrap})
        fs = admin.create_topics([
            NewTopic(_RAW_TOPIC, num_partitions=3, replication_factor=1),
            NewTopic(_SIG_TOPIC, num_partitions=3, replication_factor=1),
        ])
        for future in fs.values():
            future.result()

        time.sleep(1)

        producer = KafkaProducerClient(
            ConfluentProducer({"bootstrap.servers": bootstrap}),
            raw_topic=_RAW_TOPIC,
            signals_topic=_SIG_TOPIC,
        )

        pf = Prefilter.from_vocab(
            {"BCL11A", "HBB", "DMD", "CRISPR", "gene therapy", "base editing"}
        )

        pipeline = IngestionPipeline(
            connector=MockConnector(),
            archive=_FakeArchive(),
            extractor=_FixedExtractor(),
            producer=producer,
            prefilter=pf,
            normalizer=IdentityNormalizer(),
            now=lambda: _T0,
        )

        result = pipeline.run("mock", _T0)

        assert result.fetched == 4, f"Expected 4 docs fetched, got {result.fetched}"
        assert result.published == 4, f"Expected 4 published, got {result.published}"
        assert result.failed == 0, f"Expected 0 failures, got {result.failed}"

        raw_msgs = _drain(bootstrap, _RAW_TOPIC, expected=4)
        sig_msgs = _drain(bootstrap, _SIG_TOPIC, expected=4)

        assert len(raw_msgs) == 4, f"Expected 4 raw messages on {_RAW_TOPIC}, got {len(raw_msgs)}"
        assert len(sig_msgs) == 4, (
            f"Expected 4 signal messages on {_SIG_TOPIC}, got {len(sig_msgs)}"
        )
