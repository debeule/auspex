"""The cross-sectional portfolio backtest: rank, size, trade at the next open, mark daily."""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal, Protocol

import numpy as np
import pandas as pd

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.market_sim.costs import CostModel
from auspex_backtesting.market_sim.errors import MissingPriceDataError
from auspex_backtesting.market_sim.fills import FillModel
from auspex_backtesting.market_sim.fx import CurrencyConverter
from auspex_backtesting.portfolio.guard import CatalystGuard, CatalystSource
from auspex_backtesting.portfolio.rules import (
    PortfolioRule,
    ScoreRef,
    bottom_quintile,
    rank_scores,
)
from auspex_backtesting.portfolio.scores import ScoreSnapshot, score_key
from auspex_backtesting.portfolio.sizing import EqualRiskSizer, trailing_volatility
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore
from auspex_backtesting.universe.model import UniverseMember, UniverseSnapshot

BENCHMARK_TICKER = "XBI"
# The universe spec's bound on the loss of a delisting whose last prices are missing.
DELISTING_TAIL_RETURN = -0.30
_DELISTING_EXITS = ("delisted", "deregistered")
_MONTHS_PER_YEAR = 12
_TOP_SHARE = 0.05
# Headroom for a buy's own costs, so buys never spend more cash than the account holds.
_COST_BUFFER = 0.01

Benchmark = Literal["universe_equal_weight", "xbi"]


class MissingInputSnapshotError(LookupError):
    """A universe or score snapshot the run needs is not stored. Never computed on the fly."""


class UniverseSource(Protocol):
    def read(self, rules_version: int, month: str) -> UniverseSnapshot | None: ...
    def read_listings(self, rules_version: int) -> tuple[list[UniverseMember], date] | None: ...


class ScoreSource(Protocol):
    def dates(self, hypothesis_id: str, version: str) -> list[date]: ...
    def read(
        self, hypothesis_id: str, version: str, rebalance_date: date
    ) -> ScoreSnapshot | None: ...


@dataclass(frozen=True)
class Trade:
    session: date
    ticker: str
    shares: int
    price_usd: float
    costs: Mapping[str, float]
    reason: Literal["rebalance", "guard_exit", "guard_reentry"]

    @property
    def notional_usd(self) -> float:
        return abs(self.shares) * self.price_usd


@dataclass(frozen=True)
class Closeout:
    """A held name whose prices stopped, closed at `price_usd` as of its last bar."""

    ticker: str
    last_date: date
    shares: int
    last_close_usd: float
    price_usd: float
    delisting_bound: bool


@dataclass(frozen=True)
class GuardReport:
    """Names the catalyst guard looked at for one decision, and what it did with them."""

    checked: int = 0
    clear: int = 0
    binary: int = 0
    no_data: int = 0
    skipped: tuple[str, ...] = ()
    exited: tuple[str, ...] = ()
    members_without_catalyst_data: int = 0


@dataclass(frozen=True)
class Decision:
    decision_date: date
    fill_date: date
    score_date: date
    ranks: Mapping[str, int]
    weights: Mapping[str, float]
    cash_weight: float
    excluded_by_filter: tuple[str, ...]
    unsized: tuple[str, ...]
    guard: GuardReport


@dataclass(frozen=True)
class MonthRow:
    """One calendar month. Returns are fractions; `turnover` is one-way traded value over the
    month's opening value; `cash_share` is the mean daily share of value held as cash."""

    month: str
    start_value_usd: float
    end_value_usd: float
    gross_return: float
    net_return: float
    cost_usd: float
    turnover: float
    n_names: int
    cash_share: float
    xbi_return: float
    universe_ew_return: float
    delisting_bound: bool

    @property
    def invested_share(self) -> float:
        return 1.0 - self.cash_share

    @property
    def excess_over_xbi(self) -> float:
        return self.net_return - self.xbi_return

    @property
    def excess_over_universe_ew(self) -> float:
        return self.net_return - self.universe_ew_return

    @property
    def excess_over_invested_universe_ew(self) -> float:
        """Against the universe equal-weight held at the portfolio's invested share, the rest
        in cash earning nothing."""
        return self.net_return - self.invested_share * self.universe_ew_return


@dataclass(frozen=True)
class QuintileMonth:
    month: str
    score_date: date
    top_return: float
    bottom_return: float

    @property
    def spread(self) -> float:
        return self.top_return - self.bottom_return


