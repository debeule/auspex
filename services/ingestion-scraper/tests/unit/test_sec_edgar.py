
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import respx
from httpx import Response

from auspex_ingest.connectors import RateLimitedClient
from auspex_ingest.connectors import sec_edgar as _sec_edgar_module
from auspex_ingest.connectors.sec_edgar import SecEdgarConnector, SecRequestRefused
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
def test_published_date_without_acceptance_time_is_the_file_date_after_the_filing_cutoff():
    """Without an acceptance time, the filing is only known to be public by 17:30 ET on its file date."""
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_PAGE1))
    docs = list(_connector().fetch_since(_CURSOR))
    assert docs[0].published_date == datetime(2024, 6, 15, 21, 30, tzinfo=UTC)
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
def test_user_agent_header_sent_on_every_request():
    seen_user_agents: list[str] = []

    def side_effect(request):
        seen_user_agents.append(request.headers.get("user-agent", ""))
        return Response(200, json=_PAGE1)

    respx.get(_EFTS_URL).mock(side_effect=side_effect)
    list(_connector().fetch_since(_CURSOR))

    assert seen_user_agents
    assert all(ua == _TEST_USER_AGENT for ua in seen_user_agents)


def test_user_agent_is_a_named_constant():
    assert hasattr(_sec_edgar_module, "_USER_AGENT")
    assert isinstance(_sec_edgar_module._USER_AGENT, str)


def test_sec_hosts_share_one_rate_limit_bucket():
    """A single 'sec.gov' bucket covers all *.sec.gov subdomains."""
    slept: list[float] = []
    client = RateLimitedClient({"sec.gov": 1.0}, _clock=lambda: 0.0, _sleep=slept.append)
    client._acquire("https://efts.sec.gov/LATEST/search-index")
    client._acquire("https://data.sec.gov/submissions/CIK0001821552.json")
    assert slept == [1.0]


@respx.mock
def test_8k_with_multiple_items_yields_one_document_not_one_per_item():
    """An 8-K with items '1.01, 2.01, 8.01' is still one filing — one doc."""
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_MULTI_ITEM))
    docs = list(_connector().fetch_since(_CURSOR))
    assert len(docs) == 1
    assert "1.01, 2.01, 8.01" in docs[0].raw_content


@respx.mock
def test_edgar_stops_on_a_refused_request_without_retrying():
    """A 403 from SEC means its IP block is on; another request only extends it."""
    search = respx.get(_EFTS_URL).mock(return_value=Response(403))

    with pytest.raises(SecRequestRefused):
        list(_connector().fetch_since(_CURSOR))

    assert search.call_count == 1


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


# ── document fetch ───────────────────────────────────────────────────────────

_INDEX_HTML = (_FIXTURES / "edgar_filing_index.htm").read_text()
_COVER_HTML = (_FIXTURES / "edgar_8k_cover.htm").read_text()
_EX99_HTML = (_FIXTURES / "edgar_ex99_1_readout.htm").read_text()


def _hit(adsh: str, cik: str, items: list[str], file_date: str = "2024-06-14", **extra) -> dict:
    return {
        "_source": {
            "ciks": [cik],
            "display_names": [f"EXAMPLE CO (EXMP)  (CIK {cik})"],
            "adsh": adsh,
            "file_date": file_date,
            "period_ending": file_date,
            "form": "8-K",
            "items": items,
            **extra,
        }
    }


def _efts(*hits: dict) -> dict:
    return {"hits": {"total": {"value": len(hits)}, "hits": list(hits)}}


