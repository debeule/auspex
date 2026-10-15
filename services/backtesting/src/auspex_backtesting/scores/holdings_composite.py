"""The H9 holdings composite: specialist 13F ownership, net insider open-market buying and days
to cover, ranked monthly across a point-in-time universe, as `ScoreSnapshot`s."""

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import combinations
from typing import Any, Literal, Protocol

import pandas as pd

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.portfolio.scores import ScoreSnapshot, ScoreStore
from auspex_backtesting.short_interest.calendar import FinraCalendar
from auspex_backtesting.short_interest.model import ShortInterestRecord
from auspex_backtesting.universe.model import UniverseMember, UniverseSnapshot

ComponentVariant = Literal["three_component", "two_component"]
SPECIALIST = "specialist_13f_ownership"
INSIDER = "net_insider_buying"
DAYS_TO_COVER = "days_to_cover"
COMPONENTS = (SPECIALIST, INSIDER, DAYS_TO_COVER)
_MIN_COMPONENTS = 2
# FINRA settles twice a month; the latest period published before a rebalance settled within
# this window, so the search for it never reaches back further.
_SETTLEMENT_SEARCH = timedelta(days=60)
_EASTERN = "America/New_York"


class SpecialistOwnership(Protocol):
    def specialist_ownership(self, issuer_cik: str, as_of: datetime) -> float | None: ...

    def specialist_ownership_reason(self, issuer_cik: str, as_of: datetime) -> str | None: ...

    def specialist_ownership_known_at(
        self, issuer_cik: str, as_of: datetime
    ) -> pd.Timestamp | None: ...


class InsiderBuying(Protocol):
    def net_insider_buying(self, issuer_cik: str, as_of: datetime, days: int = 90) -> float | None: ...

    def net_insider_buying_known_at(
        self, issuer_cik: str, as_of: datetime, days: int = 90
    ) -> pd.Timestamp | None: ...


class ShortInterestHistory(Protocol):
    def records(self, ticker: str) -> list[ShortInterestRecord]: ...


class UniverseReader(Protocol):
    def months(self, rules_version: int) -> list[str]: ...

    def read(self, rules_version: int, month: str) -> UniverseSnapshot | None: ...


def component_variant(
    hypothesis: Mapping[str, Any], short_interest_start: date | None
) -> ComponentVariant:
    """H9's pre-registered component rule: the two-component variant when short interest
    history starts after the in-sample start (or does not exist), else all three. It reads
    coverage dates only, never returns."""
    in_sample_start = date(int(hypothesis["in_sample_years"][0]), 1, 1)
    selection = hypothesis["component_variants"]["selection"]
    if selection["two_component_when"] != "short_interest_history_starts_after_in_sample_start":
        raise ValueError(f"unknown component selection rule {selection['two_component_when']!r}")
    if short_interest_start is None or short_interest_start > in_sample_start:
        return "two_component"
    return "three_component"


def short_interest_start(store: Any) -> date | None:
    """The first settlement date any ticker in `store` has a reported position for."""
    starts = []
    for ticker in store.tickers():
        frame = store.read(ticker)
        reported = frame[frame["reported"].astype(bool)]
        if len(reported):
            starts.append(min(reported["settlement_date"]))
    return min(starts) if starts else None


def score_version(hypothesis_version: int, *, floor: bool) -> str:
    """Snapshots of the `no_floor` trial cells are kept apart from the floored ones."""
    return str(hypothesis_version) if floor else f"{hypothesis_version}-no_floor"


@dataclass(frozen=True)
class HoldingsScoredMonth:
    """A rebalance date's snapshot and who it leaves out: members under H9's tradable floor,
    and members with fewer than two components, by CIK."""

    snapshot: ScoreSnapshot
    members: int
    below_floor: tuple[str, ...]
    left_out: tuple[str, ...]
    specialist_missing: dict[str, int]


