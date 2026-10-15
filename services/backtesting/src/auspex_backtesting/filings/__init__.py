"""Item 1A (Risk Factors) text change between a filer's 10-K or 10-Q and the same filing a year
earlier ("lazy prices"), as a monthly `ScoreSnapshot` over a point-in-time universe."""

from auspex_backtesting.catalysts.press_releases import IndexEntry
from auspex_backtesting.filings.archive import FilingSectionArchive
from auspex_backtesting.filings.index import ANNUAL_AND_QUARTERLY_FORMS, FilingIndex
from auspex_backtesting.filings.job import FilingPanelBuild, score_version
from auspex_backtesting.filings.model import ArchivedSection, FilingScore
from auspex_backtesting.filings.score import (
    RiskFactorChangeScore,
    ScoredMonth,
    ScoreResult,
    TextChangeScore,
    text_change,
)
from auspex_backtesting.filings.sections import SectionCut, cut_item_1a, filing_to_text, form_family

__all__ = [
    "ANNUAL_AND_QUARTERLY_FORMS",
    "ArchivedSection",
    "FilingIndex",
    "FilingPanelBuild",
    "FilingScore",
    "FilingSectionArchive",
    "IndexEntry",
    "RiskFactorChangeScore",
    "ScoreResult",
    "ScoredMonth",
    "SectionCut",
    "TextChangeScore",
    "cut_item_1a",
    "filing_to_text",
    "form_family",
    "score_version",
    "text_change",
]
