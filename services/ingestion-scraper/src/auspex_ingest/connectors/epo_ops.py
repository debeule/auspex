# Two-step fetch: search → publication references, then batch biblio for full data.
# Auth: OAuth2 client credentials; token expires in 20 min, refreshed 60s before expiry.
# Rate limit: 2.5 req/s standard tier; configured at 2.0 req/s.
# Date field: publication date (A1 pre-grant), never filing date.
from __future__ import annotations

import base64
import hashlib
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree

import httpx

from ..models import RawDocument
from .base import SourceConnector
from .rate_limited_client import RateLimitedClient

_DEFAULT_BASE_URL = "https://ops.epo.org/3.2/rest-services"
_DEFAULT_TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
_PAGE_SIZE = 100
_TOKEN_REFRESH_BUFFER = 60.0  # seconds before expiry to trigger refresh
_DEFAULT_BACKOFF = 30.0

_CPC_CLASSES = ["C12N", "A61K", "A61P", "C07K"]

# EPO OPS XML namespaces (confirmed from live API 2026-09-17)
_NS_OPS = "http://ops.epo.org"
_NS_EX = "http://www.epo.org/exchange"
_NS = {"ops": _NS_OPS, "ex": _NS_EX}

_GRANT_KINDS = {"B1", "B2", "B3", "B"}


@dataclass
class _Token:
    value: str
    expires_at: float  # monotonic seconds


