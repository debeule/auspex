from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

SectionStatus = Literal["cut", "section_missing", "no_change_statement"]


@dataclass(frozen=True)
class ArchivedSection:
    """Item 1A of one filing as archived. `accepted_at` is EDGAR's acceptance time in UTC, when
    the filing became public; `filed` is EDGAR's filing date, which for a filing accepted after
    17:30 New York time is the next business day. `period_of_report` is the fiscal period end
    the filing reports on. `reason` says why a `section_missing` filing has no text."""

    cik: str
    accession: str
    form: str
    filed: date
    period_of_report: date | None
    accepted_at: datetime | None
    status: SectionStatus
    reason: str
    text: str


@dataclass(frozen=True)
class FilingScore:
    """Year-on-year change of one filing's Item 1A against `comparison_accession` (None when the
    filing only states that nothing changed). `change` is 1 - cosine similarity of the term
    frequencies, 0 for identical text; `known_at` is the later filing's acceptance time."""

    cik: str
    accession: str
    form: str
    period_of_report: date
    known_at: datetime
    comparison_accession: str | None
    change: float
    jaccard: float
