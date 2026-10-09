from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

CatalystSource = Literal["edgar", "federal_register"]
CatalystType = Literal["pdufa", "adcom"]
Precision = Literal["day", "month", "quarter", "half"]


@dataclass(frozen=True)
class Catalyst:
    """One dated catalyst as a single document disclosed it.

    `known_at` is when the document became public (UTC): an 8-K's acceptance time, or a Federal
    Register notice's publication. The date itself is the period `period_start`..`period_end`
    that `precision` allows; "second half of 2027" is July to December, never a day. `aliases`
    are the normalized application numbers and product names the document gives for it, most
    specific first, and `subject` is the first of them; rows of one company whose aliases
    overlap are the same catalyst, and a later row revises an earlier one. `cik` is None for a
    notice no universe company could be matched to.
    """

    source: CatalystSource
    catalyst_type: CatalystType
    cik: str | None
    subject: str
    aliases: tuple[str, ...]
    precision: Precision
    period_start: date
    period_end: date
    known_at: datetime
    document_id: str
    document_url: str
    evidence: str
    committee: str = ""
    company_name: str = ""


@dataclass(frozen=True)
class ExtractionResult:
    """Catalysts found in one run and the run's counters (documents read, skipped, matched)."""

    rows: tuple[Catalyst, ...] = ()
    stats: dict[str, int] = field(default_factory=dict)
