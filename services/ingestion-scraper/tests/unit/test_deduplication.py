"""Deduplication and amendment precedence tests.

Verifies the canonical marker system:
  - archive is always unconditional (invariant 13)
  - content_sha256 gate skips same-source unchanged refetches
  - canonical marker skips cross-source mirrored documents
  - markers are written only after successful publish
  - failed marker write causes at most one redundant extraction, never an error
"""

import hashlib
from datetime import UTC, datetime
from unittest.mock import MagicMock

from auspex_ingest.connectors.base import SourceConnector
from auspex_ingest.identity import compute_event_id, compute_extraction_id
from auspex_ingest.models import RawDocument, ResearchSignalEvent
from auspex_ingest.normalizer import IdentityNormalizer
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter
from auspex_ingest.storage.minio_client import minio_key

_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
_VOCAB = frozenset({"BCL11A", "CRISPR", "gene therapy", "base editing"})
_CANONICAL_ID = "doi:10.1234/dedup-test"


def _make_raw(
    *,
    external_id: str = "ext-001",
    source_type: str = "biorxiv",
    canonical_id: str | None = _CANONICAL_ID,
    content: str = "CRISPR base editing of BCL11A",
) -> RawDocument:
    sha = hashlib.sha256(content.encode()).hexdigest()
    return RawDocument(
        schema_version="1.0",
        external_id=external_id,
        canonical_id=canonical_id,
        source_type=source_type,
        source_url="https://example.com/doc",
        published_date=_T0,
        raw_content=content,
        content_sha256=sha,
        retrieved_at=_T0,
    )


def _make_event_for(doc: RawDocument) -> ResearchSignalEvent:
    event_id = compute_event_id(doc.canonical_id, doc.source_type, doc.external_id)
    extraction_id = compute_extraction_id(event_id, "1.0", "v1", "v1", "gpt-4o")
    return ResearchSignalEvent(
        schema_version="1.0",
        event_id=event_id,
        extraction_id=extraction_id,
        external_id=doc.external_id,
        canonical_id=doc.canonical_id,
        raw_object_key="raw/test/key.json",
        source_type=doc.source_type,
        source_url=doc.source_url,
        published_date=doc.published_date,
        published_date_field="published_date",
        ingested_at=_T0,
        title="BCL11A base editing study",
        raw_text_snippet="BCL11A base editing",
        gene_targets=["BCL11A"],
        mechanisms=["base editing"],
        companies_mentioned=["Test Co"],
        summary="BCL11A base editing signal",
        directionality="positive",
        confidence_score=0.9,
        prompt_version="v1",
        prefilter_version="v1",
        extraction_model="gpt-4o",
    )


class _FakeArchive:
    def __init__(self) -> None:
        self.puts: list[tuple[str, RawDocument]] = []
        self._seen_sha: set[str] = set()
        self.canonical_markers: dict[str, dict] = {}
        self.marker_write_fails: bool = False

    def put(self, doc: RawDocument) -> tuple[str, bool]:
        key = minio_key(doc)
        is_new = doc.content_sha256 not in self._seen_sha
        self._seen_sha.add(doc.content_sha256)
        self.puts.append((key, doc))
        return key, is_new

    def get_canonical_marker(self, canonical_id: str) -> dict | None:
        return self.canonical_markers.get(canonical_id)

    def put_canonical_marker(self, canonical_id: str, data: dict) -> None:
        if self.marker_write_fails:
            raise RuntimeError("Simulated marker write failure")
        self.canonical_markers[canonical_id] = data


class _SignalExtractor:
    def __init__(self) -> None:
        self.call_count = 0

    def extract(self, doc: RawDocument, prefilter_version: str,
                raw_object_key: str) -> ResearchSignalEvent:
        self.call_count += 1
        return _make_event_for(doc)


class _FailingPublishProducer:
    def publish_raw(self, doc: RawDocument, raw_object_key: str, schema_version: str) -> None:
        pass

    def publish_signal(self, event: ResearchSignalEvent) -> None:
        raise RuntimeError("Simulated publish_signal failure")

    def flush(self) -> None:
        pass