class EpoOpsConnector(SourceConnector):
    provides_canonical_id = True

    def __init__(
        self,
        *,
        client: RateLimitedClient,
        key: str,
        secret: str,
        base_url: str = _DEFAULT_BASE_URL,
        token_url: str = _DEFAULT_TOKEN_URL,
        cpc_classes: list[str] | None = None,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        mono_clock: Callable[[], float] | None = None,
        max_retries: int = 3,
    ) -> None:
        if not key:
            raise ValueError("EPO_OPS_KEY must be set")
        if not secret:
            raise ValueError("EPO_OPS_SECRET must be set")
        self._client = client
        self._auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
        self._base_url = base_url.rstrip("/")
        self._token_url = token_url
        self._cpc_classes = cpc_classes or list(_CPC_CLASSES)
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep: Callable[[float], None] = sleep or time.sleep
        self._mono = mono_clock or time.monotonic
        self._max_retries = max_retries
        self._token: _Token | None = None

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        start = cursor.strftime("%Y%m%d")
        end = self._now().strftime("%Y%m%d")
        retrieved_at = self._now()

        cpc_filter = " or ".join(f"cpc = {c}" for c in self._cpc_classes)
        query = f'({cpc_filter}) and pd within "{start},{end}"'

        range_begin = 1
        total: int | None = None

        while True:
            range_end = range_begin + _PAGE_SIZE - 1
            token = self._get_token()

            refs, page_total = self._search_page(query, range_begin, range_end, token)
            if total is None:
                total = page_total
            if not refs:
                break

            token = self._get_token()  # may expire during search round-trip
            biblio_xml = self._fetch_biblio(refs, token)
            yield from self._parse_biblio(biblio_xml, retrieved_at)

            if range_end >= total:
                break
            range_begin = range_end + 1

    def _get_token(self) -> str:
        now = self._mono()
        if (self._token is not None
                and self._token.expires_at > now + _TOKEN_REFRESH_BUFFER):
            return self._token.value

        resp = self._client.post(
            self._token_url,
            content=b"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {self._auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        expires_in = int(data.get("expires_in", 1200))
        self._token = _Token(
            value=str(data["access_token"]),
            expires_at=self._mono() + expires_in,
        )
        return self._token.value

    def _search_page(
        self, query: str, begin: int, end: int, token: str
    ) -> tuple[list[tuple[str, str, str]], int]:
        url = f"{self._base_url}/published-data/search"
        last_resp: httpx.Response | None = None

        for _ in range(self._max_retries):
            last_resp = self._client.get(
                url,
                params={"q": query},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/exchange+xml",
                    "Range": f"{begin}-{end}",
                },
            )
            if last_resp.status_code == 404:
                return [], 0  # SERVER.EntityNotFound — no results
            if last_resp.status_code == 429:
                backoff = float(last_resp.headers.get("Retry-After", str(_DEFAULT_BACKOFF)))
                self._sleep(backoff)
                token = self._get_token()
                continue
            last_resp.raise_for_status()
            return self._parse_search_refs(last_resp.content)

        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError(f"No retries left for {url}")

    def _parse_search_refs(
        self, xml_bytes: bytes
    ) -> tuple[list[tuple[str, str, str]], int]:
        root = ElementTree.fromstring(xml_bytes)
        search_el = root.find(f".//{{{_NS_OPS}}}biblio-search")
        total = int(search_el.get("total-result-count", "0")) if search_el is not None else 0

        refs: list[tuple[str, str, str]] = []
        for pub_ref in root.findall(f".//{{{_NS_OPS}}}publication-reference"):
            docid = pub_ref.find(
                f".//{{{_NS_EX}}}document-id[@document-id-type='docdb']"
            )
            if docid is None:
                continue
            country = _text(docid, f"{{{_NS_EX}}}country")
            number = _text(docid, f"{{{_NS_EX}}}doc-number")
            kind = _text(docid, f"{{{_NS_EX}}}kind")
            if country and number and kind:
                refs.append((country, number, kind))
        return refs, total

    def _fetch_biblio(self, refs: list[tuple[str, str, str]], token: str) -> bytes:
        ref_str = ",".join(f"{c}{n}.{k}" for c, n, k in refs)
        url = f"{self._base_url}/published-data/publication/docdb/{ref_str}/biblio"
        last_resp: httpx.Response | None = None

        for _ in range(self._max_retries):
            last_resp = self._client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/exchange+xml",
                },
            )
            if last_resp.status_code == 404:
                return b""
            if last_resp.status_code == 429:
                backoff = float(last_resp.headers.get("Retry-After", str(_DEFAULT_BACKOFF)))
                self._sleep(backoff)
                token = self._get_token()
                continue
            last_resp.raise_for_status()
            return last_resp.content

        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError(f"No retries left for {url}")

    def _parse_biblio(
        self, xml_bytes: bytes, retrieved_at: datetime
    ) -> Iterator[RawDocument]:
        if not xml_bytes:
            return

        root = ElementTree.fromstring(xml_bytes)
        for ex_doc in root.findall(f".//{{{_NS_EX}}}exchange-document"):
            doc = self._map(ex_doc, retrieved_at)
            if doc is not None:
                yield doc

    def _map(
        self, ex_doc: ElementTree.Element, retrieved_at: datetime
    ) -> RawDocument | None:
        bib = ex_doc.find(f"{{{_NS_EX}}}bibliographic-data")
        if bib is None:
            return None

        pub_docid = bib.find(
            f".//{{{_NS_EX}}}publication-reference"
            f"//{{{_NS_EX}}}document-id[@document-id-type='docdb']"
        )
        if pub_docid is None:
            return None

        pub_country = _text(pub_docid, f"{{{_NS_EX}}}country")
        pub_number = _text(pub_docid, f"{{{_NS_EX}}}doc-number")
        pub_kind = _text(pub_docid, f"{{{_NS_EX}}}kind")
        pub_date_str = _text(pub_docid, f"{{{_NS_EX}}}date")

        if not all([pub_country, pub_number, pub_kind, pub_date_str]):
            return None

        published_date = _parse_date(pub_date_str)  # type: ignore[arg-type]

        app_docid = bib.find(
            f".//{{{_NS_EX}}}application-reference"
            f"//{{{_NS_EX}}}document-id[@document-id-type='docdb']"
        )
        if app_docid is None:
            return None

        app_country = _text(app_docid, f"{{{_NS_EX}}}country") or pub_country
        app_number = _text(app_docid, f"{{{_NS_EX}}}doc-number") or pub_number
        app_date_str = _text(app_docid, f"{{{_NS_EX}}}date") or pub_date_str

        title_el = bib.find(f".//{{{_NS_EX}}}invention-title[@lang='en']")
        if title_el is None:
            title_el = bib.find(f".//{{{_NS_EX}}}invention-title")
        title = (title_el.text or "").strip() if title_el is not None else ""

        # Abstract (lives at exchange-document level, not inside bibliographic-data)
        abstract_paras = ex_doc.findall(
            f"{{{_NS_EX}}}abstract[@lang='en']/{{{_NS_EX}}}p"
        )
        if not abstract_paras:
            abstract_paras = ex_doc.findall(f"{{{_NS_EX}}}abstract/{{{_NS_EX}}}p")
        abstract = " ".join((p.text or "").strip() for p in abstract_paras if p.text)

        seen_names: set[str] = set()
        names: list[str] = []
        for applicant in bib.findall(
            f".//{{{_NS_EX}}}applicant[@data-format='epodoc']"
            f"/{{{_NS_EX}}}applicant-name/{{{_NS_EX}}}name"
        ):
            name = (applicant.text or "").strip()
            if name and name not in seen_names:
                seen_names.add(name)
                names.append(name)

        external_id = f"{pub_country}-{pub_number}-{pub_kind}"
        canonical_id = f"epo-app:{app_country}-{app_number}"

        is_grant = pub_kind in _GRANT_KINDS
        raw_content = (
            f"{title}\n\n"
            f"{abstract}\n\n"
            f"Publication: {external_id}\n"
            f"Application: {app_country}-{app_number}\n"
            f"Published: {pub_date_str}\n"
            f"Filed: {app_date_str}\n"
            + (f"Granted: {pub_date_str}\n" if is_grant else "")
            + f"Applicants: {'; '.join(names)}"
        )
        sha = hashlib.sha256(raw_content.encode()).hexdigest()

        return RawDocument(
            schema_version="1.0",
            external_id=external_id,
            canonical_id=canonical_id,
            source_type="epo_ops",
            source_url=f"https://ops.epo.org/3.2/rest-services/published-data/publication/docdb/{external_id.replace('-', '', 1)}/biblio",
            published_date=published_date,
            raw_content=raw_content,
            content_sha256=sha,
            retrieved_at=retrieved_at,
        )



def _text(el: ElementTree.Element, tag: str) -> str | None:
    child = el.find(tag)
    if child is None or child.text is None:
        return None
    return child.text.strip() or None


def _parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=UTC)
