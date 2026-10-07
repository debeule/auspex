import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, field_validator

from .identity import compute_event_id, compute_extraction_id
from .models import RawDocument, ResearchSignalEvent

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts" / "extraction"
_MAX_CONTENT_CHARS = 4_000
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


class LLMExtractor:
    def __init__(
        self,
        client: Any,
        model: str,
        schema_version: str,
        prompt_version: str,
        gene_vocab: frozenset[str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._schema_version = schema_version
        self._prompt_version = prompt_version
        self._gene_vocab = gene_vocab
        self._now = now or (lambda: datetime.now(UTC))
        self._prompt = (_PROMPT_DIR / f"{prompt_version}.txt").read_text()

    def extract(
        self, doc: RawDocument, prefilter_version: str, raw_object_key: str
    ) -> ResearchSignalEvent | None:
        truncated = doc.raw_content[:_MAX_CONTENT_CHARS]

        result: _ExtractionResult = self._client.chat.completions.create(
            model=self._model,
            response_model=_ExtractionResult,
            messages=[
                {"role": "system", "content": self._prompt},
                {
                    "role": "user",
                    "content": f"---BEGIN DOCUMENT---\n{truncated}\n---END DOCUMENT---",
                },
            ],
        )

        if not result.is_signal:
            return None

        gene_targets = result.gene_targets
        if self._gene_vocab:
            gene_targets = [g for g in gene_targets if g in self._gene_vocab]

        event_id = compute_event_id(doc.canonical_id, doc.source_type, doc.external_id)
        extraction_id = compute_extraction_id(
            event_id, self._schema_version, self._prompt_version, prefilter_version, self._model
        )

        return ResearchSignalEvent(
            schema_version=self._schema_version,
            event_id=event_id,
            extraction_id=extraction_id,
            external_id=doc.external_id,
            canonical_id=doc.canonical_id,
            raw_object_key=raw_object_key,
            source_type=doc.source_type,
            source_url=doc.source_url,
            published_date=doc.published_date,
            published_date_field="published_date",
            ingested_at=self._now(),
            title=result.title,
            raw_text_snippet=result.raw_text_snippet,
            gene_targets=gene_targets,
            mechanisms=result.mechanisms,
            companies_mentioned=result.companies_mentioned,
            summary=result.summary,
            directionality=result.directionality,
            confidence_score=result.confidence_score,
            prompt_version=self._prompt_version,
            prefilter_version=prefilter_version,
            extraction_model=self._model,
            event_type=result.event_type,
            primary_company=result.primary_company,
            program_identifiers=result.program_identifiers,
            trial_ids=resolve_trial_ids(result.trial_ids, doc.canonical_id),
        )
