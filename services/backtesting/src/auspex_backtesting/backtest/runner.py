from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final

import pandas as pd

from auspex_backtesting.alignment.aligner import entry_session
from auspex_backtesting.backtest.episodes import (
    GENE_TARGET,
    EntityRules,
    IndependentSources,
    SameFinding,
    build_episodes,
)
from auspex_backtesting.backtest.membership import UniverseMembership
from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.market_sim.errors import PriceDataAbsentError
from auspex_backtesting.universe.model import UniverseMember

DEFAULT_WINDOWS: Final = (5, 20, 60)
_CALENDAR: Final = MarketCalendar()
_NO_RULES: Final = EntityRules(
    "", {GENE_TARGET: {}}, {}, SameFinding(frozenset(), 1.0)
)


@dataclass(frozen=True)
class BacktestEvent:
    """One extracted signal as the backtest receives it.

    `published_date` is the public timestamp (requirements §6.7); the runner derives the entry
    session from it, so no caller can hand in an entry date that precedes disclosure.
    """

    event_id: str
    ticker: str
    published_date: datetime
    raw_object_key: str
    gene_target: str = ""
    source_type: str = ""
    directionality: str = ""
    confidence_score: float = 0.0
    title: str | None = None


@dataclass(frozen=True)
class WindowReturn:
    """Return from the entry session's open to the close `days` calendar days later.

    With a universe, a window that runs past a delisted member's last price ends at that close
    and carries the member's `exit_reason`. A window the prices do not cover is `excluded`, with
    the member's `exit_reason` and, where the entry was priced, `priced_pct` up to the last
    close available inside the window. `pct` None without `excluded` means not computable
    (no universe) or still running.
    """

    days: int
    pct: float | None
    exit_reason: str | None = None
    excluded: bool = False
    priced_pct: float | None = None


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
    """One tradeable corroboration: an episode of one canonical gene-target key and ticker
    (RES-083), with the participants published by its opening.

    `corroborated_at` is the episode's `episode_opened_at`, the `published_date` of the participant
    that completed its first independent pair, and returns run from the session after it. Joiners
    add no event, and participants contribute no return of their own. `gene_target` is the
    canonical key.
    """

    gene_target: str
    ticker: str
    source_types: frozenset[str]
    weight: float
    participant_event_ids: tuple[str, ...]
    corroborated_at: datetime
    entry_date: date
    window_returns: tuple[WindowReturn, ...]


@dataclass(frozen=True)
class VariantReport:
    variant: str
    groups: tuple[CorroborationGroup, ...]


@dataclass(frozen=True)
class BacktestReport:
    """`outside_universe` counts events dropped because their company was not a universe member
    in the month they would have been traded. Corroborations form only from the events kept."""

    results: tuple[BacktestResult, ...]
    entity_only: VariantReport | None = None
    full: VariantReport | None = None
    outside_universe: int = 0
    corroboration_rules_hash: str | None = None


class BacktestRunner:
    def __init__(
        self, windows: tuple[int, ...] = DEFAULT_WINDOWS, rules: EntityRules | None = None
    ) -> None:
        """`rules` are the corroboration entity rules; an evaluation passes the registered file's
        (EVA-029). Without them no name is a synonym, nothing is excluded and no two participants
        are one finding."""
        self._windows = windows
        self._rules = rules if rules is not None else _NO_RULES
        self._universe: UniverseMembership | None = None

    def run(
        self,
        events: list[BacktestEvent],
        price_data: dict[str, pd.DataFrame],
        universe: UniverseMembership | None = None,
    ) -> BacktestReport:
        """With `universe`, only events on companies that were members in their entry month are
        traded; the rest are dropped and counted."""
        seen: set[str] = set()
        deduped: list[BacktestEvent] = []
        outside = 0
        for event in events:
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            if universe is not None and universe.member(
                event.ticker, entry_session(event.published_date)
            ) is None:
                outside += 1
                continue
            deduped.append(event)

        self._universe = universe
        results: list[BacktestResult] = []
        for event in deduped:
            entry = entry_session(event.published_date)
            results.append(BacktestResult(
                event_id=event.event_id,
                ticker=event.ticker,
                raw_object_key=event.raw_object_key,
                entry_date=entry,
                window_returns=self._returns(event.ticker, price_data, entry),
                gene_target=event.gene_target,
                source_type=event.source_type,
            ))

        has_corroboration_fields = any(e.gene_target for e in deduped)
        entity_only: VariantReport | None = None
        full: VariantReport | None = None
        if has_corroboration_fields:
            entity_only, full = self._compute_variants(deduped, price_data)

        return BacktestReport(
            results=tuple(results), entity_only=entity_only, full=full, outside_universe=outside
        )

    def _returns(
        self, ticker: str, price_data: dict[str, pd.DataFrame], entry: date
    ) -> tuple[WindowReturn, ...]:
        prices = price_data.get(ticker)
        if self._universe is not None:
            member = self._universe.member(ticker, entry)
            assert member is not None
            return _member_window_returns(
                ticker, prices, entry, self._windows, member, self._universe.as_of
            )
        if prices is None:
            return tuple(WindowReturn(days=w, pct=None) for w in self._windows)
        return _window_returns(prices, entry, self._windows)

    def _compute_variants(
        self,
        events: list[BacktestEvent],
        price_data: dict[str, pd.DataFrame],
    ) -> tuple[VariantReport, VariantReport]:
        by_key: dict[tuple[str, str], list[BacktestEvent]] = defaultdict(list)
        for e in events:
            if not e.gene_target:
                continue
            key = self._rules.canonical_key(GENE_TARGET, e.gene_target)
            if key and not self._rules.is_excluded(GENE_TARGET, key):
                by_key[(key, e.ticker)].append(e)

        independence = IndependentSources(self._rules.same_finding)
        entity_groups: list[CorroborationGroup] = []
        full_groups: list[CorroborationGroup] = []
        for (gene_target, ticker), members in sorted(by_key.items()):
            for episode in build_episodes(members, independence):
                known = {p.event_id for p in episode.published_by_opening()}
                participants = [m for m in members if m.event_id in known]
                participants.sort(key=lambda p: (p.published_date, p.event_id))
                corroborated_at = episode.opened_at
                entry = entry_session(corroborated_at)
                entity_group = CorroborationGroup(
                    gene_target=gene_target,
                    ticker=ticker,
                    source_types=frozenset(p.source_type for p in participants),
                    weight=1.0,
                    participant_event_ids=tuple(p.event_id for p in participants),
                    corroborated_at=corroborated_at,
                    entry_date=entry,
                    window_returns=self._returns(ticker, price_data, entry),
                )
                entity_groups.append(entity_group)
                full_groups.append(_with_full_weight(entity_group, participants))

        entity_groups.sort(key=lambda g: (g.entry_date, g.gene_target, g.ticker))
        full_groups.sort(key=lambda g: (g.entry_date, g.gene_target, g.ticker))
        return (
            VariantReport(variant="entity-only", groups=tuple(entity_groups)),
            VariantReport(variant="full", groups=tuple(full_groups)),
        )


