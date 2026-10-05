import hashlib
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, cast
from xml.etree import ElementTree

import httpx

from ..models import RawDocument
from .base import SourceConnector
from .rate_limited_client import RateLimitedClient

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_RETMAX = 200
_DEFAULT_BACKOFF = 10.0

_MONTH_ABBR: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class PubmedConnector(SourceConnector):
    provides_canonical_id = False

    def __init__(
        self,
        *,
        client: RateLimitedClient,
        search_term: str,
        base_url: str = _EUTILS_BASE,
        api_key: str | None = None,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = client
        self._search_term = search_term
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep: Callable[[float], None] = sleep or time.sleep
        self._max_retries = max_retries

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        start = cursor.strftime("%Y/%m/%d")
        end = self._now().strftime("%Y/%m/%d")
        retrieved_at = self._now()

        retstart = 0
        while True:
            pmids = self._esearch(start, end, retstart)
            if not pmids:
                break
            yield from self._efetch(pmids, retrieved_at)
            if len(pmids) < _RETMAX:
                break
            retstart += _RETMAX

    def _esearch(self, start: str, end: str, retstart: int) -> list[str]:
        params: dict[str, str] = {
            "db": "pubmed",
            "term": self._search_term,
            "retmax": str(_RETMAX),
            "retstart": str(retstart),
            "retmode": "json",
            "datetype": "edat",
            "mindate": start,
            "maxdate": end,
        }
        if self._api_key:
            params["api_key"] = self._api_key
        url = f"{self._base_url}/esearch.fcgi"
        data = self._get_json(url, params)
        result = data.get("esearchresult", {})
        idlist = result.get("idlist", [])
        return cast(list[str], idlist)

    def _efetch(self, pmids: list[str], retrieved_at: datetime) -> Iterator[RawDocument]:
        params: dict[str, str] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "xml",
            "retmode": "xml",
        }
        if self._api_key:
            params["api_key"] = self._api_key
        url = f"{self._base_url}/efetch.fcgi"
        xml_text = self._get_text(url, params)
        root = ElementTree.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            doc = self._map_article(article, retrieved_at)
            if doc is not None:
                yield doc

    def _map_article(
        self, article: ElementTree.Element, retrieved_at: datetime
    ) -> RawDocument | None:
        pmid_el = article.find(".//PMID")
        if pmid_el is None or not pmid_el.text:
            return None
        pmid = pmid_el.text.strip()

        title_el = article.find(".//ArticleTitle")
        title = (title_el.text or "") if title_el is not None else ""

        abstract_el = article.find(".//AbstractText")
        abstract = (abstract_el.text or "") if abstract_el is not None else ""

        raw_content = f"{title}\n\n{abstract}"
        sha = hashlib.sha256(raw_content.encode()).hexdigest()

        doi: str | None = None
        for aid in article.findall(".//ArticleId"):
            if aid.get("IdType") == "doi" and aid.text:
                doi = aid.text.strip()
                break

        published_date = self._parse_date(article)

        return RawDocument(
            schema_version="1.0",
            external_id=f"pubmed:{pmid}",
            canonical_id=f"doi:{doi}" if doi else None,
            source_type="pubmed",
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            published_date=published_date,
            raw_content=raw_content,
            content_sha256=sha,
            retrieved_at=retrieved_at,
        )

    def _parse_date(self, article: ElementTree.Element) -> datetime:
        for path in [".//ArticleDate[@DateType='Electronic']", ".//JournalIssue/PubDate"]:
            el = article.find(path)
            if el is not None:
                year_el = el.find("Year")
                month_el = el.find("Month")
                day_el = el.find("Day")
                if year_el is not None and year_el.text:
                    year = int(year_el.text)
                    raw_month = month_el.text if month_el is not None and month_el.text else "1"
                    month = self._parse_month(raw_month)
                    day = int(day_el.text) if day_el is not None and day_el.text else 1
                    return datetime(year, month, day, tzinfo=UTC)
        return self._now()

    @staticmethod
    def _parse_month(value: str) -> int:
        try:
            return int(value)
        except ValueError:
            return _MONTH_ABBR.get(value.lower()[:3], 1)

    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        last_resp: httpx.Response | None = None
        for _ in range(self._max_retries):
            last_resp = self._client.get(url, params=params)
            if last_resp.status_code == 429:
                backoff = float(last_resp.headers.get("Retry-After", str(_DEFAULT_BACKOFF)))
                self._sleep(backoff)
                continue
            last_resp.raise_for_status()
            return cast(dict[str, Any], last_resp.json())
        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError(f"No retries configured for {url}")

    def _get_text(self, url: str, params: dict[str, str]) -> str:
        last_resp: httpx.Response | None = None
        for _ in range(self._max_retries):
            last_resp = self._client.get(url, params=params)
            if last_resp.status_code == 429:
                backoff = float(last_resp.headers.get("Retry-After", str(_DEFAULT_BACKOFF)))
                self._sleep(backoff)
                continue
            last_resp.raise_for_status()
            return last_resp.text
        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError(f"No retries configured for {url}")
