"""Point-in-time reads of the ownership panels.

Every read is as of an instant and sees only filings accepted strictly before it, joined on
`filing_accepted_at`, never on the period a report covers or the day a trade was made: a
quarter's 13F is public up to 45 days after the quarter ends, and a Form 4 up to two business
days after the trade.
"""

import logging
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd

from auspex_backtesting.ownership.datasets import instant, latest_acceptance, quarter_label
from auspex_backtesting.ownership.form13f import load_13f
from auspex_backtesting.ownership.insider import (
    INSIDER_COLUMNS,
    OFFERING_COLUMNS,
    by_label,
    concat,
)
from auspex_backtesting.ownership.reference import MarketCaps, ShareCountPanel, SharesOutstanding
from auspex_backtesting.ownership.specialists import SpecialistClassifier, report_accessions
from auspex_backtesting.ownership.store import OwnershipStore

log = logging.getLogger("auspex_backtesting.ownership")

# Insiders buying into their own company's financing is not an information signal.
_OFFERING_PROXIMITY = timedelta(days=2)


class HoldingsPanel:
    def __init__(
        self,
        filings: pd.DataFrame,
        holdings: pd.DataFrame,
        classifier: SpecialistClassifier,
        shares: SharesOutstanding,
    ) -> None:
        self._filings = filings
        self._holdings = holdings
        self._classifier = classifier
        self._shares = shares
        self._held: dict[pd.Timestamp, pd.Series] = {}

    @classmethod
    def load(
        cls,
        store: OwnershipStore,
        *,
        config_dir: Path | None = None,
        registry_path: Path | None = None,
    ) -> HoldingsPanel:
        filings, holdings = load_13f(store)
        classifier = SpecialistClassifier.from_hypothesis(
            filings, config_dir=config_dir, registry_path=registry_path
        )
        return cls(filings, holdings, classifier, ShareCountPanel.load(store))

    def specialist_ownership(self, issuer_cik: str, as_of: date | datetime) -> float | None:
        """Shares of `issuer_cik` held by specialist filers in each one's latest report
        accepted before `as_of`, over shares outstanding as known on `as_of`. None when no
        share count was filed before `as_of`."""
        moment = instant(as_of)
        outstanding = self._shares.shares_outstanding(issuer_cik, moment.date())
        if not outstanding:
            return None
        return float(self._specialist_shares(moment).get(issuer_cik, 0.0)) / outstanding

    def _specialist_shares(self, moment: pd.Timestamp) -> pd.Series:
        if moment in self._held:
            return self._held[moment]
        specialists = self._classifier.specialists(moment.to_pydatetime())
        reports = report_accessions(self._filings, moment)
        reports = reports[reports["filer_cik"].isin(specialists)]
        latest_period = reports.groupby("filer_cik")["period_of_report"].transform("max")
        accessions = reports.loc[reports["period_of_report"] == latest_period, "accession_number"]
        held = (
            self._holdings[self._holdings["accession_number"].isin(set(accessions))]
            .groupby("issuer_cik")["shares"].sum()
        )
        self._held[moment] = held
        return held


@dataclass(frozen=True)
class Disagreement:
    """A difference between the quarterly data set and the daily Form 4 rows for one filing."""

    quarter: str
    accession_number: str
    kind: Literal["missing_from_dataset", "missing_from_daily", "different"]


