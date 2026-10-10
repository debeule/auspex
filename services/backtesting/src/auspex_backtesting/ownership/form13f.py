"""Form 13F data sets: who holds each universe company, as filed.

Each data set holds the 13F filings made in its window, whatever quarter they report on, so a
late filing or an amendment lands in the data set of the window it was filed in. Two tables are
kept per data set:

- `13f/filings/{label}.parquet`: every holdings report (`13F-HR`, `13F-HR/A`) with its filer,
  period, acceptance bound, amendment kind, and the long equity value it reports in total and
  in healthcare issuers. The specialist rule reads these.
- `13f/{label}.parquet`: the holdings of universe companies, one row per report and CUSIP.

Rows that cannot count as owned shares are left out of both: options (`PUTCALL` set) and
principal amounts (`SSHPRNAMTTYPE` = `PRN`).
"""

import csv
import io
import logging
import tempfile
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Collection, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from auspex_backtesting.ownership.datasets import DatasetFile, latest_acceptance, parse_sec_date
from auspex_backtesting.ownership.issuers import IssuerDirectory
from auspex_backtesting.ownership.sec_client import SecFetcher
from auspex_backtesting.ownership.store import OwnershipStore

log = logging.getLogger("auspex_backtesting.ownership")

HEALTHCARE_SIC = frozenset({"2834", "2836", "8731", "3841"})
_HOLDINGS_FORMS = frozenset({"13F-HR", "13F-HR/A"})
_TRUE = frozenset({"Y", "YES", "TRUE", "1"})
# Filings made from 3 January 2023 report market value in dollars; earlier ones in thousands.
_DOLLAR_VALUES_FROM = date(2023, 1, 3)

FILINGS_COLUMNS = [
    "accession_number", "filer_cik", "period_of_report", "filing_accepted_at", "is_amendment",
    "amendment_type", "total_value_usd", "healthcare_value_usd",
]
HOLDINGS_COLUMNS = [
    "accession_number", "filer_cik", "issuer_cik", "cusip", "shares", "value_usd",
    "period_of_report", "filing_accepted_at", "is_amendment", "amendment_type",
]


@dataclass(frozen=True)
class Form13FReport:
    """What one data set contributed. A CUSIP is unmapped when none of the issuer names filers
    gave it matches exactly one SEC company; its holdings are counted here, not dropped."""

    label: str
    filings: int
    holdings_rows: int
    universe_issuers_held: int
    cusips: int
    unmapped_cusips: int
    unmapped_value_usd: float
    total_value_usd: float


def read_table(zf: zipfile.ZipFile, name: str) -> pd.DataFrame:
    """A data set table as strings; a missing table is empty. Fields are tab-separated and
    unquoted, so quote characters in names are data."""
    entry = next((n for n in zf.namelist() if n.rsplit("/", 1)[-1].upper() == name.upper()), None)
    if entry is None:
        return pd.DataFrame()
    with zf.open(entry) as fh:
        return pd.read_csv(
            io.TextIOWrapper(fh, encoding="utf-8", errors="replace"),
            sep="\t", dtype=str, keep_default_na=False, quoting=csv.QUOTE_NONE,
        )


def cik10(value: str) -> str:
    return value.strip().zfill(10)


