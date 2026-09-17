"""Unit tests — EPO OPS patent connector."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import respx
from httpx import Response

from auspex_ingest.connectors.epo_ops import EpoOpsConnector
from auspex_ingest.identity import compute_event_id, compute_extraction_id
from auspex_ingest.models import RawDocument, ResearchSignalEvent
from auspex_ingest.normalizer import IdentityNormalizer
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter
from auspex_ingest.rate_limited_client import RateLimitedClient
from auspex_ingest.storage.minio_client import minio_key

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_SEARCH_REFS = (_FIXTURES / "epo_ops_search_refs.xml").read_bytes()
_BIBLIO_PAGE1 = (_FIXTURES / "epo_ops_biblio_page1.xml").read_bytes()
_SEARCH_EMPTY = (_FIXTURES / "epo_ops_search_empty.xml").read_bytes()
_TOKEN_JSON = json.loads((_FIXTURES / "epo_ops_token.json").read_text())

_CURSOR = datetime(2024, 9, 1, tzinfo=UTC)
_NOW = datetime(2024, 9, 10, tzinfo=UTC)


def _make_connector(**kwargs) -> EpoOpsConnector:
    defaults: dict = {
        "client": RateLimitedClient({"ops.epo.org": 1_000.0}),
        "key": "test-key",
        "secret": "test-secret",
        "now": lambda: _NOW,
    }
    return EpoOpsConnector(**(defaults | kwargs))


def _mock_token() -> respx.Route:
    return respx.post(url__regex=r"accesstoken").mock(
        return_value=Response(200, json=_TOKEN_JSON)
    )


def _mock_empty_search() -> respx.Route:
    return respx.get(url__regex=r"published-data/search").mock(
        return_value=Response(404, content=_SEARCH_EMPTY)
    )



_NS_DECL = (
    'xmlns="http://www.epo.org/exchange" '
    'xmlns:ops="http://ops.epo.org" '
    'xmlns:xlink="http://www.w3.org/1999/xlink"'
)


def _biblio_xml(
    *,
    pub_country: str = "EP",
    pub_number: str = "4100001",
    pub_kind: str = "A1",
    pub_date: str = "20230915",
    app_country: str = "EP",
    app_number: str = "22000001",
    app_date: str = "20220315",
    title: str = "Gene therapy composition for treating DMD",
    abstract: str = "A novel AAV-based gene therapy for Duchenne muscular dystrophy.",
    applicants: str = "SAREPTA THERAPEUTICS INC",
    family_id: str = "99000001",
) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data {_NS_DECL}>
    <exchange-documents>
        <exchange-document system="ops.epo.org" family-id="{family_id}"
                country="{pub_country}" doc-number="{pub_number}" kind="{pub_kind}">
            <bibliographic-data>
                <publication-reference>
                    <document-id document-id-type="docdb">
                        <country>{pub_country}</country>
                        <doc-number>{pub_number}</doc-number>
                        <kind>{pub_kind}</kind>
                        <date>{pub_date}</date>
                    </document-id>
                </publication-reference>
                <application-reference>
                    <document-id document-id-type="docdb">
                        <country>{app_country}</country>
                        <doc-number>{app_number}</doc-number>
                        <kind>A</kind>
                        <date>{app_date}</date>
                    </document-id>
                </application-reference>
                <invention-title lang="en">{title}</invention-title>
                <parties>
                    <applicants>
                        <applicant sequence="1" data-format="epodoc">
                            <applicant-name><name>{applicants}</name></applicant-name>
                        </applicant>
                    </applicants>
                </parties>
            </bibliographic-data>
            <abstract lang="en">
                <p>{abstract}</p>
            </abstract>
        </exchange-document>
    </exchange-documents>
</ops:world-patent-data>""".encode()


