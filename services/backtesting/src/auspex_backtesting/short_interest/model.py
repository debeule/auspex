from dataclasses import dataclass
from datetime import date
from typing import Literal

from auspex_backtesting.ownership.reference import FactorMissing

PctMissing = Literal["not_reported", "no_share_count"] | FactorMissing
ChangeMissing = Literal["not_reported"] | FactorMissing


@dataclass(frozen=True)
class ShortInterestRecord:
    """One ticker in one FINRA settlement period. `reported` is False when FINRA published the
    period without this ticker: its counts are then unknown (None), never zero."""

    ticker: str
    settlement_date: date
    publication_date: date
    reported: bool
    short_interest_shares: int | None
    average_daily_volume: int | None
    days_to_cover: float | None

    @classmethod
    def from_counts(
        cls,
        ticker: str,
        settlement_date: date,
        publication_date: date,
        *,
        short_interest_shares: int | None,
        average_daily_volume: int | None,
    ) -> ShortInterestRecord:
        """A reported record when the short position is known; `days_to_cover` is the exact
        ratio, None when average daily volume is zero or unknown."""
        days = (
            short_interest_shares / average_daily_volume
            if short_interest_shares is not None and average_daily_volume
            else None
        )
        return cls(
            ticker, settlement_date, publication_date, short_interest_shares is not None,
            short_interest_shares, average_daily_volume, days,
        )

    @classmethod
    def absent(cls, ticker: str, settlement_date: date, publication_date: date) -> ShortInterestRecord:
        return cls(ticker, settlement_date, publication_date, False, None, None, None)


@dataclass(frozen=True)
class ShortInterestFeatures:
    """The latest published record and two figures derived from it, both on the share basis of
    the date asked about. A figure that cannot be put on that basis is None, with the reason."""

    record: ShortInterestRecord
    # Percent (0-100) of shares outstanding known on the date asked about.
    short_interest_pct_of_shares: float | None
    short_interest_pct_missing: PctMissing | None
    change_since_previous_shares: float | None
    change_since_previous_missing: ChangeMissing | None
