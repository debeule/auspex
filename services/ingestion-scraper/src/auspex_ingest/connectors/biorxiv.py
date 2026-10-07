import hashlib
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from ..models import RawDocument
from .base import SourceConnector
from .rate_limited_client import RateLimitedClient

_PAGE_SIZE = 100
_DEFAULT_BACKOFF = 30.0


class BiorxivConnector(SourceConnector):
    provides_canonical_id = True

    def __init__(
        self,
        *,
        client: RateLimitedClient,
        server: str = "biorxiv",
        base_url: str = "https://api.biorxiv.org",
        now: Callable[[], datetime] | None = None,
        until: datetime | None = None,
        sleep: Callable[[float], None] | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = client
        self._server = server
        self._base_url = base_url.rstrip("/")
        self._now = now or (lambda: datetime.now(UTC))
        # Inclusive upper bound of the query window; None means "up to now".
        self._until = until
        self._sleep: Callable[[float], None] = sleep or time.sleep
        self._max_retries = max_retries

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        start = cursor.strftime("%Y-%m-%d")
        end = (self._until or self._now()).strftime("%Y-%m-%d")
        page = 0
        retrieved_at = self._now()

        while True:
            url = f"{self._base_url}/details/{self._server}/{start}/{end}/{page}/json"
            data = self._get_json(url)

            msg: dict[str, Any] = data["messages"][0]
            collection: list[dict[str, Any]] = data.get("collection") or []

            for item in collection:
                yield self._map(item, retrieved_at)

            total = int(msg.get("total", 0))
            count = int(msg.get("count", 0))
            page += count if count > 0 else _PAGE_SIZE

            if page >= total or count == 0:
                break

    def _get_json(self, url: str) -> dict[str, Any]:
        last_resp: httpx.Response | None = None
        for _ in range(self._max_retries):
            last_resp = self._client.get(url)
            if last_resp.status_code == 429:
                backoff = float(last_resp.headers.get("Retry-After", str(_DEFAULT_BACKOFF)))
                self._sleep(backoff)
                continue
            last_resp.raise_for_status()
            return cast(dict[str, Any], last_resp.json())
        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError(f"No retries configured for {url}")

    def _map(self, item: dict[str, Any], retrieved_at: datetime) -> RawDocument:
        doi: str = item["doi"]
        version: str = str(item.get("version", "1"))
        title: str = str(item.get("title") or "")
        abstract: str = str(item.get("abstract") or "")
        raw_content = f"{title}\n\n{abstract}"

        date_str: str = item["date"]
        published_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)

        sha = hashlib.sha256(raw_content.encode()).hexdigest()

        return RawDocument(
            schema_version="1.0",
            external_id=f"biorxiv:{doi}:v{version}",
            canonical_id=f"doi:{doi}",
            source_type="biorxiv",
            source_url=f"https://www.biorxiv.org/content/{doi}v{version}",
            published_date=published_date,
            raw_content=raw_content,
            content_sha256=sha,
            retrieved_at=retrieved_at,
        )
