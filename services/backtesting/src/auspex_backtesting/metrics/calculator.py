import math
from dataclasses import dataclass

from auspex_backtesting.backtest.runner import BacktestReport


@dataclass(frozen=True)
class RunParameters:
    window_days: int
    source_types: tuple[str, ...]
    prompt_version: str
    prefilter_version: str
    extraction_model: str


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


class MetricsCalculator:
    def compute(
        self, backtest: BacktestReport, params: RunParameters, window_days: int
    ) -> MetricsReport:
        returns = _extract_returns(backtest, window_days)
        n = len(returns)
        return MetricsReport(
            hit_rate=MetricValue(value=_hit_rate(returns), n=n),
            mean_return=MetricValue(value=_mean(returns), n=n),
            std_return=MetricValue(value=_std(returns), n=n),
            run_parameters=params,
        )


def _extract_returns(backtest: BacktestReport, window_days: int) -> list[float]:
    result = []
    for r in backtest.results:
        for wr in r.window_returns:
            if wr.days == window_days and wr.pct is not None:
                result.append(wr.pct)
                break
    return result


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
