"""Healthcare specialist 13F filers, by rule, as of any date.

A hand-made list of specialist funds written today would pick the funds known now to have done
well, which is look-ahead. The rule here sees only what was filed before the date it classifies.
"""

from datetime import date, datetime
from pathlib import Path

import pandas as pd

from auspex_backtesting.hypothesis import load_hypothesis, verify_hypothesis
from auspex_backtesting.ownership.datasets import instant, quarter_bounds, quarter_of

_NEW_HOLDINGS = "NEW HOLDINGS"
_REPORT_KEYS = ["filer_cik", "period_of_report"]
_HYPOTHESIS_ID = "h9"
_COMPONENT = "specialist_13f_ownership"


class SpecialistThresholdsError(ValueError):
    """The registered hypothesis does not state both specialist thresholds."""


def report_accessions(filings: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """The filings that make up each (filer, period) report as known just before `as_of`.

    A report is its latest restatement if one has been accepted, else its latest original,
    plus every "new holdings" amendment accepted after that base. Amendments accepted at or
    after `as_of` are invisible, so a later restatement never changes an earlier read.
    Columns: filer_cik, period_of_report, accession_number.
    """
    visible = filings[filings["filing_accepted_at"] < as_of]
    if visible.empty:
        return pd.DataFrame(columns=[*_REPORT_KEYS, "accession_number"])
    kind = visible["amendment_type"].fillna("").astype(str).str.upper()
    is_new_holdings = visible["is_amendment"].astype(bool) & (kind == _NEW_HOLDINGS)
    visible = visible.assign(
        is_restatement=visible["is_amendment"].astype(bool) & ~is_new_holdings,
        is_new_holdings=is_new_holdings,
    )
    base = (
        visible[~visible["is_new_holdings"]]
        .sort_values(["is_restatement", "filing_accepted_at", "accession_number"])
        .groupby(_REPORT_KEYS, sort=False)
        .tail(1)
    )
    additions = visible[visible["is_new_holdings"]].merge(
        base[[*_REPORT_KEYS, "filing_accepted_at", "is_restatement"]],
        on=_REPORT_KEYS, how="left", suffixes=("", "_base"),
    )
    keep = (
        additions["filing_accepted_at_base"].isna()
        | ~additions["is_restatement_base"].fillna(False).astype(bool)
        | (additions["filing_accepted_at"] > additions["filing_accepted_at_base"])
    )
    columns = [*_REPORT_KEYS, "accession_number"]
    return pd.concat([base[columns], additions.loc[keep, columns]], ignore_index=True)


def trailing_quarter_ends(as_of: date, count: int = 4) -> list[date]:
    """The `count` most recent calendar quarter ends strictly before `as_of`, newest first."""
    year, quarter = quarter_of(as_of)
    ends: list[date] = []
    while len(ends) < count:
        year, quarter = (year - 1, 4) if quarter == 1 else (year, quarter - 1)
        ends.append(quarter_bounds(year, quarter)[1])
    return ends


class SpecialistClassifier:
    """A 13F filer is a healthcare specialist as of D when, over its reports for the four
    calendar quarters before D as accepted before D, at least `healthcare_share` of reported
    long equity value is in healthcare issuers (SIC 2834, 2836, 8731, 3841), and its latest
    such report totals at least `min_aum_usd`."""

    def __init__(self, filings: pd.DataFrame, *, healthcare_share: float, min_aum_usd: float) -> None:
        self._filings = filings
        self.healthcare_share = healthcare_share
        self.min_aum_usd = min_aum_usd
        self._cache: dict[pd.Timestamp, pd.DataFrame] = {}

    @classmethod
    def from_hypothesis(
        cls,
        filings: pd.DataFrame,
        *,
        config_dir: Path | None = None,
        registry_path: Path | None = None,
    ) -> SpecialistClassifier:
        """The classifier with the thresholds H9 registered, the only place they are set.

        Refuses an unregistered or edited hypothesis file, so a panel is never built with
        thresholds the registry does not hold."""
        verify_hypothesis(_HYPOTHESIS_ID, config_dir=config_dir, registry_path=registry_path)
        hypothesis = load_hypothesis(_HYPOTHESIS_ID, config_dir)
        thresholds = (
            hypothesis.get("components", {}).get(_COMPONENT, {}).get("thresholds", {})
        )
        try:
            share = float(thresholds["SPECIALIST_HEALTHCARE_SHARE"])
            aum = float(thresholds["SPECIALIST_MIN_AUM_USD"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SpecialistThresholdsError(
                f"{_HYPOTHESIS_ID} must set components.{_COMPONENT}.thresholds."
                "SPECIALIST_HEALTHCARE_SHARE and SPECIALIST_MIN_AUM_USD"
            ) from exc
        return cls(filings, healthcare_share=share, min_aum_usd=aum)

    def specialists(self, as_of: date | datetime) -> frozenset[str]:
        table = self.classify(as_of)
        return frozenset(table.loc[table["is_specialist"], "filer_cik"])

    def classify(self, as_of: date | datetime) -> pd.DataFrame:
        """One row per filer with a report in the window: filer_cik, healthcare_share,
        latest_total_value_usd, is_specialist."""
        moment = instant(as_of)
        if moment in self._cache:
            return self._cache[moment]
        window = trailing_quarter_ends(moment.date())
        reports = report_accessions(self._filings, moment)
        reports = reports[reports["period_of_report"].isin(window)]
        values = reports.merge(
            self._filings[["accession_number", "total_value_usd", "healthcare_value_usd"]],
            on="accession_number",
        )
        per_report = values.groupby(_REPORT_KEYS, as_index=False)[
            ["total_value_usd", "healthcare_value_usd"]
        ].sum()
        per_filer = per_report.groupby("filer_cik").agg(
            total=("total_value_usd", "sum"), healthcare=("healthcare_value_usd", "sum")
        )
        latest = per_report.sort_values("period_of_report").groupby("filer_cik").tail(1)
        latest_total = latest.set_index("filer_cik")["total_value_usd"]
        share = (per_filer["healthcare"] / per_filer["total"].where(per_filer["total"] > 0))
        table = pd.DataFrame({
            "filer_cik": per_filer.index.astype(str),
            "healthcare_share": share.fillna(0.0).to_numpy(),
            "latest_total_value_usd": latest_total.reindex(per_filer.index).to_numpy(),
        })
        table["is_specialist"] = (
            (table["healthcare_share"] >= self.healthcare_share)
            & (table["latest_total_value_usd"] >= self.min_aum_usd)
        )
        self._cache[moment] = table
        return table
