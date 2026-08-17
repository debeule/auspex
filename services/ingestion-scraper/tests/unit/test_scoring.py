"""Unit tests — extraction quality harness: golden set coverage and scoring."""
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from auspex_ingest.golden import GoldenDocument, load_golden_set, score_batch, score_field

_GOLDEN_DIR = Path(__file__).parent.parent / "golden"
_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)


# ── golden set structural tests ────────────────────────────────────────────────


def test_golden_set_covers_every_source_type_and_both_is_signal_classes():
    docs = load_golden_set(_GOLDEN_DIR)
    if not docs:
        pytest.skip("Golden set is empty — populate tests/golden/ to enable this test")

    source_types = {d.source_type for d in docs}
    required = {"biorxiv", "pubmed", "epo_ops", "clinical_trials", "edgar"}
    missing = required - source_types
    assert not missing, f"Missing source types: {missing}"

    has_signal = any(d.labels["is_signal"] for d in docs)
    has_non_signal = any(not d.labels["is_signal"] for d in docs)
    assert has_signal, "Golden set needs at least one is_signal=True document"
    assert has_non_signal, "Golden set needs at least one is_signal=False document"


def test_golden_set_includes_documents_the_prefilter_should_and_should_not_reject():
    docs = load_golden_set(_GOLDEN_DIR)
    if not docs:
        pytest.skip("Golden set is empty — populate tests/golden/ to enable this test")

    should_pass = [d for d in docs if d.labels.get("prefilter_should_pass")]
    should_reject = [d for d in docs if not d.labels.get("prefilter_should_pass")]
    assert should_pass, "Golden set needs at least one doc the prefilter should pass"
    assert should_reject, "Golden set needs at least one doc the prefilter should reject"


# ── scoring logic ──────────────────────────────────────────────────────────────


def _toy_golden() -> list[GoldenDocument]:
    return [
        GoldenDocument(
            source_type="biorxiv",
            external_id="ext-001",
            source_url="https://example.com/1",
            published_date="2024-06-15T12:00:00Z",
            raw_content="CRISPR editing of BCL11A",
            labels={
                "is_signal": True,
                "gene_targets": ["BCL11A"],
                "mechanisms": ["base editing"],
                "companies_mentioned": [],
                "directionality": "positive",
                "prefilter_should_pass": True,
            },
        ),
        GoldenDocument(
            source_type="pubmed",
            external_id="ext-002",
            source_url="https://example.com/2",
            published_date="2024-06-15T12:00:00Z",
            raw_content="BCL11A CRISPR base editing positive results",
            labels={
                "is_signal": True,
                "gene_targets": ["BCL11A", "HBB"],
                "mechanisms": ["base editing"],
                "companies_mentioned": ["Beam Therapeutics"],
                "directionality": "positive",
                "prefilter_should_pass": True,
            },
        ),
        GoldenDocument(
            source_type="edgar",
            external_id="ext-003",
            source_url="https://example.com/3",
            published_date="2024-06-15T12:00:00Z",
            raw_content="Quarterly earnings report with no gene content",
            labels={
                "is_signal": False,
                "gene_targets": [],
                "mechanisms": [],
                "companies_mentioned": [],
                "directionality": "neutral",
                "prefilter_should_pass": False,
            },
        ),
    ]


def test_scoring_script_reproduces_hand_computed_scores_on_a_toy_set():
    golden = _toy_golden()

    # Predictions: doc1 correct, doc2 misses HBB, doc3 correctly None (non-signal)
    predictions: list[dict | None] = [
        {
            "is_signal": True,
            "gene_targets": ["BCL11A"],
            "mechanisms": ["base editing"],
            "companies_mentioned": [],
            "directionality": "positive",
        },
        {
            "is_signal": True,
            "gene_targets": ["BCL11A"],  # misses HBB
            "mechanisms": ["base editing"],
            "companies_mentioned": ["Beam Therapeutics"],
            "directionality": "positive",
        },
        None,
    ]

    scores = score_batch(golden, predictions)

    # is_signal confusion matrix: TP=2, FP=0, FN=0, TN=1
    assert scores["is_signal"]["tp"] == 2
    assert scores["is_signal"]["fp"] == 0
    assert scores["is_signal"]["fn"] == 0
    assert scores["is_signal"]["tn"] == 1

    # gene_targets (only signal docs scored):
    #   doc1: predicted={"BCL11A"}, expected={"BCL11A"} → P=1.0, R=1.0
    #   doc2: predicted={"BCL11A"}, expected={"BCL11A","HBB"} → P=1.0, R=0.5
    #   macro: P=1.0, R=0.75
    assert scores["gene_targets"]["precision"] == pytest.approx(1.0)
    assert scores["gene_targets"]["recall"] == pytest.approx(0.75)

    # score_field sanity: perfect prediction
    perfect = score_field(["BCL11A"], ["BCL11A"])
    assert perfect["precision"] == pytest.approx(1.0)
    assert perfect["recall"] == pytest.approx(1.0)
    assert perfect["f1"] == pytest.approx(1.0)

    # score_field sanity: complete miss
    miss = score_field([], ["BCL11A"])
    assert miss["recall"] == pytest.approx(0.0)


def test_prompt_and_prefilter_versions_are_recorded_on_every_extracted_event():
    from auspex_ingest.extractor import LLMExtractor
    from auspex_ingest.models import RawDocument

    mock_result = MagicMock()
    mock_result.is_signal = True
    mock_result.title = "Test title"
    mock_result.raw_text_snippet = "snippet"
    mock_result.gene_targets = ["BCL11A"]
    mock_result.mechanisms = ["base editing"]
    mock_result.companies_mentioned = []
    mock_result.summary = "summary"
    mock_result.directionality = "positive"
    mock_result.confidence_score = 0.9

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_result

    extractor = LLMExtractor(
        client=mock_client,
        model="gpt-4o",
        schema_version="1.0",
        prompt_version="v1",
        now=lambda: _T0,
    )
    doc = RawDocument(
        schema_version="1.0",
        external_id="test-001",
        source_type="biorxiv",
        source_url="https://example.com/1",
        published_date=_T0,
        raw_content="CRISPR BCL11A",
        content_sha256="abc123",
        retrieved_at=_T0,
    )
    event = extractor.extract(doc, prefilter_version="v1", raw_object_key="raw/biorxiv/test-001/key.json")

    assert event is not None
    assert event.prompt_version == "v1"
    assert event.prefilter_version == "v1"
    assert event.extraction_model == "gpt-4o"