def _index_url(cik: str, adsh: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{adsh}-index.htm"


def _minimal_index_html(cik: str, adsh: str, primary: str, accepted: str = "2024-06-14 16:05:23") -> str:
    path = f"/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{primary}"
    return (
        '<div class="formGrouping"><div class="infoHead">Accepted</div>'
        f'<div class="info">{accepted}</div></div>'
        '<table class="tableFile" summary="Document Format Files">'
        "<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>"
        f'<tr><td>1</td><td>8-K</td><td><a href="{path}">{primary}</a></td><td>8-K</td><td>100</td></tr>'
        "</table>"
    )


_BEAM_ADSH = "0001821552-24-000034"
_BEAM_CIK = "1821552"
_SINGLE_HIT_BEAM = _efts(_hit(_BEAM_ADSH, "0001821552", ["8.01"], file_date="2024-06-15"))
_BEAM_INDEX_URL = _index_url(_BEAM_CIK, _BEAM_ADSH)
_BEAM_DOC_URL = f"https://www.sec.gov/Archives/edgar/data/{_BEAM_CIK}/000182155224000034/beam-8k.htm"
_BEAM_INDEX_HTML = _minimal_index_html(_BEAM_CIK, _BEAM_ADSH, "beam-8k.htm")

# Filed through a filing agent: the accession prefix (0001193125) is the agent, not the company.
_NWGT_ADSH = "0001193125-24-161234"
_NWGT_CIK = "1900123"
_NWGT_HIT = _hit(_NWGT_ADSH, "0001900123", ["7.01", "9.01"])
_NWGT_INDEX_URL = _index_url(_NWGT_CIK, _NWGT_ADSH)
_NWGT_COVER_URL = f"https://www.sec.gov/Archives/edgar/data/{_NWGT_CIK}/000119312524161234/d812345d8k.htm"
_NWGT_EX99_URL = f"https://www.sec.gov/Archives/edgar/data/{_NWGT_CIK}/000119312524161234/d812345dex991.htm"


def _mock_nwgt_filing(*, ex99: Response | None = None) -> None:
    respx.get(_NWGT_INDEX_URL).mock(return_value=Response(200, text=_INDEX_HTML))
    respx.get(_NWGT_COVER_URL).mock(return_value=Response(200, text=_COVER_HTML))
    respx.get(_NWGT_EX99_URL).mock(return_value=ex99 or Response(200, text=_EX99_HTML))


@respx.mock
def test_edgar_raw_content_is_filing_text_not_form_metadata():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_SINGLE_HIT_BEAM))
    respx.get(_BEAM_INDEX_URL).mock(return_value=Response(200, text=_BEAM_INDEX_HTML))
    respx.get(_BEAM_DOC_URL).mock(
        return_value=Response(
            200,
            text="<html><body><p>Pursuant to Section 13 of the Exchange Act</p></body></html>",
        )
    )

    docs = list(_connector().fetch_since(_CURSOR))
    assert len(docs) == 1
    assert "Pursuant to Section 13" in docs[0].raw_content
    assert "Accession:" not in docs[0].raw_content
    assert "Form type:" not in docs[0].raw_content


@respx.mock
def test_edgar_filing_is_located_by_company_cik_not_accession_prefix():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    _mock_nwgt_filing()

    docs = list(_connector().fetch_since(_CURSOR))

    assert len(docs) == 1
    assert "Accession:" not in docs[0].raw_content
    assert docs[0].source_url == f"https://www.sec.gov/Archives/edgar/data/{_NWGT_CIK}/000119312524161234/"


@respx.mock
def test_edgar_every_sec_request_goes_through_rate_limiter_with_user_agent():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    _mock_nwgt_filing()

    client = RateLimitedClient({"sec.gov": 1_000.0})
    connector = SecEdgarConnector(client=client, user_agent=_TEST_USER_AGENT, now=lambda: _NOW)

    with patch.object(client, "_acquire", wraps=client._acquire) as mock_acquire:
        list(connector.fetch_since(_CURSOR))

    acquired_urls = [call.args[0] for call in mock_acquire.call_args_list]
    for url in (_NWGT_INDEX_URL, _NWGT_COVER_URL, _NWGT_EX99_URL):
        assert url in acquired_urls, f"rate limiter not called for {url}"
    assert all(c.request.headers.get("user-agent") == _TEST_USER_AGENT for c in respx.calls)