def _search_refs_xml(refs: list[tuple[str, str, str]]) -> bytes:
    """refs: list of (country, doc_number, kind)"""
    pub_refs = "".join(
        f"""<ops:publication-reference system="ops.epo.org" family-id="1">
                <document-id document-id-type="docdb">
                    <country>{c}</country>
                    <doc-number>{n}</doc-number>
                    <kind>{k}</kind>
                </document-id>
            </ops:publication-reference>"""
        for c, n, k in refs
    )
    total = len(refs)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data {_NS_DECL}>
    <ops:biblio-search total-result-count="{total}" publications-count="{total}">
        <ops:range begin="1" end="100"/>
        <ops:search-result>
            {pub_refs}
        </ops:search-result>
    </ops:biblio-search>
</ops:world-patent-data>""".encode()



class _FakeArchive:
    def __init__(self) -> None:
        self.puts: list[RawDocument] = []
        self._canonical_markers: dict[str, dict] = {}

    def put(self, doc: RawDocument) -> tuple[str, bool]:
        self.puts.append(doc)
        return minio_key(doc), True

    def get_canonical_marker(self, canonical_id: str) -> dict | None:
        return self._canonical_markers.get(canonical_id)

    def put_canonical_marker(self, canonical_id: str, data: dict) -> None:
        self._canonical_markers[canonical_id] = data


class _FakeExtractor:
    def __init__(self, responses: list[ResearchSignalEvent | None]) -> None:
        self._responses = iter(responses)

    def extract(self, doc: RawDocument, prefilter_version: str,
                raw_object_key: str) -> ResearchSignalEvent | None:
        return next(self._responses, None)


class _FakeProducer:
    def __init__(self) -> None:
        self.published: int = 0

    def publish_raw(self, doc: RawDocument, raw_object_key: str, schema_version: str) -> None:
        self.published += 1

    def publish_signal(self, event: ResearchSignalEvent) -> None:
        pass

    def flush(self) -> None:
        pass


def _make_event(doc: RawDocument) -> ResearchSignalEvent:
    event_id = compute_event_id(doc.canonical_id, doc.source_type, doc.external_id)
    extraction_id = compute_extraction_id(event_id, "1.0", "v1", "v1", "gpt-4o-mini")
    return ResearchSignalEvent(
        schema_version="1.0",
        event_id=event_id,
        extraction_id=extraction_id,
        external_id=doc.external_id,
        canonical_id=doc.canonical_id,
        raw_object_key=f"raw/{doc.source_type}/{doc.external_id}/stub.json",
        source_type=doc.source_type,
        source_url=doc.source_url,
        published_date=doc.published_date,
        published_date_field="date_published",
        ingested_at=_NOW,
        title="Gene therapy for DMD",
        raw_text_snippet="DMD gene therapy trial results",
        gene_targets=["DMD"],
        mechanisms=["gene therapy"],
        companies_mentioned=["Sarepta"],
        summary="DMD gene therapy",
        directionality="positive",
        confidence_score=0.9,
        prompt_version="v1",
        prefilter_version="v1",
        extraction_model="gpt-4o-mini",
    )



@respx.mock
def test_epo_payload_maps_to_rawdocument():
    _mock_token()
    respx.get(url__regex=r"published-data/search").mock(
        return_value=Response(200, content=_SEARCH_REFS)
    )
    respx.get(url__regex=r"/biblio").mock(
        return_value=Response(200, content=_BIBLIO_PAGE1)
    )

    docs = list(_make_connector().fetch_since(_CURSOR))

    assert len(docs) == 2
    doc = docs[0]
    assert isinstance(doc, RawDocument)
    assert doc.source_type == "epo_ops"
    assert doc.schema_version == "1.0"
    assert doc.external_id == "CN-118615435-A"
    assert doc.canonical_id == "epo-app:CN-202410078858"
    assert doc.published_date == datetime(2024, 9, 10, tzinfo=UTC)
    assert doc.content_sha256 == hashlib.sha256(doc.raw_content.encode()).hexdigest()
    assert doc.retrieved_at == _NOW
    assert "ops.epo.org" in doc.source_url


@respx.mock
def test_published_date_is_the_public_disclosure_date_not_filing_date():
    _mock_token()
    respx.get(url__regex=r"published-data/search").mock(
        return_value=Response(200, content=_search_refs_xml([("EP", "4100001", "A1")]))
    )
    # pub_date 2023-09-15, filing_date 2022-03-15 — ~18-month gap
    respx.get(url__regex=r"/biblio").mock(
        return_value=Response(200, content=_biblio_xml(
            pub_country="EP", pub_number="4100001", pub_kind="A1",
            pub_date="20230915", app_date="20220315",
        ))
    )

    docs = list(_make_connector().fetch_since(_CURSOR))

    assert len(docs) == 1
    doc = docs[0]
    assert doc.published_date == datetime(2023, 9, 15, tzinfo=UTC)
    assert doc.published_date.year != 2022, "must not use filing year"


@respx.mock
def test_filing_date_and_granted_date_are_retained_in_raw_content_but_excluded_from_alignment():
    _mock_token()
    respx.get(url__regex=r"published-data/search").mock(
        return_value=Response(200, content=_search_refs_xml([("EP", "4200001", "B1")]))
    )
    respx.get(url__regex=r"/biblio").mock(
        return_value=Response(200, content=_biblio_xml(
            pub_country="EP", pub_number="4200001", pub_kind="B1",
            pub_date="20260115",  # grant date
            app_date="20220301",  # filing date
        ))
    )

    docs = list(_make_connector().fetch_since(_CURSOR))

    assert len(docs) == 1
    doc = docs[0]
    # Both dates in raw_content
    assert "Filed:" in doc.raw_content
    assert "Granted:" in doc.raw_content
    # published_date = the publication date (grant date), NOT the filing date
    assert doc.published_date == datetime(2026, 1, 15, tzinfo=UTC)
    assert doc.published_date != datetime(2022, 3, 1, tzinfo=UTC)


@respx.mock
def test_pregrant_publication_and_its_later_grant_resolve_to_one_event_id():
    _mock_token()

    a1_xml = _biblio_xml(
        pub_country="EP", pub_number="4100001", pub_kind="A1",
        pub_date="20230915", app_country="EP", app_number="22000001",
        app_date="20220315", family_id="99000001",
    )
    b1_xml = _biblio_xml(
        pub_country="EP", pub_number="4200001", pub_kind="B1",
        pub_date="20260115", app_country="EP", app_number="22000001",
        app_date="20220315", family_id="99000001",
    )

    search_a1 = _search_refs_xml([("EP", "4100001", "A1")])
    search_b1 = _search_refs_xml([("EP", "4200001", "B1")])

    search_route = respx.get(url__regex=r"published-data/search")
    biblio_route = respx.get(url__regex=r"/biblio")

    search_route.mock(side_effect=[
        Response(200, content=search_a1),
        Response(200, content=search_b1),
    ])
    biblio_route.mock(side_effect=[
        Response(200, content=a1_xml),
        Response(200, content=b1_xml),
    ])

    connector = _make_connector()
    [a1_doc] = list(connector.fetch_since(_CURSOR))
    [b1_doc] = list(connector.fetch_since(_CURSOR))

    assert a1_doc.canonical_id == b1_doc.canonical_id
    assert a1_doc.canonical_id == "epo-app:EP-22000001"
    assert a1_doc.external_id != b1_doc.external_id


@respx.mock
def test_oauth_token_is_refreshed_before_expiry():
    time_value = [0.0]

    connector = _make_connector(mono_clock=lambda: time_value[0])

    token_route = respx.post(url__regex=r"accesstoken").mock(
        return_value=Response(200, json=_TOKEN_JSON)
    )
    respx.get(url__regex=r"published-data/search").mock(
        return_value=Response(404, content=_SEARCH_EMPTY)
    )

    list(connector.fetch_since(_CURSOR))
    assert token_route.call_count == 1

    # 70s before expiry (buffer is 60s) — token still valid
    time_value[0] = 1200 - 70  # = 1130s elapsed
    list(connector.fetch_since(_CURSOR))
    assert token_route.call_count == 1

    # 50s before expiry — within the 60s buffer, must refresh
    time_value[0] = 1200 - 50  # = 1150s elapsed
    list(connector.fetch_since(_CURSOR))
    assert token_route.call_count == 2


@respx.mock
def test_429_respects_the_retry_after_header():
    sleep_calls: list[float] = []
    connector = _make_connector(sleep=sleep_calls.append)

    _mock_token()
    respx.get(url__regex=r"published-data/search").mock(side_effect=[
        Response(429, headers={"Retry-After": "5"}),
        Response(200, content=_search_refs_xml([("EP", "4100001", "A1")])),
    ])
    respx.get(url__regex=r"/biblio").mock(
        return_value=Response(200, content=_biblio_xml())
    )

    docs = list(connector.fetch_since(_CURSOR))

    assert len(docs) == 1
    assert sleep_calls == [5.0]


def test_missing_credentials_fail_with_clear_message_not_deep_401():
    client = RateLimitedClient({"ops.epo.org": 1_000.0})
    with pytest.raises(ValueError, match="EPO_OPS_KEY"):
        EpoOpsConnector(client=client, key="", secret="any-secret")
    with pytest.raises(ValueError, match="EPO_OPS_SECRET"):
        EpoOpsConnector(client=client, key="any-key", secret="")


@respx.mock
def test_pending_filing_with_no_grant_date_is_handled():
    _mock_token()
    respx.get(url__regex=r"published-data/search").mock(
        return_value=Response(200, content=_search_refs_xml([("EP", "4100001", "A1")]))
    )
    # A1 kind — no grant date
    respx.get(url__regex=r"/biblio").mock(
        return_value=Response(200, content=_biblio_xml(
            pub_kind="A1", pub_date="20240601", app_date="20221201",
        ))
    )

    docs = list(_make_connector().fetch_since(_CURSOR))

    assert len(docs) == 1
    doc = docs[0]
    assert "Granted:" not in doc.raw_content
    assert "Filed:" in doc.raw_content


@respx.mock
def test_pct_application_with_us_and_ep_designations_produces_one_document():
    _mock_token()
    respx.get(url__regex=r"published-data/search").mock(
        return_value=Response(200, content=_search_refs_xml([("WO", "2024134855", "A1")]))
    )
    respx.get(url__regex=r"/biblio").mock(
        return_value=Response(200, content=_biblio_xml(
            pub_country="WO", pub_number="2024134855", pub_kind="A1",
            app_country="WO", app_number="2023US049123",
            pub_date="20240627", app_date="20231215",
        ))
    )

    docs = list(_make_connector().fetch_since(_CURSOR))

    assert len(docs) == 1
    doc = docs[0]
    assert doc.canonical_id is not None
    assert doc.canonical_id.startswith("epo-app:WO-")


@respx.mock
def test_connector_runs_through_the_ingestion_pipeline_unchanged():
    _mock_token()
    respx.get(url__regex=r"published-data/search").mock(
        return_value=Response(200, content=_SEARCH_REFS)
    )
    respx.get(url__regex=r"/biblio").mock(
        return_value=Response(200, content=_BIBLIO_PAGE1)
    )

    connector = _make_connector()
    archive = _FakeArchive()

    docs_preview = list(connector.fetch_since(_CURSOR))
    events = [_make_event(d) for d in docs_preview]

    respx.get(url__regex=r"published-data/search").mock(
        return_value=Response(200, content=_SEARCH_REFS)
    )
    respx.get(url__regex=r"/biblio").mock(
        return_value=Response(200, content=_BIBLIO_PAGE1)
    )

    pipeline = IngestionPipeline(
        connector=_make_connector(),
        archive=archive,
        extractor=_FakeExtractor(events),
        producer=_FakeProducer(),
        prefilter=Prefilter.from_vocab(set()),
        normalizer=IdentityNormalizer(),
        now=lambda: _NOW,
        min_confidence_to_publish=0.0,
    )

    result = pipeline.run("epo_ops", _CURSOR)

    assert result.fetched == 2
    assert result.failed == 0
    assert result.published == 2
