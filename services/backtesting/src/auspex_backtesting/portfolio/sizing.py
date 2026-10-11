from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


class InsufficientNamesError(ValueError):
    pass


@dataclass(frozen=True)
class TargetWeights:
    weights: Mapping[str, float]
    cash: float


class EqualRiskSizer:
    """Weights proportional to 1 / trailing volatility, each capped at `max_weight`.

    Weight a cap removes goes to the uncapped names in proportion to their own weights, until
    none exceeds the cap. When every name sits at the cap the remainder is cash: no weight is
    ever scaled above the ceiling to stay fully invested.
    """

    def __init__(self, max_weight: float, min_names: int) -> None:
        self._max = max_weight
        self._min_names = min_names

    def weights(self, volatilities: Mapping[str, float]) -> TargetWeights:
        if len(volatilities) < self._min_names:
            raise InsufficientNamesError(
                f"{len(volatilities)} names to size; the protocol requires {self._min_names}"
            )
        inverse = {name: 1.0 / vol for name, vol in volatilities.items()}
        capped: set[str] = set()
        weights: dict[str, float] = {}
        while True:
            free = {n: w for n, w in inverse.items() if n not in capped}
            room = 1.0 - self._max * len(capped)
            total = sum(free.values())
            weights = {n: self._max for n in capped}
            weights.update({n: room * w / total for n, w in free.items()} if total else {})
            over = {n for n in free if weights[n] > self._max}
            if not over:
                break
            capped |= over
        return TargetWeights(weights, max(0.0, 1.0 - sum(weights.values())))


def trailing_volatility(closes: Sequence[float], sessions: int) -> float | None:
    """Standard deviation of the last `sessions` daily log returns, or None without enough
    history or with a non-positive price."""
    window = list(closes)[-(sessions + 1) :]
    if len(window) < sessions + 1 or any(not c > 0 for c in window):
        return None
    returns = [math.log(b / a) for a, b in itertools.pairwise(window)]
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    vol = math.sqrt(variance)
    return vol if vol > 0 else None