@dataclass(frozen=True)
class PortfolioResult:
    rule: PortfolioRule
    tier_eur: float
    start: date
    end: date
    capital_usd: float
    months: tuple[MonthRow, ...]
    decisions: tuple[Decision, ...]
    trades: tuple[Trade, ...]
    closeouts: tuple[Closeout, ...]
    cost_by_component: Mapping[str, float]
    yearly_cost_drag: float
    round_trips_per_year: float
    average_round_trip_cost: float
    average_holding_days: float
    holding_days_by_name: Mapping[str, float]
    catalyst_window_return: float
    other_days_return: float
    catalyst_window_days: int
    other_days: int
    rolling_beta_to_xbi: tuple[tuple[str, float], ...]
    worst_name_month: tuple[str, str, float] | None
    top_name_month_share: float
    skipped_tickets: int
    member_months: int
    unpriced_member_months: int
    quintiles: tuple[QuintileMonth, ...]
    guard_totals: GuardReport = field(default_factory=GuardReport)

    @property
    def delisting_bound_months(self) -> tuple[str, ...]:
        return tuple(m.month for m in self.months if m.delisting_bound)

    @property
    def unpriced_member_month_share(self) -> float:
        return self.unpriced_member_months / self.member_months if self.member_months else 0.0

    def monthly_net_excess(self, benchmark: Benchmark) -> list[float]:
        if benchmark == "xbi":
            return [m.excess_over_xbi for m in self.months]
        return [m.excess_over_universe_ew for m in self.months]

    def monthly_gross_excess(self, benchmark: Benchmark) -> list[float]:
        bench = {
            "xbi": lambda m: m.xbi_return,
            "universe_equal_weight": lambda m: m.universe_ew_return,
        }
        return [m.gross_return - bench[benchmark](m) for m in self.months]


class _Series:
    def __init__(self, frame: pd.DataFrame) -> None:
        frame = frame.sort_index()
        self.dates: list[date] = list(pd.DatetimeIndex(frame.index).date)
        self.opens = dict(zip(self.dates, frame["open"].astype(float), strict=True))
        self.closes = dict(zip(self.dates, frame["close"].astype(float), strict=True))

    @property
    def last_date(self) -> date:
        return self.dates[-1]

    def close_on_or_before(self, d: date) -> tuple[date, float] | None:
        i = bisect.bisect_right(self.dates, d)
        if i == 0:
            return None
        found = self.dates[i - 1]
        return found, self.closes[found]

    def closes_before(self, d: date, n: int) -> list[float]:
        i = bisect.bisect_left(self.dates, d)
        return [self.closes[x] for x in self.dates[max(0, i - n) : i]]


class _PriceBook:
    def __init__(self, store: PriceSnapshotStore) -> None:
        self._store = store
        self._series: dict[str, _Series | None] = {}

    def get(self, ticker: str) -> _Series | None:
        if ticker not in self._series:
            frame = self._store.load(ticker)
            self._series[ticker] = None if frame is None or frame.empty else _Series(frame)
        return self._series[ticker]

    def require(self, ticker: str) -> _Series:
        series = self.get(ticker)
        if series is None:
            raise MissingPriceDataError(f"no price snapshot for {ticker}")
        return series


@dataclass
class _Book:
    cash: float
    shares: dict[str, int] = field(default_factory=dict)
    marks: dict[str, float] = field(default_factory=dict)
    opened: dict[str, date] = field(default_factory=dict)
    spells: list[tuple[str, date, date]] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    closeouts: list[Closeout] = field(default_factory=list)
    flows: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    session_cost: float = 0.0
    session_traded: float = 0.0

    def value(self) -> float:
        return self.cash + sum(n * self.marks[t] for t, n in self.shares.items())