@respx.mock
def test_edgar_document_fetch_failure_falls_back_to_metadata(caplog):
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_SINGLE_HIT_BEAM))
    respx.get(_BEAM_INDEX_URL).mock(return_value=Response(503))

    with caplog.at_level(logging.WARNING, logger="auspex_ingest.connectors.sec_edgar"):
        docs = list(_connector().fetch_since(_CURSOR))

    assert len(docs) == 1
    assert "Accession:" in docs[0].raw_content
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


@respx.mock
def test_edgar_html_stripped_from_primary_document():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_SINGLE_HIT_BEAM))
    respx.get(_BEAM_INDEX_URL).mock(return_value=Response(200, text=_BEAM_INDEX_HTML))
    respx.get(_BEAM_DOC_URL).mock(
        return_value=Response(200, text="<p>Pursuant to the requirements</p>")
    )

    docs = list(_connector().fetch_since(_CURSOR))
    assert "<p>" not in docs[0].raw_content
    assert "Pursuant to the requirements" in docs[0].raw_content


# ── press-release exhibit ────────────────────────────────────────────────────


@respx.mock
def test_exhibit_99_1_press_release_is_fetched_and_leads_raw_content():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    _mock_nwgt_filing()

    doc = next(_connector().fetch_since(_CURSOR))

    assert "met its primary endpoint" in doc.raw_content
    assert "furnished as Exhibit 99.1" in doc.raw_content
    assert doc.raw_content.index("met its primary endpoint") < doc.raw_content.index(
        "furnished as Exhibit 99.1"
    )
    assert "<p>" not in doc.raw_content


@respx.mock
def test_readout_in_exhibit_99_1_reaches_the_extractor_input_window():
    """The extractor reads only the first `_MAX_CONTENT_CHARS`; the readout must sit inside it."""
    from auspex_ingest.extraction_backend import _MAX_CONTENT_CHARS

    long_cover = _COVER_HTML.replace(
        "<p>SIGNATURES", "<p>" + "Cover page boilerplate. " * 400 + "</p><p>SIGNATURES"
    )
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    respx.get(_NWGT_INDEX_URL).mock(return_value=Response(200, text=_INDEX_HTML))
    respx.get(_NWGT_COVER_URL).mock(return_value=Response(200, text=long_cover))
    respx.get(_NWGT_EX99_URL).mock(return_value=Response(200, text=_EX99_HTML))

    doc = next(_connector().fetch_since(_CURSOR))
    window = doc.raw_content[:_MAX_CONTENT_CHARS]

    assert len(doc.raw_content) > _MAX_CONTENT_CHARS
    assert "NWG-301" in window
    assert "met its primary endpoint" in window


@respx.mock
def test_filing_without_exhibit_99_1_uses_the_primary_document_only():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_SINGLE_HIT_BEAM))
    respx.get(_BEAM_INDEX_URL).mock(return_value=Response(200, text=_BEAM_INDEX_HTML))
    respx.get(_BEAM_DOC_URL).mock(return_value=Response(200, text="<p>Item 8.01 Other Events</p>"))

    doc = next(_connector().fetch_since(_CURSOR))
    assert doc.raw_content == "Item 8.01 Other Events"


@respx.mock
def test_exhibit_fetch_failure_keeps_the_primary_document_and_warns(caplog):
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    _mock_nwgt_filing(ex99=Response(404))

    with caplog.at_level(logging.WARNING, logger="auspex_ingest.connectors.sec_edgar"):
        doc = next(_connector().fetch_since(_CURSOR))

    assert "furnished as Exhibit 99.1" in doc.raw_content
    assert "met its primary endpoint" not in doc.raw_content
    assert any("exhibit" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    "items",
    [["5.02", "9.01"], ["1.01"], []],
)
@respx.mock
def test_8k_without_press_release_items_is_skipped_before_any_document_fetch(items):
    route = respx.get(url__startswith="https://www.sec.gov/Archives/")
    respx.get(_EFTS_URL).mock(
        return_value=Response(200, json=_efts(_hit("0001900123-24-000001", "0001900123", items)))
    )

    docs = list(_connector().fetch_since(_CURSOR))

    assert docs == []
    assert not route.called


