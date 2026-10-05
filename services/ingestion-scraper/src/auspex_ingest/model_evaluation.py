from __future__ import annotations

import random
import statistics
from typing import Any

from .golden import GoldenDocument, score_batch


def sample_golden(
    golden: list[GoldenDocument],
    seed: int,
    n: int | None = None,
) -> list[GoldenDocument]:
    pool = list(golden)
    if n is None or len(pool) <= n:
        return pool
    return random.Random(seed).sample(pool, n)


def compute_candidate_scores(
    golden: list[GoldenDocument],
    results: list[dict[str, Any] | None],
    latencies_s: list[float],
) -> dict[str, Any]:
    batch = score_batch(golden, results)
    cm = batch["is_signal"]
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if (cm["tp"] + cm["fp"]) else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) else 0.0
    mean_lat = statistics.mean(latencies_s) if latencies_s else 0.0
    p95_lat = sorted(latencies_s)[int(0.95 * len(latencies_s))] if latencies_s else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "cm": cm,
        "mean_latency_s": mean_lat,
        "p95_latency_s": p95_lat,
        "passed": precision >= 0.85,
    }


def sample_leakage_manifest(
    entries: list[dict[str, Any]],
    seed: int,
    n: int,
) -> list[dict[str, Any]]:
    pool = list(entries)
    if len(pool) <= n:
        return pool
    return random.Random(seed).sample(pool, n)


def score_leakage(
    entries: list[dict[str, Any]],
    model_answers: list[str],
) -> dict[str, Any]:
    by_month: dict[str, dict[str, int]] = {}
    by_source: dict[str, dict[str, int]] = {}

    for entry, answer in zip(entries, model_answers):
        month = entry["published_month"]
        source_type = entry["source_type"]
        correct = answer.strip().lower() == entry["correct_answer"].strip().lower()

        for bucket, key in [(by_month, month), (by_source, source_type)]:
            if key not in bucket:
                bucket[key] = {"correct": 0, "total": 0}
            bucket[key]["total"] += 1
            if correct:
                bucket[key]["correct"] += 1

    def _with_rate(d: dict[str, dict[str, int]]) -> dict[str, Any]:
        return {k: {**v, "rate": v["correct"] / v["total"]} for k, v in d.items()}

    return {"by_month": _with_rate(by_month), "by_source_type": _with_rate(by_source)}


def sample_archive_keys(keys: list[str], seed: int, n: int) -> list[str]:
    pool = list(keys)
    if len(pool) <= n:
        return pool
    return random.Random(seed).sample(pool, n)


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def compute_model_agreement(
    results_a: list[dict[str, Any] | None],
    results_b: list[dict[str, Any] | None],
) -> dict[str, Any]:
    total = len(results_a)
    both_signal = sum(1 for a, b in zip(results_a, results_b) if a is not None and b is not None)
    both_not = sum(1 for a, b in zip(results_a, results_b) if a is None and b is None)
    disagree = total - both_signal - both_not
    agreement = (both_signal + both_not) / total if total else 0.0

    pairs = [(a, b) for a, b in zip(results_a, results_b) if a is not None and b is not None]

    jacc_genes = statistics.mean(
        _jaccard(p[0].get("gene_targets", []), p[1].get("gene_targets", []))
        for p in pairs
    ) if pairs else 0.0

    jacc_mech = statistics.mean(
        _jaccard(p[0].get("mechanisms", []), p[1].get("mechanisms", []))
        for p in pairs
    ) if pairs else 0.0

    dir_agree = (
        sum(1 for p in pairs if p[0].get("directionality") == p[1].get("directionality"))
        / len(pairs)
    ) if pairs else 0.0

    conf_a = [p[0].get("confidence_score", 0.0) for p in pairs]
    conf_b = [p[1].get("confidence_score", 0.0) for p in pairs]
    conf_pearson: float | None = (
        statistics.correlation(conf_a, conf_b) if len(pairs) >= 2 else None
    )

    return {
        "is_signal_agreement": agreement,
        "both_signal": both_signal,
        "both_not": both_not,
        "disagree": disagree,
        "jaccard_gene_targets": jacc_genes,
        "jaccard_mechanisms": jacc_mech,
        "directionality_agreement": dir_agree,
        "confidence_pearson": conf_pearson,
    }
