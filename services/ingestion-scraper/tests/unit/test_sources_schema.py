
import pytest
from pydantic import ValidationError

from auspex_ingest.sources import SourceEntry, SourcesConfig

_VALID_ENTRY = {
    "source_type": "biorxiv",
    "schedule": "@daily",
    "rate_limit_rps": 1.0,
    "initial_lookback": 90,
    "max_documents_per_run": 200,
    "prefilter_vocabulary": ["BCL11A", "CRISPR", "gene therapy"],
    "source_config": {"base_url": "https://api.biorxiv.org"},
}


def _valid_config() -> dict:
    return {"sources": [_VALID_ENTRY]}


def test_sources_yaml_schema_validates_all_declared_fields():
    """A fully-populated sources.yaml parses without error and exposes typed fields."""
    cfg = SourcesConfig.model_validate(_valid_config())

    assert len(cfg.sources) == 1
    entry = cfg.sources[0]
    assert isinstance(entry, SourceEntry)
    assert entry.source_type == "biorxiv"
    assert entry.schedule == "@daily"
    assert entry.rate_limit_rps == 1.0
    assert entry.initial_lookback == 90
    assert entry.max_documents_per_run == 200
    assert "BCL11A" in entry.prefilter_vocabulary
    assert entry.source_config["base_url"] == "https://api.biorxiv.org"


def test_unknown_field_in_sources_yaml_is_rejected_at_parse_time():
    """An unknown field on either the top-level or a source entry raises ValidationError."""
    # Unknown at the top level
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SourcesConfig.model_validate({**_valid_config(), "extra_top_level": True})

    # Unknown inside a source entry
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SourcesConfig.model_validate(
            {"sources": [{**_VALID_ENTRY, "unknown_field": "oops"}]}
        )