def _pipeline(
    connector: SourceConnector,
    archive: _FakeArchive,
    extractor: object,
    *,
    producer: object | None = None,
) -> IngestionPipeline:
    if producer is None:
        prod = MagicMock()
        prod.flush.return_value = None
    else:
        prod = producer
    return IngestionPipeline(
        connector=connector,
        archive=archive,
        extractor=extractor,
        producer=prod,
        prefilter=Prefilter.from_vocab(_VOCAB),
        normalizer=IdentityNormalizer(),
        now=lambda: _T0,
    )



def test_same_disclosure_from_two_sources_skips_the_second_extraction_via_the_canonical_marker():
    biorxiv_doc = _make_raw(
        source_type="biorxiv",
        external_id="biorxiv:10.1234/dedup-test:v1",
        content="CRISPR BCL11A base editing (biorxiv preprint)",
    )
    pubmed_doc = _make_raw(
        source_type="pubmed",
        external_id="pubmed:99999999",
        content="CRISPR BCL11A base editing (pubmed journal)",
    )

    class _TwoSourceConnector(SourceConnector):
        provides_canonical_id = True
        def __init__(self, doc: RawDocument):
            self._doc = doc
        def fetch_since(self, cursor):
            yield self._doc

    archive = _FakeArchive()
    extractor = _SignalExtractor()

    _pipeline(_TwoSourceConnector(biorxiv_doc), archive, extractor).run("biorxiv", _T0)
    _pipeline(_TwoSourceConnector(pubmed_doc), archive, extractor).run("pubmed", _T0)

    assert len(archive.puts) == 2, "Both observations must be archived"
    assert extractor.call_count == 1, "Second source must be skipped via canonical marker"


def test_dedup_never_suppresses_the_minio_write():
    biorxiv_doc = _make_raw(source_type="biorxiv", content="CRISPR BCL11A biorxiv")
    pubmed_doc = _make_raw(
        source_type="pubmed", external_id="pubmed:1", content="CRISPR BCL11A pubmed"
    )

    class _Conn(SourceConnector):
        provides_canonical_id = True
        def __init__(self, doc):
            self._doc = doc
        def fetch_since(self, cursor):
            yield self._doc

    archive = _FakeArchive()
    extractor = _SignalExtractor()

    _pipeline(_Conn(biorxiv_doc), archive, extractor).run("biorxiv", _T0)
    _pipeline(_Conn(pubmed_doc), archive, extractor).run("pubmed", _T0)

    assert len(archive.puts) == 2, "Archive must be unconditional — dedup must never block a MinIO write"


def test_duplicate_skip_does_not_fail_the_task():
    biorxiv_doc = _make_raw(source_type="biorxiv", content="CRISPR BCL11A biorxiv2")
    pubmed_doc = _make_raw(
        source_type="pubmed", external_id="pubmed:2", content="CRISPR BCL11A pubmed2"
    )

    class _Conn(SourceConnector):
        provides_canonical_id = True
        def __init__(self, doc):
            self._doc = doc
        def fetch_since(self, cursor):
            yield self._doc

    archive = _FakeArchive()
    extractor = _SignalExtractor()

    _pipeline(_Conn(biorxiv_doc), archive, extractor).run("biorxiv", _T0)
    result = _pipeline(_Conn(pubmed_doc), archive, extractor).run("pubmed", _T0)

    assert result.failed == 0
    assert result.prefiltered_out == 1


def test_document_with_no_canonical_id_is_not_deduped_across_sources():
    doc_a = _make_raw(source_type="biorxiv", canonical_id=None, content="CRISPR BCL11A no-id-a")
    doc_b = _make_raw(
        source_type="pubmed", external_id="pubmed:3", canonical_id=None,
        content="CRISPR BCL11A no-id-b"
    )

    class _Conn(SourceConnector):
        provides_canonical_id = False
        def __init__(self, doc):
            self._doc = doc
        def fetch_since(self, cursor):
            yield self._doc

    archive = _FakeArchive()
    extractor = _SignalExtractor()

    _pipeline(_Conn(doc_a), archive, extractor).run("biorxiv", _T0)
    _pipeline(_Conn(doc_b), archive, extractor).run("pubmed", _T0)

    assert extractor.call_count == 2, "No canonical_id means no cross-source dedup"



