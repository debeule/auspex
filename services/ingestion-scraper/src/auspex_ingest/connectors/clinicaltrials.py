"""ClinicalTrials.gov API v2 connector."""

import hashlib
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from ..models import RawDocument
from ..rate_limited_client import RateLimitedClient
from .base import SourceConnector

_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
_PAGE_SIZE = 1000
_DEFAULT_BACKOFF = 10.0


class ClinicalTrialConnector(SourceConnector):
    provides_canonical_id = True

    def __init__(
        self,
        *,
        client: RateLimitedClient,
        base_url: str = _BASE_URL,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = client
        self._base_url = base_url
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep: Callable[[float], None] = sleep or time.sleep
        self._max_retries = max_retries

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        start = cursor.strftime("%Y-%m-%d")
        end = self._now().strftime("%Y-%m-%d")
        retrieved_at = self._now()
        page_token: str | None = None

        while True:
            params: dict[str, str | int] = {
                "filter.advanced": f"AREA[LastUpdatePostDate]RANGE[{start},{end}]",
                "pageSize": _PAGE_SIZE,
                "format": "json",
                "fields": (
                    "NCTId,BriefTitle,BriefSummary,"
                    "StudyFirstSubmitDate,StudyFirstPostDate,"
                    "LastUpdateSubmitDate,LastUpdatePostDate,OverallStatus"
                ),
            }
            if page_token:
                params["pageToken"] = page_token

            data = self._get_json(params)
            for study in data.get("studies") or []:
                doc = self._map(study, retrieved_at)
                if doc is not None:
                    yield doc

            page_token = cast(str | None, data.get("nextPageToken"))
            if not page_token:
                break

    def _map(self, study: dict[str, Any], retrieved_at: datetime) -> RawDocument | None:
        proto = study.get("protocolSection") or {}
        ident = proto.get("identificationModule") or {}
        desc = proto.get("descriptionModule") or {}
        status = proto.get("statusModule") or {}

        nct_id: str | None = ident.get("nctId")
        if not nct_id:
            return None

        title: str = str(ident.get("briefTitle") or "")
        summary: str = str(desc.get("briefSummary") or "")

        first_post_date: str = (status.get("studyFirstPostDateStruct") or {}).get("date", "")
        last_update_date: str = (status.get("lastUpdatePostDateStruct") or {}).get("date", "")
        first_submit_date: str = str(status.get("studyFirstSubmitDate") or "")
        overall_status: str = str(status.get("overallStatus") or "")

        # Use last_update_date for amendments; first_post_date for new studies.
        is_amendment = last_update_date and first_post_date and last_update_date > first_post_date
        pub_date_str = last_update_date if is_amendment else (first_post_date or last_update_date)
        published_date = datetime.strptime(pub_date_str, "%Y-%m-%d").replace(tzinfo=UTC)

        # Both date fields retained in raw_content.
        raw_content = (
            f"{title}\n\n{summary}\n\n"
            f"NCT ID: {nct_id}\n"
            f"Overall status: {overall_status}\n"
            f"Study first posted: {first_post_date}\n"
            f"Last updated: {last_update_date}\n"
            f"First submitted: {first_submit_date}"
        )
        sha = hashlib.sha256(raw_content.encode()).hexdigest()

        return RawDocument(
            schema_version="1.0",
            external_id=f"clinicaltrials:{nct_id}",
            canonical_id=f"nct:{nct_id}",
            source_type="clinicaltrials",
            source_url=f"https://clinicaltrials.gov/study/{nct_id}",
            published_date=published_date,
            raw_content=raw_content,
            content_sha256=sha,
            retrieved_at=retrieved_at,
        )

    def _get_json(self, params: dict[str, str | int]) -> dict[str, Any]:
        str_params = {k: str(v) for k, v in params.items()}
        last_resp: httpx.Response | None = None
        for _ in range(self._max_retries):
            last_resp = self._client.get(self._base_url, params=str_params)
            if last_resp.status_code == 429:
                backoff = float(last_resp.headers.get("Retry-After", str(_DEFAULT_BACKOFF)))
                self._sleep(backoff)
                continue
            last_resp.raise_for_status()
            return cast(dict[str, Any], last_resp.json())
        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError(f"No retries configured for {self._base_url}")
