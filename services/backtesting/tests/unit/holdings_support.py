"""Builders for the holdings composite score tests: a fake universe, specialist ownership read
from a table, insider panels from trade rows and short interest in a fake bucket."""

from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from ownership_fakes import FakeMinio, FixedMarketCaps

from auspex_backtesting.hypothesis import load_hypothesis
from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.ownership import InsiderPanel
from auspex_backtesting.ownership.datasets import latest_acceptance
from auspex_backtesting.scores.holdings_composite import HoldingsCompositeScore
from auspex_backtesting.short_interest import FinraCalendar, ShortInterestRecord, ShortInterestStore
from auspex_backtesting.universe import UniverseMember, UniverseSnapshot

CONFIG_DIR = Path(__file__).resolve().parents[4] / "config" / "hypotheses"
RULES_VERSION = 1
# First NYSE session of June 2024. FINRA's 15 May 2024 period was published on 24 May; its
# 31 May period on 11 June.
REBALANCE = date(2024, 6, 3)
MAY_15, MAY_31 = date(2024, 5, 15), date(2024, 5, 31)


def h9() -> dict[str, Any]:
    return load_hypothesis("h9", CONFIG_DIR)


def member(
    cik: str,
    ticker: str | None = None,
    *,
    market_cap: float | None = 1e9,
    dollar_volume: float | None = 5e6,
) -> UniverseMember:
    return UniverseMember(
        cik=cik, ticker=ticker or f"T{cik}", ticker_source="current", name=f"Company {cik}",
        sic="2836", exchange="Nasdaq", market_cap_usd=market_cap,
        median_dollar_volume_20d=dollar_volume, entered_on=date(2014, 1, 2), exited_on=None,
        exit_reason=None, price_coverage="complete", coverage_note="",
    )


class FakeUniverse:
    universe = "biotech"

    def __init__(self, snapshots: Iterable[UniverseSnapshot]) -> None:
        self._snapshots = {s.month: s for s in snapshots}

    def months(self, rules_version: int) -> list[str]:
        return sorted(self._snapshots)

    def read(self, rules_version: int, month: str) -> UniverseSnapshot | None:
        return self._snapshots.get(month)


def snapshot(members: Iterable[UniverseMember], rebalance: date = REBALANCE) -> UniverseSnapshot:
    return UniverseSnapshot(
        RULES_VERSION, rebalance.strftime("%Y-%m"), rebalance,
        tuple(sorted(members, key=lambda m: m.cik)),
    )


class TableHoldings:
    """Specialist ownership per CIK with the time its inputs were last accepted; a CIK that is
    not listed has no share count."""

    def __init__(self, rows: Mapping[str, tuple[float, pd.Timestamp]]) -> None:
        self.rows = dict(rows)
        self.asked: list[datetime] = []

    def specialist_ownership(self, issuer_cik: str, as_of: datetime) -> float | None:
        self.asked.append(as_of)
        row = self.rows.get(issuer_cik)
        return row[0] if row else None

    def specialist_ownership_reason(self, issuer_cik: str, as_of: datetime) -> str | None:
        return None if issuer_cik in self.rows else "no_share_count"

    def specialist_ownership_known_at(
        self, issuer_cik: str, as_of: datetime
    ) -> pd.Timestamp | None:
        row = self.rows.get(issuer_cik)
        return row[1] if row else None


def trade(
    cik: str,
    filed: date,
    *,
    code: str = "P",
    shares: float = 1_000.0,
    price: float = 10.0,
    traded: date | None = None,
    accession: str | None = None,
) -> dict[str, Any]:
    return {
        "accession_number": accession or f"{cik}-{filed.isoformat()}-{code}", "issuer_cik": cik,
        "owner_cik": "O", "role": "officer", "transaction_code": code,
        "acquired_disposed": "A" if code == "P" else "D", "shares": shares, "price": price,
        "transaction_date": traded or filed, "filing_date": filed,
        "filing_accepted_at": latest_acceptance(filed), "is_10b5_1": False,
    }


def insiders(
    trades: Iterable[Mapping[str, Any]] = (),
    market_caps: Mapping[str, float] | None = None,
    offerings: Iterable[Mapping[str, Any]] = (),
) -> InsiderPanel:
    return InsiderPanel(
        pd.DataFrame(list(trades)), pd.DataFrame(), pd.DataFrame(list(offerings)),
        FixedMarketCaps(market_caps or {}),
    )


def short_interest(
    rows: Mapping[str, Mapping[date, float | None]],
    finra: FinraCalendar | None = None,
) -> ShortInterestStore:
    """Days to cover per ticker and settlement date, published on FINRA's schedule; None is a
    period FINRA published without the ticker."""
    calendar = finra or FinraCalendar()
    store = ShortInterestStore(FakeMinio())  # type: ignore[arg-type]
    for ticker, periods in rows.items():
        records = []
        for settled, days in sorted(periods.items()):
            published = calendar.publication_date(settled)
            if days is None:
                records.append(ShortInterestRecord.absent(ticker, settled, published))
            else:
                records.append(ShortInterestRecord.from_counts(
                    ticker, settled, published,
                    short_interest_shares=round(days * 100_000), average_daily_volume=100_000,
                ))
        store.append(ticker, records)
    return store


def score(
    members: Iterable[UniverseMember],
    *,
    holdings: TableHoldings | None = None,
    insider_panel: InsiderPanel | None = None,
    short: ShortInterestStore | None = None,
    variant: str = "three_component",
    floor: bool = True,
    finra: FinraCalendar | None = None,
    snapshots: Iterable[UniverseSnapshot] | None = None,
) -> HoldingsCompositeScore:
    universe = FakeUniverse(snapshots if snapshots is not None else [snapshot(members)])
    return HoldingsCompositeScore(
        h9(), universe, RULES_VERSION,
        holdings or TableHoldings({}),
        insider_panel or insiders(),
        short or short_interest({}),
        variant=variant, floor=floor, finra=finra or FinraCalendar(),
    )


def accepted(day: date) -> pd.Timestamp:
    return latest_acceptance(day)


def opens(day: date = REBALANCE) -> pd.Timestamp:
    return pd.Timestamp(MarketCalendar().session_open(day))


def with_cap(m: UniverseMember, cap: float | None, volume: float | None = 5e6) -> UniverseMember:
    return replace(m, market_cap_usd=cap, median_dollar_volume_20d=volume)
