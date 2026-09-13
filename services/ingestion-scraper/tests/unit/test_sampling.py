"""Corroboration sampling tests."""
from auspex_ingest.sampling import sample_corroborations


def _records(n: int) -> list[dict]:
    return [{"entity_key": "BCL11A:GeneTarget", "id": i} for i in range(n)]


def test_sampling_script_is_deterministic_given_a_seed():
    records = _records(100)
    first  = sample_corroborations(records, 30, seed=42)
    second = sample_corroborations(records, 30, seed=42)
    assert first == second


def test_different_seeds_produce_different_samples():
    records = _records(100)
    a = sample_corroborations(records, 30, seed=1)
    b = sample_corroborations(records, 30, seed=2)
    assert a != b


def test_sample_smaller_than_pool_returns_requested_count():
    assert len(sample_corroborations(_records(100), 30, seed=42)) == 30


def test_sample_larger_than_pool_returns_all_records():
    records = _records(10)
    result = sample_corroborations(records, 30, seed=42)
    assert len(result) == 10
    assert result == records


def test_sample_contains_no_duplicates():
    result = sample_corroborations(_records(100), 30, seed=42)
    ids = [r["id"] for r in result]
    assert len(ids) == len(set(ids))
