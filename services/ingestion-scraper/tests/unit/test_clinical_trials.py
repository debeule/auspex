
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import respx
from httpx import Response

from auspex_ingest.connectors import RateLimitedClient
from auspex_ingest.connectors.clinicaltrials import ClinicalTrialConnector
from auspex_ingest.identity import compute_event_id
from auspex_ingest.models import RawDocument
from auspex_ingest.normalizer import IdentityNormalizer
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter
from auspex_ingest.storage.minio_client import minio_key

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_PAGE1 = json.loads((_FIXTURES / "clinicaltrials_page1.json").read_text())
_EMPTY = json.loads((_FIXTURES / "clinicaltrials_empty.json").read_text())
_AMENDMENT = json.loads((_FIXTURES / "clinicaltrials_amendment.json").read_text())

_CURSOR = datetime(2024, 6, 8, tzinfo=UTC)
_NOW = datetime(2024, 6, 15, tzinfo=UTC)
_CT_URL = "https://clinicaltrials.gov/api/v2/studies"


def _connector(**kwargs) -> ClinicalTrialConnector:
    client = RateLimitedClient({"clinicaltrials.gov": 1_000.0})
    return ClinicalTrialConnector(client=client, now=lambda: _NOW, **kwargs)


class _FakeArchive:
    """Tracks puts; returns is_new=True the first time a content_sha256 is seen."""

    def __init__(self) -> None:
        self.puts: list[tuple[str, RawDocument]] = []
        self._seen: set[str] = set()

    def put(self, doc: RawDocument) -> tuple[str, bool]:
        key = minio_key(doc)
        is_new = doc.content_sha256 not in self._seen
        self._seen.add(doc.content_sha256)
        self.puts.append((key, doc))
        return key, is_new

    def get_canonical_marker(self, canonical_id: str) -> dict | None:
        return None

    def put_canonical_marker(self, canonical_id: str, data: dict) -> None:
        pass


class _CountingExtractor:
    def __init__(self) -> None:
        self.call_count = 0

    def extract(self, doc: RawDocument, prefilter_version: str, raw_object_key: str) -> None:
        self.call_count += 1



