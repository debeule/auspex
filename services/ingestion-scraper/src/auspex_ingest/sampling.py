"""Deterministic corroboration sampling for manual quality review."""
from __future__ import annotations

import random
from typing import Any


def sample_corroborations(
    records: list[dict[str, Any]],
    n: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Return up to *n* records drawn without replacement using *seed*.

    The same (records, n, seed) triple always returns the same subset in the
    same order — required so two reviewers working from the same snapshot see
    identical items and precision figures are comparable.
    """
    pool = list(records)
    if len(pool) <= n:
        return pool
    rng = random.Random(seed)
    return rng.sample(pool, n)
