import hashlib
import json
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID

from auspex_ingest.identity import compute_event_id, compute_extraction_id
from auspex_ingest.models import RawDocument, ResearchSignalEvent
from auspex_ingest.reextract import ReextractionRunner

_UTC = UTC
_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=_UTC)
_T_BEFORE = datetime(2024, 6, 1, 0, 0, 0, tzinfo=_UTC)
_T_AFTER = datetime(2024, 7, 1, 0, 0, 0, tzinfo=_UTC)

_SCHEMA_VERSION = "1.0"
_PROMPT_V1 = "v1"
_PROMPT_V2 = "v2"
_PREFILTER_VERSION = "v1"
_MODEL = "gpt-4o"
_SOURCE_TYPE = "biorxiv"
_EXTERNAL_ID = "ext-001"
_CANONICAL_ID = "doi:10.1101/2024.06.01.001"
_CONTENT = "CRISPR base editing of BCL11A gene target"
_CONTENT_SHA = hashlib.sha256(_CONTENT.encode()).hexdigest()


def _make_archived_json(
    *,
    source_type: str = _SOURCE_TYPE,
    external_id: str = _EXTERNAL_ID,
    canonical_id: str | None = _CANONICAL_ID,
    published_date: datetime = _T0,
    content: str = _CONTENT,
) -> dict:
    sha = hashlib.sha256(content.encode()).hexdigest()
    return {
        "schema_version": _SCHEMA_VERSION,
        "external_id": external_id,
        "canonical_id": canonical_id,
        "source_type": source_type,
        "source_url": "https://example.com/doc/1",
        "published_date": published_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "content_sha256": sha,
        "retrieved_at": _T0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "raw_content": content,
    }


def _make_signal(event_id: UUID, extraction_id: UUID) -> ResearchSignalEvent:
    return ResearchSignalEvent(
        schema_version=_SCHEMA_VERSION,
        event_id=event_id,
        extraction_id=extraction_id,
        external_id=_EXTERNAL_ID,
        canonical_id=_CANONICAL_ID,
        raw_object_key=f"raw/{_SOURCE_TYPE}/{_EXTERNAL_ID}/20240615T120000Z-abcdef12.json",
        source_type=_SOURCE_TYPE,
        source_url="https://example.com/doc/1",
        published_date=_T0,
        published_date_field="published_date",
        ingested_at=_T0,
        title="CRISPR BCL11A editing",
        raw_text_snippet="BCL11A base editing results...",
        gene_targets=["BCL11A"],
        mechanisms=["base editing"],
        companies_mentioned=[],
        summary="BCL11A editing for sickle cell",
        directionality="positive",
        confidence_score=0.9,
        prompt_version=_PROMPT_V1,
        prefilter_version=_PREFILTER_VERSION,
        extraction_model=_MODEL,
    )


def _make_runner(
    *,
    archived_docs: list[dict] | None = None,
    signal: ResearchSignalEvent | None = None,
    extractor_returns: list | None = None,
) -> tuple[ReextractionRunner, MagicMock, MagicMock, MagicMock]:
    archive = MagicMock()
    extractor = MagicMock()
    producer = MagicMock()

    docs = archived_docs or [_make_archived_json()]
    keys = [f"raw/{d['source_type']}/{d['external_id']}/20240615T120000Z-aaaabbbb.json" for d in docs]

    archive.list_raw_keys.return_value = iter(keys)
    archive.get_raw.side_effect = [json.dumps(d).encode() for d in docs]

    if extractor_returns is not None:
        extractor.extract.side_effect = extractor_returns
    elif signal is not None:
        extractor.extract.return_value = signal
    else:
        event_id = compute_event_id(_CANONICAL_ID, _SOURCE_TYPE, _EXTERNAL_ID)
        extraction_id = compute_extraction_id(
            event_id, _SCHEMA_VERSION, _PROMPT_V1, _PREFILTER_VERSION, _MODEL
        )
        extractor.extract.return_value = _make_signal(event_id, extraction_id)

    runner = ReextractionRunner(archive=archive, extractor=extractor, producer=producer)
    return runner, archive, extractor, producer


