import re
from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator

_NCT_ID = re.compile(r"NCT\d{8}")
_NCT_CANONICAL_PREFIX = "nct:"

EventType = Literal[
    "trial_readout",
    "trial_initiation",
    "trial_halted",
    "trial_revised",
    "clinical_hold",
    "regulatory_submission",
    "regulatory_designation",
    "regulatory_approval",
    "complete_response_letter",
    "preclinical_data",
    "patent_publication",
    "other",
]
_EVENT_TYPES: frozenset[str] = frozenset(get_args(EventType))


class _ExtractionResult(BaseModel):
    is_signal: bool
    title: str = ""
    raw_text_snippet: str = ""
    gene_targets: list[str] = Field(default_factory=list)
    mechanisms: list[str] = Field(default_factory=list)
    companies_mentioned: list[str] = Field(default_factory=list)
    summary: str = ""
    directionality: str = "neutral"
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    event_type: EventType = "other"
    primary_company: str | None = None
    program_identifiers: list[str] = Field(default_factory=list)
    trial_ids: list[str] = Field(default_factory=list)

    @field_validator("event_type", mode="before")
    @classmethod
    def _unknown_event_type_is_other(cls, v: object) -> object:
        # A small model's near-miss label should not fail the whole document.
        return v if v in _EVENT_TYPES else "other"

    @field_validator("program_identifiers", "trial_ids", mode="before")
    @classmethod
    def _null_list_is_empty(cls, v: object) -> object:
        return [] if v is None else v

    @field_validator("primary_company", mode="before")
    @classmethod
    def _blank_company_is_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


def resolve_trial_ids(extracted: list[str], canonical_id: str | None) -> list[str]:
    """Return the NCT IDs an event concerns: well-formed model output plus the document's own trial.

    Model output is untrusted, so anything that is not ``NCT`` followed by eight digits is
    dropped rather than passed on to the graph.
    """
    trial_ids: list[str] = []
    candidates = [t.strip().upper() for t in extracted]
    if canonical_id and canonical_id.startswith(_NCT_CANONICAL_PREFIX):
        candidates.insert(0, canonical_id.removeprefix(_NCT_CANONICAL_PREFIX).upper())
    for candidate in candidates:
        if _NCT_ID.fullmatch(candidate) and candidate not in trial_ids:
            trial_ids.append(candidate)
    return trial_ids
