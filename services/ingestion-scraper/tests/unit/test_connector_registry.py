"""Every configured source resolves to a connector through the registry lookup."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from auspex_ingest.connectors import RateLimitedClient
from auspex_ingest.connectors.registry import CONNECTOR_BUILDERS, CONNECTOR_HOSTS, build_connector
from auspex_ingest.dag_factory import load_sources_config

_SOURCES = load_sources_config(Path(__file__).parent.parent.parent / "config" / "sources.yaml").sources
_REAL_SOURCES = [e for e in _SOURCES if e.source_type != "mock"]
_ENV = {"SEC_USER_AGENT": "Auspex test test@example.com", "EPO_OPS_KEY": "k", "EPO_OPS_SECRET": "s"}


@pytest.mark.parametrize("entry", _REAL_SOURCES, ids=lambda e: e.source_type)
def test_every_configured_source_builds_a_window_bounded_connector(entry) -> None:  # type: ignore[no-untyped-def]
    assert entry.source_type in CONNECTOR_HOSTS
    until = datetime(2025, 1, 31, tzinfo=UTC)
    connector = build_connector(
        entry.source_type, client=RateLimitedClient({}), source_config=entry.source_config,
        env=_ENV, until=until,
    )
    assert connector._until == until  # type: ignore[attr-defined]


def test_unknown_source_type_names_the_registered_ones() -> None:
    with pytest.raises(ValueError, match="epo_ops"):
        build_connector("nope", client=RateLimitedClient({}), source_config={}, env={})


def test_edgar_requires_a_user_agent() -> None:
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        build_connector("edgar", client=RateLimitedClient({}), source_config={}, env={})


def test_registry_and_host_map_cover_the_same_sources() -> None:
    assert set(CONNECTOR_BUILDERS) == set(CONNECTOR_HOSTS)