@respx.mock
def test_clinicaltrials_payload_maps_to_rawdocument():
    respx.get(_CT_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert len(docs) == 2
    doc = docs[0]
    assert isinstance(doc, RawDocument)
    assert doc.source_type == "clinicaltrials"
    assert doc.external_id == "clinicaltrials:NCT06123456"
    assert "BCL11A" in doc.raw_content
    assert "sickle cell" in doc.raw_content


@respx.mock
def test_nct_id_is_set_as_typed_canonical_id():
    respx.get(_CT_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs[0].canonical_id == "nct:NCT06123456"
    assert docs[1].canonical_id == "nct:NCT06234567"


@respx.mock
def test_published_date_is_the_public_posting_date_not_retrieved_at():
    respx.get(_CT_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    # First study: first post = last update = 2024-01-20 (new, not amended)
    assert docs[0].published_date == datetime(2024, 1, 20, tzinfo=UTC)
    assert docs[0].published_date != docs[0].retrieved_at


@respx.mock
def test_published_date_is_a_post_date_not_the_submission_date():
    """Submission date (studyFirstSubmitDate) is private; posting date is public."""
    respx.get(_CT_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    # First study: submitted 2024-01-15, posted 2024-01-20 — must use posted date
    assert docs[0].published_date == datetime(2024, 1, 20, tzinfo=UTC)
    assert docs[0].published_date != datetime(2024, 1, 15, tzinfo=UTC)


@respx.mock
def test_both_date_fields_retained_separately():
    """raw_content must include both the first-post date and the last-update date."""
    respx.get(_CT_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    # Second study: first posted 2024-02-10, last updated 2024-06-10
    amended = docs[1]
    assert "2024-02-10" in amended.raw_content
    assert "2024-06-10" in amended.raw_content


@respx.mock
def test_non_utc_source_date_is_converted():
    """API returns date-only strings; connector must parse them as UTC midnight."""
    respx.get(_CT_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    for doc in docs:
        assert doc.published_date.tzinfo is not None
        assert doc.published_date.tzinfo == UTC


@respx.mock
def test_missing_optional_fields_do_not_crash_mapping():
    payload = {
        "studies": [
            {
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT09999999", "briefTitle": "Minimal"},
                    "descriptionModule": {},
                    "statusModule": {
                        "overallStatus": "Unknown",
                        "studyFirstSubmitDate": "2024-01-01",
                        "studyFirstPostDateStruct": {"date": "2024-01-05", "type": "Actual"},
                        "lastUpdateSubmitDate": "2024-01-01",
                        "lastUpdatePostDateStruct": {"date": "2024-01-05", "type": "Actual"},
                    },
                }
            }
        ],
        "nextPageToken": None,
        "totalCount": 1,
    }
    respx.get(_CT_URL).mock(return_value=Response(200, json=payload))
    docs = list(_connector().fetch_since(_CURSOR))
    assert len(docs) == 1
    assert docs[0].external_id == "clinicaltrials:NCT09999999"



@respx.mock
def test_amended_trial_creates_a_new_snapshot_and_a_new_extraction_under_the_same_event_id():
    """Same NCT ID, updated content → same canonical_id/event_id, different content_sha256."""
    respx.get(_CT_URL).mock(
        side_effect=[
            Response(200, json=_PAGE1),
            Response(200, json=_AMENDMENT),
        ]
    )
    cursor1 = datetime(2024, 1, 15, tzinfo=UTC)
    cursor2 = datetime(2024, 6, 12, tzinfo=UTC)

    conn1 = ClinicalTrialConnector(
        client=RateLimitedClient({"clinicaltrials.gov": 1_000.0}),
        now=lambda: datetime(2024, 6, 10, tzinfo=UTC),
    )
    conn2 = ClinicalTrialConnector(
        client=RateLimitedClient({"clinicaltrials.gov": 1_000.0}),
        now=lambda: datetime(2024, 6, 20, tzinfo=UTC),
    )

    original = next(d for d in conn1.fetch_since(cursor1) if "NCT06123456" in d.external_id)
    amended = next(d for d in conn2.fetch_since(cursor2))

    assert original.external_id == amended.external_id == "clinicaltrials:NCT06123456"
    assert original.canonical_id == amended.canonical_id == "nct:NCT06123456"
    assert original.content_sha256 != amended.content_sha256

    original_event_id = compute_event_id(original.canonical_id, original.source_type, original.external_id)
    amended_event_id = compute_event_id(amended.canonical_id, amended.source_type, amended.external_id)
    assert original_event_id == amended_event_id


@respx.mock
def test_unchanged_refetch_is_archived_but_not_re_extracted():
    """Same study fetched twice: archived both times; extraction skipped on second (content unchanged)."""
    respx.get(_CT_URL).mock(return_value=Response(200, json=_AMENDMENT))

    archive = _FakeArchive()
    extractor = _CountingExtractor()
    producer = MagicMock()
    producer.flush.return_value = None

    conn = _connector()
    pipeline = IngestionPipeline(
        connector=conn,
        archive=archive,
        extractor=extractor,
        producer=producer,
        prefilter=Prefilter.from_vocab({"BCL11A"}),
        normalizer=IdentityNormalizer(),
        now=lambda: _NOW,
    )

    pipeline.run("clinicaltrials", _CURSOR)
    pipeline.run("clinicaltrials", _CURSOR)

    assert len(archive.puts) == 2          # archived unconditionally both times
    assert extractor.call_count == 1       # extracted only on first (content unchanged second time)



@respx.mock
def test_http_429_is_retried_after_the_limiter_backs_off():
    calls = 0

    def side_effect(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return Response(429, headers={"Retry-After": "0"})
        return Response(200, json=_PAGE1)

    respx.get(_CT_URL).mock(side_effect=side_effect)

    slept: list[float] = []
    docs = list(_connector(sleep=lambda s: slept.append(s)).fetch_since(_CURSOR))
    assert len(docs) == 2
    assert calls == 2
    assert len(slept) >= 1


@respx.mock
def test_http_500_surfaces_as_task_failure():
    respx.get(_CT_URL).mock(return_value=Response(500))
    with pytest.raises(Exception):  # noqa: B017
        list(_connector().fetch_since(_CURSOR))


@respx.mock
def test_empty_result_set_yields_no_documents_and_no_error():
    respx.get(_CT_URL).mock(return_value=Response(200, json=_EMPTY))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs == []



@respx.mock
def test_connector_runs_through_the_unchanged_ingestion_pipeline():
    """ClinicalTrialConnector integrates with IngestionPipeline without any pipeline modification."""
    respx.get(_CT_URL).mock(return_value=Response(200, json=_PAGE1))

    archive = _FakeArchive()
    extractor = MagicMock()
    extractor.extract.return_value = None
    producer = MagicMock()

    pipeline = IngestionPipeline(
        connector=_connector(),
        archive=archive,
        extractor=extractor,
        producer=producer,
        prefilter=Prefilter.from_vocab(set()),
        normalizer=IdentityNormalizer(),
        now=lambda: _NOW,
    )

    result = pipeline.run("clinicaltrials", _CURSOR)
    assert result.fetched == 2
    assert result.failed == 0
