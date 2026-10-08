import math
from dataclasses import dataclass

from auspex_backtesting.backtest.runner import (
    BacktestReport,
    BacktestResult,
    VariantReport,
    WindowReturn,
)
from auspex_backtesting.metrics.survivorship import SurvivorshipSummary, survivorship_summary


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
    survivorship: SurvivorshipSummary | None = None


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
            survivorship=survivorship_summary(
                _window(r.window_returns, window_days) for r in backtest.results
            ),
        )

    def compute_both_variants(
        self,
        backtest: BacktestReport,
        params: RunParameters,
        window_days: int,
    ) -> tuple[MetricsReport, MetricsReport]:
        entity_returns = _variant_returns(backtest.entity_only, window_days)
        full_returns = _variant_returns(backtest.full, window_days)

        n_e = len(entity_returns)
        n_f = len(full_returns)
        return (
            MetricsReport(
                hit_rate=MetricValue(_hit_rate(entity_returns), n_e),
                mean_return=MetricValue(_mean(entity_returns), n_e),
                std_return=MetricValue(_std(entity_returns), n_e),
                run_parameters=params,
                variant="entity-only",
                survivorship=_variant_survivorship(backtest.entity_only, window_days),
            ),
            MetricsReport(
                hit_rate=MetricValue(_hit_rate(full_returns), n_f),
                mean_return=MetricValue(_mean(full_returns), n_f),
                std_return=MetricValue(_std(full_returns), n_f),
                run_parameters=params,
                variant="full",
                survivorship=_variant_survivorship(backtest.full, window_days),
            ),
        )


def _variant_returns(variant_report: VariantReport | None, window_days: int) -> list[float]:
    """One return per corroboration event, entered after `corroborated_at`.

    Member signals are deliberately not counted: a member published before its corroboration
    existed would contribute a return no live system could have traded.
    """
    if variant_report is None:
        return []
    out: list[float] = []
    for group in variant_report.groups:
        if group.weight <= 0:
            continue
        pct = _pct_for_window(group.window_returns, window_days)
        if pct is not None:
            out.append(pct)
    return out


def _variant_survivorship(
    variant_report: VariantReport | None, window_days: int
) -> SurvivorshipSummary:
    groups = variant_report.groups if variant_report is not None else ()
    return survivorship_summary(
        _window(g.window_returns, window_days) for g in groups if g.weight > 0
    )


def _window(window_returns: tuple[WindowReturn, ...], window_days: int) -> WindowReturn:
    for wr in window_returns:
        if wr.days == window_days:
            return wr
    return WindowReturn(days=window_days, pct=None)


def _pct_for_window(window_returns: tuple[WindowReturn, ...], window_days: int) -> float | None:
    for wr in window_returns:
        if wr.days == window_days:
            return wr.pct
    return None


def _returns_from_results(results: list[BacktestResult], window_days: int) -> list[float]:
    out: list[float] = []
    for r in results:
        pct = _pct_for_window(r.window_returns, window_days)
        if pct is not None:
            out.append(pct)
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
