"""SEC EDGAR material disclosures connector (EFTS full-text search endpoint).

EFTS is undocumented — no published parameter list or schema commitment.
Keep the mapping thin: extract only fields that are stable across schema drift.
"""

import hashlib
import os
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from ..models import RawDocument
from ..rate_limited_client import RateLimitedClient
from .base import SourceConnector

_USER_AGENT: str = os.environ.get("SEC_USER_AGENT", "")

_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
_FORMS = "8-K,8-K/A"
_PAGE_SIZE = 20
# SEC blocks by IP for ~10 minutes on rate limit; back off conservatively.
_BLOCK_BACKOFF = 60.0


class SecEdgarConnector(SourceConnector):
    provides_canonical_id = True

    def __init__(
        self,
        *,
        client: RateLimitedClient,
        user_agent: str = _USER_AGENT,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = client
        self._user_agent = user_agent
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep: Callable[[float], None] = sleep or time.sleep
        self._max_retries = max_retries

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        start = cursor.strftime("%Y-%m-%d")
        end = self._now().strftime("%Y-%m-%d")
        retrieved_at = self._now()
        from_ = 0

        while True:
            params = {
                "q": "",
                "dateRange": "custom",
                "startdt": start,
                "enddt": end,
                "forms": _FORMS,
                "from": str(from_),
            }
            data = self._get_json(params)
            hits_wrapper = data.get("hits") or {}
            hits: list[dict[str, Any]] = hits_wrapper.get("hits") or []
            total: int = (hits_wrapper.get("total") or {}).get("value", 0)

            for hit in hits:
                source = hit.get("_source") or {}
                doc = self._map(source, retrieved_at)
                if doc is not None:
                    yield doc

            from_ += len(hits)
            if from_ >= total or not hits:
                break

    def _map(self, source: dict[str, Any], retrieved_at: datetime) -> RawDocument | None:
        accession_no: str = str(source.get("accession_no") or "")
        if not accession_no:
            return None

        file_date: str = str(source.get("file_date") or "")
        if not file_date:
            return None

        entity_id: str = str(source.get("entity_id") or "")
        entity_name: str = str(source.get("entity_name") or "")
        form_type: str = str(source.get("form_type") or "")
        period: str = str(source.get("period_of_report") or "")
        items: str = str(source.get("items") or "")

        published_date = datetime.strptime(file_date, "%Y-%m-%d").replace(tzinfo=UTC)

        raw_content = (
            f"Accession: {accession_no}\n"
            f"Entity: {entity_name}\n"
            f"Form type: {form_type}\n"
            f"Filed: {file_date}\n"
            f"Period: {period}\n"
            f"Items: {items}"
        )
        sha = hashlib.sha256(raw_content.encode()).hexdigest()

        accession_nodash = accession_no.replace("-", "")
        source_url = (
            f"https://www.sec.gov/Archives/edgar/data/{entity_id}/{accession_nodash}/"
            if entity_id
            else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&accession={accession_nodash}"
        )

        return RawDocument(
            schema_version="1.0",
            external_id=f"edgar:{accession_no}",
            canonical_id=f"edgar:{accession_no}",
            source_type="edgar",
            source_url=source_url,
            published_date=published_date,
            raw_content=raw_content,
            content_sha256=sha,
            retrieved_at=retrieved_at,
        )

    def _get_json(self, params: dict[str, str]) -> dict[str, Any]:
        headers = {"User-Agent": self._user_agent}
        last_resp: httpx.Response | None = None
        for _ in range(self._max_retries):
            last_resp = self._client.get(_EFTS_URL, params=params, headers=headers)
            if last_resp.status_code == 403:
                self._sleep(_BLOCK_BACKOFF)
                continue
            last_resp.raise_for_status()
            return cast(dict[str, Any], last_resp.json())
        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError(f"Exhausted retries for {_EFTS_URL}")