@pytest.mark.parametrize("item", ["2.02", "7.01", "8.01"])
@respx.mock
def test_8k_with_a_press_release_item_is_kept(item):
    respx.get(_EFTS_URL).mock(
        return_value=Response(200, json=_efts(_hit("0001900123-24-000001", "0001900123", [item, "9.01"])))
    )
    docs = list(_connector().fetch_since(_CURSOR))
    assert len(docs) == 1


@respx.mock
def test_one_document_per_accession_when_search_returns_a_hit_per_filed_document():
    """Full-text search indexes each document of a filing; the cover and its exhibit are one filing."""
    exhibit_hit = _hit(_NWGT_ADSH, "0001900123", ["7.01", "9.01"], file_type="EX-99.1")
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT, exhibit_hit)))
    _mock_nwgt_filing()

    docs = list(_connector().fetch_since(_CURSOR))

    assert len(docs) == 1
    assert respx.get(_NWGT_INDEX_URL).call_count == 1


# ── acceptance time ──────────────────────────────────────────────────────────


@respx.mock
def test_published_date_is_the_acceptance_time_converted_from_eastern_to_utc():
    """Accepted 16:05:23 EDT is after the close; the aligner must see 20:05:23 UTC, not midnight."""
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    _mock_nwgt_filing()

    doc = next(_connector().fetch_since(_CURSOR))

    assert doc.published_date == datetime(2024, 6, 14, 20, 5, 23, tzinfo=UTC)


@respx.mock
def test_acceptance_time_in_winter_uses_the_standard_time_offset():
    adsh = "0001821552-24-000002"
    respx.get(_EFTS_URL).mock(
        return_value=Response(200, json=_efts(_hit(adsh, "0001821552", ["8.01"], file_date="2024-01-10")))
    )
    respx.get(_index_url(_BEAM_CIK, adsh)).mock(
        return_value=Response(
            200, text=_minimal_index_html(_BEAM_CIK, adsh, "beam-8k.htm", accepted="2024-01-10 07:30:00")
        )
    )
    respx.get(f"https://www.sec.gov/Archives/edgar/data/{_BEAM_CIK}/000182155224000002/beam-8k.htm").mock(
        return_value=Response(200, text="<p>Item 8.01</p>")
    )

    doc = next(_connector().fetch_since(_CURSOR))

    assert doc.published_date == datetime(2024, 1, 10, 12, 30, tzinfo=UTC)


@respx.mock
def test_unparseable_acceptance_time_falls_back_to_the_file_date_cutoff():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_SINGLE_HIT_BEAM))
    respx.get(_BEAM_INDEX_URL).mock(
        return_value=Response(
            200, text=_minimal_index_html(_BEAM_CIK, _BEAM_ADSH, "beam-8k.htm", accepted="not a time")
        )
    )
    respx.get(_BEAM_DOC_URL).mock(return_value=Response(200, text="<p>Item 8.01</p>"))

    doc = next(_connector().fetch_since(_CURSOR))

    assert doc.published_date == datetime(2024, 6, 15, 21, 30, tzinfo=UTC)


# ── coverage of edge cases ───────────────────────────────────────────────────


def _index_with_rows(cik: str, adsh: str, rows: list[tuple[str, str]], accepted: str = "2024-06-14 16:05:23") -> str:
    """Build an index page whose document table holds `(type, filename)` rows."""
    base = f"/Archives/edgar/data/{cik}/{adsh.replace('-', '')}"
    body = "".join(
        f'<tr><td>{i}</td><td>{t}</td><td><a href="{base}/{name}">{name}</a></td><td>{t}</td><td>1</td></tr>'
        for i, (t, name) in enumerate(rows, start=1)
    )
    return (
        '<div class="infoHead">Accepted</div>'
        f'<div class="info">{accepted}</div>'
        '<table class="tableFile" summary="Document Format Files">'
        "<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>"
        f"{body}</table>"
    )


def _doc_url(cik: str, adsh: str, name: str) -> str:
    return f"{_ARCHIVES_BASE}/{cik}/{adsh.replace('-', '')}/{name}"


_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
_ODD_ADSH = "0001900123-24-000077"


