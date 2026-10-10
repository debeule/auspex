from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, Self
from urllib.parse import urlparse

import httpx


class _TokenBucket:
    """Spaces requests `1 / rate` seconds apart, with no burst: any one-second window holds at
    most `rate` requests, which is how SEC counts its limit. A caller that finds the bucket empty
    reserves the next token and is told how long to wait, so concurrent callers queue in turn."""

    def __init__(self, rate_rps: float, clock: Callable[[], float]) -> None:
        self._rate = rate_rps
        self._tokens = 1.0
        self._last = clock()
        self._clock = clock
        self._lock = threading.Lock()

    def reserve(self) -> float:
        """Takes a token and returns the seconds to wait before using it (0 when one was free)."""
        with self._lock:
            tokens, last = self._tokens, self._last
            now = self._clock()
            tokens = min(1.0, tokens + (now - last) * self._rate) - 1.0
            self._tokens, self._last = tokens, now
            return 0.0 if tokens >= 0.0 else -tokens / self._rate


class RateLimitedClient:
    """Must be shared across connectors so per-host buckets are not bypassed. A request to a host
    whose bucket is empty waits for its token; it is never refused."""

    def __init__(
        self,
        host_limits: dict[str, float],
        *,
        _httpx_client: httpx.Client | None = None,
        _clock: Callable[[], float] | None = None,
        _sleep: Callable[[float], None] | None = None,
        timeout: float = 30.0,
    ) -> None:
        clock = _clock or time.monotonic
        self._sleep = _sleep or time.sleep
        self._http = _httpx_client or httpx.Client(timeout=timeout)
        self._buckets: dict[str, _TokenBucket] = {
            host: _TokenBucket(rps, clock) for host, rps in host_limits.items()
        }

    def _acquire(self, url: str) -> None:
        host = urlparse(url).netloc
        bucket = self._buckets.get(host)
        if bucket is None:
            # Suffix match: "sec.gov" covers "efts.sec.gov", "data.sec.gov", etc.
            for configured_host, b in self._buckets.items():
                if host.endswith(f".{configured_host}"):
                    bucket = b
                    break
        if bucket is not None:
            wait = bucket.reserve()
            if wait > 0:
                self._sleep(wait)

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
