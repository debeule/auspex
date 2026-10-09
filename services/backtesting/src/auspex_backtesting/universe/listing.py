"""Exchange listing spans and tickers derived from a filer's EDGAR history.

SEC publishes only a filer's current exchange and ticker, so the history comes from filings:
an exchange registration (`8-A12B`, or `10-12B` for a spin-off) opens a span, and the first
delisting notice (`25-NSE` from the exchange, `25` from the issuer) or deregistration
(`15-12B`, `15-12G`) closes it.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from auspex_backtesting.universe.model import (
    CompanyRecord,
    ExitReason,
    Filing,
    ListingSpan,
    TickerSource,
)

_REGISTRATION_FORMS = frozenset({"8-A12B", "10-12B"})
_DELISTING_FORMS = frozenset({"25-NSE", "25"})
# A 15-12G ends a 12(g) registration, which over-the-counter issuers also hold, so on its own it
# is no evidence the company was ever exchange-listed.
_EXCHANGE_DEREGISTRATION_FORMS = frozenset({"15-12B"})
_DEREGISTRATION_FORMS = frozenset({"15-12B", "15-12G"})

# An acquired company files an 8-K for the change in control (item 5.01) around the closing;
# the exchange's delisting notice can come shortly before or after it.
_CHANGE_OF_CONTROL_ITEM = "5.01"
_CHANGE_OF_CONTROL_BEFORE = timedelta(days=30)
_CHANGE_OF_CONTROL_AFTER = timedelta(days=10)

# Inline XBRL reports (from 2019) are named `<prefix>-<yyyymmdd>.htm`, and earlier XBRL instance
# documents `<prefix>-<yyyymmdd>.xml`; filers almost always use their trading symbol as the prefix.
_TICKER_DOCUMENT = re.compile(r"^([a-z]{1,5})-\d{8}\.htm$")
_TICKER_INSTANCE = re.compile(r"^([a-z]{1,5})-\d{8}\.xml$")
_TICKER_DOCUMENT_FORMS = frozenset({"10-K", "10-Q", "20-F", "40-F", "10-KT", "10-QT"})


@dataclass(frozen=True)
class ListingHistory:
    spans: tuple[ListingSpan, ...]
    ticker: str | None
    ticker_source: TickerSource

    @classmethod
    def from_record(cls, record: CompanyRecord, allowed_exchanges: frozenset[str]) -> ListingHistory:
        ticker, source = _resolve_ticker(record)
        return cls(_spans(record, allowed_exchanges), ticker, source)

    def span_on(self, d: date) -> ListingSpan | None:
        """The span the company was listed in on `d`: registered before `d`, and not yet delisted
        before `d`. A notice filed on `d` itself leaves the company listed that day."""
        for span in self.spans:
            if span.entered_on < d and (span.exited_on is None or span.exited_on >= d):
                return span
        return None


def _spans(record: CompanyRecord, allowed_exchanges: frozenset[str]) -> tuple[ListingSpan, ...]:
    filings = sorted(record.filings, key=lambda f: (f.filed, f.form))
    if not filings:
        return ()
    first_filed, last_filed = filings[0].filed, filings[-1].filed
    currently_listed = any(e in allowed_exchanges for e in record.exchanges)

    spans: list[ListingSpan] = []
    open_since: date | None = None
    for f in filings:
        if f.form in _REGISTRATION_FORMS:
            if open_since is None:
                open_since = f.filed
        elif f.form in _DELISTING_FORMS or f.form in _DEREGISTRATION_FORMS:
            if open_since is not None:
                spans.append(_closed(open_since, f, filings))
                open_since = None
            elif not spans and (f.form in _DELISTING_FORMS or f.form in _EXCHANGE_DEREGISTRATION_FORMS):
                # Listed before EDGAR: the exchange registration predates the electronic record.
                spans.append(_closed(first_filed, f, filings))

    if open_since is not None:
        if currently_listed:
            spans.append(ListingSpan(open_since, None, None))
        elif not record.exchanges and last_filed > open_since:
            # Stopped filing without a delisting notice on record.
            spans.append(ListingSpan(open_since, last_filed, _reason(last_filed, "deregistered", filings)))
        # A company now quoted only off-exchange without a notice on record is left out: when it
        # left the exchange is unknown.
    elif currently_listed:
        if spans:
            # Still listed after its last notice, so that notice was for another class of
            # security (warrants, notes) and the common stock never left.
            last = spans.pop()
            spans.append(ListingSpan(last.entered_on, None, None))
        else:
            spans.append(ListingSpan(first_filed, None, None))
    return tuple(spans)


def _closed(entered_on: date, notice: Filing, filings: list[Filing]) -> ListingSpan:
    default: ExitReason = "delisted" if notice.form in _DELISTING_FORMS else "deregistered"
    return ListingSpan(entered_on, notice.filed, _reason(notice.filed, default, filings))


def _reason(exited_on: date, default: ExitReason, filings: list[Filing]) -> ExitReason:
    for f in filings:
        if (
            f.form == "8-K"
            and _CHANGE_OF_CONTROL_ITEM in f.items
            and exited_on - _CHANGE_OF_CONTROL_BEFORE <= f.filed <= exited_on + _CHANGE_OF_CONTROL_AFTER
        ):
            return "acquired"
    return default


def _resolve_ticker(record: CompanyRecord) -> tuple[str | None, TickerSource]:
    """SEC's current ticker when there is one: price vendors file a renamed issuer's whole
    history under its current symbol. A delisted filer has none, so its last report's document
    prefix stands in."""
    if record.tickers:
        return record.tickers[0], "current"
    named = [
        (f.filed, m.group(1))
        for f in record.filings
        if f.form in _TICKER_DOCUMENT_FORMS
        and (
            (m := _TICKER_DOCUMENT.match(f.primary_document))
            or (m := _TICKER_INSTANCE.match(f.instance_document))
        )
    ]
    if named:
        return max(named)[1].upper(), "filing"
    return None, "unresolved"


def instance_lookup_filing(
    record: CompanyRecord, allowed_exchanges: frozenset[str], since: date
) -> Filing | None:
    """The report whose filing index may name the XBRL instance, for a company that was listed
    on or after `since` and whose ticker neither SEC nor an inline XBRL document name gives:
    its latest XBRL periodic report. None when no lookup is needed or none can help."""
    history = ListingHistory.from_record(record, allowed_exchanges)
    if history.ticker is not None:
        return None
    if not any(s.exited_on is None or s.exited_on >= since for s in history.spans):
        return None
    reports = [
        f for f in record.filings if f.form in _TICKER_DOCUMENT_FORMS and f.xbrl and f.accession
    ]
    return max(reports, key=lambda f: f.filed) if reports else None
