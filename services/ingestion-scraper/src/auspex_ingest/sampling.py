from __future__ import annotations

import random
from typing import Any


def sample_corroborations(
    records: list[dict[str, Any]],
    n: int,
    seed: int,
) -> list[dict[str, Any]]:
    # Same (records, n, seed) always returns the same subset — required so two
    # reviewers get identical items and precision figures stay comparable.
    pool = list(records)
    if len(pool) <= n:
        return pool
    rng = random.Random(seed)
    return rng.sample(pool, n)
