"""Cross-sectional portfolio backtests of score hypotheses, and their portfolio verdict.

A score writes `ScoreSnapshot`s; `PortfolioBacktest` ranks them over the point-in-time universe,
trades a `PortfolioRule` with `EqualRiskSizer` weights and a `CatalystGuard`, and reports a
`PortfolioResult`. `PortfolioEvaluation` admits the hypothesis, reserves its cell in the trial
ledger and applies `PortfolioVerdict`.
"""

from auspex_backtesting.portfolio.engine import (
    Closeout,
    Decision,
    GuardReport,
    MissingInputSnapshotError,
    MonthRow,
    PortfolioBacktest,
    PortfolioResult,
    QuintileMonth,
    Trade,
)
from auspex_backtesting.portfolio.guard import CatalystGuard, GuardCheck
from auspex_backtesting.portfolio.report import result_dict, write_report
from auspex_backtesting.portfolio.rules import PortfolioRule, ScoreRef, rank_scores
from auspex_backtesting.portfolio.scores import (
    ScoreLookaheadError,
    ScoreSnapshot,
    ScoreSnapshotExistsError,
    ScoreStore,
    score_key,
)
from auspex_backtesting.portfolio.sizing import (
    EqualRiskSizer,
    InsufficientNamesError,
    TargetWeights,
    trailing_volatility,
)
from auspex_backtesting.portfolio.verdict import (
    HoldoutAlreadyReadError,
    HoldoutRecord,
    HoldoutSealedError,
    InputManifests,
    InputsNotPinnedError,
    NoInputManifests,
    PortfolioEvaluation,
    PortfolioEvidence,
    PortfolioReport,
    PortfolioVerdict,
    VerdictReport,
    newey_west_t,
)

__all__ = [
    "CatalystGuard",
    "Closeout",
    "Decision",
    "EqualRiskSizer",
    "GuardCheck",
    "GuardReport",
    "HoldoutAlreadyReadError",
    "HoldoutRecord",
    "HoldoutSealedError",
    "InputManifests",
    "InputsNotPinnedError",
    "InsufficientNamesError",
    "MissingInputSnapshotError",
    "MonthRow",
    "NoInputManifests",
    "PortfolioBacktest",
    "PortfolioEvaluation",
    "PortfolioEvidence",
    "PortfolioReport",
    "PortfolioResult",
    "PortfolioRule",
    "PortfolioVerdict",
    "QuintileMonth",
    "ScoreLookaheadError",
    "ScoreRef",
    "ScoreSnapshot",
    "ScoreSnapshotExistsError",
    "ScoreStore",
    "TargetWeights",
    "Trade",
    "VerdictReport",
    "newey_west_t",
    "rank_scores",
    "result_dict",
    "score_key",
    "trailing_volatility",
    "write_report",
]
