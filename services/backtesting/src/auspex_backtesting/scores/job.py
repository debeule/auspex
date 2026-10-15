"""The H9 score build over the stores in MinIO: the job a backfill script or a scheduled
refresh runs."""

from datetime import date
from pathlib import Path

from minio import Minio

from auspex_backtesting.hypothesis import load_hypothesis, verify_hypothesis
from auspex_backtesting.ownership import (
    HoldingsPanel,
    InsiderPanel,
    OwnershipStore,
    UniverseMarketCaps,
    UniverseSplitFactors,
)
from auspex_backtesting.portfolio.scores import ScoreStore
from auspex_backtesting.prices.splits import SplitStore
from auspex_backtesting.scores.holdings_composite import (
    HoldingsCompositeScore,
    HoldingsScoreBuild,
    component_variant,
    short_interest_start,
)
from auspex_backtesting.short_interest import FinraCalendar, ShortInterestStore
from auspex_backtesting.universe.store import UniverseStore

HYPOTHESIS_ID = "h9"


def holdings_score_build(
    client: Minio,
    rules_version: int,
    finra_calendar: Path,
    *,
    floor: bool,
    config_dir: Path | None = None,
    registry_path: Path | None = None,
    today: date | None = None,
) -> HoldingsScoreBuild:
    """Refuses an unregistered or edited H9 before reading any data. The component variant
    is chosen from the stored short interest's first reported settlement date."""
    verify_hypothesis(HYPOTHESIS_ID, config_dir=config_dir, registry_path=registry_path)
    hypothesis = load_hypothesis(HYPOTHESIS_ID, config_dir)
    universe = UniverseStore(client)
    ownership = OwnershipStore(client)
    short = ShortInterestStore(client)
    splits = UniverseSplitFactors.load(universe, rules_version, SplitStore(client))
    score = HoldingsCompositeScore(
        hypothesis,
        universe,
        rules_version,
        HoldingsPanel.load(ownership, splits, config_dir=config_dir, registry_path=registry_path),
        InsiderPanel.load(ownership, UniverseMarketCaps(universe, rules_version)),
        short,
        variant=component_variant(hypothesis, short_interest_start(short)),
        floor=floor,
        finra=FinraCalendar.from_csv(finra_calendar),
    )
    if today is None:
        return HoldingsScoreBuild(score, universe, rules_version, ScoreStore(client))
    return HoldingsScoreBuild(
        score, universe, rules_version, ScoreStore(client), today=lambda: today
    )