def _mock_rows(rows: list[tuple[str, str]], form: str = "8-K") -> None:
    respx.get(_EFTS_URL).mock(
        return_value=Response(200, json=_efts(_hit(_ODD_ADSH, "0001900123", ["8.01"], form=form)))
    )
    respx.get(_index_url(_NWGT_CIK, _ODD_ADSH)).mock(
        return_value=Response(200, text=_index_with_rows(_NWGT_CIK, _ODD_ADSH, rows))
    )
    for _, name in rows:
        respx.get(_doc_url(_NWGT_CIK, _ODD_ADSH, name)).mock(
            return_value=Response(200, text=f"<p>text of {name}</p>")
        )


@pytest.mark.parametrize("exhibit_type", ["EX-99.1", "EX-99.01", "ex-99.1"])
@respx.mock
def test_press_release_exhibit_is_recognised_under_its_type_variants(exhibit_type):
    _mock_rows([("8-K", "cover.htm"), (exhibit_type, "pr.htm")])
    doc = next(_connector().fetch_since(_CURSOR))
    assert doc.raw_content == "text of pr.htm\n\ntext of cover.htm"


@pytest.mark.parametrize("other_type", ["EX-99.2", "EX-99.10", "EX-99", "EX-10.1"])
@respx.mock
def test_other_exhibits_are_not_taken_for_the_press_release(other_type):
    _mock_rows([("8-K", "cover.htm"), (other_type, "other.htm")])
    doc = next(_connector().fetch_since(_CURSOR))
    assert doc.raw_content == "text of cover.htm"
    assert not respx.get(_doc_url(_NWGT_CIK, _ODD_ADSH, "other.htm")).called


@respx.mock
def test_amended_8k_uses_its_8k_a_cover_document():
    _mock_rows([("8-K/A", "cover-a.htm"), ("EX-99.1", "pr.htm")], form="8-K/A")
    doc = next(_connector().fetch_since(_CURSOR))
    assert doc.raw_content == "text of pr.htm\n\ntext of cover-a.htm"


@respx.mock
def test_xbrl_data_files_are_never_fetched():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    _mock_nwgt_filing()
    list(_connector().fetch_since(_CURSOR))
    archive_requests = {str(c.request.url) for c in respx.calls if "/Archives/" in str(c.request.url)}
    assert archive_requests == {_NWGT_INDEX_URL, _NWGT_COVER_URL, _NWGT_EX99_URL}


@respx.mock
def test_index_without_a_cover_document_keeps_the_exhibit_and_warns(caplog):
    _mock_rows([("EX-99.1", "pr.htm")])
    with caplog.at_level(logging.WARNING, logger="auspex_ingest.connectors.sec_edgar"):
        doc = next(_connector().fetch_since(_CURSOR))
    assert doc.raw_content == "text of pr.htm"
    assert any("no primary document" in r.getMessage() for r in caplog.records)


@respx.mock
def test_index_with_no_documents_keeps_metadata_but_takes_the_acceptance_time(caplog):
    _mock_rows([])
    with caplog.at_level(logging.WARNING, logger="auspex_ingest.connectors.sec_edgar"):
        doc = next(_connector().fetch_since(_CURSOR))
    assert "Accession:" in doc.raw_content
    assert doc.published_date == datetime(2024, 6, 14, 20, 5, 23, tzinfo=UTC)
    assert any("no primary document" in r.getMessage() for r in caplog.records)


@respx.mock
def test_cover_fetch_failure_keeps_the_exhibit_and_warns(caplog):
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    respx.get(_NWGT_INDEX_URL).mock(return_value=Response(200, text=_INDEX_HTML))
    respx.get(_NWGT_COVER_URL).mock(return_value=Response(500))
    respx.get(_NWGT_EX99_URL).mock(return_value=Response(200, text=_EX99_HTML))

    with caplog.at_level(logging.WARNING, logger="auspex_ingest.connectors.sec_edgar"):
        doc = next(_connector().fetch_since(_CURSOR))

    assert "met its primary endpoint" in doc.raw_content
    assert "furnished as Exhibit 99.1" not in doc.raw_content
    assert any("primary document" in r.getMessage() for r in caplog.records)


