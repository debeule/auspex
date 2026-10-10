"""Requirements §7.1 step 3: an unchanged re-fetch skips extraction and publish.

"Unchanged" means same (source_type, external_id, content_sha256) already fully processed
under the same extraction identity (model, prompt, prefilter). A document whose
extraction or delivery failed is not marked, so the next fetch retries it.
"""
from datetime import UTC, datetime
from unittest.mock import MagicMock

import structlog.testing

from auspex_ingest.pipeline import IngestionPipeline

_IDENTITY = "llama3.1:8b|v1"


class MarkerArchive:
    def __init__(self, processed: set[tuple[str, str, str, str]] | None = None) -> None:
        self.processed = set(processed or ())
        self.marked: list[tuple[str, str, str, str]] = []
        self.puts = 0

    def put(self, doc):
        self.puts += 1
        return f"raw/{doc.source_type}/{doc.external_id}/{self.puts}.json", True

    def get_canonical_marker(self, canonical_id):
        return None

    def put_canonical_marker(self, canonical_id, data):
        pass

    def has_processed_marker(self, doc, identity):
        return (doc.source_type, doc.external_id, doc.content_sha256, identity) in self.processed

    def put_processed_marker(self, doc, identity):
        entry = (doc.source_type, doc.external_id, doc.content_sha256, identity)
        self.marked.append(entry)
        self.processed.add(entry)


def _doc(external_id="ext-1", sha="a" * 64):
    doc = MagicMock()
    doc.external_id = external_id
    doc.source_type = "biorxiv"
    doc.published_date = datetime(2026, 1, 5, tzinfo=UTC)
    doc.canonical_id = None
    doc.schema_version = "1.0"
    doc.content_sha256 = sha
    return doc


def _event(confidence=0.9):
    event = MagicMock()
    event.confidence_score = confidence
    event.gene_targets = []
    event.companies_mentioned = []
    event.model_copy.return_value = event
    return event


def _pipeline(docs, archive, *, extractor=None, producer=None, identity=_IDENTITY):
    connector = MagicMock()
    connector.fetch_since.return_value = docs
    connector.provides_canonical_id = False
    prefilter = MagicMock()
    prefilter.passes.return_value = True
    prefilter.version = "pf1"
    normalizer = MagicMock()
    normalizer.normalize_gene.side_effect = lambda x: x
    normalizer.normalize_company.side_effect = lambda x: x
    if extractor is None:
        extractor = MagicMock()
        extractor.extract.return_value = _event()
    return IngestionPipeline(
        connector=connector,
        archive=archive,
        extractor=extractor,
        producer=producer or MagicMock(),
        prefilter=prefilter,
        normalizer=normalizer,
        now=lambda: datetime.now(UTC),
        extraction_identity=identity,
    ), extractor


def test_refetch_of_processed_unchanged_document_skips_extraction_and_publish():
    doc = _doc()
    archive = MarkerArchive({("biorxiv", "ext-1", doc.content_sha256, f"{_IDENTITY}|pf1")})
    producer = MagicMock()
    pipeline, extractor = _pipeline([doc], archive, producer=producer)

    with structlog.testing.capture_logs() as cap:
        result = pipeline.run("biorxiv", datetime(2026, 1, 1, tzinfo=UTC))

    assert archive.puts == 1, "the archive write stays unconditional (Invariant 13)"
    extractor.extract.assert_not_called()
    producer.publish_signal.assert_not_called()
    producer.publish_raw.assert_not_called()
    assert result.prefiltered_out == 1
    assert any(e.get("event") == "unchanged re-fetch skipped" for e in cap)


def test_published_document_is_marked_with_model_prompt_and_prefilter_identity():
    doc = _doc()
    archive = MarkerArchive()
    pipeline, _ = _pipeline([doc], archive)

    pipeline.run("biorxiv", datetime(2026, 1, 1, tzinfo=UTC))

    assert archive.marked == [("biorxiv", "ext-1", doc.content_sha256, f"{_IDENTITY}|pf1")]


