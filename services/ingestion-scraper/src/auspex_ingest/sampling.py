"""Stratified sample and score of the corroboration hand review (EXT-022)."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

PRECISION_BAR = 0.85
GENUINE = "genuine"
VERDICTS = frozenset({GENUINE, "coincidental", "wrong_ticker", "extraction_error"})


def entity_label(record: dict[str, Any]) -> str:
    """`GeneTarget` or `Mechanism`: the part of `entity_key` after its last colon."""
    return str(record["entity_key"]).rpartition(":")[2]


def sample_ticker_records(
    records: list[dict[str, Any]], per_label: int, seed: int
) -> list[dict[str, Any]]:
    """Up to `per_label` live ticker records per entity label, the same for the same seed.

    Records without a ticker are not sampled. Each label is drawn with its own generator, so a
    change in one label's pool never changes another's sample.
    """
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("ticker"):
            by_label[entity_label(record)].append(record)
    sample: list[dict[str, Any]] = []
    for label in sorted(by_label):
        pool = sorted(by_label[label], key=lambda r: (r["entity_key"], r["ticker"], r["participants_hash"]))
        if len(pool) > per_label:
            pool = random.Random(f"{seed}:{label}").sample(pool, per_label)
        sample.extend(pool)
    return sample


@dataclass(frozen=True)
class StratumScore:
    label: str
    reviewed: int
    genuine: int
    status: str  # "pass", "fail" or "insufficient"

    @property
    def precision(self) -> float:
        return self.genuine / self.reviewed if self.reviewed else 0.0


def score_review(
    records: list[dict[str, Any]], minimum: int, bar: float = PRECISION_BAR
) -> list[StratumScore]:
    """One score per entity label; a stratum with fewer than `minimum` rows is `insufficient`.

    Raises ValueError on a missing or unknown verdict.
    """
    reviewed: dict[str, int] = defaultdict(int)
    genuine: dict[str, int] = defaultdict(int)
    for i, record in enumerate(records, 1):
        verdict = str(record.get("verdict", "")).strip()
        if verdict not in VERDICTS:
            raise ValueError(f"line {i}: verdict {verdict!r} is not one of {sorted(VERDICTS)}")
        label = entity_label(record)
        reviewed[label] += 1
        genuine[label] += verdict == GENUINE
    scores = []
    for label in sorted(reviewed):
        n, g = reviewed[label], genuine[label]
        status = "insufficient" if n < minimum else "pass" if g / n >= bar else "fail"
        scores.append(StratumScore(label, n, g, status))
    return scores


def review_passes(scores: list[StratumScore]) -> bool:
    return bool(scores) and all(s.status == "pass" for s in scores)
