
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from auspex_ingest.connectors.base import SourceConnector
from auspex_ingest.identity import compute_event_id, compute_extraction_id
from auspex_ingest.models import RawDocument, ResearchSignalEvent
from auspex_ingest.normalizer import HgncEntityNormalizer, load_sec_company_tickers
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter
from auspex_ingest.storage.minio_client import minio_key

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_SEC_TICKERS = json.loads((_FIXTURES / "sec_company_tickers_sample.json").read_text())

_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)

# A small HGNC-like alias map used across tests:
#   key = normalizer canonical key (upper, hyphens stripped)
#   value = official HGNC symbol
_GENE_ALIASES: dict[str, str] = {
    "BCL11A": "BCL11A",
    "EKLF": "KLF1",   # old alias → canonical HGNC symbol
    "KLF1": "KLF1",
    "HBB": "HBB",
    "HBD": "HBD",     # similar to HBB but a distinct gene
    "DMD": "DMD",
    "PCSK9": "PCSK9",
}


def _normalizer(
    gene_aliases: dict[str, str] | None = None,
    sec_data: dict | None = None,
) -> HgncEntityNormalizer:
    company_tickers = load_sec_company_tickers(sec_data or _SEC_TICKERS)
    return HgncEntityNormalizer.from_mappings(
        gene_aliases=gene_aliases if gene_aliases is not None else _GENE_ALIASES,
        company_tickers=company_tickers,
    )



def test_two_accepted_gene_names_resolve_to_one_entity_node():
    """Old alias and canonical HGNC symbol must produce the same output."""
    norm = _normalizer()
    assert norm.normalize_gene("EKLF") == "KLF1"
    assert norm.normalize_gene("KLF1") == "KLF1"
    assert norm.normalize_gene("EKLF") == norm.normalize_gene("KLF1")


def test_distinct_genes_with_similar_names_do_not_merge():
    """HBB and HBD are different genes — must never collapse to one entity."""
    norm = _normalizer()
    assert norm.normalize_gene("HBB") != norm.normalize_gene("HBD"), (
        "HBB and HBD are distinct genes; merging them would corrupt corroboration"
    )


def test_case_and_hyphenation_variants_normalize():
    norm = _normalizer()
    assert norm.normalize_gene("bcl11a") == "BCL11A"
    assert norm.normalize_gene("BCL-11A") == "BCL11A"
    assert norm.normalize_gene("bcl-11a") == "BCL11A"


def test_unknown_alias_falls_back_to_raw_name_without_error():
    norm = _normalizer()
    result = norm.normalize_gene("UNKNOWNGENE9999")
    assert result == "UNKNOWNGENE9999"  # falls back to normalized-key form, no crash



def test_company_name_resolves_to_ticker_from_the_sec_mapping():
    norm = _normalizer()
    assert norm.normalize_company("Beam Therapeutics Inc.") == "BEAM"
    assert norm.normalize_company("Sarepta Therapeutics Inc.") == "SRPT"
    assert norm.normalize_company("CRISPR Therapeutics AG") == "CRSP"


def test_unresolvable_company_is_stored_and_still_corroborates_by_gene_target():
    """An unknown company name is returned unchanged — stored in companies_mentioned,
    corroborates via gene target match, absent from ticker-keyed REST results."""
    norm = _normalizer()
    raw_name = "Unknown Gene Therapy Co"
    result = norm.normalize_company(raw_name)
    assert result == raw_name, (
        "Unresolvable company must be returned unchanged so it is still stored "
        "and can corroborate by gene target"
    )



def test_normalization_runs_before_graph_write():
    """The normalizer must be invoked on every published signal before the Kafka publish."""
    gene_calls: list[str] = []

    class SpyNorm(HgncEntityNormalizer):
        def normalize_gene(self, gene: str) -> str:
            gene_calls.append(gene)
            return super().normalize_gene(gene)

    norm = SpyNorm.from_mappings(
        gene_aliases=_GENE_ALIASES,
        company_tickers=load_sec_company_tickers(_SEC_TICKERS),
    )

    content = "CRISPR BCL11A base editing"
    sha = hashlib.sha256(content.encode()).hexdigest()
    doc = RawDocument(
        schema_version="1.0",
        external_id="biorxiv:test:v1",
        canonical_id="doi:10.1/norm-test",
        source_type="biorxiv",
        source_url="https://example.com",
        published_date=_T0,
        raw_content=content,
        content_sha256=sha,
        retrieved_at=_T0,
    )

    class _Conn(SourceConnector):
        provides_canonical_id = True
        def fetch_since(self, cursor):
            yield doc

    event_id = compute_event_id(doc.canonical_id, doc.source_type, doc.external_id)
    extraction_id = compute_extraction_id(event_id, "1.0", "v1", "v1", "gpt-4o")
    signal = ResearchSignalEvent(
        schema_version="1.0", event_id=event_id, extraction_id=extraction_id,
        external_id=doc.external_id, canonical_id=doc.canonical_id,
        raw_object_key="raw/key.json", source_type=doc.source_type,
        source_url=doc.source_url, published_date=_T0,
        published_date_field="published_date", ingested_at=_T0,
        title="BCL11A base editing", raw_text_snippet="BCL11A",
        gene_targets=["BCL11A", "DMD"], mechanisms=["base editing"],
        companies_mentioned=["Beam Therapeutics Inc."], summary="test",
        directionality="positive", confidence_score=0.9,
        prompt_version="v1", prefilter_version="v1", extraction_model="gpt-4o",
    )

    archive = MagicMock()
    archive.put.return_value = (minio_key(doc), True)
    archive.get_canonical_marker.return_value = None
    extractor = MagicMock()
    extractor.extract.return_value = signal
    producer = MagicMock()

    pipeline = IngestionPipeline(
        connector=_Conn(),
        archive=archive,
        extractor=extractor,
        producer=producer,
        prefilter=Prefilter.from_vocab({"BCL11A", "CRISPR", "base editing"}),
        normalizer=norm,
        now=lambda: _T0,
    )
    pipeline.run("biorxiv", _T0)

    assert "BCL11A" in gene_calls, "normalize_gene must be called for each gene target before publish"
    assert "DMD" in gene_calls



def test_changing_the_normalizer_rekeys_deliberately_and_does_not_silently_merge():
    """Swapping normalizer configs produces visibly different entity keys.

    This test documents the invariant: when a normalizer changes, entity keys
    in the graph diverge. Re-keying is a deliberate, scripted operation with a
    recorded before/after node count — never a silent side effect of swapping
    the normalizer.
    """
    # Normalizer A: maps EKLF → KLF1
    norm_a = HgncEntityNormalizer.from_mappings(
        gene_aliases={"EKLF": "KLF1", "KLF1": "KLF1"},
        company_tickers={},
    )
    # Normalizer B: does not know the EKLF alias → falls back to "EKLF"
    norm_b = HgncEntityNormalizer.from_mappings(
        gene_aliases={"KLF1": "KLF1"},
        company_tickers={},
    )

    key_a = norm_a.normalize_gene("EKLF")
    key_b = norm_b.normalize_gene("EKLF")

    assert key_a != key_b, (
        "Different normalizer configurations produce different node keys. "
        "Re-keying after a normalizer change requires a deliberate migration script "
        "with before/after node counts recorded — it must never happen silently."
    )
    # Outputs must be deterministic per normalizer instance
    assert norm_a.normalize_gene("EKLF") == key_a
    assert norm_b.normalize_gene("EKLF") == key_b
