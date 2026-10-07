"""Source-type → connector construction, as a lookup table.

Adding a source means adding one builder here plus its `sources.yaml` entry;
callers never branch on `source_type` themselves (Invariant 4).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from .base import SourceConnector
from .rate_limited_client import RateLimitedClient

_Builder = Callable[
    [RateLimitedClient, Mapping[str, Any], Mapping[str, str], datetime | None],
    SourceConnector,
]


def _biorxiv(client: RateLimitedClient, cfg: Mapping[str, Any], env: Mapping[str, str],
             until: datetime | None) -> SourceConnector:
    from .biorxiv import BiorxivConnector
    return BiorxivConnector(client=client, until=until)


def _clinicaltrials(client: RateLimitedClient, cfg: Mapping[str, Any], env: Mapping[str, str],
                    until: datetime | None) -> SourceConnector:
    from .clinicaltrials import ClinicalTrialConnector
    return ClinicalTrialConnector(client=client, until=until)


def _pubmed(client: RateLimitedClient, cfg: Mapping[str, Any], env: Mapping[str, str],
            until: datetime | None) -> SourceConnector:
    from .pubmed import PubmedConnector
    search_term = cfg.get("search_term")
    if not search_term:
        raise ValueError("pubmed source_config.search_term is required")
    return PubmedConnector(
        client=client,
        search_term=str(search_term),
        api_key=env.get("NCBI_API_KEY") or None,
        until=until,
    )


def _edgar(client: RateLimitedClient, cfg: Mapping[str, Any], env: Mapping[str, str],
           until: datetime | None) -> SourceConnector:
    from .sec_edgar import SecEdgarConnector
    user_agent = env.get("SEC_USER_AGENT", "")
    if not user_agent:
        raise ValueError("SEC_USER_AGENT is required for the edgar connector (SEC returns 403 without it)")
    return SecEdgarConnector(client=client, user_agent=user_agent, until=until)


def _epo_ops(client: RateLimitedClient, cfg: Mapping[str, Any], env: Mapping[str, str],
             until: datetime | None) -> SourceConnector:
    from .epo_ops import EpoOpsConnector
    return EpoOpsConnector(
        client=client,
        key=env.get("EPO_OPS_KEY", ""),
        secret=env.get("EPO_OPS_SECRET", ""),
        until=until,
    )


CONNECTOR_BUILDERS: dict[str, _Builder] = {
    "biorxiv": _biorxiv,
    "clinicaltrials": _clinicaltrials,
    "pubmed": _pubmed,
    "edgar": _edgar,
    "epo_ops": _epo_ops,
}

# Host each connector calls, for the shared per-host rate limiter. EDGAR's
# "sec.gov" covers efts./data./www. by suffix match: SEC limits all hosts as one.
CONNECTOR_HOSTS: dict[str, str] = {
    "biorxiv": "api.biorxiv.org",
    "clinicaltrials": "clinicaltrials.gov",
    "pubmed": "eutils.ncbi.nlm.nih.gov",
    "edgar": "sec.gov",
    "epo_ops": "ops.epo.org",
}


def build_connector(
    source_type: str,
    *,
    client: RateLimitedClient,
    source_config: Mapping[str, Any],
    env: Mapping[str, str],
    until: datetime | None = None,
) -> SourceConnector:
    builder = CONNECTOR_BUILDERS.get(source_type)
    if builder is None:
        raise ValueError(
            f"No connector registered for source_type={source_type!r}; "
            f"available: {sorted(CONNECTOR_BUILDERS)}"
        )
    return builder(client, source_config, env, until)
