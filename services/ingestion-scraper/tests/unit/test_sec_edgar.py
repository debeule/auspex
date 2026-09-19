"""SEC EDGAR material disclosures connector tests.

All HTTP calls are intercepted by respx. pytest-socket ensures no live calls.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import respx
from httpx import Response

from auspex_ingest.connectors import RateLimitedClient, RateLimitExceeded
from auspex_ingest.connectors import sec_edgar as _sec_edgar_module
from auspex_ingest.connectors.sec_edgar import SecEdgarConnector
from auspex_ingest.models import RawDocument
from auspex_ingest.normalizer import IdentityNormalizer
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter
from auspex_ingest.storage.minio_client import minio_key

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_PAGE1 = json.loads((_FIXTURES / "edgar_efts_page1.json").read_text())
_EMPTY = json.loads((_FIXTURES / "edgar_efts_empty.json").read_text())
_MULTI_ITEM = json.loads((_FIXTURES / "edgar_efts_multi_item.json").read_text())

_CURSOR = datetime(2024, 6, 1, tzinfo=UTC)
_NOW = datetime(2024, 6, 20, tzinfo=UTC)
_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
_TEST_USER_AGENT = "Auspex-Test/1.0 (test@example.com)"


def _connector(**kwargs) -> SecEdgarConnector:
    client = RateLimitedClient({"efts.sec.gov": 1_000.0})
    return SecEdgarConnector(
        client=client,
        user_agent=_TEST_USER_AGENT,
        now=lambda: _NOW,
        **kwargs,
    )


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
def test_efts_payload_maps_to_rawdocument():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert len(docs) == 2
    doc = docs[0]
    assert isinstance(doc, RawDocument)
    assert doc.source_type == "edgar"
    assert "BEAM THERAPEUTICS" in doc.raw_content
    assert "0001821552-24-000034" in doc.raw_content


@respx.mock
def test_canonical_id_uses_edgar_prefix():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs[0].canonical_id == "edgar:0001821552-24-000034"
    assert docs[1].canonical_id == "edgar:0001253986-24-000018"


@respx.mock
def test_external_id_is_the_accession_number():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs[0].external_id == "edgar:0001821552-24-000034"


@respx.mock
def test_published_date_is_the_file_date_not_retrieved_at():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs[0].published_date == datetime(2024, 6, 15, tzinfo=UTC)
    assert docs[0].published_date != docs[0].retrieved_at


@respx.mock
def test_non_utc_source_date_is_converted():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    for doc in docs:
        assert doc.published_date.tzinfo is not None
        assert doc.published_date.tzinfo == UTC


@respx.mock
def test_empty_result_set_yields_no_documents_and_no_error():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_EMPTY))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs == []



@respx.mock
def test_user_agent_header_sent_on_every_request_including_retries():
    calls = 0
    seen_user_agents: list[str] = []

    def side_effect(request):
        nonlocal calls
        calls += 1
        seen_user_agents.append(request.headers.get("user-agent", ""))
        if calls == 1:
            return Response(403)
        return Response(200, json=_PAGE1)

    respx.get(_EFTS_URL).mock(side_effect=side_effect)
    list(_connector(sleep=lambda _: None).fetch_since(_CURSOR))

    assert calls == 2
    assert all(ua == _TEST_USER_AGENT for ua in seen_user_agents)


def test_user_agent_is_a_named_constant():
    assert hasattr(_sec_edgar_module, "_USER_AGENT")
    assert isinstance(_sec_edgar_module._USER_AGENT, str)


def test_sec_hosts_share_one_rate_limit_bucket():
    """A single 'sec.gov' bucket covers all *.sec.gov subdomains."""
    t = 0.0
    client = RateLimitedClient({"sec.gov": 1.0}, _clock=lambda: t)
    client._acquire("https://efts.sec.gov/LATEST/search-index")
    with pytest.raises(RateLimitExceeded):
        client._acquire("https://data.sec.gov/submissions/CIK0001821552.json")


@respx.mock
def test_8k_with_multiple_items_yields_one_document_not_one_per_item():
    """An 8-K with items '1.01, 2.01, 8.01' is still one filing — one doc."""
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_MULTI_ITEM))
    docs = list(_connector().fetch_since(_CURSOR))
    assert len(docs) == 1
    assert "1.01, 2.01, 8.01" in docs[0].raw_content


@respx.mock
def test_403_is_treated_as_a_block_and_backs_off_before_retrying():
    """403 from SEC signals an IP block — must sleep before retrying, not fail immediately."""
    calls = 0

    def side_effect(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return Response(403)
        return Response(200, json=_PAGE1)

    respx.get(_EFTS_URL).mock(side_effect=side_effect)
    slept: list[float] = []
    docs = list(_connector(sleep=lambda s: slept.append(s)).fetch_since(_CURSOR))
    assert len(docs) == 2
    assert calls == 2
    assert len(slept) >= 1
    assert slept[0] > 0



@respx.mock
def test_http_500_surfaces_as_task_failure():
    respx.get(_EFTS_URL).mock(return_value=Response(500))
    with pytest.raises(Exception):  # noqa: B017
        list(_connector().fetch_since(_CURSOR))



@respx.mock
def test_connector_runs_through_the_unchanged_ingestion_pipeline():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_PAGE1))

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

    result = pipeline.run("edgar", _CURSOR)
    assert result.fetched == 2
    assert result.failed == 0
