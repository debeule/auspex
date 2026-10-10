import importlib
import pkgutil
from pathlib import Path

import pytest
from pydantic import ValidationError

import auspex_ingest
from auspex_ingest.sources import SourceEntry, SourcesConfig, load_sources_config

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_SOURCES_YAML = _SERVICE_ROOT / "config" / "sources.yaml"

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


def test_load_sources_config_reads_every_entry():
    import yaml

    declared = [s["source_type"] for s in yaml.safe_load(_SOURCES_YAML.read_text())["sources"]]

    config = load_sources_config(_SOURCES_YAML)

    assert [entry.source_type for entry in config.sources] == declared


def test_malformed_sources_yaml_fails_loudly(tmp_path: Path) -> None:
    bad = tmp_path / "sources.yaml"
    bad.write_text(
        "sources:\n"
        "  - source_type: mock\n"
        "    schedule: '@daily'\n"
        "    rate_limit_rps: NOT_A_NUMBER\n"
        "    initial_lookback: 7\n"
        "    max_documents_per_run: 100\n"
        "    prefilter_vocabulary: []\n"
        "    source_config: {}\n"
    )
    with pytest.raises(ValueError):
        load_sources_config(bad)


def test_duplicate_source_type_is_rejected() -> None:
    with pytest.raises(ValidationError, match="[Dd]uplicate"):
        SourcesConfig.model_validate({"sources": [_VALID_ENTRY, _VALID_ENTRY]})


def test_prefilter_vocabulary_is_declared_only_in_sources_yaml():
    config = load_sources_config(_SOURCES_YAML)

    assert not (_SERVICE_ROOT / "config" / "prefilter").exists()
    assert any(entry.prefilter_vocabulary for entry in config.sources)


def test_no_module_builds_dags_in_the_scraper_package():
    modules = [
        importlib.import_module(info.name)
        for info in pkgutil.walk_packages(auspex_ingest.__path__, "auspex_ingest.")
    ]
    airflow_users = [
        m.__name__ for m in modules
        if m.__file__ and "airflow" in Path(m.__file__).read_text(encoding="utf-8")
    ]

    assert airflow_users == []
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("auspex_ingest.dag_factory")
