from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .identity import compute_event_id, compute_extraction_id
from .models import RawDocument, ResearchSignalEvent

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts" / "extraction"
_MAX_CONTENT_CHARS = 4_000


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
        )
