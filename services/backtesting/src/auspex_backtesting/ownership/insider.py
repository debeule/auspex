"""Insider transactions (Forms 4 and 5) and issuer offerings, as filed.

Stored under `ownership/` in the prices bucket:

| Key | Source | Written |
|---|---|---|
| `insider/{yyyy}q{q}.parquet` | SEC's quarterly insider transactions data set | once |
| `insider/daily/{yyyy-mm-dd}.parquet` | that day's form index and each Form 4's XML | once |
| `offerings/{yyyy}q{q}.parquet` | `424B4` / `424B5` rows of the quarterly form index | once |
| `offerings/daily/{yyyy-mm-dd}.parquet` | the same rows of that day's form index | once |

The quarterly data set appears weeks after its quarter ends; the daily files cover the gap and
stay stored when it arrives. Readers prefer the data set (`InsiderPanel`).

Only original Forms 4 and 5 are kept, not their amendments: an amendment repeats the
transactions it corrects, so counting both would double them. Non-derivative transactions only;
a filing by several reporting owners (a fund and its affiliates) is one set of transactions,
attributed to the lowest owner CIK with the union of their roles.
"""

import logging
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from auspex_backtesting.ownership.datasets import (
    DatasetFile,
    eastern_to_utc,
    latest_acceptance,
    parse_sec_date,
    quarter_of,
)
from auspex_backtesting.ownership.form13f import cik10, read_table
from auspex_backtesting.ownership.sec_client import SecFetcher, SecNotFoundError
from auspex_backtesting.ownership.store import OwnershipStore

log = logging.getLogger("auspex_backtesting.ownership")

INSIDER_COLUMNS = [
    "accession_number", "issuer_cik", "owner_cik", "role", "transaction_code",
    "acquired_disposed", "shares", "price", "transaction_date", "filing_date",
    "filing_accepted_at", "is_10b5_1",
]
OFFERING_COLUMNS = ["issuer_cik", "form", "filing_date", "accession_number"]
OFFERING_FORMS = frozenset({"424B4", "424B5"})
_TRANSACTION_FORMS = frozenset({"4", "5"})
_TRUE = frozenset({"1", "TRUE", "Y", "YES"})
_PLAN = re.compile(r"10b\W?5\W?1", re.IGNORECASE)
_FOOTNOTE_ID = re.compile(r"F\d+", re.IGNORECASE)
_ROLES = {
    "director": "director", "officer": "officer", "tenpercentowner": "ten_percent_owner",
    "other": "other",
}


@dataclass(frozen=True)
class IndexEntry:
    form: str
    company: str
    cik: str
    filing_date: date
    path: str

    @property
    def accession_number(self) -> str:
        return self.path.rsplit("/", 1)[-1].removesuffix(".txt")


def parse_form_index(text: str) -> list[IndexEntry]:
    """Rows of an EDGAR `form.idx` (daily or quarterly). Columns are fixed-width and form
    types and company names contain spaces, so fields are cut at the header's positions."""
    lines = text.splitlines()
    header_at = next((i for i, line in enumerate(lines) if line.startswith("Form Type")), None)
    if header_at is None:
        raise ValueError("not an EDGAR form index: no 'Form Type' header")
    header = lines[header_at]
    starts = [header.index(h) for h in ("Form Type", "Company Name", "CIK", "Date Filed", "File Name")]
    entries = []
    for line in lines[header_at + 1:]:
        if not line.strip() or set(line.strip()) == {"-"}:
            continue
        form, company, cik, filed, path = (
            line[a:b].strip() for a, b in zip(starts, [*starts[1:], None], strict=True)
        )
        filed_on = (
            datetime.strptime(filed, "%Y%m%d").replace(tzinfo=UTC).date() if "-" not in filed
            else date.fromisoformat(filed)
        )
        entries.append(IndexEntry(form, company, cik10(cik), filed_on, path))
    return entries


def offerings_from_index(entries: Iterable[IndexEntry], universe: Collection[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"issuer_cik": e.cik, "form": e.form, "filing_date": e.filing_date,
             "accession_number": e.accession_number}
            for e in entries if e.form in OFFERING_FORMS and e.cik in universe
        ],
        columns=OFFERING_COLUMNS,
    ).drop_duplicates("accession_number")


def _role(flags: Iterable[str]) -> str:
    return ",".join(sorted({_ROLES[f] for f in flags if f in _ROLES}))


def _number(text: object) -> float | None:
    try:
        return float(str(text).strip())
    except ValueError:
        return None


