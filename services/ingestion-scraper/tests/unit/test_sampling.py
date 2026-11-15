from auspex_ingest.sampling import review_passes, sample_ticker_records, score_review


def _records(label: str, n: int, ticker: str = "SRPT") -> list[dict]:
    return [
        {"entity_key": f"K{i}:{label}", "ticker": ticker, "participants_hash": f"{label}{i}"}
        for i in range(n)
    ]


def _reviewed(label: str, genuine: int, other: int) -> list[dict]:
    return [{"entity_key": f"K:{label}", "verdict": "genuine"}] * genuine + [
        {"entity_key": f"K:{label}", "verdict": "coincidental"}
    ] * other


def test_sample_draws_the_requested_count_per_entity_label_from_ticker_records():
    records = _records("GeneTarget", 80) + _records("Mechanism", 120) + _records("Mechanism", 40, ticker="")

    sample = sample_ticker_records(records, per_label=50, seed=7)

    assert sum(r["entity_key"].endswith(":GeneTarget") for r in sample) == 50
    assert sum(r["entity_key"].endswith(":Mechanism") for r in sample) == 50
    assert all(r["ticker"] for r in sample)
    assert len({(r["entity_key"], r["participants_hash"]) for r in sample}) == 100
    assert len(sample_ticker_records(_records("GeneTarget", 10), per_label=50, seed=7)) == 10


def test_sample_is_identical_for_the_same_seed():
    records = _records("GeneTarget", 80) + _records("Mechanism", 120)

    first = sample_ticker_records(records, per_label=50, seed=7)
    again = sample_ticker_records(list(reversed(records)), per_label=50, seed=7)
    other = sample_ticker_records(records, per_label=50, seed=8)

    assert first == again
    assert first != other


def test_review_fails_when_one_stratum_is_below_the_bar_though_the_pooled_precision_passes():
    records = _reviewed("GeneTarget", 50, 0) + _reviewed("Mechanism", 40, 10)  # pooled 0.90

    scores = score_review(records, minimum=50)

    assert {s.label: s.status for s in scores} == {"GeneTarget": "pass", "Mechanism": "fail"}
    assert not review_passes(scores)
    assert review_passes(score_review(_reviewed("GeneTarget", 50, 0) + _reviewed("Mechanism", 43, 7), minimum=50))


def test_review_reports_a_stratum_below_the_minimum_row_count_as_insufficient():
    records = _reviewed("GeneTarget", 50, 0) + _reviewed("Mechanism", 30, 0)

    scores = score_review(records, minimum=50)

    assert {s.label: s.status for s in scores} == {"GeneTarget": "pass", "Mechanism": "insufficient"}
    assert not review_passes(scores)