@respx.mock
def test_both_documents_failing_keeps_metadata_with_the_acceptance_time(caplog):
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    _mock_nwgt_filing(ex99=Response(503))
    respx.get(_NWGT_COVER_URL).mock(return_value=Response(503))

    with caplog.at_level(logging.WARNING, logger="auspex_ingest.connectors.sec_edgar"):
        doc = next(_connector().fetch_since(_CURSOR))

    assert "Accession: 0001193125-24-161234" in doc.raw_content
    assert doc.published_date == datetime(2024, 6, 14, 20, 5, 23, tzinfo=UTC)
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 2


@respx.mock
def test_network_error_on_the_index_falls_back_to_metadata_and_warns(caplog):
    import httpx

    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_SINGLE_HIT_BEAM))
    respx.get(_BEAM_INDEX_URL).mock(side_effect=httpx.ConnectError("boom"))

    with caplog.at_level(logging.WARNING, logger="auspex_ingest.connectors.sec_edgar"):
        docs = list(_connector().fetch_since(_CURSOR))

    assert len(docs) == 1
    assert "Accession:" in docs[0].raw_content
    assert docs[0].published_date == datetime(2024, 6, 15, 21, 30, tzinfo=UTC)
    assert any("filing index fetch error" in r.getMessage() for r in caplog.records)


@respx.mock
def test_index_403_stops_the_run_without_further_sec_requests():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_SINGLE_HIT_BEAM))
    archives = respx.get(url__startswith="https://www.sec.gov/Archives/").mock(
        return_value=Response(403)
    )

    with pytest.raises(SecRequestRefused):
        list(_connector().fetch_since(_CURSOR))

    assert [str(c.request.url) for c in archives.calls] == [_BEAM_INDEX_URL]


@respx.mock
def test_hit_without_a_company_cik_keeps_metadata_and_makes_no_archive_request():
    route = respx.get(url__startswith="https://www.sec.gov/Archives/")
    respx.get(_EFTS_URL).mock(
        return_value=Response(200, json=_efts(_hit("0001900123-24-000009", "", ["8.01"])))
    )
    docs = list(_connector().fetch_since(_CURSOR))
    assert len(docs) == 1
    assert "Accession:" in docs[0].raw_content
    assert not route.called


@respx.mock
def test_hit_without_an_items_field_is_skipped():
    hit = _hit("0001900123-24-000010", "0001900123", ["8.01"])
    del hit["_source"]["items"]
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(hit)))
    assert list(_connector().fetch_since(_CURSOR)) == []


@respx.mock
def test_one_document_per_accession_across_search_pages():
    exhibit_hit = _hit(_NWGT_ADSH, "0001900123", ["7.01", "9.01"], file_type="EX-99.1")
    pages = [
        {"hits": {"total": {"value": 2}, "hits": [_NWGT_HIT]}},
        {"hits": {"total": {"value": 2}, "hits": [exhibit_hit]}},
    ]
    respx.get(_EFTS_URL).mock(side_effect=[Response(200, json=p) for p in pages])
    _mock_nwgt_filing()

    docs = list(_connector().fetch_since(_CURSOR))

    assert len(docs) == 1
    assert respx.get(_EFTS_URL).call_count == 2


