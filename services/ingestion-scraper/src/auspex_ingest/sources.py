"""Schema for sources.yaml — validated at DAG-factory load time (Step 2.1)."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class SourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    schedule: str
    rate_limit_rps: float
    initial_lookback: int
    max_documents_per_run: int
    prefilter_vocabulary: list[str]
    source_config: dict[str, Any]


class SourcesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[SourceEntry]
