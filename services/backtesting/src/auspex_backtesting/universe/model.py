from dataclasses import dataclass
from datetime import date
from typing import Literal

ExitReason = Literal["delisted", "acquired", "deregistered"]
TickerSource = Literal["current", "filing", "unresolved"]
PriceCoverage = Literal["complete", "partial", "none"]


@dataclass(frozen=True)
class Filing:
    """One EDGAR filing as listed in a filer's submissions history. `filed` is the UTC filing
    date; `items` holds the 8-K item numbers."""

    form: str
    filed: date
    items: tuple[str, ...] = ()
    primary_document: str = ""


@dataclass(frozen=True)
class CompanyRecord:
    """A filer from SEC's submissions data. `sic`, `exchanges` and `tickers` are SEC's current
    values, not history; inactive filers usually have no exchange or ticker left."""

    cik: str
    name: str
    sic: str
    exchanges: tuple[str, ...]
    tickers: tuple[str, ...]
    filings: tuple[Filing, ...]


@dataclass(frozen=True)
class ShareCount:
    """A reported common-shares-outstanding value. `end` is the date the count refers to and
    is used only to place it against stock splits; `filed` is when it became public."""

    value: float
    end: date
    filed: date


@dataclass(frozen=True)
class ListingSpan:
    entered_on: date
    exited_on: date | None
    exit_reason: ExitReason | None


@dataclass(frozen=True)
class UniverseMember:
    cik: str
    ticker: str | None
    ticker_source: TickerSource
    name: str
    sic: str
    exchange: str
    market_cap_usd: float | None
    median_dollar_volume_20d: float | None
    entered_on: date
    exited_on: date | None
    exit_reason: ExitReason | None
    price_coverage: PriceCoverage
    coverage_note: str


@dataclass(frozen=True)
class UniverseSnapshot:
    """Members on `rebalance_date`, the first NYSE session of `month` (`YYYY-MM`), ordered by
    CIK."""

    rules_version: int
    month: str
    rebalance_date: date
    members: tuple[UniverseMember, ...]
