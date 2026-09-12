"""Step 2.2 — Academic Papers Connector tests.

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

from auspex_ingest.connectors.biorxiv import BiorxivConnector
from auspex_ingest.connectors.pubmed import PubmedConnector
from auspex_ingest.identity import compute_event_id
from auspex_ingest.models import RawDocument
from auspex_ingest.normalizer import IdentityNormalizer
from auspex_ingest.rate_limited_client import RateLimitedClient


_FIXTURES = Path(__file__).parent.parent / "fixtures"
_BIORXIV_PAGE1 = json.loads((_FIXTURES / "biorxiv_page1.json").read_text())
_BIORXIV_EMPTY = json.loads((_FIXTURES / "biorxiv_empty.json").read_text())
_BIORXIV_V2 = json.loads((_FIXTURES / "biorxiv_v2.json").read_text())
_PUBMED_ESEARCH = json.loads((_FIXTURES / "pubmed_esearch.json").read_text())
_PUBMED_EFETCH = (_FIXTURES / "pubmed_efetch.xml").read_text()

_CURSOR = datetime(2024, 6, 8, tzinfo=UTC)
_NOW = datetime(2024, 6, 15, tzinfo=UTC)


def _biorxiv(server: str = "biorxiv", rate: float = 1_000.0, **kwargs) -> BiorxivConnector:
    client = RateLimitedClient({"api.biorxiv.org": rate})
    return BiorxivConnector(client=client, server=server, now=lambda: _NOW, **kwargs)


def _pubmed(**kwargs) -> PubmedConnector:
    client = RateLimitedClient({"eutils.ncbi.nlm.nih.gov": 3.0})
    return PubmedConnector(client=client, search_term="gene therapy", now=lambda: _NOW, **kwargs)


# ---------------------------------------------------------------------------
# bioRxiv
# ---------------------------------------------------------------------------

@respx.mock
def test_biorxiv_payload_maps_to_rawdocument():
    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv").mock(
        return_value=Response(200, json=_BIORXIV_PAGE1)
    )
    docs = list(_biorxiv().fetch_since(_CURSOR))
    assert len(docs) == 2
    doc = docs[0]
    assert isinstance(doc, RawDocument)
    assert doc.source_type == "biorxiv"
    assert doc.external_id == "biorxiv:10.1101/2024.06.01.001:v1"
    assert "BCL11A erythroid enhancer" in doc.raw_content
    assert "base editing" in doc.raw_content


@respx.mock
def test_published_date_is_the_public_posting_date_not_retrieved_at():
    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv").mock(
        return_value=Response(200, json=_BIORXIV_PAGE1)
    )
    docs = list(_biorxiv().fetch_since(_CURSOR))
    assert docs[0].published_date == datetime(2024, 6, 10, tzinfo=UTC)
    assert docs[0].published_date != docs[0].retrieved_at


@respx.mock
def test_doi_is_set_as_typed_canonical_id():
    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv").mock(
        return_value=Response(200, json=_BIORXIV_PAGE1)
    )
    docs = list(_biorxiv().fetch_since(_CURSOR))
    assert docs[0].canonical_id == "doi:10.1101/2024.06.01.001"
    assert docs[1].canonical_id == "doi:10.1101/2024.06.02.002"


@respx.mock
def test_missing_author_corresponding_and_missing_category_do_not_crash_mapping():
    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv").mock(
        return_value=Response(200, json=_BIORXIV_PAGE1)
    )
    docs = list(_biorxiv().fetch_since(_CURSOR))
    # second item has author_corresponding=null, category=null
    doc = docs[1]
    assert doc.external_id == "biorxiv:10.1101/2024.06.02.002:v2"
    assert isinstance(doc, RawDocument)


@respx.mock
def test_empty_result_set_yields_no_documents_and_no_error():
    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv").mock(
        return_value=Response(200, json=_BIORXIV_EMPTY)
    )
    docs = list(_biorxiv().fetch_since(_CURSOR))
    assert docs == []


@respx.mock
def test_new_biorxiv_version_of_the_same_doi_is_an_amendment_not_a_duplicate():
    """v1 and v2 share canonical_id (same DOI) but differ in external_id."""
    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv/2024-06-08").mock(
        return_value=Response(200, json=_BIORXIV_PAGE1)
    )
    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv/2024-06-15").mock(
        return_value=Response(200, json=_BIORXIV_V2)
    )
    cursor_v1 = datetime(2024, 6, 8, tzinfo=UTC)
    cursor_v2 = datetime(2024, 6, 15, tzinfo=UTC)

    client1 = RateLimitedClient({"api.biorxiv.org": 1_000.0})
    client2 = RateLimitedClient({"api.biorxiv.org": 1_000.0})
    conn_v1 = BiorxivConnector(client=client1, now=lambda: datetime(2024, 6, 15, tzinfo=UTC))
    conn_v2 = BiorxivConnector(client=client2, now=lambda: datetime(2024, 6, 20, tzinfo=UTC))
    docs_v1 = list(conn_v1.fetch_since(cursor_v1))
    docs_v2 = list(conn_v2.fetch_since(cursor_v2))

    doi_docs_v1 = [d for d in docs_v1 if "10.1101/2024.06.01.001" in d.external_id]
    doi_docs_v2 = [d for d in docs_v2 if "10.1101/2024.06.01.001" in d.external_id]
    assert len(doi_docs_v1) == 1
    assert len(doi_docs_v2) == 1

    assert doi_docs_v1[0].external_id != doi_docs_v2[0].external_id
    assert doi_docs_v1[0].canonical_id == doi_docs_v2[0].canonical_id == "doi:10.1101/2024.06.01.001"


@respx.mock
def test_non_utc_source_date_is_converted():
    """bioRxiv returns date-only strings; connector must parse them as UTC midnight."""
    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv").mock(
        return_value=Response(200, json=_BIORXIV_PAGE1)
    )
    docs = list(_biorxiv().fetch_since(_CURSOR))
    for doc in docs:
        assert doc.published_date.tzinfo is not None
        assert doc.published_date.tzinfo == UTC


@respx.mock
def test_http_429_is_retried_after_the_limiter_backs_off():
    calls = 0

    def side_effect(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return Response(429, headers={"Retry-After": "0"})
        return Response(200, json=_BIORXIV_PAGE1)

    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv").mock(side_effect=side_effect)

    slept: list[float] = []
    docs = list(_biorxiv(sleep=lambda s: slept.append(s)).fetch_since(_CURSOR))
    assert len(docs) == 2
    assert calls == 2
    assert len(slept) >= 1


@respx.mock
def test_http_500_surfaces_as_task_failure():
    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv").mock(
        return_value=Response(500)
    )
    with pytest.raises(Exception):  # noqa: B017
        list(_biorxiv().fetch_since(_CURSOR))


# ---------------------------------------------------------------------------
# PubMed
# ---------------------------------------------------------------------------

@respx.mock
def test_pubmed_payload_maps_to_rawdocument():
    respx.get(url__regex=r"eutils\.ncbi\.nlm\.nih\.gov/entrez/eutils/esearch").mock(
        return_value=Response(200, json=_PUBMED_ESEARCH)
    )
    respx.get(url__regex=r"eutils\.ncbi\.nlm\.nih\.gov/entrez/eutils/efetch").mock(
        return_value=Response(200, text=_PUBMED_EFETCH)
    )
    docs = list(_pubmed().fetch_since(_CURSOR))
    assert len(docs) == 1
    doc = docs[0]
    assert isinstance(doc, RawDocument)
    assert doc.source_type == "pubmed"
    assert doc.external_id == "pubmed:38855120"
    assert "BCL11A erythroid enhancer" in doc.raw_content


@respx.mock
def test_same_paper_from_biorxiv_and_pubmed_produces_one_event_id_and_two_source_observations():
    """Same DOI → same canonical_id → same event_id via compute_event_id."""
    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv").mock(
        return_value=Response(200, json=_BIORXIV_PAGE1)
    )
    respx.get(url__regex=r"eutils\.ncbi\.nlm\.nih\.gov/entrez/eutils/esearch").mock(
        return_value=Response(200, json=_PUBMED_ESEARCH)
    )
    respx.get(url__regex=r"eutils\.ncbi\.nlm\.nih\.gov/entrez/eutils/efetch").mock(
        return_value=Response(200, text=_PUBMED_EFETCH)
    )

    biorxiv_docs = list(_biorxiv().fetch_since(_CURSOR))
    pubmed_docs = list(_pubmed().fetch_since(_CURSOR))

    biorxiv_doc = next(d for d in biorxiv_docs if d.canonical_id == "doi:10.1101/2024.06.01.001")
    pubmed_doc = next(d for d in pubmed_docs if d.canonical_id == "doi:10.1101/2024.06.01.001")

    assert biorxiv_doc.external_id != pubmed_doc.external_id
    assert biorxiv_doc.canonical_id == pubmed_doc.canonical_id

    biorxiv_event_id = compute_event_id(biorxiv_doc.canonical_id, biorxiv_doc.source_type, biorxiv_doc.external_id)
    pubmed_event_id = compute_event_id(pubmed_doc.canonical_id, pubmed_doc.source_type, pubmed_doc.external_id)
    assert biorxiv_event_id == pubmed_event_id


@respx.mock
def test_connector_runs_through_the_unchanged_ingestion_pipeline():
    """BiorxivConnector integrates with IngestionPipeline without any pipeline modification."""
    from auspex_ingest.pipeline import IngestionPipeline
    from auspex_ingest.prefilter import Prefilter

    respx.get(url__regex=r"api\.biorxiv\.org/details/biorxiv").mock(
        return_value=Response(200, json=_BIORXIV_PAGE1)
    )

    client = RateLimitedClient({"api.biorxiv.org": 1.0})
    connector = BiorxivConnector(client=client, now=lambda: _NOW)

    archive = MagicMock()
    archive.put.return_value = ("raw/biorxiv/key.json", b"")
    extractor = MagicMock()
    extractor.extract.return_value = None
    producer = MagicMock()

    pipeline = IngestionPipeline(
        connector=connector,
        archive=archive,
        extractor=extractor,
        producer=producer,
        prefilter=Prefilter.from_vocab(set()),
        normalizer=IdentityNormalizer(),
        now=lambda: _NOW,
    )

    result = pipeline.run("biorxiv", _CURSOR)
    assert result.fetched == 2
    assert result.failed == 0
