from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from auspex_backtesting.market_sim import MarketCalendar

from auspex_strategy.models import Direction, TradeIntent
from auspex_strategy.risk.decision import ExitIntent
from auspex_strategy.risk.limits import RiskLimits
from auspex_strategy.runtime.risk import RiskCheckRecord
from auspex_strategy.runtime.store import ObjectStore, append_line

log = logging.getLogger(__name__)

HOLDS_KEY = "strategy/risk/catalyst_holds.jsonl"

CatalystTypes = Callable[[str], frozenset[str]]


@dataclass(frozen=True)
class KnownCatalyst:
    """A scheduled binary event as known at `known_at`. An imprecise date ("Q3") is the
    period `period_start`..`period_end`; `catalyst_type` is `readout`, `pdufa`, `adcom` or
    `other`."""

    ticker: str
    catalyst_type: str
    period_start: date
    period_end: date
    known_at: datetime


class CatalystSource(Protocol):
    def between(self, ticker: str, start: date, end: date, as_of: datetime) -> list[KnownCatalyst]:
        """Catalysts for `ticker`, as known at `as_of`, whose period overlaps `start`..`end`.
        Raises `LookupError` when the source cannot answer for this ticker."""
        ...


class CatalystPanelReader(Protocol):
    def binaries_between(self, cik: str, start: date, end: date, as_of: datetime) -> Sequence[
        _PanelRow
    ]: ...


class _PanelRow(Protocol):
    @property
    def catalyst_type(self) -> str: ...
    @property
    def period_start(self) -> date: ...
    @property
    def period_end(self) -> date: ...
    @property
    def known_at(self) -> datetime: ...


class PanelCatalysts:
    """PDUFA and AdCom dates from the point-in-time catalyst panel. Readout dates have no
    automated source yet, so they are not guarded."""

    def __init__(self, panel: CatalystPanelReader, cik_for: Callable[[str], str | None]) -> None:
        self._panel = panel
        self._cik_for = cik_for

    def between(self, ticker: str, start: date, end: date, as_of: datetime) -> list[KnownCatalyst]:
        cik = self._cik_for(ticker)
        if cik is None:
            raise LookupError(f"no CIK for {ticker}; its catalysts cannot be looked up")
        return [
            KnownCatalyst(ticker, r.catalyst_type, r.period_start, r.period_end, r.known_at)
            for r in self._panel.binaries_between(cik, start, end, as_of)
        ]


class BinaryEventGuard:
    """No new position within `catalyst_guard_days` of a known binary event, and an exit at
    the last close before one for positions already held.

    Shorts never pass. A long may enter or hold only through catalyst types its strategy
    declares in `trades_catalyst_types`; every such entry or hold is appended to
    `strategy/risk/catalyst_holds.jsonl`.
    """

    def __init__(
        self,
        limits: RiskLimits,
        source: CatalystSource,
        catalyst_types: CatalystTypes,
        store: ObjectStore,
        *,
        calendar: MarketCalendar | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._limits = limits
        self._source = source
        self._catalyst_types = catalyst_types
        self._store = store
        self._calendar = calendar or MarketCalendar()
        self._clock = clock

    def check(self, intent: TradeIntent) -> RiskCheckRecord:
        inputs: dict[str, object] = {
            "ticker": intent.ticker,
            "direction": intent.direction.value,
            "guard_days": self._limits.catalyst_guard_days,
        }
        try:
            upcoming = self._upcoming(intent.ticker, intent.as_of)
        except LookupError as exc:
            return RiskCheckRecord("CATALYST_UNKNOWN", {**inputs, "error": str(exc)}, False)
        if not upcoming:
            return RiskCheckRecord("CATALYST_GUARD", inputs, True)
        declared = self._catalyst_types(intent.strategy_name)
        blocking = [
            c for c in upcoming
            if intent.direction is Direction.SHORT or c.catalyst_type not in declared
        ]
        inputs["catalysts"] = [_describe(c) for c in upcoming]
        if blocking:
            return RiskCheckRecord("CATALYST_GUARD", inputs, False)
        for catalyst in upcoming:
            self._record(intent.strategy_name, catalyst, "entry", intent.as_of)
        return RiskCheckRecord("CATALYST_GUARD", inputs, True)

    def exits(
        self, positions: Sequence[tuple[str, str, str, Direction]], as_of: datetime
    ) -> list[ExitIntent]:
        """`positions` are (strategy_name, position_id, ticker, direction)."""
        exits = []
        for strategy_name, position_id, ticker, direction in positions:
            try:
                upcoming = self._upcoming(ticker, as_of)
            except LookupError:
                log.warning("catalysts for %s cannot be looked up; position %s is not guarded",
                            ticker, position_id)
                continue
            declared = self._catalyst_types(strategy_name)
            blocking = [
                c for c in upcoming if direction is Direction.SHORT or c.catalyst_type not in declared
            ]
            if not blocking:
                for catalyst in upcoming:
                    self._record(strategy_name, catalyst, "hold", as_of)
                continue
            first = min(blocking, key=lambda c: c.period_start)
            exits.append(ExitIntent(
                strategy_name=strategy_name,
                position_id=position_id,
                ticker=ticker,
                exit_on=self._exit_session(first.period_start, as_of),
                check_name="CATALYST_GUARD",
                reason=f"{first.catalyst_type} from {first.period_start.isoformat()}",
            ))
        return exits

    def _upcoming(self, ticker: str, as_of: datetime) -> list[KnownCatalyst]:
        today = as_of.date()
        end = today + timedelta(days=self._limits.catalyst_guard_days)
        return self._source.between(ticker, today, end, as_of)

    def _exit_session(self, catalyst_start: date, as_of: datetime) -> date:
        """The last session before the catalyst, but never one already past."""
        earliest: date = self._calendar.next_trading_day(as_of.date())
        day = catalyst_start - timedelta(days=1)
        while day > earliest and not self._calendar.is_trading_day(day):
            day -= timedelta(days=1)
        return max(day, earliest)

    def _record(
        self, strategy_name: str, catalyst: KnownCatalyst, action: str, as_of: datetime
    ) -> None:
        append_line(self._store, HOLDS_KEY, json.dumps({
            "strategy_name": strategy_name,
            "ticker": catalyst.ticker,
            "catalyst_type": catalyst.catalyst_type,
            "period_start": catalyst.period_start.isoformat(),
            "period_end": catalyst.period_end.isoformat(),
            "action": action,
            "as_of": as_of.isoformat(),
            "recorded_at": self._clock().isoformat(),
        }))


def _describe(c: KnownCatalyst) -> dict[str, str]:
    return {
        "type": c.catalyst_type,
        "period_start": c.period_start.isoformat(),
        "period_end": c.period_end.isoformat(),
    }
