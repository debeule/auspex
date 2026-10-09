"""Deterministic phrase rules: document text to sentences, dates with their precision, PDUFA
sentences, and the application numbers and product names a sentence names."""

import calendar
import itertools
import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser

from auspex_backtesting.catalysts.model import Precision

_BLOCK_TAGS = frozenset({
    "p", "div", "br", "tr", "li", "ul", "ol", "table", "h1", "h2", "h3", "h4", "h5", "h6",
    "title", "center", "blockquote",
})
_HTML_HINT = re.compile(r"<\s*(?:html|body|p|div|br|font|table)\b", re.IGNORECASE)


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        # Line breaks inside HTML text are wrapping, not structure.
        self.parts.append(data.replace("\r", " ").replace("\n", " "))


def paragraphs(document: str) -> list[str]:
    """The document's paragraphs as plain text with whitespace collapsed. HTML is split at
    block elements; plain text at blank lines."""
    if _HTML_HINT.search(document):
        parser = _TextParser()
        parser.feed(document)
        parser.close()
        blocks = "".join(parser.parts).split("\n")
    else:
        blocks = re.split(r"\n\s*\n", document)
    result = []
    for block in blocks:
        text = " ".join(block.replace("\xa0", " ").split())
        if text:
            result.append(text)
    return result


_SENTENCE_END = re.compile(
    r"(?<=[.!?])"
    # Initials and the abbreviations press releases use mid-sentence.
    r"(?<!\b[A-Z]\.)(?<!Inc\.)(?<!Corp\.)(?<!Ltd\.)(?<!No\.)(?<!Co\.)(?<!Dr\.)(?<!vs\.)"
    r"\s+(?=[A-Z\"“(])"
)


def sentences(document: str) -> list[str]:
    return [s for p in paragraphs(document) for s in _SENTENCE_END.split(p) if s]


@dataclass(frozen=True)
class DateMention:
    start: int
    end: int
    precision: Precision
    period_start: date
    period_end: date


_MONTH_NUMBERS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH = (
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November"
    r"|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?"
)
_YEAR = r"(?P<year>(?:19|20)\d{2})"
_ORDINAL = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4}
_YEAR_QUALIFIER = r"(?:of\s+)?(?:(?:the\s+)?calendar\s+(?:year\s+)?|fiscal\s+(?:year\s+)?)?"

# Most specific first: a span claimed by a day is not read again as a month.
_DATE_PATTERNS: list[tuple[Precision, re.Pattern[str]]] = [
    ("day", re.compile(rf"\b{_MONTH}\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?,?\s+{_YEAR}\b")),
    ("day", re.compile(rf"\b(?P<day>\d{{1,2}})\s+{_MONTH},?\s+{_YEAR}\b")),
    ("month", re.compile(rf"\b{_MONTH},?\s+(?:of\s+)?{_YEAR}\b")),
    ("quarter", re.compile(
        rf"\b(?P<n>first|second|third|fourth|1st|2nd|3rd|4th)[\s-]+(?:calendar\s+)?quarter\s+"
        rf"{_YEAR_QUALIFIER}{_YEAR}\b", re.IGNORECASE)),
    ("quarter", re.compile(rf"\b(?:Q(?P<n>[1-4])|(?P<m>[1-4])Q)\s*(?:of\s+)?'?{_YEAR}\b")),
    ("half", re.compile(
        rf"\b(?P<n>first|second|1st|2nd)[\s-]+half\s+{_YEAR_QUALIFIER}{_YEAR}\b", re.IGNORECASE)),
    ("half", re.compile(rf"\b(?:H(?P<n>[12])|(?P<m>[12])H)\s*(?:of\s+)?'?{_YEAR}\b")),
]


def _period(precision: Precision, match: re.Match[str]) -> tuple[date, date] | None:
    groups = match.groupdict()
    year = int(groups["year"])
    if precision in ("day", "month"):
        month = _MONTH_NUMBERS[groups["month"][:3].lower()]
        last = calendar.monthrange(year, month)[1]
        if precision == "month":
            return date(year, month, 1), date(year, month, last)
        day = int(groups["day"])
        if not 1 <= day <= last:
            return None
        return date(year, month, day), date(year, month, day)
    raw = groups.get("n") or groups.get("m") or ""
    n = _ORDINAL[raw.lower()] if raw.lower() in _ORDINAL else int(raw)
    months_per_part = 3 if precision == "quarter" else 6
    first = (n - 1) * months_per_part + 1
    final = first + months_per_part - 1
    return date(year, first, 1), date(year, final, calendar.monthrange(year, final)[1])


def date_mentions(text: str) -> list[DateMention]:
    """Every date expression in `text`, in order, each with the precision it was written at."""
    found: list[DateMention] = []
    for precision, pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            if any(match.start() < m.end and m.start < match.end() for m in found):
                continue
            period = _period(precision, match)
            if period is not None:
                found.append(DateMention(match.start(), match.end(), precision, *period))
    return sorted(found, key=lambda m: m.start)


