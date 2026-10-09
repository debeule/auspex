import hashlib
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from ..models import RawDocument
from .base import SourceConnector
from .rate_limited_client import RateLimitedClient
from .registry import REGISTRY, BuildContext

_BASE_URL = "https://api.fda.gov/drug/drugsfda.json"
_PAGE_SIZE = 100

_ACTION_LABELS: dict[str, str] = {
    "AP": "Approved",
    "TA": "Tentatively Approved",
    "RE": "Refused to File",
    "W": "Withdrawn",
}


class QuotaExhaustedError(RuntimeError):
    pass


class FdaApprovalConnector(SourceConnector):
    provides_canonical_id = True

    def __init__(
        self,
        *,
        client: RateLimitedClient,
        base_url: str = _BASE_URL,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._base_url = base_url
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep: Callable[[float], None] = sleep or time.sleep

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        start = cursor.strftime("%Y%m%d")
        end = self._now().strftime("%Y%m%d")
        retrieved_at = self._now()
        skip = 0

        while True:
            params = {
                "search": f"submissions.action_date:[{start}+TO+{end}]",
                "limit": str(_PAGE_SIZE),
                "skip": str(skip),
            }
            data = self._get_json(params)
            results = data.get("results") or []
            for record in results:
                docs = list(self._map(record, retrieved_at))
                yield from docs

            total: int = (data.get("meta") or {}).get("results", {}).get("total", 0)
            skip += len(results)
            if skip >= total or not results:
                break

    def _map(self, record: dict[str, Any], retrieved_at: datetime) -> Iterator[RawDocument]:
        application_number: str = str(record.get("application_number") or "")
        if not application_number:
            return

        sponsor_name: str = str(record.get("sponsor_name") or "")
        openfda: dict[str, Any] = record.get("openfda") or {}
        brand_names: list[str] = openfda.get("brand_name") or []
        generic_names: list[str] = openfda.get("generic_name") or []

        submissions: list[dict[str, Any]] = record.get("submissions") or []
        products: list[dict[str, Any]] = record.get("products") or []
        product_summary = "; ".join(
            f"{p.get('brand_name', '')} ({p.get('dosage_form', '')})"
            for p in products
        )

        for sub in submissions:
            action_date_str: str = str(sub.get("action_date") or "")
            if not action_date_str or len(action_date_str) != 8:
                continue

            action_type: str = str(sub.get("action_type") or "")
            action_label = _ACTION_LABELS.get(action_type, action_type)
            sub_type: str = str(sub.get("submission_type") or "")
            sub_number: str = str(sub.get("submission_number") or "")
            review_priority: str = str(sub.get("review_priority") or "")
            sub_class: str = str(sub.get("submission_class_code_description") or "")

            published_date = datetime.strptime(action_date_str, "%Y%m%d").replace(tzinfo=UTC)

            raw_content = (
                f"Application: {application_number}\n"
                f"Sponsor: {sponsor_name}\n"
                f"Action: {action_label} ({action_type})\n"
                f"Submission: {sub_type}{sub_number}\n"
                f"Review priority: {review_priority}\n"
                f"Submission class: {sub_class}\n"
                f"Action date: {action_date_str}\n"
                f"Brand names: {', '.join(brand_names)}\n"
                f"Generic names: {', '.join(generic_names)}\n"
                f"Products: {product_summary}"
            )
            sha = hashlib.sha256(raw_content.encode()).hexdigest()

            yield RawDocument(
                schema_version="1.0",
                external_id=f"fda_approval:{application_number}:{sub_type}{sub_number}",
                canonical_id=f"fda:{application_number}",
                source_type="fda_approval",
                source_url=f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={application_number}",
                published_date=published_date,
                raw_content=raw_content,
                content_sha256=sha,
                retrieved_at=retrieved_at,
            )

    def _get_json(self, params: dict[str, str]) -> dict[str, Any]:
        last_resp: httpx.Response | None = None
        last_resp = self._client.get(self._base_url, params=params)
        if last_resp.status_code == 429:
            raise QuotaExhaustedError(
                "openFDA daily query limit reached. Register for an API key at https://open.fda.gov/apis/authentication/"
            )
        if last_resp.status_code == 404:
            return {}
        last_resp.raise_for_status()
        return cast(dict[str, Any], last_resp.json())


@REGISTRY.register("fda_approval", rate_limit_host="api.fda.gov")
def _build(ctx: BuildContext) -> FdaApprovalConnector:
    return FdaApprovalConnector(client=ctx.client)