def test_raw_document_reconstructed_from_archived_json() -> None:
    runner, _archive, extractor, _ = _make_runner()

    runner.run(
        source_type=_SOURCE_TYPE,
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    extractor.extract.assert_called_once()
    passed_doc: RawDocument = extractor.extract.call_args[0][0]
    assert isinstance(passed_doc, RawDocument)
    assert passed_doc.raw_content == _CONTENT
    assert passed_doc.external_id == _EXTERNAL_ID
    assert passed_doc.source_type == _SOURCE_TYPE


def test_event_id_stable_across_prompt_version_change() -> None:
    event_id_v1 = compute_event_id(_CANONICAL_ID, _SOURCE_TYPE, _EXTERNAL_ID)
    signal_v1 = _make_signal(
        event_id_v1,
        compute_extraction_id(event_id_v1, _SCHEMA_VERSION, _PROMPT_V1, _PREFILTER_VERSION, _MODEL),
    )

    runner_v1, _, extractor_v1, _ = _make_runner(signal=signal_v1)
    result_v1 = runner_v1.run(
        source_type=_SOURCE_TYPE,
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    event_id_v2 = compute_event_id(_CANONICAL_ID, _SOURCE_TYPE, _EXTERNAL_ID)
    signal_v2 = _make_signal(
        event_id_v2,
        compute_extraction_id(event_id_v2, _SCHEMA_VERSION, _PROMPT_V2, _PREFILTER_VERSION, _MODEL),
    )
    runner_v2, _, extractor_v2, _ = _make_runner(signal=signal_v2)
    result_v2 = runner_v2.run(
        source_type=_SOURCE_TYPE,
        prompt_version=_PROMPT_V2,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    published_v1: ResearchSignalEvent = extractor_v1.extract.return_value
    published_v2: ResearchSignalEvent = extractor_v2.extract.return_value
    assert published_v1.event_id == published_v2.event_id
    assert result_v1["published"] == 1
    assert result_v2["published"] == 1


def test_extraction_id_changes_on_prompt_version_change() -> None:
    event_id = compute_event_id(_CANONICAL_ID, _SOURCE_TYPE, _EXTERNAL_ID)
    extraction_id_v1 = compute_extraction_id(
        event_id, _SCHEMA_VERSION, _PROMPT_V1, _PREFILTER_VERSION, _MODEL
    )
    extraction_id_v2 = compute_extraction_id(
        event_id, _SCHEMA_VERSION, _PROMPT_V2, _PREFILTER_VERSION, _MODEL
    )
    assert extraction_id_v1 != extraction_id_v2


def test_publishes_to_signals_extracted_topic() -> None:
    runner, _, _extractor, producer = _make_runner()

    runner.run(
        source_type=_SOURCE_TYPE,
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    producer.publish_signal.assert_called_once()
    signal_arg: ResearchSignalEvent = producer.publish_signal.call_args[0][0]
    assert isinstance(signal_arg, ResearchSignalEvent)
    producer.flush.assert_called_once()


def test_dry_run_does_not_call_llm_or_publish() -> None:
    runner, _, extractor, producer = _make_runner()

    result = runner.run(
        source_type=_SOURCE_TYPE,
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
        dry_run=True,
    )

    extractor.extract.assert_not_called()
    producer.publish_signal.assert_not_called()
    producer.flush.assert_not_called()
    assert result["scanned"] == 1


def test_dry_run_returns_estimated_document_count() -> None:
    docs = [_make_archived_json(external_id=f"ext-{i}") for i in range(3)]
    runner, _, _, _ = _make_runner(archived_docs=docs)

    result = runner.run(
        source_type=_SOURCE_TYPE,
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
        dry_run=True,
    )

    assert result["scanned"] == 3


def test_source_type_filter_restricts_listed_keys() -> None:
    runner, archive, _, _ = _make_runner()

    runner.run(
        source_type="biorxiv",
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    archive.list_raw_keys.assert_called_once_with("biorxiv")


def test_since_filter_excludes_documents_before_date() -> None:
    doc = _make_archived_json(published_date=_T_BEFORE)
    runner, _, extractor, _ = _make_runner(archived_docs=[doc])

    result = runner.run(
        source_type=_SOURCE_TYPE,
        since="2024-06-10",
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    extractor.extract.assert_not_called()
    assert result["skipped_by_filter"] == 1


def test_until_filter_excludes_documents_after_date() -> None:
    doc = _make_archived_json(published_date=_T_AFTER)
    runner, _, extractor, _ = _make_runner(archived_docs=[doc])

    result = runner.run(
        source_type=_SOURCE_TYPE,
        until="2024-06-20",
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    extractor.extract.assert_not_called()
    assert result["skipped_by_filter"] == 1


def test_non_signal_document_increments_not_signal_counter() -> None:
    runner, _, extractor, producer = _make_runner()
    extractor.extract.return_value = None

    result = runner.run(
        source_type=_SOURCE_TYPE,
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    producer.publish_signal.assert_not_called()
    assert result["not_signal"] == 1
    assert result["published"] == 0


def test_per_document_failure_does_not_abort_run() -> None:
    docs = [_make_archived_json(external_id=f"ext-{i}") for i in range(3)]
    event_id = compute_event_id(_CANONICAL_ID, _SOURCE_TYPE, _EXTERNAL_ID)
    extraction_id = compute_extraction_id(
        event_id, _SCHEMA_VERSION, _PROMPT_V1, _PREFILTER_VERSION, _MODEL
    )
    good_signal = _make_signal(event_id, extraction_id)

    runner, _, _extractor, _ = _make_runner(
        archived_docs=docs,
        extractor_returns=[RuntimeError("boom"), good_signal, good_signal],
    )

    result = runner.run(
        source_type=_SOURCE_TYPE,
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    assert result["failed"] == 1
    assert result["published"] == 2


def test_runner_never_writes_to_airflow_or_cursor() -> None:
    runner, archive, _, _ = _make_runner()

    runner.run(
        source_type=_SOURCE_TYPE,
        prompt_version=_PROMPT_V1,
        model=_MODEL,
        schema_version=_SCHEMA_VERSION,
        prefilter_version=_PREFILTER_VERSION,
    )

    # archive.put and put_canonical_marker must never be called during re-extraction
    archive.put.assert_not_called()
    archive.put_canonical_marker.assert_not_called()