def _with_full_weight(group: CorroborationGroup, participants: list[BacktestEvent]) -> CorroborationGroup:
    directionalities = {e.directionality for e in participants if e.directionality}
    confidences = [e.confidence_score for e in participants]
    weight = statistics.mean(confidences) if len(directionalities) <= 1 and confidences else 0.0
    return CorroborationGroup(
        gene_target=group.gene_target,
        ticker=group.ticker,
        source_types=group.source_types,
        weight=weight,
        participant_event_ids=group.participant_event_ids,
        corroborated_at=group.corroborated_at,
        entry_date=group.entry_date,
        window_returns=group.window_returns,
    )


def _window_returns(
    prices: pd.DataFrame,
    entry_date: date,
    windows: tuple[int, ...],
) -> tuple[WindowReturn, ...]:
    """Open of `entry_date` to the close of the first session on or after `entry_date + w` days.

    A missing entry or exit row gives `None` rather than the nearest available price, so a series
    that ends early (delisting, a gap in the snapshot) never shortens the holding period silently.
    """
    sessions = [ts.date() for ts in prices.index]
    opens = dict(zip(sessions, prices["open"], strict=True))
    closes = dict(zip(sessions, prices["close"], strict=True))
    entry_price = opens.get(entry_date)
    result: list[WindowReturn] = []
    for w in windows:
        exit_price = closes.get(_CALENDAR.next_trading_day(entry_date + timedelta(days=w)))
        if entry_price is None or exit_price is None or entry_price == 0.0:
            result.append(WindowReturn(days=w, pct=None))
            continue
        result.append(WindowReturn(days=w, pct=float(exit_price) / float(entry_price) - 1))
    return tuple(result)


def _member_window_returns(
    ticker: str,
    prices: pd.DataFrame | None,
    entry_date: date,
    windows: tuple[int, ...],
    member: UniverseMember,
    as_of: date,
) -> tuple[WindowReturn, ...]:
    """Window returns for a universe member, never shortening a window silently.

    A window ending after `as_of` is still running. One that runs past the last price ends at
    the last close when the member delisted and its prices reach the exit; it is excluded when
    the member's price history is incomplete; and it raises when a fully priced member that is
    still listed has run out of data, because that is a broken snapshot, not a market event.
    A missing bar inside the price range, such as a trading halt, also excludes the window
    rather than borrowing a neighbouring close.
    """
    if prices is None or prices.empty:
        return tuple(_excluded(w, member, None) for w in windows)
    sessions = sorted(ts.date() for ts in prices.index)
    opens = dict(zip((ts.date() for ts in prices.index), prices["open"], strict=True))
    closes = dict(zip((ts.date() for ts in prices.index), prices["close"], strict=True))
    last = sessions[-1]
    complete = member.price_coverage == "complete"
    entry_price = opens.get(entry_date)

    result: list[WindowReturn] = []
    for w in windows:
        exit_session = _CALENDAR.next_trading_day(entry_date + timedelta(days=w))
        if exit_session > as_of:
            result.append(WindowReturn(days=w, pct=None))
            continue
        if entry_price is None or float(entry_price) == 0.0:
            if complete and member.exited_on is None and entry_date > last:
                raise PriceDataAbsentError(
                    f"{ticker}: prices end {last}, before the entry session {entry_date}, "
                    "and the company is still listed"
                )
            result.append(_excluded(w, member, None))
            continue
        entry_value = float(entry_price)
        exit_price = closes.get(exit_session)
        if exit_price is not None:
            result.append(WindowReturn(days=w, pct=float(exit_price) / entry_value - 1))
            continue
        last_inside = max(d for d in sessions if d < exit_session)
        priced = float(closes[last_inside]) / entry_value - 1
        if exit_session < last or not complete:
            result.append(_excluded(w, member, priced))
        elif member.exited_on is not None:
            result.append(WindowReturn(days=w, pct=priced, exit_reason=member.exit_reason))
        else:
            raise PriceDataAbsentError(
                f"{ticker}: prices end {last}, before the {w}-day exit session {exit_session}, "
                "and the company is still listed"
            )
    return tuple(result)


def _excluded(days: int, member: UniverseMember, priced_pct: float | None) -> WindowReturn:
    return WindowReturn(
        days=days, pct=None, exit_reason=member.exit_reason, excluded=True, priced_pct=priced_pct
    )
