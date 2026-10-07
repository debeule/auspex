
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    from auspex_ingest.extractor import _MAX_CONTENT_CHARS

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
