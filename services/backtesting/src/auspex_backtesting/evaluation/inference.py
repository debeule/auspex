from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from auspex_backtesting.evaluation.returns import AbnormalReturnSeries

_NORMAL = NormalDist()
_EULER_MASCHERONI = 0.5772156649015329
# Webb (2023) six-point weights: +-sqrt(1/2), +-1, +-sqrt(3/2), each with probability 1/6.
_WEBB_WEIGHTS = np.array(
    [-math.sqrt(1.5), -1.0, -math.sqrt(0.5), math.sqrt(0.5), 1.0, math.sqrt(1.5)]
)


@dataclass(frozen=True)
class InferenceResult:
    t_stat: float
    p_value: float
    method: str
    n_clusters_ticker: int
    n_clusters_month: int
    n_independent: int


class ClusteredInference:
    """Inference on the mean abnormal return, with errors clustered by ticker and event month.

    With at least the registered minimum of clusters in both dimensions the t-statistic uses
    two-way cluster-robust errors (Cameron, Gelbach and Miller 2011) and a normal p-value. Below
    it, cluster-robust errors understate the variance, so the t-statistic is clustered one way
    on the dimension with fewer clusters (at least two) and its p-value comes from a wild cluster bootstrap
    with Webb weights, imposing the null of a zero mean.
    """

    def __init__(self, protocol: dict[str, Any]) -> None:
        settings = protocol["inference"]
        if (
            settings["standard_errors"] != "two_way_clustered"
            or settings["cluster_by"] != ["ticker", "event_month"]
            or settings["below_min_clusters"] != "wild_cluster_bootstrap"
            or settings["bootstrap_weights"] != "webb"
            or settings["independent_event_rule"] != "same_ticker_overlapping_window_is_one"
        ):
            raise ValueError(f"unsupported inference settings: {settings}")
        self._min_clusters = int(settings["min_clusters_per_dimension"])
        self._draws = int(settings["bootstrap_draws"])
        self._seed = int(settings["seed"])

    def t_stat(self, series: AbnormalReturnSeries) -> InferenceResult:
        x = np.asarray(series.values, dtype=float)
        tickers = _codes(series.tickers)
        months = _codes(series.event_months)
        n_ticker, n_month = int(tickers.max(initial=-1)) + 1, int(months.max(initial=-1)) + 1
        n_independent = self.independent_events(series)

        def result(t: float, p: float, method: str) -> InferenceResult:
            return InferenceResult(t, p, method, n_ticker, n_month, n_independent)

        if min(n_ticker, n_month) >= self._min_clusters:
            residuals = x - x.mean()
            pairs = _codes([f"{a}|{b}" for a, b in zip(tickers, months, strict=True)])
            variance = (
                _cluster_variance(residuals, tickers)
                + _cluster_variance(residuals, months)
                - _cluster_variance(residuals, pairs)
            )
            if variance <= 0:
                # The two-way estimate can go negative in small samples; CGM take the larger
                # one-way variance instead.
                variance = max(
                    _cluster_variance(residuals, tickers), _cluster_variance(residuals, months)
                )
            t = float(x.mean() / math.sqrt(variance))
            return result(t, 2 * (1 - _NORMAL.cdf(abs(t))), "two_way_clustered")

        # A dimension with a single cluster says nothing about dependence; use the other.
        usable = [(g, codes) for g, codes in ((n_ticker, tickers), (n_month, months)) if g >= 2]
        if not usable:
            return result(float("nan"), float("nan"), "too_few_clusters")
        clusters = min(usable, key=lambda pair: pair[0])[1]
        t = _one_way_t(x, clusters)
        return result(t, self._wild_bootstrap_p(x, clusters, t), "wild_cluster_bootstrap")

    def independent_events(self, series: AbnormalReturnSeries) -> int:
        """Events, counting same-ticker events whose holding windows overlap as one."""
        windows: dict[str, list[tuple[Any, Any]]] = defaultdict(list)
        for ticker, start, end in zip(
            series.tickers, series.window_starts, series.window_ends, strict=True
        ):
            windows[ticker].append((start, end))
        count = 0
        for spans in windows.values():
            spans.sort()
            current_end = None
            for start, end in spans:
                if current_end is None or start > current_end:
                    count += 1
                    current_end = end
                else:
                    current_end = max(current_end, end)
        return count

    def _wild_bootstrap_p(self, x: np.ndarray, clusters: np.ndarray, t: float) -> float:
        if math.isnan(t):
            return float("nan")
        n, g = len(x), int(clusters.max()) + 1
        sums = np.bincount(clusters, weights=x, minlength=g)
        sizes = np.bincount(clusters, minlength=g).astype(float)
        rng = np.random.default_rng(self._seed)
        weights = rng.choice(_WEBB_WEIGHTS, size=(self._draws, g))
        # Under the null the restricted residuals are the observations themselves.
        draw_sums = weights * sums
        draw_means = draw_sums.sum(axis=1) / n
        residual_sums = draw_sums - np.outer(draw_means, sizes)
        variance = g / (g - 1) * (residual_sums**2).sum(axis=1) / n**2
        with np.errstate(divide="ignore", invalid="ignore"):
            draw_t = draw_means / np.sqrt(variance)
        return float(np.mean(np.abs(draw_t) >= abs(t)))