def test_unchanged_refetch_is_archived_but_not_re_extracted():
    doc = _make_raw()

    class _Conn(SourceConnector):
        provides_canonical_id = True
        def fetch_since(self, cursor):
            yield doc

    archive = _FakeArchive()
    extractor = _SignalExtractor()
    pipeline = _pipeline(_Conn(), archive, extractor)

    pipeline.run("biorxiv", _T0)
    pipeline.run("biorxiv", _T0)

    assert len(archive.puts) == 2, "Archive must receive both puts"
    assert extractor.call_count == 1, "Content unchanged → extraction skipped on second fetch"



def test_changed_content_is_treated_as_an_amendment_and_republished():
    doc_v1 = _make_raw(content="CRISPR BCL11A base editing v1")
    doc_v2 = _make_raw(content="CRISPR BCL11A base editing v2 updated results")

    class _Conn(SourceConnector):
        provides_canonical_id = True
        def __init__(self, doc):
            self._doc = doc
        def fetch_since(self, cursor):
            yield self._doc

    archive = _FakeArchive()
    extractor = _SignalExtractor()

    _pipeline(_Conn(doc_v1), archive, extractor).run("biorxiv", _T0)
    _pipeline(_Conn(doc_v2), archive, extractor).run("biorxiv", _T0)

    assert extractor.call_count == 2, (
        "Same source, changed content = amendment — must re-extract even when marker exists"
    )



def test_marker_written_only_after_successful_publish():
    doc = _make_raw()

    class _Conn(SourceConnector):
        provides_canonical_id = True
        def fetch_since(self, cursor):
            yield doc

    archive = _FakeArchive()
    extractor = _SignalExtractor()

    _pipeline(_Conn(), archive, extractor, producer=_FailingPublishProducer()).run("biorxiv", _T0)

    assert _CANONICAL_ID not in archive.canonical_markers, (
        "Marker must not be written when publish_signal fails"
    )


def test_failed_marker_write_causes_at_most_one_redundant_extraction():
    doc_v1 = _make_raw(content="CRISPR BCL11A unique content v1 marker-fail")
    doc_v2 = _make_raw(
        source_type="pubmed", external_id="pubmed:4",
        content="CRISPR BCL11A unique content v2 marker-fail",
    )

    class _Conn(SourceConnector):
        provides_canonical_id = True
        def __init__(self, doc):
            self._doc = doc
        def fetch_since(self, cursor):
            yield self._doc

    archive = _FakeArchive()
    archive.marker_write_fails = True
    extractor = _SignalExtractor()

    result1 = _pipeline(_Conn(doc_v1), archive, extractor).run("biorxiv", _T0)
    result2 = _pipeline(_Conn(doc_v2), archive, extractor).run("pubmed", _T0)

    assert extractor.call_count == 2, (
        "No marker written → second source re-extracts (the one accepted redundancy)"
    )
    assert result1.failed == 0, "Marker write failure must not fail the task"
    assert result2.failed == 0, "Marker write failure must not fail the task"



def test_dedup_requires_no_state_outside_minio():
    """Two separate pipeline instances sharing an archive correctly deduplicate."""
    biorxiv_doc = _make_raw(source_type="biorxiv", content="CRISPR BCL11A shared-archive")
    pubmed_doc = _make_raw(
        source_type="pubmed", external_id="pubmed:5",
        content="CRISPR BCL11A pubmed shared-archive",
    )

    class _Conn(SourceConnector):
        provides_canonical_id = True
        def __init__(self, doc):
            self._doc = doc
        def fetch_since(self, cursor):
            yield self._doc

    shared_archive = _FakeArchive()
    extractor = _SignalExtractor()

    pipeline_a = _pipeline(_Conn(biorxiv_doc), shared_archive, extractor)
    pipeline_b = _pipeline(_Conn(pubmed_doc), shared_archive, extractor)

    pipeline_a.run("biorxiv", _T0)
    pipeline_b.run("pubmed", _T0)

    assert extractor.call_count == 1, (
        "Fresh pipeline instance with shared archive must read marker state from archive"
    )