class HoldingsCompositeScore:
    """Reads every input as of the rebalance session's open. A component's percentile rank is
    taken among the names that are scored (two components or more), best = 1.0, ties broken
    by CIK; the score is the mean of a name's available ranks."""

    def __init__(
        self,
        hypothesis: Mapping[str, Any],
        universe: UniverseReader,
        rules_version: int,
        holdings: SpecialistOwnership,
        insiders: InsiderBuying,
        short_interest: ShortInterestHistory,
        *,
        variant: ComponentVariant,
        floor: bool = True,
        finra: FinraCalendar | None = None,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self._hypothesis_id = str(hypothesis["id"])
        self._version = score_version(int(hypothesis["version"]), floor=floor)
        liquidity = hypothesis["universe"]["liquidity_floor"]
        self._min_cap = float(liquidity["min_market_cap_usd"])
        self._min_volume = float(liquidity["min_median_dollar_volume_20d_usd"])
        self._window = int(hypothesis["components"][INSIDER]["window_days"])
        self._higher_ranks_higher = {
            c: bool(hypothesis["components"][c]["higher_ranks_higher"]) for c in COMPONENTS
        }
        self._components = tuple(hypothesis["component_variants"][variant])
        self._variant = variant
        self._floor = floor
        self._universe = universe
        self._rules_version = rules_version
        self._holdings = holdings
        self._insiders = insiders
        self._short = short_interest
        self._short_records: dict[str, list[ShortInterestRecord]] = {}
        self._finra = finra or FinraCalendar()
        self._calendar = calendar or MarketCalendar()

    @property
    def hypothesis_id(self) -> str:
        return self._hypothesis_id

    @property
    def version(self) -> str:
        return self._version

    @property
    def variant(self) -> ComponentVariant:
        return self._variant

    def compute(self, rebalance_date: date) -> HoldingsScoredMonth:
        snapshot = self._universe.read(self._rules_version, rebalance_date.strftime("%Y-%m"))
        if snapshot is None or snapshot.rebalance_date != rebalance_date:
            raise ValueError(f"no universe snapshot rebalancing on {rebalance_date}")
        opens = self._calendar.session_open(rebalance_date)
        settlement = self._latest_published_settlement(rebalance_date)
        below_floor, left_out, rows = [], [], []
        specialist_missing: Counter[str] = Counter()
        for m in snapshot.members:
            if self._floor and not self._tradable(m):
                below_floor.append(m.cik)
                continue
            row = self._inputs(m, opens, settlement, specialist_missing)
            if row["components"] < _MIN_COMPONENTS:
                left_out.append(m.cik)
                continue
            rows.append(row)
        frame = self._ranked(rows)
        return HoldingsScoredMonth(
            ScoreSnapshot(self._hypothesis_id, self._version, rebalance_date, frame),
            len(snapshot.members), tuple(below_floor), tuple(left_out), dict(specialist_missing),
        )

    def _tradable(self, m: UniverseMember) -> bool:
        return (
            m.market_cap_usd is not None and m.market_cap_usd >= self._min_cap
            and m.median_dollar_volume_20d is not None
            and m.median_dollar_volume_20d >= self._min_volume
        )

    def _inputs(
        self,
        m: UniverseMember,
        opens: datetime,
        settlement: date | None,
        specialist_missing: Counter[str],
    ) -> dict[str, Any]:
        values: dict[str, float | None] = dict.fromkeys(COMPONENTS)
        known: list[pd.Timestamp] = []
        dtc_settlement = None
        if SPECIALIST in self._components:
            values[SPECIALIST] = self._holdings.specialist_ownership(m.cik, opens)
            if values[SPECIALIST] is None:
                reason = self._holdings.specialist_ownership_reason(m.cik, opens)
                specialist_missing[reason or "unknown"] += 1
            elif (t := self._holdings.specialist_ownership_known_at(m.cik, opens)) is not None:
                known.append(t)
        if INSIDER in self._components:
            values[INSIDER] = self._insiders.net_insider_buying(m.cik, opens, self._window)
            if values[INSIDER] is not None and (
                t := self._insiders.net_insider_buying_known_at(m.cik, opens, self._window)
            ) is not None:
                known.append(t)
        if DAYS_TO_COVER in self._components and m.ticker and settlement is not None:
            record = self._record(m.ticker, settlement)
            if record is not None and record.reported and record.days_to_cover is not None:
                values[DAYS_TO_COVER] = record.days_to_cover
                dtc_settlement = record.settlement_date
                known.append(_end_of_day(record.publication_date))
        available = sum(v is not None for v in values.values())
        return {
            "cik": m.cik,
            "ticker": m.ticker,
            "known_at_max": max(known) if known else None,
            **values,
            "days_to_cover_settlement": dtc_settlement,
            "components": available,
        }

    def _latest_published_settlement(self, rebalance_date: date) -> date | None:
        """FINRA's latest period published before the rebalance session: its publication time
        of day is unknown, so the rebalance day's own publication is too late."""
        day_before = rebalance_date - timedelta(days=1)
        periods = self._finra.periods(rebalance_date - _SETTLEMENT_SEARCH, day_before)
        return periods[-1].settlement_date if periods else None

    def _record(self, ticker: str, settlement: date) -> ShortInterestRecord | None:
        """The ticker's record for that period; a ticker missing from it is missing, never
        carried forward from an older period."""
        if ticker not in self._short_records:
            self._short_records[ticker] = self._short.records(ticker)
        return next(
            (r for r in self._short_records[ticker] if r.settlement_date == settlement), None
        )

    def _ranked(self, rows: Sequence[dict[str, Any]]) -> pd.DataFrame:
        columns = [
            "cik", "ticker", "score", "known_at_max", *COMPONENTS,
            *(f"{c}_rank" for c in COMPONENTS), "days_to_cover_settlement", "components",
            "variant",
        ]
        if not rows:
            return pd.DataFrame(columns=columns)
        frame = pd.DataFrame(rows)
        for c in COMPONENTS:
            frame[f"{c}_rank"] = _percentile_ranks(frame, c, self._higher_ranks_higher[c])
        frame["score"] = frame[[f"{c}_rank" for c in self._components]].mean(axis=1)
        frame["variant"] = self._variant
        frame["known_at_max"] = pd.to_datetime(frame["known_at_max"], utc=True)
        frame = frame.sort_values(["score", "cik"], ascending=[False, True], ignore_index=True)
        return frame[columns]


def _percentile_ranks(frame: pd.DataFrame, column: str, higher_ranks_higher: bool) -> pd.Series:
    present = frame[frame[column].notna()]
    order = present.assign(_key=present[column] * (-1 if higher_ranks_higher else 1)).sort_values(
        ["_key", "cik"]
    )
    n = len(order)
    ranks = pd.Series(float("nan"), index=frame.index)
    for position, index in enumerate(order.index):
        ranks[index] = (n - position) / n
    return ranks


def _end_of_day(day: date) -> pd.Timestamp:
    """Midnight after `day` in New York: the latest a figure published that day became known."""
    return (
        pd.Timestamp(day + timedelta(days=1)).tz_localize(_EASTERN).tz_convert("UTC")
    )


def _utc_today() -> date:
    return datetime.now(UTC).date()


class HoldingsScoreBuild:
    def __init__(
        self,
        score: HoldingsCompositeScore,
        universe: UniverseReader,
        rules_version: int,
        scores: ScoreStore,
        *,
        today: Callable[[], date] = _utc_today,
    ) -> None:
        self._score = score
        self._universe = universe
        self._rules_version = rules_version
        self._scores = scores
        self._today = today

    def run(self) -> dict[str, Any]:
        """Writes a snapshot for every stored universe month whose rebalance date has passed
        and has none yet, and reports coverage: per month, the members, those under the floor,
        scored and left out; per year, the correlation of each pair of component ranks over
        the scored names (three near-identical ranks would be one signal)."""
        months = self._universe.months(self._rules_version)
        if not months:
            raise ValueError(f"universe rules version {self._rules_version} has no snapshot yet")
        stored = set(self._scores.dates(self._score.hypothesis_id, self._score.version))
        today = self._today()
        written, per_month, frames = 0, [], []
        for month in months:
            snapshot = self._universe.read(self._rules_version, month)
            if snapshot is None or snapshot.rebalance_date >= today:
                continue
            if snapshot.rebalance_date in stored:
                continue
            scored = self._score.compute(snapshot.rebalance_date)
            self._scores.write(scored.snapshot)
            written += 1
            frames.append(scored.snapshot.rows.assign(year=snapshot.rebalance_date.year))
            per_month.append({
                "month": month,
                "members": scored.members,
                "below_floor": len(scored.below_floor),
                "scored": len(scored.snapshot.rows),
                "left_out": len(scored.left_out),
                "specialist_missing": scored.specialist_missing,
            })
        return {
            "score": {"hypothesis_id": self._score.hypothesis_id, "version": self._score.version},
            "variant": self._score.variant,
            "snapshots_written": written,
            "snapshots_already_stored": len(stored),
            "months": per_month,
            "component_rank_correlations": _rank_correlations(frames),
        }


def _rank_correlations(frames: Sequence[pd.DataFrame]) -> dict[str, dict[str, float | None]]:
    if not frames:
        return {}
    pooled = pd.concat(frames, ignore_index=True)
    result: dict[str, dict[str, float | None]] = {}
    for year, rows in pooled.groupby("year"):
        pairs: dict[str, float | None] = {}
        for a, b in combinations(COMPONENTS, 2):
            both = rows[[f"{a}_rank", f"{b}_rank"]].dropna().astype(float)
            r = both.iloc[:, 0].corr(both.iloc[:, 1]) if len(both) > 2 else float("nan")
            pairs[f"{a}~{b}"] = None if pd.isna(r) else float(r)
        result[str(year)] = pairs
    return result
