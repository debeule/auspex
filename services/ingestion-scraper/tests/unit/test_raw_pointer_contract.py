"""The raw pointer on `auspex.raw.ingested`: one per archived document, sent right after the archive.

Also generates the Java contract fixture core-hub's raw audit tests read:

    cd services/ingestion-scraper && uv run pytest tests/unit/test_raw_pointer_contract.py

writes services/core-hub/src/test/resources/contract/raw_pointer_v1.json.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from auspex_ingest.connectors.base import SourceConnector
from auspex_ingest.identity import compute_event_id, compute_extraction_id
from auspex_ingest.messaging.kafka_producer import KafkaProducerClient
from auspex_ingest.models import RawDocument, ResearchSignalEvent
from auspex_ingest.normalizer import IdentityNormalizer
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter
from auspex_ingest.storage.minio_client import minio_key

_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
_RAW_TOPIC = "auspex.raw.ingested"
_SIGNALS_TOPIC = "auspex.signals.extracted"
_RAW_POINTER_PATH = (
    Path(__file__).resolve().parents[4]
    / "services/core-hub/src/test/resources/contract/raw_pointer_v1.json"
)


def _doc(
    external_id: str,
    *,
    content: str = "CRISPR base editing of BCL11A",
    published_date: datetime = _T0,
    canonical_id: str | None = None,
) -> RawDocument:
    return RawDocument(
        schema_version="1.0",
        external_id=external_id,
        canonical_id=canonical_id,
        source_type="biorxiv",
        source_url=f"https://example.com/{external_id}",
        published_date=published_date,
        raw_content=content,
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        retrieved_at=_T0,
    )


def _event(doc: RawDocument, confidence: float) -> ResearchSignalEvent:
    event_id = compute_event_id(doc.canonical_id, doc.source_type, doc.external_id)
    return ResearchSignalEvent(
        schema_version="1.0",
        event_id=event_id,
        extraction_id=compute_extraction_id(event_id, "1.0", "v1", "v1", "test-model"),
        external_id=doc.external_id,
        canonical_id=doc.canonical_id,
        raw_object_key=minio_key(doc),
        source_type=doc.source_type,
        source_url=doc.source_url,
        published_date=doc.published_date,
        published_date_field="date",
        ingested_at=_T0,
        title="BCL11A base editing",
        raw_text_snippet="BCL11A base editing results",
        gene_targets=["BCL11A"],
        mechanisms=["base editing"],
        companies_mentioned=[],
        summary="BCL11A editing",
        directionality="positive",
        confidence_score=confidence,
        prompt_version="v1",
        prefilter_version="v1",
        extraction_model="test-model",
    )


class _Docs(SourceConnector):
    def __init__(self, docs: list[RawDocument]) -> None:
        self._docs = docs

    def fetch_since(self, cursor: datetime):
        yield from self._docs


class _Archive:
    def __init__(self, calls: list[str], *, existing: bool = False) -> None:
        self._calls = calls
        self._existing = existing

    def put(self, doc: RawDocument) -> tuple[str, bool]:
        self._calls.append(f"archive:{doc.external_id}")
        return minio_key(doc), not self._existing

    def get_canonical_marker(self, canonical_id: str) -> dict | None:
        return None

    def put_canonical_marker(self, canonical_id: str, data: dict) -> None:
        pass


class _Extractor:
    def __init__(self, calls: list[str], responses: dict[str, float | None]) -> None:
        self._calls = calls
        self._responses = responses
        self.extracted: list[str] = []

    def extract(self, doc: RawDocument, prefilter_version: str,
                raw_object_key: str) -> ResearchSignalEvent | None:
        self._calls.append(f"extract:{doc.external_id}")
        self.extracted.append(doc.external_id)
        confidence = self._responses.get(doc.external_id)
        return None if confidence is None else _event(doc, confidence)


class _Producer:
    def __init__(self, calls: list[str], *, fail_for: str | None = None) -> None:
        self._calls = calls
        self._fail_for = fail_for
        self.pointers: list[tuple[str, str]] = []
        self.signals: list[str] = []

    def publish_raw(self, doc: RawDocument, raw_object_key: str, schema_version: str) -> None:
        self._calls.append(f"publish_raw:{doc.external_id}")
        if doc.external_id == self._fail_for:
            raise RuntimeError("raw pointer produce failed (simulated)")
        self.pointers.append((doc.external_id, raw_object_key))

    def publish_signal(self, event: ResearchSignalEvent) -> None:
        self._calls.append(f"publish_signal:{event.external_id}")
        self.signals.append(event.external_id)

    def flush(self) -> None:
        pass


def _pipeline(
    docs: list[RawDocument],
    *,
    responses: dict[str, float | None] | None = None,
    existing: bool = False,
    fail_for: str | None = None,
) -> tuple[IngestionPipeline, list[str], _Extractor, _Producer]:
    calls: list[str] = []
    extractor = _Extractor(calls, responses or {})
    producer = _Producer(calls, fail_for=fail_for)
    pipeline = IngestionPipeline(
        connector=_Docs(docs),
        archive=_Archive(calls, existing=existing),
        extractor=extractor,
        producer=producer,
        prefilter=Prefilter.from_vocab({"BCL11A", "CRISPR", "base editing"}),
        normalizer=IdentityNormalizer(),
        now=lambda: _T0,
        min_confidence_to_publish=0.5,
    )
    return pipeline, calls, extractor, producer


class _FakeConfluentProducer:
    def __init__(self) -> None:
        self.produced: list[dict[str, Any]] = []

    def produce(self, topic: str, *, key: str, value: bytes,
                headers: dict[str, str], callback: Any) -> None:
        self.produced.append({"topic": topic, "key": key, "value": value, "headers": headers})


def _contract_doc() -> RawDocument:
    return _doc(
        "ext-contract-001",
        content="CRISPR base editing of BCL11A in sickle cell disease",
        canonical_id="doi:10.1101/2024.06.01.600001",
    )


def _published_pointer() -> dict[str, Any]:
    confluent = _FakeConfluentProducer()
    client = KafkaProducerClient(confluent, raw_topic=_RAW_TOPIC, signals_topic=_SIGNALS_TOPIC)
    doc = _contract_doc()
    client.publish_raw(doc, minio_key(doc), doc.schema_version)
    assert len(confluent.produced) == 1
    return confluent.produced[0]


def test_raw_pointer_published_for_every_archived_document():
    docs = [
        _doc("ext-prefiltered", content="quarterly earnings call transcript"),
        _doc("ext-not-signal"),
        _doc("ext-below-threshold"),
        _doc("ext-signal"),
    ]
    pipeline, _, _, producer = _pipeline(docs, responses={
        "ext-not-signal": None,
        "ext-below-threshold": 0.1,
        "ext-signal": 0.9,
    })

    result = pipeline.run("biorxiv", _T0)

    assert result.failed == 0
    assert [external_id for external_id, _ in producer.pointers] == [d.external_id for d in docs]
    assert [key for _, key in producer.pointers] == [minio_key(d) for d in docs]
    assert producer.signals == ["ext-signal"]


def test_raw_pointer_published_before_extraction():
    pipeline, calls, _, _ = _pipeline([_doc("ext-1")], responses={"ext-1": 0.9})

    pipeline.run("biorxiv", _T0)

    assert calls[:3] == ["archive:ext-1", "publish_raw:ext-1", "extract:ext-1"]
    assert calls.count("publish_raw:ext-1") == 1


def test_raw_pointer_not_republished_for_existing_archive_object():
    pipeline, calls, extractor, producer = _pipeline(
        [_doc("ext-1")], responses={"ext-1": 0.9}, existing=True,
    )

    pipeline.run("biorxiv", _T0)

    assert calls == ["archive:ext-1"]
    assert producer.pointers == []
    assert extractor.extracted == []


def test_raw_pointer_publish_failure_fails_the_document():
    failing = _doc("ext-failing", published_date=_T0)
    later = _doc("ext-later", published_date=_T0 + timedelta(days=1))
    pipeline, _, extractor, producer = _pipeline(
        [failing, later],
        responses={"ext-failing": 0.9, "ext-later": 0.9},
        fail_for="ext-failing",
    )

    result = pipeline.run("biorxiv", _T0 - timedelta(days=1))

    assert result.failed == 1
    assert extractor.extracted == ["ext-later"]
    assert producer.signals == ["ext-later"]
    assert result.next_cursor is not None
    assert result.next_cursor <= failing.published_date


def test_raw_pointer_payload_carries_contract_fields_and_no_content():
    produced = _published_pointer()
    payload = json.loads(produced["value"])
    doc = _contract_doc()

    assert produced["topic"] == _RAW_TOPIC
    assert produced["key"] == doc.external_id
    assert produced["headers"] == {"schema_version": doc.schema_version}
    for field in ("raw_object_key", "external_id", "canonical_id", "source_type",
                  "source_url", "retrieved_at", "content_sha256", "schema_version"):
        assert field in payload, f"raw pointer is missing {field}"
    assert "raw_content" not in payload
    assert payload["raw_object_key"] == minio_key(doc)
    retrieved_at = datetime.fromisoformat(payload["retrieved_at"])
    assert retrieved_at.utcoffset() == timedelta(0)
    assert retrieved_at == doc.retrieved_at


def test_raw_pointer_contract_fixture_is_generated():
    committed = _RAW_POINTER_PATH.read_text(encoding="utf-8") if _RAW_POINTER_PATH.exists() else None
    generated = json.dumps(json.loads(_published_pointer()["value"]), indent=2) + "\n"

    _RAW_POINTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RAW_POINTER_PATH.write_text(generated, encoding="utf-8")

    assert committed == generated, (
        f"{_RAW_POINTER_PATH.name} differed from the producer's output and was regenerated; "
        "commit the regenerated file"
    )