def parse_insider_dataset(archive: Path, universe: Collection[str]) -> pd.DataFrame:
    """Non-derivative transactions in original Forms 4 and 5 of universe issuers."""
    with zipfile.ZipFile(archive) as zf:
        submissions = read_table(zf, "SUBMISSION.tsv")
        owners = read_table(zf, "REPORTINGOWNER.tsv")
        transactions = read_table(zf, "NONDERIV_TRANS.tsv")
        footnotes = read_table(zf, "FOOTNOTES.tsv")
    if submissions.empty or transactions.empty:
        return pd.DataFrame(columns=INSIDER_COLUMNS)

    submissions = submissions.assign(issuer=submissions["ISSUERCIK"].map(cik10))
    submissions = submissions[
        submissions["DOCUMENT_TYPE"].str.strip().isin(_TRANSACTION_FORMS)
        & submissions["issuer"].isin(universe)
    ]
    filings = {str(r["ACCESSION_NUMBER"]).strip(): r for r in submissions.to_dict("records")}

    owner_of: dict[str, tuple[str, str]] = {}
    for accession, group in owners.groupby(owners["ACCESSION_NUMBER"].str.strip()):
        if accession not in filings:
            continue
        flags = {
            flag.strip().lower().replace(" ", "")
            for value in group["RPTOWNER_RELATIONSHIP"]
            for flag in str(value).split(",")
        }
        owner_of[str(accession)] = (min(cik10(c) for c in group["RPTOWNERCIK"]), _role(flags))

    plan_notes = {
        (str(r["ACCESSION_NUMBER"]).strip(), str(r["FOOTNOTE_ID"]).strip().upper())
        for r in footnotes.to_dict("records") if _PLAN.search(str(r["FOOTNOTE_TXT"]))
    } if not footnotes.empty else set()
    footnote_columns = [c for c in transactions.columns if c.upper().endswith("_FN")]

    rows = []
    for t in transactions.to_dict("records"):
        accession = str(t["ACCESSION_NUMBER"]).strip()
        filing = filings.get(accession)
        if filing is None:
            continue
        referenced = {
            note.upper() for c in footnote_columns for note in _FOOTNOTE_ID.findall(str(t[c]))
        }
        filed = parse_sec_date(str(filing["FILING_DATE"]))
        owner, role = owner_of.get(accession, ("", ""))
        rows.append({
            "accession_number": accession,
            "issuer_cik": filing["issuer"],
            "owner_cik": owner,
            "role": role,
            "transaction_code": str(t.get("TRANS_CODE", "")).strip().upper(),
            "acquired_disposed": str(t.get("TRANS_ACQUIRED_DISP_CD", "")).strip().upper(),
            "shares": _number(t.get("TRANS_SHARES")),
            "price": _number(t.get("TRANS_PRICEPERSHARE")),
            "transaction_date": parse_sec_date(str(t["TRANS_DATE"])),
            "filing_date": filed,
            "filing_accepted_at": latest_acceptance(filed),
            "is_10b5_1": (
                str(filing.get("AFF10B5ONE", "")).strip().upper() in _TRUE
                or bool(_PLAN.search(str(filing.get("REMARKS", ""))))
                or any((accession, note) in plan_notes for note in referenced)
            ),
        })
    return pd.DataFrame(rows, columns=INSIDER_COLUMNS)


_ACCEPTED = re.compile(r"<ACCEPTANCE-DATETIME>\s*(\d{14})")
_XML = re.compile(r"<XML>\s*(.*?)\s*</XML>", re.DOTALL | re.IGNORECASE)


def _text(node: ET.Element | None, path: str) -> str:
    found = node.find(path) if node is not None else None
    return (found.text or "").strip() if found is not None else ""


def parse_form4_submission(text: str, universe: Collection[str]) -> list[dict[str, object]]:
    """Transactions in one Form 4 full submission (`.txt`: SEC header, then the XML). The
    header's acceptance time is US Eastern."""
    accepted = _ACCEPTED.search(text)
    document = _XML.search(text)
    if accepted is None or document is None:
        return []
    root = ET.fromstring(document.group(1).encode())
    if _text(root, "documentType") not in _TRANSACTION_FORMS:
        return []
    issuer = cik10(_text(root, "issuer/issuerCik"))
    if issuer not in universe:
        return []
    accession_match = re.search(r"ACCESSION NUMBER:\s*(\S+)", text)
    accession = accession_match.group(1) if accession_match else ""
    accepted_at = eastern_to_utc(
        datetime.strptime(accepted.group(1), "%Y%m%d%H%M%S")  # noqa: DTZ007 - US Eastern
    )

    owners = root.findall("reportingOwner")
    flags = {
        flag
        for owner in owners
        for flag, tag in (("director", "isDirector"), ("officer", "isOfficer"),
                          ("tenpercentowner", "isTenPercentOwner"), ("other", "isOther"))
        if _text(owner, f"reportingOwnerRelationship/{tag}").upper() in _TRUE
    }
    owner_cik = min((cik10(_text(o, "reportingOwnerId/rptOwnerCik")) for o in owners), default="")
    plan_filing = (
        _text(root, "aff10b5One").upper() in _TRUE or bool(_PLAN.search(_text(root, "remarks")))
    )
    plan_notes = {
        (f.get("id") or "").upper()
        for f in root.findall("footnotes/footnote") if _PLAN.search("".join(f.itertext()))
    }

    rows: list[dict[str, object]] = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        referenced = {(f.get("id") or "").upper() for f in t.iter("footnoteId")}
        rows.append({
            "accession_number": accession,
            "issuer_cik": issuer,
            "owner_cik": owner_cik,
            "role": _role(flags),
            "transaction_code": _text(t, "transactionCoding/transactionCode").upper(),
            "acquired_disposed": _text(
                t, "transactionAmounts/transactionAcquiredDisposedCode/value"
            ).upper(),
            "shares": _number(_text(t, "transactionAmounts/transactionShares/value")),
            "price": _number(_text(t, "transactionAmounts/transactionPricePerShare/value")),
            "transaction_date": date.fromisoformat(_text(t, "transactionDate/value")[:10]),
            "filing_date": accepted_at.tz_convert("America/New_York").date(),
            "filing_accepted_at": accepted_at,
            "is_10b5_1": plan_filing or bool(referenced & plan_notes),
        })
    return rows


