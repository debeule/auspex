"""FINRA Query API client for consolidated short interest.

Every request needs a FINRA API credential (a free public credential from FINRA's API
console): a client id and secret exchanged for a bearer token, fetched again when it expires.
Synchronous requests return at most 5000 rows, so a settlement period is read page by page.
"""

import base64
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import date
from typing import Any, Protocol

PAGE_SIZE = 5000


class FinraAuthError(Exception):
    """FINRA refused the API credential."""


class ShortInterestSource(Protocol):
    def records(self, settlement_date: date) -> list[dict[str, Any]]:
        """FINRA's rows for one settlement date; empty when FINRA has none for it."""
        ...


class FinraClient:
    def __init__(
        self,
        data_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        *,
        min_interval_seconds: float = 0.2,
        opener: Callable[..., Any] = urllib.request.urlopen,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not client_id.strip() or not client_secret.strip():
            raise FinraAuthError("FINRA_API_CLIENT_ID and FINRA_API_CLIENT_SECRET must be set")
        self._data_url = data_url
        self._token_url = token_url
        self._basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        self._interval = min_interval_seconds
        self._opener = opener
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None
        self._token: str | None = None

    def records(self, settlement_date: date) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        while True:
            page = self._page(settlement_date, len(rows))
            rows.extend(page)
            if len(page) < PAGE_SIZE:
                return rows

    def _page(self, settlement_date: date, offset: int) -> list[dict[str, Any]]:
        body = json.dumps({
            "limit": PAGE_SIZE,
            "offset": offset,
            "compareFilters": [{
                "compareType": "EQUAL",
                "fieldName": "settlementDate",
                "fieldValue": settlement_date.isoformat(),
            }],
        }).encode()
        for _ in range(2):
            request = urllib.request.Request(
                self._data_url, data=body, method="POST",
                headers={
                    "Authorization": f"Bearer {self._bearer()}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            try:
                with self._open(request) as resp:
                    raw = resp.read()
            except urllib.error.HTTPError as exc:
                if exc.code != 401:
                    raise
                self._token = None
                continue
            if not raw.strip():
                return []
            page: list[dict[str, Any]] = json.loads(raw)
            return page
        raise FinraAuthError(f"FINRA rejected a fresh token for {self._data_url}")

    def _bearer(self) -> str:
        if self._token is None:
            request = urllib.request.Request(
                self._token_url, data=b"", method="POST",
                headers={"Authorization": f"Basic {self._basic}"},
            )
            try:
                with self._open(request) as resp:
                    payload = json.loads(resp.read())
            except urllib.error.HTTPError as exc:
                if exc.code in (400, 401, 403):
                    raise FinraAuthError(f"FINRA refused the credential (HTTP {exc.code})") from exc
                raise
            self._token = str(payload["access_token"])
        return self._token

    def _open(self, request: urllib.request.Request) -> Any:
        if self._last is not None:
            wait = self._interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()
        return self._opener(request, timeout=120)
