"""SEC EDGAR material disclosures connector (EFTS full-text search endpoint).

EFTS is undocumented — no published parameter list or schema commitment.
Keep the mapping thin: extract only fields that are stable across schema drift.
"""

import hashlib
import logging
import os
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any, cast

import httpx

from ..models import RawDocument
from .base import SourceConnector
from .rate_limited_client import RateLimitedClient

_USER_AGENT: str = os.environ.get("SEC_USER_AGENT", "")

_log = logging.getLogger(__name__)


def _cik_from_accession(accession_no: str) -> str:
    """Return the numeric CIK (no leading zeros) from the first segment of an accession number."""
    return str(int(accession_no.split("-")[0]))


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self._parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()

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
        until: datetime | None = None,
        sleep: Callable[[float], None] | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = client
        self._user_agent = user_agent
        self._now = now or (lambda: datetime.now(UTC))
        # Inclusive upper bound of the query window; None means "up to now".
        self._until = until
        self._sleep: Callable[[float], None] = sleep or time.sleep
        self._max_retries = max_retries

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        start = cursor.strftime("%Y-%m-%d")
        end = (self._until or self._now()).strftime("%Y-%m-%d")
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
                    accession_no: str = str(source.get("adsh") or "")
                    text = self._fetch_primary_document_text(accession_no)
                    if text is not None:
                        sha = hashlib.sha256(text.encode()).hexdigest()
                        doc = doc.model_copy(update={"raw_content": text, "content_sha256": sha})
                    yield doc

            from_ += len(hits)
            if from_ >= total or not hits:
                break

    def _map(self, source: dict[str, Any], retrieved_at: datetime) -> RawDocument | None:
        accession_no: str = str(source.get("adsh") or "")
        if not accession_no:
            return None

        file_date: str = str(source.get("file_date") or "")
        if not file_date:
            return None

        # ciks[0] is zero-padded; strip for the Archives URL path
        entity_id: str = str((source.get("ciks") or [""])[0]).lstrip("0")
        # display_names[0] may include " (TICKER)  (CIK XXXXXXXXXX)" suffix
        entity_name: str = str((source.get("display_names") or [""])[0]).split("(")[0].strip()
        form_type: str = str(source.get("form") or "")
        period: str = str(source.get("period_ending") or "")
        items: str = ", ".join(source.get("items") or [])

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

    def _fetch_primary_document_text(self, accession_no: str) -> str | None:
        if not accession_no:
            return None
        try:
            cik = _cik_from_accession(accession_no)
            cik_padded = cik.zfill(10)
            accession_nodash = accession_no.replace("-", "")
            headers = {"User-Agent": self._user_agent}

            # data.sec.gov/submissions returns primaryDocument per accession number
            submissions_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
            sub_resp = self._client.get(submissions_url, headers=headers)
            if sub_resp.status_code >= 400:
                _log.warning(
                    "edgar submissions fetch failed: accession=%s status=%d",
                    accession_no,
                    sub_resp.status_code,
                )
                return None

            recent = sub_resp.json().get("filings", {}).get("recent", {})
            acc_nums: list[str] = recent.get("accessionNumber") or []
            if accession_no not in acc_nums:
                return None
            idx = acc_nums.index(accession_no)
            primary_doc: str = (recent.get("primaryDocument") or [])[idx]
            if not primary_doc:
                return None

            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}"
                f"/{accession_nodash}/{primary_doc}"
            )
            doc_resp = self._client.get(doc_url, headers=headers)
            if doc_resp.status_code >= 400:
                _log.warning(
                    "edgar document fetch failed: accession=%s status=%d",
                    accession_no,
                    doc_resp.status_code,
                )
                return None

            return _strip_html(doc_resp.text) or None
        except Exception as exc:  # noqa: BLE001
            _log.warning("edgar document fetch error: accession=%s exc=%s", accession_no, exc)
            return None

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