class InsiderPanel:
    """Insider transactions from the quarterly data sets, and from daily Form 4s for quarters
    whose data set is not stored yet."""

    def __init__(
        self,
        quarterly: pd.DataFrame,
        daily: pd.DataFrame,
        offerings: pd.DataFrame,
        market_caps: MarketCaps,
        *,
        quarterly_labels: Collection[str] | None = None,
        daily_days: Collection[date] | None = None,
    ) -> None:
        quarterly = quarterly if len(quarterly) else pd.DataFrame(columns=INSIDER_COLUMNS)
        daily = daily if len(daily) else pd.DataFrame(columns=INSIDER_COLUMNS)
        self._quarterly = quarterly.assign(quarter=quarterly["filing_date"].map(quarter_label))
        self._daily = daily.assign(quarter=daily["filing_date"].map(quarter_label))
        self._labels = frozenset(
            quarterly_labels if quarterly_labels is not None else self._quarterly["quarter"]
        )
        self._daily_days = frozenset(
            daily_days if daily_days is not None else self._daily["filing_date"]
        )
        gap = self._daily[~self._daily["quarter"].isin(self._labels)]
        self._rows = pd.concat(
            [f for f in (self._quarterly, gap) if len(f)] or [self._quarterly], ignore_index=True
        )
        offerings = offerings if len(offerings) else pd.DataFrame(columns=OFFERING_COLUMNS)
        self._offerings = offerings.drop_duplicates("accession_number")
        self._market_caps = market_caps
        for d in self.disagreements():
            log.warning("insider %s: %s %s", d.quarter, d.accession_number, d.kind)

    @classmethod
    def load(cls, store: OwnershipStore, market_caps: MarketCaps) -> InsiderPanel:
        quarterly = by_label(store.read_all("insider/"))
        daily = by_label(store.read_all("insider/daily/"))
        offerings = [f for _, f in store.read_all("offerings/")]
        offerings += [f for _, f in store.read_all("offerings/daily/")]
        return cls(
            concat(quarterly.values(), INSIDER_COLUMNS),
            concat(daily.values(), INSIDER_COLUMNS),
            concat(offerings, OFFERING_COLUMNS),
            market_caps,
            quarterly_labels=quarterly.keys(),
            daily_days={date.fromisoformat(d) for d in daily},
        )

    def transactions(
        self, issuer_cik: str, as_of: date | datetime, days: int = 90
    ) -> pd.DataFrame:
        """Transactions in `issuer_cik` accepted in the `days` before `as_of`, with
        `offering_participation` set on purchases within two days of an offering the issuer
        filed before `as_of`."""
        moment = instant(as_of)
        accepted = self._rows["filing_accepted_at"]
        rows = self._rows[
            (self._rows["issuer_cik"] == issuer_cik)
            & (accepted >= moment - timedelta(days=days))
            & (accepted < moment)
        ].copy()
        offerings = self._offerings[self._offerings["issuer_cik"] == issuer_cik]
        offering_dates = [
            d for d in offerings["filing_date"] if latest_acceptance(d) < moment
        ]
        rows["offering_participation"] = [
            code == "P" and any(abs(traded - d) <= _OFFERING_PROXIMITY for d in offering_dates)
            for code, traded in zip(rows["transaction_code"], rows["transaction_date"], strict=True)
        ]
        return rows.reset_index(drop=True)

    def net_insider_buying(
        self, issuer_cik: str, as_of: date | datetime, days: int = 90
    ) -> float | None:
        """Open-market purchases (`P`) minus sales (`S`) in USD over market cap, excluding
        10b5-1 plan trades and offering participation. None without a market cap."""
        moment = instant(as_of)
        market_cap = self._market_caps.market_cap_usd(issuer_cik, moment.date())
        if not market_cap:
            return None
        rows = self.transactions(issuer_cik, moment.to_pydatetime(), days)
        counted = rows[
            rows["transaction_code"].isin(["P", "S"])
            & ~rows["is_10b5_1"].astype(bool)
            & ~rows["offering_participation"].astype(bool)
        ]
        value = counted["shares"].fillna(0.0) * counted["price"].fillna(0.0)
        signed = value.where(counted["transaction_code"] == "P", -value)
        return float(signed.sum()) / market_cap

    def disagreements(self) -> list[Disagreement]:
        """Filings where a stored quarterly data set and the daily Form 4 rows differ, for
        the days the daily rows cover."""
        result = []
        for quarter in sorted(self._labels & set(self._daily["quarter"])):
            ours = _by_accession(self._daily[self._daily["quarter"] == quarter])
            theirs_rows = self._quarterly[
                (self._quarterly["quarter"] == quarter)
                & self._quarterly["filing_date"].isin(self._daily_days)
            ]
            theirs = _by_accession(theirs_rows)
            for accession in sorted(ours.keys() | theirs.keys()):
                if accession not in theirs:
                    kind: Literal["missing_from_dataset", "missing_from_daily", "different"] = (
                        "missing_from_dataset"
                    )
                elif accession not in ours:
                    kind = "missing_from_daily"
                elif ours[accession] != theirs[accession]:
                    kind = "different"
                else:
                    continue
                result.append(Disagreement(quarter, accession, kind))
        return result


def _by_accession(rows: pd.DataFrame) -> dict[str, list[tuple[str, float, float]]]:
    result: dict[str, list[tuple[str, float, float]]] = {}
    for accession, code, shares, price in zip(
        rows["accession_number"], rows["transaction_code"], rows["shares"], rows["price"],
        strict=True,
    ):
        result.setdefault(str(accession), []).append(
            (str(code), _rounded(shares), _rounded(price))
        )
    return {k: sorted(v) for k, v in result.items()}


def _rounded(value: object) -> float:
    return 0.0 if pd.isna(value) else round(float(value), 2)  # type: ignore[arg-type]
