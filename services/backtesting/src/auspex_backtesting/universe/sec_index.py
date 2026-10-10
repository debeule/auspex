"""Tickers of companies that left the exchange before inline XBRL, from their filing indexes.

SEC keeps no ticker for an inactive filer, and before 2019 a report's primary document is
named by the filing agent, not the issuer. The XBRL instance filed with each 10-K and 10-Q
from 2009-2011 onward is named `<symbol>-<yyyymmdd>.xml`, but only the filing's index page
lists it, so this costs one request per company: the few hundred delisted names in the window,
not the whole filer population.
"""

import logging
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date

from auspex_backtesting.universe.listing import instance_lookup_filing
from auspex_backtesting.universe.model import CompanyRecord

log = logging.getLogger("auspex_backtesting.universe")

# SEC allows 10 requests per second across all of its hosts and blocks the address for about
# ten minutes beyond that; retrying during a block extends it. 5 per second leaves room for EDGAR
# ingestion's 4 when both run at once from different containers.
_REQUEST_INTERVAL_S = 0.2
_BLOCKED_STATUSES = frozenset({403, 429})

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_INSTANCE_TYPE = re.compile(r">\s*EX-101\.INS\s*<", re.IGNORECASE)
_LINKED_XML = re.compile(r"<a\s[^>]*>\s*([^<>\s]+\.xml)\s*</a>", re.IGNORECASE)


def instance_document(index_html: str) -> str | None:
    """The XBRL instance's file name from a `-index.htm` page, or None if it lists none."""
    for row in _ROW.findall(index_html):
        if _INSTANCE_TYPE.search(row) and (link := _LINKED_XML.search(row)):
            return link.group(1)
    return None


def _fetch(url: str, user_agent: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=60) as resp:
        body: bytes = resp.read()
    return body.decode("utf-8", errors="replace")


class InstanceDocuments:
    def __init__(
        self,
        archives_url: str,
        user_agent: str,
        *,
        fetch: Callable[[str, str], str] = _fetch,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._archives_url = archives_url.rstrip("/")
        self._user_agent = user_agent
        self._fetch = fetch
        self._sleep = sleep

    def attach(
        self, records: Sequence[CompanyRecord], allowed_exchanges: frozenset[str], since: date
    ) -> list[CompanyRecord]:
        """`records` in order, each unresolved company listed on or after `since` with the
        instance document name set on its latest XBRL report. Lookups that fail leave the
        company as it was; a refusal from SEC ends the lookups for this run."""
        result: list[CompanyRecord] = []
        requested = found = 0
        blocked = False
        for record in records:
            report = None if blocked else instance_lookup_filing(record, allowed_exchanges, since)
            if report is None:
                result.append(record)
                continue
            if requested:
                self._sleep(_REQUEST_INTERVAL_S)
            requested += 1
            accession = report.accession
            url = (
                f"{self._archives_url}/{int(record.cik)}/"
                f"{accession.replace('-', '')}/{accession}-index.htm"
            )
            try:
                name = instance_document(self._fetch(url, self._user_agent))
            except urllib.error.HTTPError as exc:
                if exc.code in _BLOCKED_STATUSES:
                    log.warning("SEC refused %s (HTTP %d): no further index lookups", url, exc.code)
                    blocked = True
                else:
                    log.info("no filing index at %s (HTTP %d)", url, exc.code)
                result.append(record)
                continue
            except OSError as exc:
                log.info("filing index %s unreachable: %s", url, exc)
                result.append(record)
                continue
            if name is None:
                result.append(record)
                continue
            found += 1
            filings = tuple(
                replace(f, instance_document=name) if f is report else f for f in record.filings
            )
            result.append(replace(record, filings=filings))
        log.info("filing index lookups: %d requested, %d instance documents found", requested, found)
        return result
