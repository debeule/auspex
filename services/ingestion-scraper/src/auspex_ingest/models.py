from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, field_validator

_CANONICAL_PREFIXES: frozenset[str] = frozenset({"doi:", "nct:", "epo-app:", "edgar:", "fda:"})


class RawDocument(BaseModel):
    schema_version: str
    external_id: str
    canonical_id: str | None = None
    source_type: str
    source_url: str
    published_date: datetime
    raw_content: str = Field(exclude=True)
    content_sha256: str
    retrieved_at: datetime

    @field_validator("published_date", "retrieved_at", mode="before")
    @classmethod
    def _require_aware(cls, v: object) -> object:
        if isinstance(v, datetime) and v.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return v

    @field_validator("published_date", "retrieved_at", mode="after")
    @classmethod
    def _normalize_utc(cls, v: datetime) -> datetime:
        return v.astimezone(UTC)

    @field_validator("canonical_id", mode="after")
    @classmethod
    def _typed_prefix(cls, v: str | None) -> str | None:
        if v is not None and not any(v.startswith(p) for p in _CANONICAL_PREFIXES):
            raise ValueError(
                f"canonical_id must start with one of {sorted(_CANONICAL_PREFIXES)}, got {v!r}"
            )
        return v


class ResearchSignalEvent(BaseModel):
    schema_version: str
    event_id: UUID
    extraction_id: UUID
    external_id: str
    canonical_id: str | None = None
    raw_object_key: str
    source_type: str
    source_url: str
    published_date: datetime
    published_date_field: str
    ingested_at: datetime
    title: str
    raw_text_snippet: str
    gene_targets: list[str]
    mechanisms: list[str]
    companies_mentioned: list[str]
    summary: str
    directionality: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    prompt_version: str
    prefilter_version: str
    extraction_model: str

    @field_validator("published_date", "ingested_at", mode="before")
    @classmethod
    def _require_aware(cls, v: object) -> object:
        if isinstance(v, datetime) and v.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return v

    @field_validator("published_date", "ingested_at", mode="after")
    @classmethod
    def _normalize_utc(cls, v: datetime) -> datetime:
        return v.astimezone(UTC)

    @field_serializer("published_date", "ingested_at")
    def _serialize_dt(self, v: datetime) -> str:
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")