@pytest.mark.parametrize(
    ("accepted", "expected_utc"),
    [
        # Last trading day on EST before the spring-forward change (2024-03-10 02:00).
        ("2024-03-08 16:30:00", datetime(2024, 3, 8, 21, 30, tzinfo=UTC)),
        # First trading day on EDT after it.
        ("2024-03-11 09:00:00", datetime(2024, 3, 11, 13, 0, tzinfo=UTC)),
        # Last trading day on EDT before the fall-back change (2024-11-03 02:00).
        ("2024-11-01 16:30:00", datetime(2024, 11, 1, 20, 30, tzinfo=UTC)),
        # First trading day on EST after it.
        ("2024-11-04 16:30:00", datetime(2024, 11, 4, 21, 30, tzinfo=UTC)),
        # Late filing that crosses midnight UTC.
        ("2024-06-14 21:45:10", datetime(2024, 6, 15, 1, 45, 10, tzinfo=UTC)),
    ],
)
@respx.mock
def test_acceptance_time_converts_to_utc_across_daylight_saving_changes(accepted, expected_utc):
    respx.get(_EFTS_URL).mock(
        return_value=Response(200, json=_efts(_hit(_ODD_ADSH, "0001900123", ["8.01"])))
    )
    respx.get(_index_url(_NWGT_CIK, _ODD_ADSH)).mock(
        return_value=Response(
            200, text=_index_with_rows(_NWGT_CIK, _ODD_ADSH, [("8-K", "c.htm")], accepted=accepted)
        )
    )
    respx.get(_doc_url(_NWGT_CIK, _ODD_ADSH, "c.htm")).mock(return_value=Response(200, text="<p>x</p>"))

    doc = next(_connector().fetch_since(_CURSOR))

    assert doc.published_date == expected_utc
    assert doc.published_date.tzinfo == UTC


@respx.mock
def test_file_date_fallback_in_winter_is_17_30_eastern_standard_time():
    respx.get(_EFTS_URL).mock(
        return_value=Response(200, json=_efts(_hit(_ODD_ADSH, "0001900123", ["8.01"], file_date="2024-01-10")))
    )
    respx.get(_index_url(_NWGT_CIK, _ODD_ADSH)).mock(return_value=Response(404))

    doc = next(_connector().fetch_since(_CURSOR))

    assert doc.published_date == datetime(2024, 1, 10, 22, 30, tzinfo=UTC)


@respx.mock
def test_content_hash_matches_the_fetched_text():
    import hashlib

    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    _mock_nwgt_filing()
    doc = next(_connector().fetch_since(_CURSOR))
    assert doc.content_sha256 == hashlib.sha256(doc.raw_content.encode()).hexdigest()


@respx.mock
def test_identity_does_not_depend_on_fetched_content_or_acceptance_time():
    respx.get(_EFTS_URL).mock(return_value=Response(200, json=_efts(_NWGT_HIT)))
    _mock_nwgt_filing()
    doc = next(_connector().fetch_since(_CURSOR))
    assert doc.canonical_id == f"edgar:{_NWGT_ADSH}"
    assert doc.external_id == f"edgar:{_NWGT_ADSH}"


@respx.mock
def test_first_press_release_exhibit_wins_when_the_index_lists_two():
    _mock_rows([("8-K", "cover.htm"), ("EX-99.1", "pr-first.htm"), ("EX-99.1", "pr-second.htm")])
    doc = next(_connector().fetch_since(_CURSOR))
    assert doc.raw_content.startswith("text of pr-first.htm")


@respx.mock
def test_documents_in_the_xbrl_data_files_table_are_ignored():
    html = _index_with_rows(_NWGT_CIK, _ODD_ADSH, [("8-K", "cover.htm")]) + (
        '<table class="tableFile" summary="Data Files">'
        "<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>"
        f'<tr><td>2</td><td>x</td><td><a href="/Archives/edgar/data/{_NWGT_CIK}/000190012324000077/data.htm">'
        "data.htm</a></td><td>EX-99.1</td><td>1</td></tr></table>"
    )
    respx.get(_EFTS_URL).mock(
        return_value=Response(200, json=_efts(_hit(_ODD_ADSH, "0001900123", ["8.01"])))
    )
    respx.get(_index_url(_NWGT_CIK, _ODD_ADSH)).mock(return_value=Response(200, text=html))
    respx.get(_doc_url(_NWGT_CIK, _ODD_ADSH, "cover.htm")).mock(return_value=Response(200, text="<p>cover</p>"))

    data_route = respx.get(_doc_url(_NWGT_CIK, _ODD_ADSH, "data.htm")).mock(
        return_value=Response(200, text="<p>data</p>")
    )

    doc = next(_connector().fetch_since(_CURSOR))

    assert doc.raw_content == "cover"
    assert not data_route.called
