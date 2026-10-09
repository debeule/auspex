from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    schedule: str
    rate_limit_rps: float
    initial_lookback: int
    max_documents_per_run: int
    prefilter_vocabulary: list[str]
    source_config: dict[str, Any]
    # Events scoring below this are counted in `below_threshold` instead of published.
    # 0.0 (off) until the confidence score's calibration justifies raising it.
    min_confidence_to_publish: float = Field(default=0.0, ge=0.0, le=1.0)


class SourcesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[SourceEntry]

    @model_validator(mode="after")
    def _no_duplicate_source_types(self) -> SourcesConfig:
        counts = Counter(s.source_type for s in self.sources)
        dupes = [t for t, n in counts.items() if n > 1]
        if dupes:
            raise ValueError(f"Duplicate source_type(s): {dupes}")
        return self


def load_sources_config(path: Path) -> SourcesConfig:
    return SourcesConfig.model_validate(yaml.safe_load(path.read_text()))
