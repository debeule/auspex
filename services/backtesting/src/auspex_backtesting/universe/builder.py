from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

import pandas as pd

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.universe.listing import ListingHistory
from auspex_backtesting.universe.market_cap import market_cap_usd, median_dollar_volume
from auspex_backtesting.universe.model import (
    CompanyRecord,
    ListingSpan,
    PriceCoverage,
    ShareCount,
    UniverseMember,
    UniverseSnapshot,
)
from auspex_backtesting.universe.rules import UniverseRules

# A delisting notice takes effect ten days after filing and the stock trades until then, so bars
# shortly after `exited_on` are the company's own. Bars well past it belong to whoever the
# vendor later gave the symbol to.
_TRADING_AFTER_NOTICE = timedelta(days=30)
# Sessions a series may start late or end early and still count as complete: an IPO first
# trades a few days after its exchange registration, and the last bar before a build can lag.
_COVERAGE_TOLERANCE_SESSIONS = 5


class PriceSource(Protocol):
    def bars(self, ticker: str) -> pd.DataFrame | None:
        """Split-adjusted daily OHLCV with a UTC midnight index, or None."""
        ...

    def splits(self, ticker: str) -> pd.Series:
        """New-shares-per-old-share ratios indexed by split date; empty when none are known."""
        ...


def rebalance_date(month: str, calendar: MarketCalendar | None = None) -> date:
    """First NYSE session of `month` (`YYYY-MM`)."""
    return (calendar or MarketCalendar()).next_trading_day(_first_day(month))


@dataclass(frozen=True)
class _Prices:
    bars: pd.DataFrame
    coverage: PriceCoverage
    note: str


