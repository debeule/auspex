"""Model evaluation script unit tests.

Computation functions live in auspex_ingest.model_evaluation; scripts are thin wrappers.
All LLM calls are stubbed; sockets are disabled by pytest-socket.
"""
from auspex_ingest.golden import GoldenDocument
from auspex_ingest.model_evaluation import (
    compute_candidate_scores,
    compute_model_agreement,
    sample_archive_keys,
    sample_golden,
    sample_leakage_manifest,
    score_leakage,
)


def _golden(n: int = 5) -> list[GoldenDocument]:
    return [
        GoldenDocument(
            source_type="biorxiv",
            external_id=f"doi:{i}",
            source_url="https://example.com",
            published_date="2024-01-01T00:00:00Z",
            raw_content=f"doc {i}",
            labels={"is_signal": i % 2 == 0},
        )
        for i in range(n)
    ]


def test_candidate_comparison_is_deterministic_given_a_seed():
    golden = _golden(10)
    first = sample_golden(golden, seed=42, n=6)
    second = sample_golden(golden, seed=42, n=6)
    assert first == second
    assert len(first) == 6


def test_candidate_comparison_reproduces_hand_computed_scores_on_toy_set():
    golden = [
        GoldenDocument("biorxiv", "a", "", "2024-01-01T00:00:00Z", "doc a", {"is_signal": True}),
        GoldenDocument("biorxiv", "b", "", "2024-01-01T00:00:00Z", "doc b", {"is_signal": False}),
        GoldenDocument("biorxiv", "c", "", "2024-01-01T00:00:00Z", "doc c", {"is_signal": True}),
    ]
    # Doc a: TP (signal predicted for signal label)
    # Doc b: TN (no prediction for non-signal label)
    # Doc c: FN (no prediction for signal label)
    results = [{"is_signal": True, "gene_targets": [], "mechanisms": [], "companies_mentioned": [], "directionality": "positive"}, None, None]
    latencies = [1.0, 0.5, 0.8]

    scores = compute_candidate_scores(golden, results, latencies)

    assert scores["precision"] == 1.0                  # 1 TP, 0 FP
    assert scores["recall"] == 0.5                     # 1 TP, 1 FN
    assert abs(scores["mean_latency_s"] - (1.0 + 0.5 + 0.8) / 3) < 1e-9
    assert scores["p95_latency_s"] == 1.0              # sorted[int(0.95*3)] = sorted[2]
    assert scores["passed"] is True                    # 1.0 >= 0.85


def test_leakage_canary_sampling_is_deterministic_given_a_seed():
    entries = [{"event_id": str(i)} for i in range(20)]
    first = sample_leakage_manifest(entries, seed=7, n=10)
    second = sample_leakage_manifest(entries, seed=7, n=10)
    assert first == second
    assert len(first) == 10


def test_leakage_canary_scoring_reproduces_hand_computed_result_on_toy_set():
    entries = [
        {"published_month": "2024-01", "source_type": "pubmed", "correct_answer": "positive"},
        {"published_month": "2024-02", "source_type": "clinicaltrials", "correct_answer": "negative"},
        {"published_month": "2024-01", "source_type": "pubmed", "correct_answer": "positive"},
    ]
    answers = ["positive", "positive", "positive"]

    result = score_leakage(entries, answers)

    assert result["by_month"]["2024-01"]["correct"] == 2
    assert result["by_month"]["2024-01"]["total"] == 2
    assert result["by_month"]["2024-01"]["rate"] == 1.0
    assert result["by_month"]["2024-02"]["correct"] == 0
    assert result["by_month"]["2024-02"]["rate"] == 0.0
    assert result["by_source_type"]["pubmed"]["rate"] == 1.0
    assert result["by_source_type"]["clinicaltrials"]["rate"] == 0.0


def test_cross_model_agreement_is_deterministic_given_a_seed():
    keys = [f"raw/{i}" for i in range(30)]
    first = sample_archive_keys(keys, seed=99, n=15)
    second = sample_archive_keys(keys, seed=99, n=15)
    assert first == second
    assert len(first) == 15


def test_cross_model_agreement_reproduces_hand_computed_metrics_on_toy_set():
    # Doc 0: both signal — different gene coverage, same mechanism, different directionality
    # Doc 1: both signal — perfect agreement
    results_a = [
        {"is_signal": True, "gene_targets": ["BCL11A"], "mechanisms": ["base editing"], "directionality": "positive", "confidence_score": 0.9},
        {"is_signal": True, "gene_targets": ["VEGFA"], "mechanisms": ["inhibition"], "directionality": "negative", "confidence_score": 0.7},
    ]
    results_b = [
        {"is_signal": True, "gene_targets": ["BCL11A", "PCSK9"], "mechanisms": ["base editing"], "directionality": "positive", "confidence_score": 0.8},
        {"is_signal": True, "gene_targets": ["VEGFA"], "mechanisms": ["inhibition"], "directionality": "positive", "confidence_score": 0.6},
    ]

    m = compute_model_agreement(results_a, results_b)

    assert m["is_signal_agreement"] == 1.0             # both signal for both docs
    assert abs(m["jaccard_gene_targets"] - 0.75) < 1e-9  # (0.5 + 1.0) / 2
    assert m["jaccard_mechanisms"] == 1.0
    assert m["directionality_agreement"] == 0.5        # doc 0 agrees, doc 1 disagrees
    assert abs(m["confidence_pearson"] - 1.0) < 1e-9  # perfectly correlated offsets
