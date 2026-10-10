from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


class InsufficientEventsError(Exception):
    pass


@dataclass(frozen=True)
class WalkForwardSegment:
    in_sample: pd.DataFrame
    oos: pd.DataFrame
    in_sample_start: date
    boundary: date
    oos_end: date
    oos_truncated: bool


class WalkForwardSplitter:
    """Rolling in-sample and out-of-sample segments over the events before the holdout.

    The holdout is the last `holdout_months` of the event date range; no segment touches it.
    Segments slide by the out-of-sample length, and the last one's out-of-sample part is cut at
    the holdout (`oos_truncated`) rather than dropped. Events within `embargo_days` either side
    of a segment's boundary are left out of both parts.
    """

    def __init__(self, holdout_months: int, date_column: str = "corroborated_at") -> None:
        self._holdout_months = holdout_months
        self._column = date_column

    def holdout_start(self, events: pd.DataFrame) -> date:
        """First day of the holdout; the events before it are the ones a run may read."""
        if events.empty:
            raise InsufficientEventsError("no events")
        end = _dates(events[self._column]).max() + timedelta(days=1)
        return _add_months(end, -self._holdout_months)

    def before_holdout(self, events: pd.DataFrame) -> pd.DataFrame:
        return events[_dates(events[self._column]) < self.holdout_start(events)]

    def holdout(self, events: pd.DataFrame) -> pd.DataFrame:
        return events[_dates(events[self._column]) >= self.holdout_start(events)]

    def split(
        self,
        events: pd.DataFrame,
        in_sample_months: int,
        oos_months: int,
        embargo_days: int,
    ) -> list[WalkForwardSegment]:
        if events.empty:
            raise InsufficientEventsError(
                f"need {in_sample_months} in-sample months plus out-of-sample time; no events"
            )
        dates = _dates(events[self._column])
        start = dates.min()
        usable_end = self.holdout_start(events)
        segments: list[WalkForwardSegment] = []
        k = 0
        while True:
            seg_start = _add_months(start, k * oos_months)
            boundary = _add_months(seg_start, in_sample_months)
            if boundary >= usable_end:
                break
            oos_end = min(_add_months(boundary, oos_months), usable_end)
            embargo = timedelta(days=embargo_days)
            in_sample = (dates >= seg_start) & (dates < boundary - embargo)
            oos = (dates >= boundary + embargo) & (dates < oos_end)
            segments.append(
                WalkForwardSegment(
                    in_sample=events[in_sample],
                    oos=events[oos],
                    in_sample_start=seg_start,
                    boundary=boundary,
                    oos_end=oos_end,
                    oos_truncated=oos_end < _add_months(boundary, oos_months),
                )
            )
            k += 1
        if not segments:
            available = (usable_end - start).days
            raise InsufficientEventsError(
                f"need more than {in_sample_months} months of events before the "
                f"{self._holdout_months}-month holdout; {len(events)} events span {available} days"
            )
        return segments


def _dates(column: pd.Series) -> pd.Series:
    return pd.to_datetime(column).dt.date


def _add_months(d: date, months: int) -> date:
    result: date = (pd.Timestamp(d) + pd.DateOffset(months=months)).date()
    return result
