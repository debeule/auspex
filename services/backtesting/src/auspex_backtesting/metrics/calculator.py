import math
from dataclasses import dataclass

from auspex_backtesting.backtest.runner import BacktestReport, BacktestResult, VariantReport


@dataclass(frozen=True)
class RunParameters:
    window_days: int
    source_types: tuple[str, ...]
    prompt_version: str
    prefilter_version: str
    extraction_model: str
    variant: str = "full"


@dataclass(frozen=True)
class MetricValue:
    value: float | None
    n: int


@dataclass(frozen=True)
class MetricsReport:
    hit_rate: MetricValue
    mean_return: MetricValue
    std_return: MetricValue
    run_parameters: RunParameters
    variant: str = "full"


class MetricsCalculator:
    def compute(
        self, backtest: BacktestReport, params: RunParameters, window_days: int
    ) -> MetricsReport:
        returns = _returns_from_results(list(backtest.results), window_days)
        n = len(returns)
        return MetricsReport(
            hit_rate=MetricValue(value=_hit_rate(returns), n=n),
            mean_return=MetricValue(value=_mean(returns), n=n),
            std_return=MetricValue(value=_std(returns), n=n),
            run_parameters=params,
            variant=params.variant,
        )

    def compute_both_variants(
        self,
        backtest: BacktestReport,
        params: RunParameters,
        window_days: int,
    ) -> tuple[MetricsReport, MetricsReport]:
        entity_results = _qualifying_results(backtest.results, backtest.entity_only)
        full_results = _qualifying_results(backtest.results, backtest.full)

        entity_returns = _returns_from_results(entity_results, window_days)
        full_returns = _returns_from_results(full_results, window_days)

        n_e = len(entity_returns)
        n_f = len(full_returns)
        return (
            MetricsReport(
                hit_rate=MetricValue(_hit_rate(entity_returns), n_e),
                mean_return=MetricValue(_mean(entity_returns), n_e),
                std_return=MetricValue(_std(entity_returns), n_e),
                run_parameters=params,
                variant="entity-only",
            ),
            MetricsReport(
                hit_rate=MetricValue(_hit_rate(full_returns), n_f),
                mean_return=MetricValue(_mean(full_returns), n_f),
                std_return=MetricValue(_std(full_returns), n_f),
                run_parameters=params,
                variant="full",
            ),
        )


def _qualifying_results(
    results: tuple[BacktestResult, ...],
    variant_report: VariantReport | None,
) -> list[BacktestResult]:
    if variant_report is None:
        return list(results)
    qualifying: list[BacktestResult] = []
    for result in results:
        if not result.gene_target:
            continue
        for group in variant_report.groups:
            if (
                result.gene_target == group.gene_target
                and result.source_type in group.source_types
                and group.weight > 0
            ):
                qualifying.append(result)
                break
    return qualifying


def _returns_from_results(results: list[BacktestResult], window_days: int) -> list[float]:
    out: list[float] = []
    for r in results:
        for wr in r.window_returns:
            if wr.days == window_days and wr.pct is not None:
                out.append(wr.pct)
                break
    return out


def _hit_rate(returns: list[float]) -> float | None:
    if not returns:
        return None
    return sum(1 for r in returns if r > 0) / len(returns)


def _mean(returns: list[float]) -> float | None:
    if not returns:
        return None
    return sum(returns) / len(returns)


def _std(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    m = _mean(returns)
    assert m is not None
    return math.sqrt(sum((r - m) ** 2 for r in returns) / (len(returns) - 1))
