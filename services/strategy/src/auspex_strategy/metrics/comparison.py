from __future__ import annotations

from typing import Any

from auspex_strategy.metrics.returns import ReturnMetrics


class BacktestPaperComparison:
    """Whether a forward book's mean abnormal return falls inside its backtest's bootstrap
    interval. `deviation_from_backtest_ci` is the distance to the nearest bound: positive
    inside, negative outside. The verdicts are None when either side lacks the data.

    On the class, `is_inside_backtest_ci(paper, backtest)` is the check; on an instance it is
    the stored verdict.
    """

    def __init__(
        self,
        *,
        n_paper: int,
        n_backtest: int,
        inside: bool | None,
        deviation: float | None,
    ) -> None:
        self.n = n_paper
        self.n_paper = n_paper
        self.n_backtest = n_backtest
        self.is_inside_backtest_ci = inside  # type: ignore[assignment]
        self.deviation_from_backtest_ci = deviation
        self.paper_tracking_deviation = None if inside is None else not inside

    @staticmethod
    def is_inside_backtest_ci(paper: ReturnMetrics, backtest: ReturnMetrics) -> bool:
        if paper.mean_abnormal_return is None or backtest.bootstrap_ci_95 is None:
            raise ValueError("both sides need a mean and the backtest a bootstrap interval")
        low, high = backtest.bootstrap_ci_95
        return low <= paper.mean_abnormal_return <= high

    @classmethod
    def compute(cls, paper: ReturnMetrics, backtest: ReturnMetrics) -> BacktestPaperComparison:
        if paper.mean_abnormal_return is None or backtest.bootstrap_ci_95 is None:
            return cls(n_paper=paper.n, n_backtest=backtest.n, inside=None, deviation=None)
        low, high = backtest.bootstrap_ci_95
        mean = paper.mean_abnormal_return
        inside = BacktestPaperComparison.is_inside_backtest_ci(paper, backtest)
        nearest = min(abs(mean - low), abs(mean - high))
        return cls(
            n_paper=paper.n,
            n_backtest=backtest.n,
            inside=inside,
            deviation=nearest if inside else -nearest,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "n_paper": self.n_paper,
            "n_backtest": self.n_backtest,
            "is_inside_backtest_ci": self.is_inside_backtest_ci,
            "deviation_from_backtest_ci": self.deviation_from_backtest_ci,
            "paper_tracking_deviation": self.paper_tracking_deviation,
        }
