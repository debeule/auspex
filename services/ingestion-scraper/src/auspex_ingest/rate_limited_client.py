"""HTTP client with per-host token-bucket rate limiting."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Self
from urllib.parse import urlparse

import httpx


class RateLimitExceeded(Exception):
    """Raised when a request exceeds the configured per-host rate limit."""


class _TokenBucket:
    """Token bucket with injectable clock for testability."""

    def __init__(self, rate_rps: float, clock: Callable[[], float]) -> None:
        self._rate = rate_rps
        self._tokens = rate_rps  # start full (1 second of capacity)
        self._last = clock()
        self._clock = clock

    def try_acquire(self) -> bool:
        now = self._clock()
        elapsed = now - self._last
        self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
        self._last = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False


class RateLimitedClient:
    """Wraps `httpx.Client` with per-host token-bucket rate limiting.

    Every connector must issue HTTP through one shared instance of this class
    so that the per-host buckets are shared across connectors that hit the
    same host.
    """

    def __init__(
        self,
        host_limits: dict[str, float],
        *,
        _httpx_client: httpx.Client | None = None,
        _clock: Callable[[], float] | None = None,
    ) -> None:
        clock = _clock or time.monotonic
        self._http = _httpx_client or httpx.Client()
        self._buckets: dict[str, _TokenBucket] = {
            host: _TokenBucket(rps, clock) for host, rps in host_limits.items()
        }

    def _acquire(self, url: str) -> None:
        host = urlparse(url).netloc
        bucket = self._buckets.get(host)
        if bucket is not None and not bucket.try_acquire():
            raise RateLimitExceeded(f"Rate limit exceeded for host {host!r}")

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self._acquire(url)
        return self._http.get(url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self._acquire(url)
        return self._http.post(url, **kwargs)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
