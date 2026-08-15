from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, field_validator

_CANONICAL_PREFIXES: frozenset[str] = frozenset({"doi:", "nct:", "epo-app:", "edgar:"})


class RawDocument(BaseModel):
    schema_version: str
    external_id: str
    canonical_id: Optional[str] = None
    source_type: str
    source_url: str
    published_date: datetime
    raw_content: str
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
        return v.astimezone(timezone.utc)

    @field_validator("canonical_id", mode="after")
    @classmethod
    def _typed_prefix(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not any(v.startswith(p) for p in _CANONICAL_PREFIXES):
            raise ValueError(
                f"canonical_id must start with one of {sorted(_CANONICAL_PREFIXES)}, got {v!r}"
            )
        return v
