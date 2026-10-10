"""The run-level guarantees a daily ingestion run makes to the DAG that calls it: the cursor it
reports never passes a document that failed, the extraction cap ends a run without losing its
place, and one source never runs twice at once."""
from __future__ import annotations

import threading
from datetime import UTC, datetime
from unittest.mock import MagicMock

from auspex_ingest.api import create_app
from auspex_ingest.pipeline import IngestionPipeline, RunResult
from auspex_ingest.sources import SourceEntry, SourcesConfig

_IDENTITY = "llama3.1:8b|v1"
_CURSOR = datetime(2026, 1, 1, tzinfo=UTC)


class _MarkerArchive:
    def __init__(self) -> None:
        self.processed: set[tuple[str, str]] = set()

    def put(self, doc):
        return f"raw/{doc.source_type}/{doc.external_id}.json", True

    def get_canonical_marker(self, canonical_id):
        return None

    def put_canonical_marker(self, canonical_id, data):
        pass

    def has_processed_marker(self, doc, identity):
        return (doc.external_id, identity) in self.processed

    def put_processed_marker(self, doc, identity):
        self.processed.add((doc.external_id, identity))


def _doc(external_id: str, day: int):
    doc = MagicMock()
    doc.external_id = external_id
    doc.source_type = "biorxiv"
    doc.published_date = datetime(2026, 1, day, 12, tzinfo=UTC)
    doc.canonical_id = None
    doc.schema_version = "1.0"
    doc.content_sha256 = external_id * 8
    return doc


def _event():
    event = MagicMock()
    event.confidence_score = 0.9
    event.gene_targets = []
    event.companies_mentioned = []
    event.model_copy.return_value = event
    return event


class _Extractor:
    """Extracts every document except those named in `failing`, recording each call."""

    def __init__(self, failing: set[str] | None = None) -> None:
        self.failing = set(failing or ())
        self.calls: list[str] = []

    def extract(self, doc, prefilter_version, key):
        self.calls.append(doc.external_id)
        if doc.external_id in self.failing:
            raise TimeoutError("model server did not answer")
        return _event()


def _pipeline(docs, archive, extractor, *, cap: int | None = None) -> IngestionPipeline:
    connector = MagicMock()
    connector.fetch_since.side_effect = lambda cursor: [
        d for d in docs if d.published_date.date() >= cursor.date()
    ]
    connector.provides_canonical_id = False
    prefilter = MagicMock()
    prefilter.passes.return_value = True
    prefilter.version = "pf1"
    normalizer = MagicMock()
    normalizer.normalize_gene.side_effect = lambda x: x
    normalizer.normalize_company.side_effect = lambda x: x
    return IngestionPipeline(
        connector=connector,
        archive=archive,
        extractor=extractor,
        producer=MagicMock(),
        prefilter=prefilter,
        normalizer=normalizer,
        now=lambda: datetime.now(UTC),
        extraction_identity=_IDENTITY,
        max_extractions_per_run=cap,
    )


def test_cursor_stops_at_the_earliest_failed_document():
    docs = [_doc("a", 3), _doc("b", 5), _doc("c", 8), _doc("d", 9)]
    result = _pipeline(docs, _MarkerArchive(), _Extractor({"b"})).run("biorxiv", _CURSOR)

    assert result.failed == 1
    assert result.next_cursor == datetime(2026, 1, 5, 12, tzinfo=UTC)
    assert result.max_published_date_processed == datetime(2026, 1, 9, 12, tzinfo=UTC)


def test_cursor_is_the_latest_processed_date_when_nothing_failed():
    docs = [_doc("a", 3), _doc("b", 9), _doc("c", 5)]
    result = _pipeline(docs, _MarkerArchive(), _Extractor()).run("biorxiv", _CURSOR)

    assert result.failed == 0
    assert result.next_cursor == datetime(2026, 1, 9, 12, tzinfo=UTC)


