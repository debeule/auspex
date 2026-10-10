"""Which SEC filer a 13F holding is in, by issuer name.

13F reports a CUSIP and a free-text issuer name; nothing in the filing gives the issuer's CIK.
Every operating company in SEC's submissions archive is indexed by its current and former
conformed names, and a holding resolves when its normalized name matches exactly one company.
Names shared by several companies resolve to none, so a match is never a guess.
"""

import json
import re
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

_MAIN_FILE = re.compile(r"CIK(\d{10})\.json")
# Operating companies list `sic`, `name` and `formerNames` before their (possibly
# multi-megabyte) filing history, so the head of each file usually holds everything needed.
_HEADER_BYTES = 16384
_SIC_FIELD = re.compile(r'"sic"\s*:\s*"(\d+)"')
_NAME_FIELD = re.compile(r'"name"\s*:\s*("(?:[^"\\]|\\.)*")')
_FORMER_NAMES = re.compile(r'"formerNames"\s*:\s*(\[[^\[\]]*\])')

_SUFFIXES = frozenset({
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC",
    "LLC", "LP", "NV", "SA", "AG", "SE", "AB", "AS", "ASA", "THE", "NEW", "DE", "DEL", "COM",
})
# Spellings 13F filers abbreviate in different ways, mapped to one form.
_CANONICAL = {
    "PHARMACEUTICAL": "PHARM", "PHARMACEUTICALS": "PHARM", "PHARMACEUTICA": "PHARM",
    "PHARMA": "PHARM", "PHARMS": "PHARM",
    "THERAPEUTICS": "THERAP", "THERAPEUTIC": "THERAP", "THERAPEUTCS": "THERAP",
    "THERAPTCS": "THERAP", "THERAPEUT": "THERAP",
    "BIOSCIENCES": "BIOSCI", "BIOSCIENCE": "BIOSCI",
    "TECHNOLOGIES": "TECH", "TECHNOLOGY": "TECH",
    "LABORATORIES": "LAB", "LABS": "LAB",
    "INTERNATIONAL": "INTL", "HOLDINGS": "HLDGS", "HLDG": "HLDGS",
    "GROUP": "GRP", "MEDICAL": "MED", "SYSTEMS": "SYS",
}
_STATE_TAG = re.compile(r"/[A-Z]{2,3}/?\s*$")


@dataclass(frozen=True)
class Issuer:
    cik: str
    sic: str
    names: tuple[str, ...]


def normalize_name(name: str) -> str:
    text = _STATE_TAG.sub("", name.upper().strip()).replace("&", " AND ")
    tokens = [_CANONICAL.get(t, t) for t in re.sub(r"[^A-Z0-9]+", " ", text).split()]
    while tokens and tokens[-1] in _SUFFIXES:
        tokens.pop()
    while tokens and tokens[0] == "THE":
        tokens.pop(0)
    return " ".join(tokens)


class IssuerDirectory:
    def __init__(self, issuers: Iterable[Issuer]) -> None:
        by_name: dict[str, set[str]] = defaultdict(set)
        self._sic: dict[str, str] = {}
        for issuer in issuers:
            self._sic[issuer.cik] = issuer.sic
            for name in issuer.names:
                if key := normalize_name(name):
                    by_name[key].add(issuer.cik)
        self._by_name = {k: next(iter(v)) for k, v in by_name.items() if len(v) == 1}

    def resolve(self, name: str) -> str | None:
        """The CIK of the one company with this name, or None if none or several have it."""
        return self._by_name.get(normalize_name(name))

    def sic(self, cik: str) -> str | None:
        return self._sic.get(cik)


def read_issuer_directory(archive: Path) -> IssuerDirectory:
    return IssuerDirectory(_issuers(archive))


def _issuers(archive: Path) -> Iterator[Issuer]:
    """Every filer in a submissions archive that has a SIC code (operating companies; funds
    and individuals have none), with its current and former names."""
    with zipfile.ZipFile(archive) as zf:
        for entry in zf.namelist():
            m = _MAIN_FILE.fullmatch(entry)
            if m is None:
                continue
            with zf.open(entry) as fh:
                head = fh.read(_HEADER_BYTES).decode("utf-8", errors="replace")
            sic = _SIC_FIELD.search(head)
            if sic is None:
                continue
            name = _NAME_FIELD.search(head)
            former = _FORMER_NAMES.search(head)
            if name is None or (former is None and '"filings"' not in head):
                data = json.loads(zf.read(entry))
                names = [str(data.get("name") or "")] + [
                    str(f.get("name") or "") for f in data.get("formerNames") or []
                ]
            else:
                names = [json.loads(name.group(1))] + [
                    str(f.get("name") or "") for f in (json.loads(former.group(1)) if former else [])
                ]
            yield Issuer(m.group(1), sic.group(1), tuple(n for n in names if n))