def test_not_signal_outcome_is_marked_so_it_is_not_re_extracted():
    archive = MarkerArchive()
    extractor = MagicMock()
    extractor.extract.return_value = None
    pipeline, _ = _pipeline([_doc()], archive, extractor=extractor)

    pipeline.run("biorxiv", datetime(2026, 1, 1, tzinfo=UTC))

    assert len(archive.marked) == 1


def test_failed_extraction_is_not_marked_so_the_next_fetch_retries_it():
    archive = MarkerArchive()
    extractor = MagicMock()
    extractor.extract.side_effect = RuntimeError("model server unreachable")
    pipeline, _ = _pipeline([_doc()], archive, extractor=extractor)

    pipeline.run("biorxiv", datetime(2026, 1, 1, tzinfo=UTC))

    assert archive.marked == []


def test_failed_kafka_flush_marks_nothing_so_undelivered_signals_are_retried():
    archive = MarkerArchive()
    producer = MagicMock()
    producer.flush.side_effect = RuntimeError("Kafka flush timed out: 1 messages undelivered")
    pipeline, _ = _pipeline([_doc()], archive, producer=producer)

    pipeline.run("biorxiv", datetime(2026, 1, 1, tzinfo=UTC))

    assert archive.marked == []


def test_changed_content_is_an_amendment_and_is_extracted():
    old_sha, new_sha = "a" * 64, "b" * 64
    archive = MarkerArchive({("biorxiv", "ext-1", old_sha, f"{_IDENTITY}|pf1")})
    pipeline, extractor = _pipeline([_doc(sha=new_sha)], archive)

    pipeline.run("biorxiv", datetime(2026, 1, 1, tzinfo=UTC))

    extractor.extract.assert_called_once()


def test_a_different_model_re_extracts_unchanged_content():
    doc = _doc()
    archive = MarkerArchive({("biorxiv", "ext-1", doc.content_sha256, "gpt-4o-mini|v1|pf1")})
    pipeline, extractor = _pipeline([doc], archive)

    pipeline.run("biorxiv", datetime(2026, 1, 1, tzinfo=UTC))

    extractor.extract.assert_called_once()


def test_without_an_extraction_identity_every_fetch_is_extracted():
    doc = _doc()
    archive = MarkerArchive({("biorxiv", "ext-1", doc.content_sha256, f"{_IDENTITY}|pf1")})
    pipeline, extractor = _pipeline([doc], archive, identity=None)

    pipeline.run("biorxiv", datetime(2026, 1, 1, tzinfo=UTC))

    extractor.extract.assert_called_once()
    assert archive.marked == []


def test_live_api_pipelines_skip_unchanged_refetches_for_their_model(monkeypatch):
    import confluent_kafka
    from prometheus_client import CollectorRegistry

    import auspex_ingest.pipeline as pipeline_module
    from auspex_ingest.api import _make_env_pipeline_factory
    from auspex_ingest.sources import SourceEntry

    for name, value in {
        "MINIO_ENDPOINT": "minio.invalid:9000", "MINIO_ACCESS_KEY": "k", "MINIO_SECRET_KEY": "s",
        "MINIO_BUCKET": "auspex-raw", "KAFKA_BOOTSTRAP_SERVERS": "kafka.invalid:9092",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(confluent_kafka, "Producer", MagicMock())
    extractor = MagicMock(model_id="llama3.1:8b", prompt_version="v1")
    monkeypatch.setattr(
        "auspex_ingest.extraction_backend.build_extractor_from_env", lambda **_: extractor
    )
    built = MagicMock()
    monkeypatch.setattr(pipeline_module, "IngestionPipeline", built)

    entry = SourceEntry(
        source_type="biorxiv", schedule="@daily", rate_limit_rps=3.0, initial_lookback=7,
        max_documents_per_run=100, prefilter_vocabulary=["gene therapy"], source_config={},
    )
    _make_env_pipeline_factory({"biorxiv": entry}, CollectorRegistry())("biorxiv")

    assert built.call_args.kwargs["extraction_identity"] == "llama3.1:8b|v1"
