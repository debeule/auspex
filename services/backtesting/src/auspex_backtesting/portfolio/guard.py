from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol

GuardStatus = Literal["clear", "binary", "no_data"]

_EARLIEST = date(1900, 1, 1)
_LATEST = date(2200, 1, 1)


class DatedCatalyst(Protocol):
    @property
    def period_start(self) -> date: ...
    @property
    def period_end(self) -> date: ...
    @property
    def precision(self) -> str: ...


class CatalystSource(Protocol):
    """Point-in-time binary event dates, as `CatalystPanel` serves them."""

    def binaries_between(
        self, cik: str, start: date, end: date, as_of: datetime
    ) -> Sequence[DatedCatalyst]: ...


@dataclass(frozen=True)
class GuardCheck:
    status: GuardStatus
    binary_start: date | None = None
    binary_end: date | None = None


class CatalystGuard:
    """Whether a name has a binary event due inside a holding window, as known at a moment.

    A name with no catalyst row known at all is `no_data`, never `clear`: the guard only
    protects names whose dates the panel has.
    """

    def __init__(self, source: CatalystSource) -> None:
        self._source = source

    def check(self, cik: str, start: date, end: date, as_of: datetime) -> GuardCheck:
        due = self._source.binaries_between(cik, start, end, as_of)
        if due:
            return GuardCheck(
                "binary",
                min(c.period_start for c in due),
                max(c.period_end for c in due),
            )
        if not self._source.binaries_between(cik, _EARLIEST, _LATEST, as_of):
            return GuardCheck("no_data")
        return GuardCheck("clear")

    def window_days(self, cik: str, start: date, end: date, as_of: datetime) -> list[date]:
        """Days of day-precision binaries for `cik` in `[start, end]`, as known at `as_of`."""
        return sorted(
            c.period_start
            for c in self._source.binaries_between(cik, start, end, as_of)
            if c.precision == "day"
        )