def test_failed_document_is_extracted_again_on_the_next_run():
    docs = [_doc("a", 3), _doc("b", 5), _doc("c", 8)]
    archive = _MarkerArchive()
    first = _pipeline(docs, archive, _Extractor({"b"})).run("biorxiv", _CURSOR)
    assert first.next_cursor is not None

    retry = _Extractor()
    second = _pipeline(docs, archive, retry).run("biorxiv", first.next_cursor)

    assert retry.calls == ["b"]
    assert second.failed == 0
    assert second.next_cursor == datetime(2026, 1, 8, 12, tzinfo=UTC)


def test_extraction_cap_stops_the_run_and_returns_the_input_cursor():
    docs = [_doc(name, day) for name, day in [("a", 2), ("b", 3), ("c", 4), ("d", 5)]]
    archive = _MarkerArchive()
    extractor = _Extractor()

    result = _pipeline(docs, archive, extractor, cap=2).run("biorxiv", _CURSOR)

    assert extractor.calls == ["a", "b"]
    assert result.capped is True
    assert result.next_cursor == _CURSOR
    # What was extracted is marked, so the next run from the same cursor continues after it.
    follow_up = _Extractor()
    _pipeline(docs, archive, follow_up, cap=2).run("biorxiv", _CURSOR)
    assert follow_up.calls == ["c", "d"]


def test_already_processed_documents_do_not_count_toward_the_extraction_cap():
    docs = [_doc(name, day) for name, day in [("a", 2), ("b", 3), ("c", 4)]]
    archive = _MarkerArchive()
    archive.processed |= {("a", f"{_IDENTITY}|pf1"), ("b", f"{_IDENTITY}|pf1")}
    extractor = _Extractor()

    result = _pipeline(docs, archive, extractor, cap=1).run("biorxiv", _CURSOR)

    assert extractor.calls == ["c"]
    assert result.capped is False
    assert result.next_cursor == datetime(2026, 1, 4, 12, tzinfo=UTC)


def _sources(*source_types: str) -> SourcesConfig:
    return SourcesConfig(sources=[
        SourceEntry(
            source_type=st,
            schedule=None,
            rate_limit_rps=1.0,
            initial_lookback=7,
            max_documents_per_run=10,
            prefilter_vocabulary=["gene therapy"],
            source_config={},
        )
        for st in source_types
    ])


class _BlockingPipeline:
    """A run that holds until released, so a second request arrives while it is in progress."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, source_type, cursor):
        self.started.set()
        assert self.release.wait(5), "test never released the run"
        return RunResult()


def _start_blocked_run(client, source_type: str, pipeline: _BlockingPipeline) -> threading.Thread:
    responses: list[int] = []
    thread = threading.Thread(
        target=lambda: responses.append(client.post(f"/ingest/{source_type}", json={}).status_code)
    )
    thread.start()
    assert pipeline.started.wait(5)
    thread.responses = responses  # type: ignore[attr-defined]
    return thread


def test_second_concurrent_run_of_a_source_is_refused_with_409():
    blocking = _BlockingPipeline()
    app = create_app(pipeline_for_source=lambda _st: blocking, sources_config=_sources("biorxiv"))
    client = app.test_client()

    first = _start_blocked_run(client, "biorxiv", blocking)
    try:
        second = client.post("/ingest/biorxiv", json={})
    finally:
        blocking.release.set()
        first.join(5)

    assert second.status_code == 409
    assert first.responses == [200]  # type: ignore[attr-defined]
    # The lock is released when the run ends.
    assert client.post("/ingest/biorxiv", json={}).status_code == 200


def test_runs_of_different_sources_are_not_blocked_by_the_source_lock():
    blocking = _BlockingPipeline()
    other = MagicMock()
    other.run.return_value = RunResult()
    pipelines = {"biorxiv": blocking, "pubmed": other}
    app = create_app(
        pipeline_for_source=lambda st: pipelines[st], sources_config=_sources("biorxiv", "pubmed")
    )
    client = app.test_client()

    first = _start_blocked_run(client, "biorxiv", blocking)
    try:
        response = client.post("/ingest/pubmed", json={})
    finally:
        blocking.release.set()
        first.join(5)

    assert response.status_code == 200
    other.run.assert_called_once()
