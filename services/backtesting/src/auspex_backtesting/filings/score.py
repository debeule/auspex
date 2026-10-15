"""Year-on-year Item 1A change per filing, and the monthly score over a universe."""

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from auspex_backtesting.filings.model import ArchivedSection, FilingScore
from auspex_backtesting.filings.sections import form_family
from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.portfolio.scores import ScoreSnapshot
from auspex_backtesting.universe.store import UniverseStore

_TOKEN = re.compile(r"[a-z]+")
_YEAR_DAYS = 365
# How far the comparison's period end may sit from exactly a year earlier: enough for 52/53-week
# fiscal years and a moved quarter end, less than a quarter so it is always the same quarter.
_PERIOD_TOLERANCE_DAYS = 45
# A filing's score stays current until the next 10-Q or 10-K replaces it, about a quarter later.
SCORE_LOOKBACK = timedelta(days=120)


def text_change(earlier: str, later: str) -> tuple[float, float]:
    """(1 - cosine similarity, Jaccard similarity) of two texts' lowercase letter-only tokens,
    without stemming. Two empty texts are identical."""
    a, b = Counter(_TOKEN.findall(earlier.lower())), Counter(_TOKEN.findall(later.lower()))
    if not a and not b:
        return 0.0, 1.0
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    cosine = sum(n * b[t] for t, n in a.items()) / norm if norm else 0.0
    union = a.keys() | b.keys()
    return max(0.0, 1.0 - cosine), len(a.keys() & b.keys()) / len(union)


@dataclass(frozen=True)
class ScoreResult:
    scores: tuple[FilingScore, ...]
    unscored: dict[str, int]


class TextChangeScore:
    def score(self, sections: Iterable[ArchivedSection]) -> ScoreResult:
        """Scores every filing against the same form's filing for the same fiscal period a year
        earlier from the same filer, accepted before it. A filing that only states its risk
        factors did not change scores 0 against nothing. Filings without a score are counted by
        reason."""
        by_filer: dict[tuple[str, str], list[ArchivedSection]] = defaultdict(list)
        unscored: Counter[str] = Counter()
        for s in sections:
            family = form_family(s.form)
            if family is None:
                unscored["not_annual_or_quarterly"] += 1
            elif s.status == "section_missing" or s.accepted_at is None or s.period_of_report is None:
                unscored["section_missing"] += 1
            else:
                by_filer[(s.cik, family)].append(s)
        scores = []
        for filings in by_filer.values():
            for later in filings:
                if later.status == "no_change_statement":
                    scores.append(_score(later, None, 0.0, 1.0))
                    continue
                earlier = _comparison(later, filings)
                if earlier is None:
                    unscored["no_comparison"] += 1
                elif earlier.status != "cut":
                    unscored["comparison_without_text"] += 1
                else:
                    scores.append(_score(later, earlier, *text_change(earlier.text, later.text)))
        scores.sort(key=lambda s: (s.known_at, s.cik, s.accession))
        return ScoreResult(tuple(scores), dict(unscored))


def _comparison(later: ArchivedSection, filings: Sequence[ArchivedSection]) -> ArchivedSection | None:
    assert later.period_of_report is not None and later.accepted_at is not None
    target = later.period_of_report - timedelta(days=_YEAR_DAYS)
    candidates = [
        f for f in filings
        if f.period_of_report is not None and f.accepted_at is not None
        and f.accepted_at < later.accepted_at
        and abs((f.period_of_report - target).days) <= _PERIOD_TOLERANCE_DAYS
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda f: (abs((f.period_of_report - target).days), -f.accepted_at.timestamp()),  # type: ignore[operator, union-attr]
    )


def _score(
    later: ArchivedSection, earlier: ArchivedSection | None, change: float, jaccard: float
) -> FilingScore:
    assert later.period_of_report is not None and later.accepted_at is not None
    return FilingScore(
        later.cik, later.accession, later.form, later.period_of_report, later.accepted_at,
        earlier.accession if earlier else None, change, jaccard,
    )


@dataclass(frozen=True)
class ScoredMonth:
    """A rebalance date's snapshot, the universe's member count and the members left out for
    want of a score."""

    snapshot: ScoreSnapshot
    members: int
    left_out: tuple[str, ...]


class RiskFactorChangeScore:
    """The filing-text score of every universe member on a rebalance date: the change of its
    latest filing accepted before the session opened, within `SCORE_LOOKBACK`. The score is the
    negative change, so the least-changed filer ranks highest."""

    def __init__(
        self,
        scores: Iterable[FilingScore],
        universe: UniverseStore,
        rules_version: int,
        hypothesis_id: str,
        score_version: str,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self._by_cik: dict[str, list[FilingScore]] = defaultdict(list)
        for s in scores:
            self._by_cik[s.cik].append(s)
        for filings in self._by_cik.values():
            filings.sort(key=lambda s: s.known_at)
        self._universe = universe
        self._rules_version = rules_version
        self._hypothesis_id = hypothesis_id
        self._score_version = score_version
        self._calendar = calendar or MarketCalendar()

    def compute(self, rebalance_date: date) -> ScoredMonth:
        month = rebalance_date.strftime("%Y-%m")
        snapshot = self._universe.read(self._rules_version, month)
        if snapshot is None or snapshot.rebalance_date != rebalance_date:
            raise ValueError(f"no universe snapshot rebalancing on {rebalance_date}")
        opens = self._calendar.session_open(rebalance_date)
        rows, left_out = [], []
        for member in snapshot.members:
            current = [
                s for s in self._by_cik.get(member.cik, ())
                if opens - SCORE_LOOKBACK <= s.known_at < opens
            ]
            if not current:
                left_out.append(member.cik)
                continue
            latest = current[-1]
            rows.append({
                "cik": member.cik,
                "ticker": member.ticker,
                "score": -latest.change,
                "known_at_max": latest.known_at,
                "change": latest.change,
                "jaccard": latest.jaccard,
                "accession": latest.accession,
                "form": latest.form,
                "comparison_accession": latest.comparison_accession,
            })
        frame = pd.DataFrame(rows, columns=[
            "cik", "ticker", "score", "known_at_max", "change", "jaccard", "accession", "form",
            "comparison_accession",
        ])
        frame = frame.sort_values(["score", "cik"], ascending=[False, True], ignore_index=True)
        frame["known_at_max"] = pd.to_datetime(frame["known_at_max"], utc=True)
        result = ScoreSnapshot(self._hypothesis_id, self._score_version, rebalance_date, frame)
        return ScoredMonth(result, len(snapshot.members), tuple(left_out))