class UniverseBuilder:
    """Builds monthly snapshots from filings, share counts and price snapshots, using for each
    month only what was public before its rebalance session opened.

    `as_of` is the build date: the latest month that can be built is the one whose rebalance
    session is on or before it, and price coverage is judged up to it.
    """

    def __init__(
        self,
        rules: UniverseRules,
        companies: Sequence[CompanyRecord],
        shares: Mapping[str, Sequence[ShareCount]],
        prices: PriceSource,
        *,
        as_of: date,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self._rules = rules
        self._calendar = calendar or MarketCalendar()
        self._as_of = as_of
        self._shares = shares
        self._prices = prices
        eligible = sorted((c for c in companies if c.sic in rules.sic_codes), key=lambda c: c.cik)
        self._companies = [
            (c, ListingHistory.from_record(c, rules.exchanges)) for c in eligible
        ]
        self._priced: dict[tuple[str, ListingSpan], _Prices] = {}

    def tickers_listed_between(self, start: date, end: date) -> list[str]:
        """Resolved tickers of every eligible company listed at any time in `[start, end]`: the
        names whose prices a build over that period reads."""
        return sorted({
            history.ticker
            for _, history in self._companies
            if history.ticker is not None
            and any(
                s.entered_on <= end and (s.exited_on is None or s.exited_on >= start)
                for s in history.spans
            )
        })

    def listings(self) -> list[UniverseMember]:
        """Every eligible company's listing spans that overlap the window, as known on `as_of`,
        with price coverage. Unlike a month's snapshot, this view is rebuilt on every build, so
        it carries exits that happened after a month was stored."""
        window_start = self._rules.window_start
        rows = []
        for company, history in self._companies:
            for span in history.spans:
                if span.entered_on > self._as_of or (
                    span.exited_on is not None and span.exited_on < window_start
                ):
                    continue
                prices = self._prices_for(company, history, span)
                rows.append(self._row(company, history, span, prices, None, None))
        return rows

    def build(self, month: str) -> UniverseSnapshot:
        d = rebalance_date(month, self._calendar)
        self._check_month(month, d)
        members = [
            m
            for company, history in self._companies
            if (m := self._member(company, history, d)) is not None
        ]
        return UniverseSnapshot(self._rules.version, month, d, tuple(members))

    def _check_month(self, month: str, d: date) -> None:
        start = _first_day(month)
        rules = self._rules
        if start < rules.window_start.replace(day=1) or (
            rules.window_end is not None and start > rules.window_end
        ):
            raise ValueError(f"{month} is outside the rules window")
        if d > self._as_of:
            raise ValueError(f"{month} rebalances on {d}, after the build date {self._as_of}")

    def _member(
        self, company: CompanyRecord, history: ListingHistory, d: date
    ) -> UniverseMember | None:
        span = history.span_on(d)
        if span is None:
            return None
        prices = self._prices_for(company, history, span)
        before = prices.bars[_dates(prices.bars) < d].sort_index()
        recent = before.tail(self._rules.liquidity_sessions)
        cap = (
            market_cap_usd(
                self._shares.get(company.cik, ()),
                float(before["close"].iloc[-1]),
                d,
                self._prices.splits(history.ticker) if history.ticker else pd.Series(dtype=float),
            )
            if not before.empty
            else None
        )
        liquidity = median_dollar_volume(recent)
        # A rule that cannot be evaluated for lack of data does not exclude: dropping such names
        # would remove exactly the delisted companies the universe exists to keep.
        if cap is not None and cap < self._rules.min_market_cap_usd:
            return None
        if liquidity is not None and liquidity < self._rules.min_median_dollar_volume_usd:
            return None
        return self._row(company, history, span, prices, cap, liquidity)

    def _row(
        self,
        company: CompanyRecord,
        history: ListingHistory,
        span: ListingSpan,
        prices: _Prices,
        cap: float | None,
        liquidity: float | None,
    ) -> UniverseMember:
        return UniverseMember(
            cik=company.cik,
            ticker=history.ticker,
            ticker_source=history.ticker_source,
            name=company.name,
            sic=company.sic,
            exchange=next((e for e in company.exchanges if e in self._rules.exchanges), "unknown"),
            market_cap_usd=cap,
            median_dollar_volume_20d=liquidity,
            entered_on=span.entered_on,
            exited_on=span.exited_on,
            exit_reason=span.exit_reason,
            price_coverage=prices.coverage,
            coverage_note=prices.note,
        )

    def _prices_for(
        self, company: CompanyRecord, history: ListingHistory, span: ListingSpan
    ) -> _Prices:
        key = (company.cik, span)
        if key not in self._priced:
            self._priced[key] = self._load_prices(history, span)
        return self._priced[key]

    def _load_prices(self, history: ListingHistory, span: ListingSpan) -> _Prices:
        empty = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"],
            index=pd.DatetimeIndex([], tz="UTC", name="date"),
        )
        if history.ticker is None:
            return _Prices(empty, "none", "ticker unresolved")
        bars = self._prices.bars(history.ticker)
        if bars is None or bars.empty:
            return _Prices(empty, "none", f"no price history for {history.ticker}")
        dates = _dates(bars)
        if span.exited_on is not None and max(dates) > span.exited_on + _TRADING_AFTER_NOTICE:
            return _Prices(
                empty, "none",
                f"{history.ticker} trades until {max(dates)}, long after the exit on "
                f"{span.exited_on}: the ticker was reused by another issuer",
            )
        bars = bars[dates >= span.entered_on]
        if bars.empty:
            return _Prices(empty, "none", f"no price history for {history.ticker} while listed")
        return _Prices(bars, *self._coverage(bars, span))

    def _coverage(self, bars: pd.DataFrame, span: ListingSpan) -> tuple[PriceCoverage, str]:
        expected_first = max(span.entered_on, self._rules.window_start)
        expected_last = min(span.exited_on or self._as_of, self._as_of)
        dates = _dates(bars)
        first, last = min(dates), max(dates)
        gaps = []
        if self._sessions_between(expected_first, first) > _COVERAGE_TOLERANCE_SESSIONS:
            gaps.append(f"prices start {first}, listed from {expected_first}")
        if self._sessions_between(last, expected_last) > _COVERAGE_TOLERANCE_SESSIONS:
            gaps.append(f"prices end {last}, listed until {expected_last}")
        if gaps:
            return "partial", "; ".join(gaps)
        return "complete", ""

    def _sessions_between(self, start: date, end: date) -> int:
        if end <= start:
            return 0
        return self._calendar.trading_days_in(start + timedelta(days=1), end)


def _first_day(month: str) -> date:
    return date.fromisoformat(f"{month}-01")


def _dates(df: pd.DataFrame) -> pd.Index:
    return pd.Index(pd.DatetimeIndex(df.index).date)