def parse_13f_dataset(
    archive: Path,
    label: str,
    directory: IssuerDirectory,
    universe_ciks: Collection[str],
    healthcare_sic: Collection[str] = HEALTHCARE_SIC,
) -> tuple[pd.DataFrame, pd.DataFrame, Form13FReport]:
    """(filings, universe holdings, report) from one 13F data set archive."""
    with zipfile.ZipFile(archive) as zf:
        submissions = read_table(zf, "SUBMISSION.tsv")
        cover = read_table(zf, "COVERPAGE.tsv")
        info = read_table(zf, "INFOTABLE.tsv")

    submissions = submissions[submissions["SUBMISSIONTYPE"].str.strip().isin(_HOLDINGS_FORMS)]
    cover_by_accession = (
        cover.drop_duplicates("ACCESSION_NUMBER").set_index("ACCESSION_NUMBER")
        if not cover.empty else pd.DataFrame()
    )
    reports: dict[str, dict[str, object]] = {}
    for row in submissions.itertuples(index=False):
        accession = str(row.ACCESSION_NUMBER).strip()
        page: Mapping[str, str] = (
            cover_by_accession.loc[accession].to_dict()
            if accession in cover_by_accession.index else {}
        )
        if "NOTICE" in str(page.get("REPORTTYPE", "")).upper():
            continue
        filed = parse_sec_date(str(row.FILING_DATE))
        amendment_type = str(page.get("AMENDMENTTYPE", "")).strip().upper() or None
        is_amendment = (
            str(page.get("ISAMENDMENT", "")).strip().upper() in _TRUE
            or str(row.SUBMISSIONTYPE).strip().endswith("/A")
        )
        reports[accession] = {
            "accession_number": accession,
            "filer_cik": cik10(str(row.CIK)),
            "period_of_report": parse_sec_date(str(row.PERIODOFREPORT)),
            "filing_accepted_at": latest_acceptance(filed),
            "filing_date": filed,
            "is_amendment": is_amendment,
            "amendment_type": amendment_type if is_amendment else None,
        }

    filing_dates = {a: parse_sec_date(str(d)) for a, d in zip(
        submissions["ACCESSION_NUMBER"].str.strip(), submissions["FILING_DATE"], strict=True
    )}
    info = info[info["ACCESSION_NUMBER"].str.strip().isin(reports)] if not info.empty else info
    long_equity = info[
        (info["SSHPRNAMTTYPE"].str.strip().str.upper() == "SH")
        & (info["PUTCALL"].str.strip() == "")
    ] if not info.empty else info

    resolved = _resolve_cusips(long_equity, directory)
    holdings: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    unmapped: dict[str, float] = defaultdict(float)
    for row in long_equity.itertuples(index=False):
        accession = str(row.ACCESSION_NUMBER).strip()
        cusip = str(row.CUSIP).strip().upper()
        filed = filing_dates[accession]
        value = float(row.VALUE or 0) * (1 if filed >= _DOLLAR_VALUES_FROM else 1000)
        shares = float(row.SSHPRNAMT or 0)
        issuer = resolved.get(cusip)
        totals[accession][0] += value
        if issuer is None:
            unmapped[cusip] += value
            continue
        if directory.sic(issuer) in healthcare_sic:
            totals[accession][1] += value
        if issuer in universe_ciks:
            entry = holdings[(accession, cusip)]
            entry[0] += shares
            entry[1] += value

    filings = pd.DataFrame(
        [
            {k: v for k, v in r.items() if k != "filing_date"}
            | {"total_value_usd": totals[a][0], "healthcare_value_usd": totals[a][1]}
            for a, r in reports.items()
        ],
        columns=FILINGS_COLUMNS,
    )
    holding_rows = pd.DataFrame(
        [
            {
                "accession_number": accession,
                "filer_cik": reports[accession]["filer_cik"],
                "issuer_cik": resolved[cusip],
                "cusip": cusip,
                "shares": shares,
                "value_usd": value,
                "period_of_report": reports[accession]["period_of_report"],
                "filing_accepted_at": reports[accession]["filing_accepted_at"],
                "is_amendment": reports[accession]["is_amendment"],
                "amendment_type": reports[accession]["amendment_type"],
            }
            for (accession, cusip), (shares, value) in sorted(holdings.items())
        ],
        columns=HOLDINGS_COLUMNS,
    )
    report = Form13FReport(
        label=label,
        filings=len(filings),
        holdings_rows=len(holding_rows),
        universe_issuers_held=int(holding_rows["issuer_cik"].nunique()),
        cusips=int(long_equity["CUSIP"].str.strip().str.upper().nunique()) if len(long_equity) else 0,
        unmapped_cusips=len(unmapped),
        unmapped_value_usd=float(sum(unmapped.values())),
        total_value_usd=float(sum(t[0] for t in totals.values())),
    )
    return filings, holding_rows, report