class BootstrapCI:
    @staticmethod
    def compute(
        series: pd.Series | Sequence[float],
        n_bootstrap: int = 10_000,
        ci: float = 0.95,
        seed: int = 42,
    ) -> tuple[float, float]:
        """Percentile bootstrap interval for the mean, resampling events with replacement."""
        values = np.asarray(series, dtype=float)
        if len(values) == 0:
            return float("nan"), float("nan")
        rng = np.random.default_rng(seed)
        draws = rng.choice(values, size=(n_bootstrap, len(values)), replace=True).mean(axis=1)
        tail = (1 - ci) / 2
        return float(np.quantile(draws, tail)), float(np.quantile(draws, 1 - tail))


class DeflatedSharpe:
    @staticmethod
    def compute(
        sharpe_ratio: float,
        n_obs: int,
        n_trials: int,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
    ) -> float:
        """Probability that the true Sharpe ratio exceeds the best of `n_trials` unskilled ones.

        Bailey and López de Prado (2014), Eq. 2. `sharpe_ratio` is per observation (not
        annualised) over `n_obs` observations; `kurtosis` is raw, 3 for a normal distribution.
        The benchmark Sharpe is the expected maximum of `n_trials` independent zero-skill
        estimates, each with the null variance `1 / (n_obs - 1)` of a Sharpe estimate.
        """
        if n_obs < 2:
            raise ValueError("the deflated Sharpe ratio needs at least 2 observations")
        if n_trials < 1:
            raise ValueError("n_trials must be at least 1")
        expected_max = 0.0
        if n_trials > 1:
            expected_max = math.sqrt(1 / (n_obs - 1)) * (
                (1 - _EULER_MASCHERONI) * _NORMAL.inv_cdf(1 - 1 / n_trials)
                + _EULER_MASCHERONI * _NORMAL.inv_cdf(1 - 1 / (n_trials * math.e))
            )
        dispersion = 1 - skewness * sharpe_ratio + (kurtosis - 1) / 4 * sharpe_ratio**2
        if dispersion <= 0:
            raise ValueError("skewness and kurtosis give a non-positive Sharpe variance")
        z = (sharpe_ratio - expected_max) * math.sqrt(n_obs - 1) / math.sqrt(dispersion)
        return _NORMAL.cdf(z)


def _codes(labels: Sequence[Any]) -> np.ndarray:
    index: dict[Any, int] = {}
    return np.array([index.setdefault(label, len(index)) for label in labels], dtype=int)


def _cluster_variance(residuals: np.ndarray, clusters: np.ndarray) -> float:
    """Cluster-robust variance of the mean, with the `G / (G - 1)` small-sample factor."""
    n, g = len(residuals), int(clusters.max()) + 1
    sums = np.bincount(clusters, weights=residuals, minlength=g)
    return float(g / (g - 1) * (sums**2).sum() / n**2)


def _one_way_t(x: np.ndarray, clusters: np.ndarray) -> float:
    variance = _cluster_variance(x - x.mean(), clusters)
    if variance <= 0:
        return float("nan")
    return float(x.mean() / math.sqrt(variance))
