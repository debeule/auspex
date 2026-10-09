"""The one place a `sources.yaml` `source_type` maps to a connector class.

Each connector module registers a builder on `REGISTRY` under its `source_type`. Shared code
(the scraper API, `scripts/run_pipeline.py`) builds connectors through `default_registry()` and
never branches on the source type, so a new source is a connector module plus a `sources.yaml`
entry.
"""
from __future__ import annotations

import importlib
import os
import pkgutil
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .base import SourceConnector
from .rate_limited_client import RateLimitedClient

if TYPE_CHECKING:
    from ..sources import SourceEntry


@dataclass(frozen=True)
class BuildContext:
    """What a builder may use: the shared rate-limited client, its `sources.yaml` entry, and
    the environment for credentials."""

    client: RateLimitedClient
    entry: SourceEntry
    env: Mapping[str, str]


ConnectorBuilder = Callable[[BuildContext], SourceConnector]


@dataclass(frozen=True)
class ConnectorRegistration:
    """`rate_limit_host` is the host the entry's `rate_limit_rps` applies to; subdomains share
    its bucket. `live` is false for fixture sources that a full run skips."""

    source_type: str
    build: ConnectorBuilder
    rate_limit_host: str | None = None
    live: bool = True


class UnknownSourceTypeError(LookupError):
    def __init__(self, source_type: str, registered: Iterable[str]) -> None:
        names = ", ".join(sorted(registered))
        super().__init__(
            f"No connector registered for source_type={source_type!r}; registered: {names}"
        )
        self.source_type = source_type


class ConnectorConfigurationError(RuntimeError):
    """A connector cannot be built because a setting it needs is missing."""


class ConnectorRegistry:
    def __init__(self) -> None:
        self._registrations: dict[str, ConnectorRegistration] = {}

    def add(self, registration: ConnectorRegistration) -> None:
        if registration.source_type in self._registrations:
            raise ValueError(f"source_type {registration.source_type!r} is already registered")
        self._registrations[registration.source_type] = registration

    def register(
        self, source_type: str, *, rate_limit_host: str | None = None, live: bool = True
    ) -> Callable[[ConnectorBuilder], ConnectorBuilder]:
        def decorator(build: ConnectorBuilder) -> ConnectorBuilder:
            self.add(ConnectorRegistration(source_type, build, rate_limit_host, live))
            return build

        return decorator

    def source_types(self) -> list[str]:
        return sorted(self._registrations)

    def registration(self, source_type: str) -> ConnectorRegistration:
        try:
            return self._registrations[source_type]
        except KeyError:
            raise UnknownSourceTypeError(source_type, self._registrations) from None

    def build(
        self,
        entry: SourceEntry,
        client: RateLimitedClient,
        env: Mapping[str, str] | None = None,
    ) -> SourceConnector:
        registration = self.registration(entry.source_type)
        return registration.build(BuildContext(client, entry, os.environ if env is None else env))

    def host_limits(self, entries: Iterable[SourceEntry]) -> dict[str, float]:
        """Per-host request rates for a shared `RateLimitedClient`, from each entry's
        `rate_limit_rps`."""
        limits: dict[str, float] = {}
        for entry in entries:
            host = self.registration(entry.source_type).rate_limit_host
            if host is not None:
                limits[host] = entry.rate_limit_rps
        return limits


REGISTRY = ConnectorRegistry()

_NOT_CONNECTOR_MODULES = frozenset({"base", "registry", "rate_limited_client"})


def default_registry() -> ConnectorRegistry:
    """`REGISTRY` with every connector module in this package imported, so each has
    registered itself."""
    for module in pkgutil.iter_modules([str(Path(__file__).parent)]):
        if module.name not in _NOT_CONNECTOR_MODULES:
            importlib.import_module(f"{__package__}.{module.name}")
    return REGISTRY

