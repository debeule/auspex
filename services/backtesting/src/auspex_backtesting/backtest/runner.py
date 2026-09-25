from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

import pandas as pd

DEFAULT_WINDOWS: Final = (5, 20, 60)
_CORROBORATION_WINDOW_DAYS: Final = 90


@dataclass(frozen=True)
class BacktestEvent:
    event_id: str
    ticker: str
    entry_date: date
    raw_object_key: str
    gene_target: str = ""
    source_type: str = ""
    directionality: str = ""
    confidence_score: float = 0.0


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
    gene_target: str = ""
    source_type: str = ""


@dataclass(frozen=True)
class CorroborationGroup:
    gene_target: str
    source_types: frozenset[str]
    weight: float


@dataclass(frozen=True)
class VariantReport:
    variant: str
    groups: tuple[CorroborationGroup, ...]


@dataclass(frozen=True)
class BacktestReport:
    results: tuple[BacktestResult, ...]
    entity_only: VariantReport | None = None
    full: VariantReport | None = None


class BacktestRunner:
    def __init__(self, windows: tuple[int, ...] = DEFAULT_WINDOWS) -> None:
        self._windows = windows

    def run(
        self,
        events: list[BacktestEvent],
        price_data: dict[str, pd.DataFrame],
    ) -> BacktestReport:
        seen: set[str] = set()
        deduped: list[BacktestEvent] = []
        for event in events:
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            deduped.append(event)

        results: list[BacktestResult] = []
        for event in deduped:
            series = price_data.get(event.ticker)
            returns = _window_returns(series, event.entry_date, self._windows) if series is not None else ()
            results.append(BacktestResult(
                event_id=event.event_id,
                ticker=event.ticker,
                raw_object_key=event.raw_object_key,
                entry_date=event.entry_date,
                window_returns=returns,
                gene_target=event.gene_target,
                source_type=event.source_type,
            ))

        has_corroboration_fields = any(e.gene_target for e in deduped)
        entity_only: VariantReport | None = None
        full: VariantReport | None = None
        if has_corroboration_fields:
            entity_only, full = _compute_variants(deduped)

        return BacktestReport(results=tuple(results), entity_only=entity_only, full=full)


def _compute_variants(events: list[BacktestEvent]) -> tuple[VariantReport, VariantReport]:
    by_gene: dict[str, list[BacktestEvent]] = defaultdict(list)
    for e in events:
        if e.gene_target:
            by_gene[e.gene_target].append(e)

    entity_groups: list[CorroborationGroup] = []
    full_groups: list[CorroborationGroup] = []

    for gene_target, members in sorted(by_gene.items()):
        qualifying = _within_window(members)
        source_types = {e.source_type for e in qualifying}
        if len(source_types) < 2:
            continue

        entity_groups.append(CorroborationGroup(
            gene_target=gene_target,
            source_types=frozenset(source_types),
            weight=1.0,
        ))

        directionalities = [e.directionality for e in qualifying if e.directionality]
        confidences = [e.confidence_score for e in qualifying]
        all_agree = len(set(directionalities)) <= 1 if directionalities else True
        weight = statistics.mean(confidences) if all_agree and confidences else 0.0
        full_groups.append(CorroborationGroup(
            gene_target=gene_target,
            source_types=frozenset(source_types),
            weight=weight,
        ))

    return (
        VariantReport(variant="entity-only", groups=tuple(entity_groups)),
        VariantReport(variant="full", groups=tuple(full_groups)),
    )


def _within_window(events: list[BacktestEvent]) -> list[BacktestEvent]:
    if not events:
        return []
    dates = [e.entry_date for e in events]
    span = max(dates) - min(dates)
    if span <= timedelta(days=_CORROBORATION_WINDOW_DAYS):
        return events
    # Keep events within 90 days of the earliest
    anchor = min(dates)
    return [e for e in events if e.entry_date - anchor <= timedelta(days=_CORROBORATION_WINDOW_DAYS)]


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