class PortfolioBacktest:
    """Monthly scores to a traded, costed, daily-marked long-only portfolio.

    At each decision date the universe snapshot of that month and the latest score snapshot
    dated on or before it are ranked; the rule picks the names, the catalyst guard removes or
    schedules around binaries, and `EqualRiskSizer` weights them on volatility from sessions
    before the decision date. Orders fill at the open of the next session, through `FillModel`,
    with each order costed by `CostModel` at the capital tier's size. A held name whose prices
    stop is closed at its last close; when it was delisted or deregistered and its prices stop
    before the last session before `exited_on`, the missing tail is booked at -30% and the
    month flagged.
    """

    def __init__(
        self,
        *,
        prices: PriceSnapshotStore,
        universe: UniverseSource,
        scores: ScoreSource,
        cost_model: CostModel,
        sizer: EqualRiskSizer,
        catalysts: CatalystSource | None = None,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self._store = prices
        self._universe = universe
        self._scores = scores
        self._costs = cost_model
        self._sizer = sizer
        self._guard = CatalystGuard(catalysts) if catalysts is not None else None
        self._calendar = calendar or MarketCalendar()
        self._fills = FillModel(prices, self._calendar)
        self._fx = CurrencyConverter(prices)

    def input_keys(
        self, rule: PortfolioRule, universe_version: int, start: date, end: date
    ) -> list[str]:
        """Every universe and score snapshot a run over `[start, end]` reads, as object keys."""
        decisions = rule.decision_dates(start, end, self._calendar)
        months = _months_between(start, end) | {d.strftime("%Y-%m") for d in decisions}
        keys = {f"universe/{universe_version}/{m}.parquet" for m in months}
        for ref in (rule.score, rule.exclusion):
            if ref is None:
                continue
            dates = self._scores.dates(ref.hypothesis_id, ref.version)
            used = {_latest_on_or_before(dates, d) for d in decisions}
            used |= {_latest_on_or_before(dates, self._first_session(m)) for m in months}
            keys |= {score_key(ref.hypothesis_id, ref.version, d) for d in used if d is not None}
        return sorted(keys)

    def run(
        self, rule: PortfolioRule, universe_version: int, tier_eur: float, start: date, end: date
    ) -> PortfolioResult:
        if rule.catalyst_guard != "none" and self._guard is None:
            raise ValueError(f"catalyst guard {rule.catalyst_guard} needs a catalyst source")
        book = _PriceBook(self._store)
        decision_dates = rule.decision_dates(start, end, self._calendar)
        fill_dates = [self._next_session(d) for d in decision_dates]
        if not fill_dates or fill_dates[0] > end:
            raise ValueError(f"no decision date with a fill in {start}..{end}")
        sessions = self._calendar.sessions_between(fill_dates[0], end)
        listings = self._listings(universe_version)
        capital_usd = tier_eur / self._fx.eur_per_usd(fill_dates[0])
        state = _Book(cash=capital_usd)
        ticker_cik: dict[str, str] = {}

        decisions: list[Decision] = []
        fills = dict(zip(fill_dates, decision_dates, strict=True))
        next_fill = {
            f: (fill_dates[i + 1] if i + 1 < len(fill_dates) else end + timedelta(days=1))
            for i, f in enumerate(fill_dates)
        }
        exits_at: dict[date, list[str]] = defaultdict(list)
        reentries_at: dict[date, list[tuple[str, float]]] = defaultdict(list)
        skipped_tickets = 0

        all_sessions = self._calendar.sessions_between(
            fill_dates[0] - timedelta(days=40), end + timedelta(days=40)
        )
        window_as_of = self._calendar.session_close(sessions[-1])
        window_sessions: dict[str, set[date]] = {}

        month_rows: list[dict[str, object]] = []
        month_start_value = capital_usd
        month_costs = 0.0
        month_traded = 0.0
        month_cash_shares: list[float] = []
        month_flagged = False
        name_month_pnl: dict[tuple[str, str], float] = defaultdict(float)
        name_month_base: dict[str, float] = {}
        window_return = other_return = 0.0
        window_days = other_days = 0
        prev_value = capital_usd

        for i, s in enumerate(sessions):
            month = s.strftime("%Y-%m")
            name_month_base.setdefault(month, month_start_value)
            before = {t: n * state.marks[t] for t, n in state.shares.items()}
            state.flows = defaultdict(float)
            state.session_cost = 0.0
            state.session_traded = 0.0

            for ticker in list(state.shares):
                series = book.require(ticker)
                if s not in series.closes and series.last_date < s:
                    month_flagged |= self._close_out(
                        state, ticker, ticker_cik[ticker], series, s, listings
                    )

            for ticker, weight in reentries_at.pop(s, []):
                if state.shares.get(ticker):
                    continue
                if not self._buy_weight(state, book, ticker, weight, s, "guard_reentry"):
                    skipped_tickets += 1

            if s in fills:
                decision = self._decide(
                    rule,
                    universe_version,
                    fills[s],
                    s,
                    next_fill[s],
                    book,
                    state,
                    ticker_cik,
                    exits_at,
                    reentries_at,
                )
                decisions.append(decision)
                skipped_tickets += self._rebalance(state, book, decision, s, ticker_cik)

            for ticker in exits_at.pop(s, []):
                shares = state.shares.get(ticker, 0)
                close = book.require(ticker).closes.get(s)
                if shares and close is not None:
                    self._trade(state, ticker, -shares, close, s, "guard_exit")

            for ticker in state.shares:
                close = book.require(ticker).closes.get(s)
                if close is not None:
                    state.marks[ticker] = close
            value = state.value()

            for ticker in set(before) | set(state.flows) | set(state.shares):
                after = state.shares.get(ticker, 0) * state.marks.get(ticker, 0.0)
                pnl = after - before.get(ticker, 0.0) - state.flows.get(ticker, 0.0)
                if pnl == 0.0:
                    continue
                name_month_pnl[(ticker, month)] += pnl
                cik = ticker_cik[ticker]
                if cik not in window_sessions:
                    window_sessions[cik] = self._window_sessions(
                        rule, cik, all_sessions, sessions[0], end, window_as_of
                    )
                if s in window_sessions[cik]:
                    window_return += pnl / prev_value
                else:
                    other_return += pnl / prev_value
            if any(s in window_sessions.get(ticker_cik[t], set()) for t in state.shares):
                window_days += 1
            elif state.shares:
                other_days += 1

            month_costs += state.session_cost
            month_traded += state.session_traded
            month_cash_shares.append(state.cash / value if value else 1.0)
            prev_value = value

            last_of_month = i + 1 == len(sessions) or sessions[i + 1].month != s.month
            if last_of_month:
                month_rows.append(
                    {
                        "month": month,
                        "start": month_start_value,
                        "end": value,
                        "costs": month_costs,
                        "traded": month_traded,
                        "names": sum(1 for n in state.shares.values() if n),
                        "cash_share": float(np.mean(month_cash_shares)),
                        "flagged": month_flagged,
                        "end_session": s,
                    }
                )
                month_start_value = value
                month_costs = month_traded = 0.0
                month_cash_shares = []
                month_flagged = False

        for ticker, opened in state.opened.items():
            state.spells.append((ticker, opened, sessions[-1]))

        base_first = self._previous_session(sessions[0])
        months = self._month_rows(month_rows, base_first, book, universe_version, listings)
        member_months, unpriced = self._member_months(month_rows, book, universe_version)
        quintiles = self._quintiles(rule, month_rows, book, universe_version, listings)
        return self._result(
            rule,
            tier_eur,
            start,
            end,
            capital_usd,
            months,
            decisions,
            state,
            skipped_tickets,
            name_month_pnl,
            name_month_base,
            window_return,
            other_return,
            window_days,
            other_days,
            member_months,
            unpriced,
            quintiles,
            sessions,
        )

    def _decide(
        self,
        rule: PortfolioRule,
        universe_version: int,
        decision_date: date,
        fill_date: date,
        next_fill: date,
        book: _PriceBook,
        state: _Book,
        ticker_cik: dict[str, str],
        exits_at: dict[date, list[str]],
        reentries_at: dict[date, list[tuple[str, float]]],
    ) -> Decision:
        snapshot = self._universe_snapshot(universe_version, decision_date.strftime("%Y-%m"))
        members = {m.cik: m for m in snapshot.members if m.ticker}
        for cik, member in members.items():
            assert member.ticker is not None
            ticker_cik.setdefault(member.ticker, cik)
        scores = self._score_snapshot(rule.score, decision_date)
        ranks = rank_scores(scores.rows, set(members))
        cik_ticker = {cik: m.ticker for cik, m in members.items()}
        held_ciks = {ticker_cik[t] for t, n in state.shares.items() if n}
        target = rule.target(ranks, held_ciks)

        excluded: set[str] = set()
        if rule.exclusion is not None:
            filter_scores = self._score_snapshot(rule.exclusion, decision_date)
            excluded = bottom_quintile(rank_scores(filter_scores.rows, set(members))) & target
            target -= excluded

        guard = GuardReport()
        reentry: dict[str, tuple[date, date]] = {}
        if rule.catalyst_guard != "none":
            assert self._guard is not None
            target, guard, exit_before, reentry = self._apply_guard(
                rule, target, ranks, held_ciks, set(members), decision_date, fill_date, next_fill
            )
        else:
            exit_before = {}

        volatilities: dict[str, float] = {}
        unsized: list[str] = []
        for cik in sorted(target | set(reentry)):
            ticker = cik_ticker[cik]
            series = book.get(ticker) if ticker else None
            vol = (
                trailing_volatility(
                    series.closes_before(decision_date, rule.volatility_sessions + 1),
                    rule.volatility_sessions,
                )
                if series is not None
                else None
            )
            if vol is None:
                unsized.append(cik)
            else:
                volatilities[cik] = vol
        sized = self._sizer.weights(
            {c: v for c, v in volatilities.items() if c in target or c in reentry}
        )
        weights = {c: w for c, w in sized.weights.items() if c in target}

        for cik, start in exit_before.items():
            if cik in weights:
                exits_at[self._previous_session(start)].append(cik_ticker[cik] or "")
        for cik, (_, binary_end) in reentry.items():
            if cik not in sized.weights:
                continue
            back = self._next_session(binary_end)
            if back < next_fill:
                reentries_at[back].append((cik_ticker[cik] or "", sized.weights[cik]))
        return Decision(
            decision_date=decision_date,
            fill_date=fill_date,
            score_date=scores.rebalance_date,
            ranks=ranks,
            weights={cik_ticker[c] or c: w for c, w in weights.items()},
            cash_weight=1.0 - sum(weights.values()),
            excluded_by_filter=tuple(sorted(excluded)),
            unsized=tuple(unsized),
            guard=guard,
        )

    def _apply_guard(
        self,
        rule: PortfolioRule,
        target: set[str],
        ranks: Mapping[str, int],
        held: set[str],
        members: set[str],
        decision_date: date,
        fill_date: date,
        next_fill: date,
    ) -> tuple[set[str], GuardReport, dict[str, date], dict[str, tuple[date, date]]]:
        assert self._guard is not None
        as_of = self._calendar.session_open(decision_date)
        window_end = next_fill - timedelta(days=1)
        kept = set(target)
        counts = {"clear": 0, "binary": 0, "no_data": 0}
        skipped: list[str] = []
        exited: list[str] = []
        exit_before: dict[str, date] = {}
        reentry: dict[str, tuple[date, date]] = {}
        for cik in sorted(target):
            guarded = {
                "skip_entry": cik not in held,
                "exit_and_reenter": True,
                "exit_low_score_only": cik in held
                and not rule.in_entry_band(ranks.get(cik), len(ranks)),
            }[rule.catalyst_guard]
            check = self._guard.check(cik, fill_date, window_end, as_of)
            counts[check.status] += 1
            if not guarded or check.status != "binary":
                continue
            assert check.binary_start is not None and check.binary_end is not None
            if rule.catalyst_guard == "skip_entry":
                kept.discard(cik)
                skipped.append(cik)
                continue
            exited.append(cik)
            if check.binary_start <= fill_date:
                kept.discard(cik)
            else:
                exit_before[cik] = check.binary_start
            reentry[cik] = (check.binary_start, check.binary_end)
        without_data = sum(
            1
            for cik in members
            if self._guard.check(cik, fill_date, window_end, as_of).status == "no_data"
        )
        report = GuardReport(
            checked=len(target),
            clear=counts["clear"],
            binary=counts["binary"],
            no_data=counts["no_data"],
            skipped=tuple(skipped),
            exited=tuple(exited),
            members_without_catalyst_data=without_data,
        )
        return kept, report, exit_before, reentry

    def _rebalance(
        self,
        state: _Book,
        book: _PriceBook,
        decision: Decision,
        session: date,
        ticker_cik: Mapping[str, str],
    ) -> int:
        """Sells, then buys within the cash available; returns new positions skipped as below
        the minimum ticket."""
        opens = {
            t: book.require(t).opens.get(session) for t in set(state.shares) | set(decision.weights)
        }
        for ticker, price in opens.items():
            if price is not None and ticker in state.shares:
                state.marks[ticker] = price
        value = state.value()
        min_ticket = self._costs.min_ticket_usd()
        skipped = 0
        orders: dict[str, int] = {}
        for ticker in sorted(set(state.shares) | set(decision.weights)):
            price = opens[ticker]
            if price is None:
                continue
            current = state.shares.get(ticker, 0)
            wanted = math.floor(decision.weights.get(ticker, 0.0) * value / price)
            if current == 0 and wanted * price < min_ticket:
                skipped += 1 if ticker in decision.weights else 0
                continue
            if wanted and abs(wanted - current) * price < min_ticket:
                continue
            if wanted != current:
                orders[ticker] = wanted - current
        for ticker, delta in orders.items():
            if delta < 0:
                self._trade(
                    state,
                    ticker,
                    delta,
                    self._fills.entry_price(ticker, session),
                    session,
                    "rebalance",
                )
        prices = {t: p for t, p in opens.items() if p is not None}
        buys = {t: d for t, d in orders.items() if d > 0}
        spend = sum(d * prices[t] * (1 + _COST_BUFFER) for t, d in buys.items())
        scale = min(1.0, state.cash / spend) if spend > 0 else 1.0
        for ticker, delta in sorted(buys.items()):
            shares = math.floor(delta * scale)
            if shares > 0:
                self._trade(
                    state,
                    ticker,
                    shares,
                    self._fills.entry_price(ticker, session),
                    session,
                    "rebalance",
                )
        return skipped

    def _buy_weight(
        self,
        state: _Book,
        book: _PriceBook,
        ticker: str,
        weight: float,
        session: date,
        reason: Literal["guard_reentry"],
    ) -> bool:
        price = book.require(ticker).opens.get(session)
        if price is None:
            return False
        shares = math.floor(min(weight * state.value(), state.cash / (1 + _COST_BUFFER)) / price)
        if shares * price < self._costs.min_ticket_usd():
            return False
        self._trade(state, ticker, shares, price, session, reason)
        return True

    def _trade(
        self,
        state: _Book,
        ticker: str,
        shares: int,
        price: float,
        session: date,
        reason: Literal["rebalance", "guard_exit", "guard_reentry"],
    ) -> None:
        cost = self._costs.leg_cost_usd(ticker, price, shares, session)
        state.cash -= shares * price + float(cost)
        state.session_cost += float(cost)
        state.session_traded += abs(shares) * price
        state.flows[ticker] += shares * price
        held = state.shares.get(ticker, 0) + shares
        if state.shares.get(ticker, 0) == 0 and held > 0:
            state.opened[ticker] = session
        if held == 0:
            state.shares.pop(ticker, None)
            state.marks.pop(ticker, None)
            state.spells.append((ticker, state.opened.pop(ticker), session))
        else:
            state.shares[ticker] = held
            state.marks[ticker] = price
        state.trades.append(Trade(session, ticker, shares, price, cost.components(), reason))

    def _close_out(
        self,
        state: _Book,
        ticker: str,
        cik: str,
        series: _Series,
        session: date,
        listings: Mapping[str, UniverseMember],
    ) -> bool:
        """Closes a position whose prices have stopped; True when the delisting bound applied."""
        last_date, last_close = series.last_date, series.closes[series.last_date]
        price = last_close
        bound = False
        listing = listings.get(cik)
        if (
            listing is not None
            and listing.exit_reason in _DELISTING_EXITS
            and listing.exited_on is not None
            and last_date < self._previous_session(listing.exited_on)
        ):
            price = last_close * (1 + DELISTING_TAIL_RETURN)
            bound = True
        shares = state.shares.pop(ticker)
        state.marks.pop(ticker, None)
        state.cash += shares * price
        state.flows[ticker] -= shares * price
        state.spells.append((ticker, state.opened.pop(ticker), last_date))
        state.closeouts.append(Closeout(ticker, last_date, shares, last_close, price, bound))
        return bound

    def _window_sessions(
        self,
        rule: PortfolioRule,
        cik: str,
        all_sessions: Sequence[date],
        start: date,
        end: date,
        as_of: object,
    ) -> set[date]:
        if self._guard is None:
            return set()
        k = rule.catalyst_window_sessions
        days = self._guard.window_days(
            cik,
            start - timedelta(days=30),
            end + timedelta(days=30),
            as_of,  # type: ignore[arg-type]
        )
        window: set[date] = set()
        for day in days:
            i = bisect.bisect_left(all_sessions, day)
            window.update(all_sessions[max(0, i - k) : i + k + 1])
        return window

    def _month_rows(
        self,
        rows: list[dict[str, object]],
        base_first: date,
        book: _PriceBook,
        universe_version: int,
        listings: Mapping[str, UniverseMember],
    ) -> tuple[MonthRow, ...]:
        xbi = book.require(BENCHMARK_TICKER)
        out = []
        base = base_first
        for row in rows:
            end_session = row["end_session"]
            assert isinstance(end_session, date)
            snapshot = self._universe_snapshot(universe_version, str(row["month"]))
            member_returns = [
                r
                for m in snapshot.members
                if (r := self._member_return(m, book, base, end_session, listings)) is not None
            ]
            start_value, end_value = float(row["start"]), float(row["end"])  # type: ignore[arg-type]
            costs = float(row["costs"])  # type: ignore[arg-type]
            out.append(
                MonthRow(
                    month=str(row["month"]),
                    start_value_usd=start_value,
                    end_value_usd=end_value,
                    gross_return=(end_value + costs) / start_value - 1,
                    net_return=end_value / start_value - 1,
                    cost_usd=costs,
                    turnover=float(row["traded"]) / 2 / start_value,  # type: ignore[arg-type]
                    n_names=int(row["names"]),  # type: ignore[call-overload]
                    cash_share=float(row["cash_share"]),  # type: ignore[arg-type]
                    xbi_return=_period_return(xbi, base, end_session),
                    universe_ew_return=float(np.mean(member_returns)) if member_returns else 0.0,
                    delisting_bound=bool(row["flagged"]),
                )
            )
            base = end_session
        return tuple(out)

    def _member_months(
        self, rows: list[dict[str, object]], book: _PriceBook, universe_version: int
    ) -> tuple[int, int]:
        total = unpriced = 0
        for row in rows:
            snapshot = self._universe_snapshot(universe_version, str(row["month"]))
            total += len(snapshot.members)
            unpriced += sum(
                1
                for m in snapshot.members
                if m.ticker is None or m.price_coverage == "none" or book.get(m.ticker) is None
            )
        return total, unpriced

    def _quintiles(
        self,
        rule: PortfolioRule,
        rows: list[dict[str, object]],
        book: _PriceBook,
        universe_version: int,
        listings: Mapping[str, UniverseMember],
    ) -> tuple[QuintileMonth, ...]:
        """Top and bottom score quintiles of the universe, equal-weighted, from the close of
        each month's score date to the month's last close. Gross of costs."""
        out = []
        for row in rows:
            month = str(row["month"])
            end_session = row["end_session"]
            assert isinstance(end_session, date)
            score_date = self._latest_score_date(rule.score, self._first_session(month))
            if score_date is None or score_date > end_session:
                continue
            snapshot = self._universe_snapshot(universe_version, month)
            members = {m.cik: m for m in snapshot.members if m.ticker}
            scores = self._score_snapshot(rule.score, score_date)
            ranks = rank_scores(scores.rows, set(members))
            q = len(ranks) // 5
            if q == 0:
                continue

            n = len(ranks)
            top = [members[c] for c, r in ranks.items() if r <= q]
            bottom = [members[c] for c, r in ranks.items() if r > n - q]
            out.append(
                QuintileMonth(
                    month,
                    score_date,
                    self._mean_return(top, book, score_date, end_session, listings),
                    self._mean_return(bottom, book, score_date, end_session, listings),
                )
            )
        return tuple(out)

    def _mean_return(
        self,
        members: Sequence[UniverseMember],
        book: _PriceBook,
        base: date,
        end: date,
        listings: Mapping[str, UniverseMember],
    ) -> float:
        values = [
            r
            for m in members
            if (r := self._member_return(m, book, base, end, listings)) is not None
        ]
        return float(np.mean(values)) if values else 0.0

    def _member_return(
        self,
        member: UniverseMember,
        book: _PriceBook,
        base: date,
        end: date,
        listings: Mapping[str, UniverseMember],
    ) -> float | None:
        if member.ticker is None or member.price_coverage == "none":
            return None
        series = book.get(member.ticker)
        if series is None:
            return None
        start = series.close_on_or_before(base)
        last = series.close_on_or_before(end)
        if start is None or last is None or series.last_date <= base:
            return None
        value = last[1] / start[1] - 1
        listing = listings.get(member.cik)
        if (
            series.last_date < end
            and listing is not None
            and listing.exit_reason in _DELISTING_EXITS
            and listing.exited_on is not None
            and series.last_date < self._previous_session(listing.exited_on)
        ):
            value = (1 + value) * (1 + DELISTING_TAIL_RETURN) - 1
        return value

    def _result(
        self,
        rule: PortfolioRule,
        tier_eur: float,
        start: date,
        end: date,
        capital_usd: float,
        months: tuple[MonthRow, ...],
        decisions: list[Decision],
        state: _Book,
        skipped: int,
        name_month_pnl: Mapping[tuple[str, str], float],
        name_month_base: Mapping[str, float],
        window_return: float,
        other_return: float,
        window_days: int,
        other_days: int,
        member_months: int,
        unpriced: int,
        quintiles: tuple[QuintileMonth, ...],
        sessions: Sequence[date],
    ) -> PortfolioResult:
        components: dict[str, float] = defaultdict(float)
        for trade in state.trades:
            for name, amount in trade.costs.items():
                components[name] += amount
        total_cost = sum(components.values())
        traded = sum(t.notional_usd for t in state.trades)
        years = max((sessions[-1] - sessions[0]).days, 1) / 365.25
        mean_value = float(np.mean([m.end_value_usd for m in months])) if months else capital_usd
        round_trips = traded / 2 / mean_value / years
        round_trip_cost = total_cost / (traded / 2) if traded else 0.0

        by_name: dict[str, list[int]] = defaultdict(list)
        for ticker, opened, closed in state.spells:
            by_name[ticker].append((closed - opened).days)
        spells = [d for days in by_name.values() for d in days]

        contributions = {
            (ticker, month): pnl / name_month_base[month]
            for (ticker, month), pnl in name_month_pnl.items()
        }
        worst = min(contributions.items(), key=lambda kv: kv[1]) if contributions else None
        net_pnl = (months[-1].end_value_usd - capital_usd) if months else 0.0
        pnls = sorted(name_month_pnl.values(), reverse=True)
        top_k = max(1, math.ceil(_TOP_SHARE * len(pnls))) if pnls else 0
        top_share = sum(pnls[:top_k]) / net_pnl if pnls and net_pnl > 0 else float("nan")

        guard_totals = GuardReport(
            checked=sum(d.guard.checked for d in decisions),
            clear=sum(d.guard.clear for d in decisions),
            binary=sum(d.guard.binary for d in decisions),
            no_data=sum(d.guard.no_data for d in decisions),
            skipped=tuple(c for d in decisions for c in d.guard.skipped),
            exited=tuple(c for d in decisions for c in d.guard.exited),
            members_without_catalyst_data=sum(
                d.guard.members_without_catalyst_data for d in decisions
            ),
        )
        return PortfolioResult(
            rule=rule,
            tier_eur=tier_eur,
            start=start,
            end=end,
            capital_usd=capital_usd,
            months=months,
            decisions=tuple(decisions),
            trades=tuple(state.trades),
            closeouts=tuple(state.closeouts),
            cost_by_component=dict(components),
            yearly_cost_drag=round_trip_cost * round_trips,
            round_trips_per_year=round_trips,
            average_round_trip_cost=round_trip_cost,
            average_holding_days=float(np.mean(spells)) if spells else 0.0,
            holding_days_by_name={t: float(np.mean(d)) for t, d in sorted(by_name.items())},
            catalyst_window_return=window_return,
            other_days_return=other_return,
            catalyst_window_days=window_days,
            other_days=other_days,
            rolling_beta_to_xbi=_rolling_beta(months),
            worst_name_month=(worst[0][0], worst[0][1], worst[1]) if worst else None,
            top_name_month_share=top_share,
            skipped_tickets=skipped,
            member_months=member_months,
            unpriced_member_months=unpriced,
            quintiles=quintiles,
            guard_totals=guard_totals,
        )

    def _universe_snapshot(self, universe_version: int, month: str) -> UniverseSnapshot:
        snapshot = self._universe.read(universe_version, month)
        if snapshot is None:
            raise MissingInputSnapshotError(f"no universe snapshot {universe_version}/{month}")
        return snapshot

    def _score_snapshot(self, ref: ScoreRef, as_of: date) -> ScoreSnapshot:
        score_date = self._latest_score_date(ref, as_of)
        snapshot = (
            self._scores.read(ref.hypothesis_id, ref.version, score_date) if score_date else None
        )
        if snapshot is None:
            raise MissingInputSnapshotError(
                f"no score snapshot {ref.hypothesis_id}/{ref.version} on or before {as_of}"
            )
        snapshot.validate(self._calendar)
        return snapshot

    def _latest_score_date(self, ref: ScoreRef, as_of: date) -> date | None:
        return _latest_on_or_before(self._scores.dates(ref.hypothesis_id, ref.version), as_of)

    def _listings(self, universe_version: int) -> dict[str, UniverseMember]:
        listings = self._universe.read_listings(universe_version)
        return {m.cik: m for m in listings[0]} if listings else {}

    def _next_session(self, d: date) -> date:
        return self._calendar.next_trading_day(d + timedelta(days=1))

    def _previous_session(self, d: date) -> date:
        earlier = self._calendar.sessions_between(d - timedelta(days=14), d - timedelta(days=1))
        return earlier[-1]

    def _first_session(self, month: str) -> date:
        return self._calendar.next_trading_day(date.fromisoformat(f"{month}-01"))


def _latest_on_or_before(dates: Sequence[date], d: date) -> date | None:
    i = bisect.bisect_right(list(dates), d)
    return dates[i - 1] if i else None


def _months_between(start: date, end: date) -> set[str]:
    return {
        m.strftime("%Y-%m") for m in pd.date_range(date(start.year, start.month, 1), end, freq="MS")
    }


def _period_return(series: _Series, base: date, end: date) -> float:
    start = series.close_on_or_before(base)
    last = series.close_on_or_before(end)
    if start is None or last is None:
        raise MissingPriceDataError(f"no benchmark price between {base} and {end}")
    return last[1] / start[1] - 1


def _rolling_beta(months: Sequence[MonthRow]) -> tuple[tuple[str, float], ...]:
    out = []
    for i in range(_MONTHS_PER_YEAR - 1, len(months)):
        window = months[i - _MONTHS_PER_YEAR + 1 : i + 1]
        p = np.array([m.net_return for m in window])
        x = np.array([m.xbi_return for m in window])
        variance = float(np.var(x, ddof=1))
        beta = float(np.cov(p, x, ddof=1)[0, 1] / variance) if variance > 0 else float("nan")
        out.append((months[i].month, beta))
    return tuple(out)
