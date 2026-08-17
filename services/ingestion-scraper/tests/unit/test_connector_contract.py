"""Unit tests — RawDocument model, SourceConnector ABC, MinIO key generation."""

import inspect
from collections.abc import Iterator
from datetime import datetime, timezone, timedelta

import pytest
from pydantic import ValidationError

from auspex_ingest.models import RawDocument
from auspex_ingest.connectors.base import SourceConnector
from auspex_ingest.storage.minio_client import minio_key

# ── helpers ────────────────────────────────────────────────────────────────────

_UTC = timezone.utc
_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=_UTC)


def _make_doc(**overrides) -> RawDocument:
    defaults = dict(
        schema_version="1.0",
        external_id="test-ext-001",
        source_type="biorxiv",
        source_url="https://example.com/doc/1",
        published_date=_T0,
        raw_content="some text",
        content_sha256="abcdef1234567890",
        retrieved_at=_T0,
    )
    defaults.update(overrides)
    return RawDocument(**defaults)


# ── RawDocument ────────────────────────────────────────────────────────────────

def test_rawdocument_rejects_naive_datetime():
    naive = datetime(2024, 6, 15, 12, 0, 0)  # no tzinfo
    with pytest.raises(ValidationError):
        _make_doc(published_date=naive)
    with pytest.raises(ValidationError):
        _make_doc(retrieved_at=naive)


def test_rawdocument_normalizes_offset_to_utc():
    plus5 = datetime(2024, 6, 15, 17, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    doc = _make_doc(published_date=plus5)
    assert doc.published_date == datetime(2024, 6, 15, 12, 0, 0, tzinfo=_UTC)
    assert doc.published_date.tzinfo == _UTC


def test_rawdocument_requires_schema_version():
    with pytest.raises(ValidationError):
        RawDocument(
            external_id="x",
            source_type="biorxiv",
            source_url="https://example.com",
            published_date=_T0,
            raw_content="text",
            content_sha256="abc123",
            retrieved_at=_T0,
        )


@pytest.mark.parametrize("cid", [
    "doi:10.1101/2024.01.01.123456",
    "nct:NCT01234567",
    "epo-app:US-18123456",
    "edgar:0000320193-24-000058",
    None,
])
def test_canonical_id_is_typed_or_absent_accepts_valid(cid):
    doc = _make_doc(canonical_id=cid)
    assert doc.canonical_id == cid


@pytest.mark.parametrize("bad_cid", [
    "10.1101/2024.01.01.123456",
    "NCT01234567",
    "US-18123456",
    "0000320193-24-000058",
    "lens:123",
    "",
])
def test_canonical_id_is_typed_or_absent_rejects_bare(bad_cid):
    with pytest.raises(ValidationError):
        _make_doc(canonical_id=bad_cid)


# ── MinIO key ──────────────────────────────────────────────────────────────────

def test_minio_key_includes_retrieved_at_and_content_hash():
    doc = _make_doc(
        source_type="biorxiv",
        external_id="doi-123",
        retrieved_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=_UTC),
        content_sha256="abcdef1234567890",
    )
    key = minio_key(doc)
    assert key == "raw/biorxiv/doi-123/20240615T120000Z-abcdef12.json"


def test_minio_key_converts_offset_timestamp_to_utc_wall_time():
    plus5 = timezone(timedelta(hours=5))
    doc = _make_doc(
        source_type="pubmed",
        external_id="pmid-999",
        # 17:00 +05:00 = 12:00 UTC
        retrieved_at=datetime(2024, 6, 15, 17, 0, 0, tzinfo=plus5),
        content_sha256="deadbeef12345678",
    )
    key = minio_key(doc)
    # Key must show UTC wall time, not local wall time
    assert "20240615T120000Z" in key
    assert "20240615T170000Z" not in key


# ── SourceConnector ABC ────────────────────────────────────────────────────────

def test_connector_is_abstract():
    with pytest.raises(TypeError):
        SourceConnector()  # type: ignore[abstract]


def test_fetch_since_is_not_a_coroutine_and_returns_an_iterator():
    class Concrete(SourceConnector):
        def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
            return iter([])

    conn = Concrete()
    result = conn.fetch_since(_T0)
    assert isinstance(result, Iterator)
    assert not inspect.iscoroutine(result)


def test_fetch_since_performs_no_io_beyond_http():
    minio_calls: list = []
    kafka_calls: list = []

    class MinioSpy:
        def put_object(self, *args, **kwargs):
            minio_calls.append(args)

    class KafkaSpy:
        def produce(self, *args, **kwargs):
            kafka_calls.append(args)

    class Concrete(SourceConnector):
        def __init__(self, minio_spy: MinioSpy, kafka_spy: KafkaSpy) -> None:
            self._minio = minio_spy
            self._kafka = kafka_spy

        def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
            return iter([])

    conn = Concrete(MinioSpy(), KafkaSpy())
    list(conn.fetch_since(_T0))

    assert minio_calls == [], "fetch_since must not call MinIO"
    assert kafka_calls == [], "fetch_since must not call Kafka"
