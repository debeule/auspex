from dataclasses import dataclass
from datetime import date
from typing import Final

import pandas as pd

DEFAULT_WINDOWS: Final = (5, 20, 60)


@dataclass(frozen=True)
class BacktestEvent:
    event_id: str
    ticker: str
    entry_date: date
    raw_object_key: str


@dataclass(frozen=True)
class WindowReturn:
    days: int
    pct: float | None


@dataclass(frozen=True)
class BacktestResult:
    event_id: str
    ticker: str
    raw_object_key: str
    entry_date: date
    window_returns: tuple[WindowReturn, ...]


@dataclass(frozen=True)
class BacktestReport:
    results: tuple[BacktestResult, ...]


class BacktestRunner:
    def __init__(self, windows: tuple[int, ...] = DEFAULT_WINDOWS) -> None:
        self._windows = windows

    def run(
        self,
        events: list[BacktestEvent],
        price_data: dict[str, pd.DataFrame],
    ) -> BacktestReport:
        seen: set[str] = set()
        results: list[BacktestResult] = []
        for event in events:
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            series = price_data.get(event.ticker)
            returns = _window_returns(series, event.entry_date, self._windows) if series is not None else ()
            results.append(BacktestResult(
                event_id=event.event_id,
                ticker=event.ticker,
                raw_object_key=event.raw_object_key,
                entry_date=event.entry_date,
                window_returns=returns,
            ))
        return BacktestReport(results=tuple(results))


def _window_returns(
    prices: pd.DataFrame,
    entry_date: date,
    windows: tuple[int, ...],
) -> tuple[WindowReturn, ...]:
    cutoff = pd.Timestamp(entry_date, tz="UTC")
    closes = prices[prices.index.normalize() >= cutoff]["close"]
    if closes.empty:
        return tuple(WindowReturn(days=w, pct=None) for w in windows)
    entry_price = float(closes.iloc[0])
    result: list[WindowReturn] = []
    for w in windows:
        exit_price = float(closes.iloc[min(w, len(closes) - 1)])
        pct = (exit_price - entry_price) / entry_price if entry_price != 0.0 else None
        result.append(WindowReturn(days=w, pct=pct))
    return tuple(result)