_PDUFA_TRIGGER = re.compile(r"\bPDUFA\b|target\s+action\s+date|goal\s+date", re.IGNORECASE)
# "from October 15, 2024 to January 15, 2025": the date after "to" is the current one.
_REVISION_LINK = re.compile(r"\s*,?\s*(?:to|until)\s+(?:a\s+(?:new\s+)?(?:date\s+of\s+)?)?", re.IGNORECASE)
# "a March 15, 2027 PDUFA date": a date written just before the phrase.
_LEADING_DATE_GAP = 40


def pdufa_date(sentence: str) -> DateMention | None:
    """The PDUFA date a sentence states, or None if it names no PDUFA phrase or no date for
    it. The first date after the phrase is taken, moved on along "from X to Y"; failing that,
    a date written immediately before the phrase."""
    trigger = _PDUFA_TRIGGER.search(sentence)
    if trigger is None:
        return None
    mentions = date_mentions(sentence)
    after = [m for m in mentions if m.start >= trigger.end()]
    if after:
        chosen = after[0]
        for current, following in itertools.pairwise(after):
            if current is chosen and _REVISION_LINK.fullmatch(sentence[current.end:following.start]):
                chosen = following
        return chosen
    before = [
        m for m in mentions
        if m.end <= trigger.start() and trigger.start() - m.end <= _LEADING_DATE_GAP
    ]
    return before[-1] if before else None


_APPLICATION = re.compile(r"\b(s?NDA|s?BLA)\)?\s*(?:No\.?\s*)?(\d{6})\b")
_CODE_NAME = re.compile(r"\b([A-Z]{2,6})([- ]?)(\d{3,6}[A-Za-z]?)\b")
_NOT_CODE_PREFIXES = frozenset({
    "NDA", "SNDA", "BLA", "SBLA", "MAA", "IND", "PDUFA", "FDA", "CFR", "USC", "ITEM", "FORM",
    "NYSE", "CIK", "EST", "EDT", "UTC", "ET",
})
_BRAND = re.compile(r"\b([A-Z][A-Za-z0-9-]{2,})\s*(?:®|™|\(R\)|\(TM\))")
# INN stems that rarely end ordinary English words.
_GENERIC = re.compile(
    r"\b([a-z]{3,}(?:mab|nib|ciclib|parib|lisib|glutide|leucel|vec|vir|sartan|gliflozin|olone"
    r"|tecan|zomib|platin|cogene|mersen|siran|rsen))\b",
    re.IGNORECASE,
)
_YEARLIKE = re.compile(r"(?:19|20)\d{2}")


def normalize_alias(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def product_aliases(text: str) -> tuple[str, ...]:
    """Normalized application numbers, code names, trademarked brands and INN generic names
    in `text`, in that order of preference, without repeats."""
    found: list[str] = []
    for kind, number in _APPLICATION.findall(text):
        found.append(normalize_alias(f"{kind.lower().removeprefix('s')}{number}"))
    for prefix, separator, number in _CODE_NAME.findall(text):
        if prefix.upper() in _NOT_CODE_PREFIXES:
            continue
        if separator == " " and _YEARLIKE.fullmatch(number):
            continue
        found.append(normalize_alias(prefix + number))
    found.extend(normalize_alias(b) for b in _BRAND.findall(text))
    found.extend(normalize_alias(g) for g in _GENERIC.findall(text))
    return tuple(dict.fromkeys(a for a in found if a))


@dataclass(frozen=True)
class PdufaHit:
    sentence: str
    when: DateMention
    aliases: tuple[str, ...]


# A PDUFA sentence often names the product only in the sentence before it
# ("... accepted its NDA for X. The FDA has assigned a PDUFA date of ...").
_ALIAS_LOOKBACK = 3


def pdufa_hits(document: str) -> list[PdufaHit]:
    """One hit per sentence that states a PDUFA date, with the product it refers to."""
    text = sentences(document)
    hits = []
    for i, sentence in enumerate(text):
        when = pdufa_date(sentence)
        if when is None:
            continue
        aliases = product_aliases(sentence)
        for earlier in reversed(text[max(0, i - _ALIAS_LOOKBACK):i]):
            if aliases:
                break
            aliases = product_aliases(earlier)
        hits.append(PdufaHit(sentence, when, aliases))
    return hits


_LEGAL_SUFFIXES = frozenset({
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "llc",
    "lp", "sa", "ag", "nv", "se", "holdings", "holding", "group", "the", "and",
})


def name_tokens(name: str) -> tuple[str, ...]:
    """A company name as comparable tokens: lowercased, punctuation and legal suffixes
    dropped, so "ACME BIO, INC." and "Acme Bio Inc" compare equal."""
    words = re.sub(r"[^a-z0-9]+", " ", name.lower().replace("&", " and ")).split()
    return tuple(w for w in words if w not in _LEGAL_SUFFIXES)
