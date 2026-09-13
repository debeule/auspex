"""FDA drugsfda regulatory connector tests.

All HTTP calls are intercepted by respx before they reach the socket layer.
pytest-socket ensures no real network calls can slip through.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import respx
from httpx import Response

from auspex_ingest.connectors.fda_approval import FdaApprovalConnector, QuotaExhaustedError
from auspex_ingest.models import RawDocument
from auspex_ingest.normalizer import IdentityNormalizer
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter
from auspex_ingest.rate_limited_client import RateLimitedClient
from auspex_ingest.storage.minio_client import minio_key

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_PAGE1 = json.loads((_FIXTURES / "fda_drugsfda_page1.json").read_text())
_404 = json.loads((_FIXTURES / "fda_drugsfda_404.json").read_text())
_429 = json.loads((_FIXTURES / "fda_drugsfda_429.json").read_text())

_CURSOR = datetime(2024, 6, 1, tzinfo=UTC)
_NOW = datetime(2024, 6, 20, tzinfo=UTC)
_FDA_URL = "https://api.fda.gov/drug/drugsfda.json"


def _connector(**kwargs) -> FdaApprovalConnector:
    client = RateLimitedClient({"api.fda.gov": 1_000.0})
    return FdaApprovalConnector(client=client, now=lambda: _NOW, **kwargs)


class _FakeArchive:
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



@respx.mock
def test_fda_payload_maps_to_rawdocument():
    respx.get(_FDA_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert len(docs) == 2
    doc = docs[0]
    assert isinstance(doc, RawDocument)
    assert doc.source_type == "fda_approval"
    assert "NDA021029" in doc.raw_content
    assert "BEAM THERAPEUTICS" in doc.raw_content


@respx.mock
def test_published_date_is_the_action_date_not_retrieved_at():
    respx.get(_FDA_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs[0].published_date == datetime(2024, 6, 15, tzinfo=UTC)
    assert docs[0].published_date != docs[0].retrieved_at


@respx.mock
def test_canonical_id_uses_fda_prefix():
    respx.get(_FDA_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs[0].canonical_id == "fda:NDA021029"
    assert docs[1].canonical_id == "fda:BLA125514"


@respx.mock
def test_external_id_encodes_application_and_submission():
    respx.get(_FDA_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs[0].external_id == "fda_approval:NDA021029:ORIG1"
    assert docs[1].external_id == "fda_approval:BLA125514:ORIG1"


@respx.mock
def test_non_utc_source_date_is_converted():
    """YYYYMMDD action_date strings must be parsed as UTC midnight."""
    respx.get(_FDA_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    for doc in docs:
        assert doc.published_date.tzinfo is not None
        assert doc.published_date.tzinfo == UTC


@respx.mock
def test_ap_action_type_appears_in_raw_content():
    """AP action type must appear as human-readable text in raw_content."""
    respx.get(_FDA_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert "Approved" in docs[0].raw_content


@respx.mock
def test_record_without_openfda_fields_still_ingests():
    """BLA125514 fixture has empty openfda — must not crash."""
    respx.get(_FDA_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    bla_doc = next(d for d in docs if "BLA125514" in d.external_id)
    assert bla_doc is not None
    assert bla_doc.canonical_id == "fda:BLA125514"



@respx.mock
def test_daily_quota_exhaustion_raises_quota_exhausted_error():
    """429 from openFDA is a daily hard limit — must raise, not retry."""
    respx.get(_FDA_URL).mock(return_value=Response(429, json=_429))
    with pytest.raises(QuotaExhaustedError):
        list(_connector().fetch_since(_CURSOR))


@respx.mock
def test_empty_result_set_yields_no_documents_and_no_error():
    """404 from openFDA means no matching records — must yield nothing."""
    respx.get(_FDA_URL).mock(return_value=Response(404, json=_404))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs == []


@respx.mock
def test_http_500_surfaces_as_task_failure():
    respx.get(_FDA_URL).mock(return_value=Response(500))
    with pytest.raises(Exception):  # noqa: B017
        list(_connector().fetch_since(_CURSOR))



@respx.mock
def test_connector_runs_through_the_unchanged_ingestion_pipeline():
    respx.get(_FDA_URL).mock(return_value=Response(200, json=_PAGE1))

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

    result = pipeline.run("fda_approval", _CURSOR)
    assert result.fetched == 2
    assert result.failed == 0