def quarterly_key(label: str) -> str:
    return f"insider/{label}.parquet"


def daily_key(day: date) -> str:
    return f"insider/daily/{day.isoformat()}.parquet"


def offerings_key(year: int, quarter: int) -> str:
    return f"offerings/{year}q{quarter}.parquet"


def daily_offerings_key(day: date) -> str:
    return f"offerings/daily/{day.isoformat()}.parquet"


class InsiderTransactionStore:
    def __init__(
        self,
        store: OwnershipStore,
        sec: SecFetcher,
        universe_ciks: Collection[str],
        *,
        daily_index_url: str,
        full_index_url: str,
        archives_url: str,
    ) -> None:
        self._store = store
        self._sec = sec
        self._universe = frozenset(universe_ciks)
        self._daily_index_url = daily_index_url.rstrip("/")
        self._full_index_url = full_index_url.rstrip("/")
        self._archives_url = archives_url.rstrip("/")

    def stored(self, label: str) -> bool:
        return self._store.exists(quarterly_key(label))

    def fetch_quarter(self, dataset: DatasetFile) -> int:
        """Stores one quarterly data set; returns its universe transaction count."""
        key = quarterly_key(dataset.label)
        stored = self._store.read(key)
        if stored is not None:
            return len(stored[0])
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._sec.download(dataset.url, Path(tmp) / f"{dataset.label}.zip")
            rows = parse_insider_dataset(archive, self._universe)
        self._store.write(key, rows, {"source_url": dataset.url, "label": dataset.label})
        log.info("insider %s: %d universe transactions", dataset.label, len(rows))
        return len(rows)

    def fetch_offerings(self, year: int, quarter: int) -> int:
        """Stores a completed quarter's 424B4/424B5 filings of universe issuers."""
        key = offerings_key(year, quarter)
        stored = self._store.read(key)
        if stored is not None:
            return len(stored[0])
        url = f"{self._full_index_url}/{year}/QTR{quarter}/form.idx"
        rows = offerings_from_index(parse_form_index(self._sec.get(url).decode("latin-1")),
                                    self._universe)
        self._store.write(key, rows, {"source_url": url})
        return len(rows)

    def fetch_day(self, day: date) -> int | None:
        """Stores one day's Form 4 transactions and offerings of universe issuers from the
        daily form index; returns the transaction count, or None when SEC published no index
        for the day (weekends, holidays)."""
        key = daily_key(day)
        stored = self._store.read(key)
        if stored is not None:
            return len(stored[0])
        year, quarter = quarter_of(day)
        url = f"{self._daily_index_url}/{year}/QTR{quarter}/form.{day:%Y%m%d}.idx"
        try:
            index = parse_form_index(self._sec.get(url).decode("latin-1"))
        except SecNotFoundError:
            return None
        paths = sorted({e.path for e in index if e.form == "4" and e.cik in self._universe})
        rows: list[dict[str, object]] = []
        for path in paths:
            document = f"{self._archives_url}/{path.removeprefix('edgar/data/')}"
            try:
                text = self._sec.get(document).decode("utf-8", errors="replace")
            except SecNotFoundError:
                log.info("Form 4 %s listed in %s but not found", document, url)
                continue
            rows.extend(parse_form4_submission(text, self._universe))
        # The transactions file marks the day stored, so it is written last.
        self._store.replace(daily_offerings_key(day), offerings_from_index(index, self._universe),
                            {"source_url": url})
        self._store.write(key, pd.DataFrame(rows, columns=INSIDER_COLUMNS), {"source_url": url})
        return len(rows)


def concat(frames: Iterable[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    non_empty = [f for f in frames if len(f)]
    return pd.concat(non_empty, ignore_index=True) if non_empty else pd.DataFrame(columns=columns)


def by_label(keys_and_frames: Iterable[tuple[str, pd.DataFrame]]) -> Mapping[str, pd.DataFrame]:
    return {k.rsplit("/", 1)[-1].removesuffix(".parquet"): f for k, f in keys_and_frames}
