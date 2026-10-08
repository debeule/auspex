"""SEC's nightly bulk archives: filer submissions and XBRL company facts.

Two downloads replace tens of thousands of per-company requests against SEC's 10 requests per
second limit. Both archives hold one `CIK##########.json` per filer; filers with a long history
spill older filings into `CIK##########-submissions-NNN.json`.
"""

import json
import re
import shutil
import urllib.request
import zipfile
from collections import defaultdict
from collections.abc import Collection, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from auspex_backtesting.universe.model import CompanyRecord, Filing, ShareCount

_MAIN_FILE = re.compile(r"CIK(\d{10})\.json")
_OVERFLOW_FILE = re.compile(r"CIK(\d{10})-submissions-\d+\.json")
# `sic` sits among the first few fields of a submissions file, so the header decides whether
# the rest of a (possibly multi-megabyte) file needs parsing.
_SIC_FIELD = re.compile(rb'"sic"\s*:\s*"(\d*)"')
_HEADER_BYTES = 4096
_SHARES_CONCEPT = ("dei", "EntityCommonStockSharesOutstanding")


def download(url: str, dest: Path, user_agent: str) -> Path:
    """Streams `url` to `dest`. SEC refuses requests without a descriptive User-Agent."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=600) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)
    return dest


def read_submissions(archive: Path, sic_codes: Collection[str]) -> list[CompanyRecord]:
    """Every filer whose current SIC code is in `sic_codes`, with its full filing history."""
    with zipfile.ZipFile(archive) as zf:
        overflow: dict[str, list[str]] = defaultdict(list)
        main: list[tuple[str, str]] = []
        for name in zf.namelist():
            if m := _MAIN_FILE.fullmatch(name):
                main.append((m.group(1), name))
            elif m := _OVERFLOW_FILE.fullmatch(name):
                overflow[m.group(1)].append(name)

        records = []
        for cik, name in sorted(main):
            with zf.open(name) as fh:
                header = fh.read(_HEADER_BYTES)
            sic = _SIC_FIELD.search(header)
            if sic is None or sic.group(1).decode() not in sic_codes:
                continue
            data = json.loads(zf.read(name))
            filings = _filings(data.get("filings", {}).get("recent", {}))
            for extra in sorted(overflow.get(cik, [])):
                filings.extend(_filings(json.loads(zf.read(extra))))
            records.append(CompanyRecord(
                cik=cik,
                name=str(data.get("name") or ""),
                sic=str(data.get("sic") or ""),
                exchanges=tuple(str(e) for e in data.get("exchanges") or [] if e),
                tickers=tuple(str(t) for t in data.get("tickers") or [] if t),
                filings=tuple(filings),
            ))
    return records


def read_share_counts(archive: Path, ciks: Collection[str]) -> Mapping[str, list[ShareCount]]:
    """Cover-page shares outstanding (`dei:EntityCommonStockSharesOutstanding`) for `ciks`."""
    counts: dict[str, list[ShareCount]] = {}
    with zipfile.ZipFile(archive) as zf:
        present = set(zf.namelist())
        for cik in sorted(ciks):
            name = f"CIK{cik}.json"
            if name not in present:
                continue
            facts = json.loads(zf.read(name)).get("facts", {})
            namespace, concept = _SHARES_CONCEPT
            units = facts.get(namespace, {}).get(concept, {}).get("units", {}).get("shares", [])
            counts[cik] = sorted({
                ShareCount(float(u["val"]), date.fromisoformat(u["end"]), date.fromisoformat(u["filed"]))
                for u in units
                if u.get("val") is not None and u.get("end") and u.get("filed")
            }, key=lambda s: (s.filed, s.end, s.value))
    return counts


def _filings(columns: Mapping[str, Any]) -> list[Filing]:
    forms = columns.get("form", [])
    dates = columns.get("filingDate", [])
    items = columns.get("items", [""] * len(forms))
    documents = columns.get("primaryDocument", [""] * len(forms))
    return [
        Filing(
            form=str(form),
            filed=date.fromisoformat(filed),
            items=tuple(i.strip() for i in str(item or "").split(",") if i.strip()),
            primary_document=str(document or ""),
        )
        for form, filed, item, document in zip(forms, dates, items, documents, strict=True)
    ]
