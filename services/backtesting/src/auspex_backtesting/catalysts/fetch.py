"""Rate-limited HTTP reads and a MinIO copy of every document read, so each is fetched once."""

import io
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from minio import Minio
from minio.error import S3Error

from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET

log = logging.getLogger("auspex_backtesting.catalysts")

DOCUMENTS_PREFIX = "catalyst-documents/"
_BLOCKED_STATUSES = frozenset({403, 429})
_MISSING_STATUSES = frozenset({404, 410})


class SourceBlockedError(Exception):
    """The source refused a request (HTTP 403 or 429). SEC extends an IP block when requests
    continue during it, so the run stops instead of retrying."""


class DocumentNotFoundError(Exception):
    """The source has no document at the URL (HTTP 404 or 410)."""


def _urlopen(url: str, user_agent: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=60) as resp:
        body: bytes = resp.read()
    return body


class HttpSource:
    """One host's request budget: at most one request per `min_interval_s`, shared by every
    fetch that goes through this instance."""

    def __init__(
        self,
        user_agent: str,
        min_interval_s: float,
        *,
        fetch: Callable[[str, str], bytes] = _urlopen,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("a descriptive User-Agent is required (SEC answers 403 without one)")
        self._user_agent = user_agent
        self._interval = min_interval_s
        self._fetch = fetch
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def get(self, url: str) -> bytes:
        if self._last is not None:
            wait = self._last + self._interval - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()
        try:
            return self._fetch(url, self._user_agent)
        except urllib.error.HTTPError as exc:
            if exc.code in _BLOCKED_STATUSES:
                raise SourceBlockedError(f"{url}: HTTP {exc.code}") from exc
            if exc.code in _MISSING_STATUSES:
                raise DocumentNotFoundError(f"{url}: HTTP {exc.code}") from exc
            raise


class DocumentCache:
    """Documents under `catalyst-documents/` in the prices bucket, keyed by the caller's stable
    name for the document (accession, notice number), not its URL."""

    def __init__(self, minio_client: Minio, bucket: str = PRICES_BUCKET) -> None:
        self._minio = minio_client
        self._bucket = bucket

    def fetch(self, key: str, url: str, source: HttpSource, *, keep: bool = True) -> bytes:
        """The stored copy of `key`, or else the document at `url`, stored when `keep`. A
        document that can still change (the index of a quarter in progress) is not kept."""
        stored = self._get(DOCUMENTS_PREFIX + key)
        if stored is not None:
            return stored
        data = source.get(url)
        if keep:
            self._minio.put_object(
                self._bucket, DOCUMENTS_PREFIX + key, io.BytesIO(data), len(data),
                content_type="application/octet-stream",
            )
        return data

    def _get(self, key: str) -> bytes | None:
        try:
            resp = self._minio.get_object(self._bucket, key)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise
        try:
            return bytes(resp.read())
        finally:
            resp.close()
            resp.release_conn()