def _resolve_cusips(info: pd.DataFrame, directory: IssuerDirectory) -> dict[str, str]:
    """CUSIP -> CIK. Each name a filer gave a CUSIP votes for the company it resolves to and
    the most-voted company wins; a tie resolves nothing. A CUSIP whose names all fail takes
    the company of other CUSIPs with the same six-character issuer prefix, if they agree."""
    names: dict[str, Counter[str]] = defaultdict(Counter)
    for cusip, name in zip(info["CUSIP"] if len(info) else [], info["NAMEOFISSUER"] if len(info) else [],
                           strict=True):
        names[str(cusip).strip().upper()][str(name)] += 1

    resolved: dict[str, str] = {}
    for cusip, counts in names.items():
        votes: Counter[str] = Counter()
        for name, n in counts.items():
            if cik := directory.resolve(name):
                votes[cik] += n
        ranked = votes.most_common(2)
        if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
            resolved[cusip] = ranked[0][0]

    by_prefix: dict[str, set[str]] = defaultdict(set)
    for cusip, cik in resolved.items():
        by_prefix[cusip[:6]].add(cik)
    for cusip in names:
        if cusip not in resolved and len(ciks := by_prefix.get(cusip[:6], set())) == 1:
            resolved[cusip] = next(iter(ciks))
    return resolved


class Form13FDatasetStore:
    """Downloads each 13F data set once and keeps what the panels need from it.

    `directory` is called only when a data set has to be parsed: building it costs SEC's
    submissions archive, which a run with every data set already stored never downloads.
    """

    def __init__(
        self,
        store: OwnershipStore,
        sec: SecFetcher,
        directory: Callable[[], IssuerDirectory],
        universe_ciks: Collection[str],
        healthcare_sic: Collection[str] = HEALTHCARE_SIC,
    ) -> None:
        self._store = store
        self._sec = sec
        self._directory_factory = directory
        self._directory: IssuerDirectory | None = None
        self._universe = frozenset(universe_ciks)
        self._healthcare_sic = frozenset(healthcare_sic)

    def stored(self, label: str) -> bool:
        return self._store.exists(holdings_key(label))

    def fetch(self, dataset: DatasetFile) -> Form13FReport:
        existing = self.report(dataset.label)
        if existing is not None:
            return existing
        if self._directory is None:
            self._directory = self._directory_factory()
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._sec.download(dataset.url, Path(tmp) / f"{dataset.label}.zip")
            filings, holdings, report = parse_13f_dataset(
                archive, dataset.label, self._directory, self._universe, self._healthcare_sic
            )
        meta: dict[str, object] = {"report": asdict(report), "source_url": dataset.url}
        # The holdings file marks the data set stored, so it is written last.
        self._store.replace(filings_key(dataset.label), filings, meta)
        self._store.write(holdings_key(dataset.label), holdings, meta)
        log.info(
            "13F %s: %d reports, %d universe holdings, %d of %d CUSIPs unmapped",
            dataset.label, report.filings, report.holdings_rows, report.unmapped_cusips,
            report.cusips,
        )
        return report

    def report(self, label: str) -> Form13FReport | None:
        stored = self._store.read(holdings_key(label))
        if stored is None:
            return None
        values = stored[1]["report"]
        assert isinstance(values, dict)
        return Form13FReport(**values)


def holdings_key(label: str) -> str:
    return f"13f/{label}.parquet"


def filings_key(label: str) -> str:
    return f"13f/filings/{label}.parquet"


def specialists_key(label: str) -> str:
    return f"13f/specialists/{label}.parquet"


def load_13f(store: OwnershipStore) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every stored (filings, holdings) row, across data sets."""
    filings = [f for _, f in store.read_all("13f/filings/")]
    holdings = [h for _, h in store.read_all("13f/")]
    return (
        pd.concat(filings, ignore_index=True) if filings else pd.DataFrame(columns=FILINGS_COLUMNS),
        pd.concat(holdings, ignore_index=True) if holdings else pd.DataFrame(columns=HOLDINGS_COLUMNS),
    )
