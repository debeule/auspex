"""Statistical evaluation of event hypotheses under the registered protocol.

Market-model abnormal returns against XBI, clustered inference, the family trial ledger,
deflated Sharpe ratio, kill criteria, walk-forward segments and the sealed holdout.
`EvaluationProtocol.run` in `auspex_backtesting.protocol` ties them together.
"""

from auspex_backtesting.evaluation.costs import TradeCosts
from auspex_backtesting.evaluation.inference import (
    BootstrapCI,
    ClusteredInference,
    DeflatedSharpe,
    InferenceResult,
)
from auspex_backtesting.evaluation.ledger import (
    Reservation,
    TrialBudgetExhaustedError,
    TrialLedger,
    TrialLedgerCorruptError,
)
from auspex_backtesting.evaluation.results import (
    CellResult,
    EvaluationResult,
    HoldoutGuard,
    HoldoutSealedError,
    KillCriteria,
    KillVerdict,
    TradeRecord,
)
from auspex_backtesting.evaluation.returns import (
    AbnormalReturnCalculator,
    AbnormalReturnSeries,
    KnownAtDelay,
)
from auspex_backtesting.evaluation.walk_forward import (
    InsufficientEventsError,
    WalkForwardSegment,
    WalkForwardSplitter,
)


class HypothesisSuspendedError(Exception):
    pass


class UnregisteredCellError(Exception):
    pass


__all__ = [
    "AbnormalReturnCalculator",
    "AbnormalReturnSeries",
    "BootstrapCI",
    "CellResult",
    "ClusteredInference",
    "DeflatedSharpe",
    "EvaluationResult",
    "HoldoutGuard",
    "HoldoutSealedError",
    "HypothesisSuspendedError",
    "InferenceResult",
    "InsufficientEventsError",
    "KillCriteria",
    "KillVerdict",
    "KnownAtDelay",
    "Reservation",
    "TradeCosts",
    "TradeRecord",
    "TrialBudgetExhaustedError",
    "TrialLedger",
    "TrialLedgerCorruptError",
    "UnregisteredCellError",
    "WalkForwardSegment",
    "WalkForwardSplitter",
]
