"""One paced HTTP client for every SEC request the ownership panels make.

SEC allows 10 requests per second across all of its hosts and blocks the address for about ten
minutes beyond that; retrying during a block extends it. Requests here are spaced to at most
`max_per_second` (5 by default, half the limit, so a universe build running at the same time
stays under it too), and a refusal ends the run instead of retrying.
"""

import shutil
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

_BLOCKED_STATUSES = frozenset({403, 429})


class SecBlockedError(Exception):
    """SEC refused a request (HTTP 403 or 429). Stop: a retry extends the block."""


class SecNotFoundError(Exception):
    """SEC has no document at this URL (HTTP 404), e.g. a daily index for a market holiday."""


class SecFetcher(Protocol):
    def get(self, url: str) -> bytes: ...

    def download(self, url: str, dest: Path) -> Path: ...


class SecClient:
    def __init__(
        self,
        user_agent: str,
        *,
        max_per_second: float = 5.0,
        opener: Callable[..., Any] = urllib.request.urlopen,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("SEC refuses requests without a descriptive User-Agent")
        self._user_agent = user_agent
        self._interval = 1.0 / max_per_second
        self._opener = opener
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def get(self, url: str) -> bytes:
        with self._open(url, timeout=60) as resp:
            body: bytes = resp.read()
        return body

    def download(self, url: str, dest: Path) -> Path:
        """Streams `url` to `dest` (bulk data sets run to hundreds of megabytes)."""
        with self._open(url, timeout=600) as resp, dest.open("wb") as out:
            shutil.copyfileobj(resp, out, length=1 << 20)
        return dest

    def _open(self, url: str, timeout: float) -> Any:
        if self._last is not None:
            wait = self._interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()
        request = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
        try:
            return self._opener(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in _BLOCKED_STATUSES:
                raise SecBlockedError(f"SEC refused {url} (HTTP {exc.code})") from exc
            if exc.code == 404:
                raise SecNotFoundError(url) from exc
            raise
