from unittest.mock import MagicMock

import pytest

from auspex_ingest.connectors import RateLimitedClient, RateLimitExceeded


def test_rate_limited_client_enforces_configured_rps() -> None:
    current_time = [0.0]
    mock_http = MagicMock()
    mock_http.get.return_value = MagicMock(status_code=200)

    client = RateLimitedClient(
        host_limits={"api.example.com": 1.0},
        _httpx_client=mock_http,
        _clock=lambda: current_time[0],
    )

    client.get("https://api.example.com/1")  # OK: 1 token consumed

    with pytest.raises(RateLimitExceeded):
        client.get("https://api.example.com/2")  # fail: 0 tokens at t=0

    current_time[0] = 1.0  # advance 1 second → 1 token refilled
    client.get("https://api.example.com/3")  # OK again


def test_two_connectors_on_the_same_host_share_one_bucket() -> None:
    """Two URL paths on the same host share one rate-limit bucket."""
    current_time = [0.0]
    mock_http = MagicMock()
    mock_http.get.return_value = MagicMock(status_code=200)

    client = RateLimitedClient(
        host_limits={"eutils.ncbi.nlm.nih.gov": 1.0},
        _httpx_client=mock_http,
        _clock=lambda: current_time[0],
    )

    # "biorxiv connector" calls esearch
    client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi")

    # "pubmed connector" calls efetch on same host — bucket exhausted
    with pytest.raises(RateLimitExceeded):
        client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi")
