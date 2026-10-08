import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import yaml
from minio.error import S3Error

from auspex_backtesting.api import create_app
from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.prices.price_refresher import (
    PriceDataUnavailableError,
    SnapshotDiscontinuityError,
)
from auspex_backtesting.prices.splits import SplitStore
from auspex_backtesting.universe import CompanyRecord, Filing, ShareCount, UniverseStore
from auspex_backtesting.universe.job import (
    SnapshotPrices,
    UniverseBuildJob,
    months_due,
)
from auspex_backtesting.universe.rules import parse_rules
from auspex_backtesting.universe.sec_bulk import read_share_counts, read_submissions
from auspex_backtesting.universe.store import RulesVersionError

_RULES_YAML = """\
version: 1
sic_codes: ["2834", "2836", "8731"]
exchanges: [NYSE, Nasdaq, NYSE American]
min_market_cap_usd: 50000000
min_median_dollar_volume_usd: 500000
liquidity_sessions: 20
rebalance: monthly
window:
  start: 2024-01-01
  end: null
"""


class _FakeMinio:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts: list[str] = []

    def put_object(self, bucket: str, key: str, data: io.BytesIO, length: int, **_: object) -> None:
        self.puts.append(key)
        self.objects[key] = data.read(length)

    def stat_object(self, bucket: str, key: str) -> object:
        if key not in self.objects:
            raise S3Error(MagicMock(), "NoSuchKey", "missing", "/", "", "")
        return object()

    def get_object(self, bucket: str, key: str) -> MagicMock:
        if key not in self.objects:
            raise S3Error(MagicMock(), "NoSuchKey", "missing", "/", "", "")
        response = MagicMock()
        response.read.return_value = self.objects[key]
        return response


# --- SEC bulk archives -------------------------------------------------------------------------


def _submissions_file(sic: str, name: str, recent: dict[str, list[str]], **extra: object) -> bytes:
    body = {"cik": "1", "entityType": "operating", "sic": sic, "name": name, **extra,
            "filings": {"recent": recent, "files": []}}
    return json.dumps(body).encode()


def _zip(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return path


def test_submissions_archive_yields_filers_in_the_sic_codes_with_their_full_history(
    tmp_path: Path,
) -> None:
    recent = {
        "form": ["8-K", "10-Q"],
        "filingDate": ["2024-03-14", "2023-11-10"],
        "items": ["2.01,5.01", ""],
        "primaryDocument": ["tm1_8k.htm", "alph-20230930.htm"],
    }
    older = {
        "form": ["8-A12B"], "filingDate": ["2015-05-01"], "items": [""], "primaryDocument": ["a.htm"]
    }
    archive = _zip(tmp_path / "submissions.zip", {
        "CIK0000000001.json": _submissions_file(
            "2836", "Alpha Therapeutics", recent, exchanges=["Nasdaq"], tickers=["ALPH"]
        ),
        "CIK0000000001-submissions-001.json": json.dumps(older).encode(),
        "CIK0000000002.json": _submissions_file("3841", "Device Co", recent),
    })

    (record,) = read_submissions(archive, {"2834", "2836"})

    assert record == CompanyRecord(
        cik="0000000001",
        name="Alpha Therapeutics",
        sic="2836",
        exchanges=("Nasdaq",),
        tickers=("ALPH",),
        filings=(
            Filing("8-K", date(2024, 3, 14), ("2.01", "5.01"), "tm1_8k.htm"),
            Filing("10-Q", date(2023, 11, 10), (), "alph-20230930.htm"),
            Filing("8-A12B", date(2015, 5, 1), (), "a.htm"),
        ),
    )


def test_company_facts_archive_yields_cover_page_share_counts_with_filed_dates(
    tmp_path: Path,
) -> None:
    facts = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2024-04-30", "val": 21_000_000, "filed": "2024-05-10", "form": "10-Q"},
        {"end": "2024-01-31", "val": 20_000_000, "filed": "2024-02-20", "form": "10-K"},
        {"end": "2024-01-31", "val": 20_000_000, "filed": "2024-02-20", "form": "10-K"},
    ]}}}}}
    archive = _zip(tmp_path / "companyfacts.zip", {
        "CIK0000000001.json": json.dumps(facts).encode(),
        "CIK0000000009.json": json.dumps(facts).encode(),
    })

    counts = read_share_counts(archive, {"0000000001", "0000000002"})

    assert counts == {"0000000001": [
        ShareCount(20_000_000.0, date(2024, 1, 31), date(2024, 2, 20)),
        ShareCount(21_000_000.0, date(2024, 4, 30), date(2024, 5, 10)),
    ]}


# --- splits ------------------------------------------------------------------------------------


def test_split_history_is_fetched_once_and_then_read_from_the_bucket() -> None:
    minio = _FakeMinio()
    ticker = MagicMock()
    ticker.splits = pd.Series([0.1], index=pd.DatetimeIndex(["2024-06-03"], tz="America/New_York"))
    store = SplitStore(minio)  # type: ignore[arg-type]

    with patch("auspex_backtesting.prices.splits.yf.Ticker", return_value=ticker) as yf_ticker:
        first = store.ensure("ALPH")
        second = store.ensure("ALPH")

    assert yf_ticker.call_count == 1
    assert minio.puts == ["splits/ALPH.parquet"]
    assert list(second) == [0.1]
    assert second.index[0] == pd.Timestamp("2024-06-03 04:00", tz="UTC")
    pd.testing.assert_series_equal(first, second, check_freq=False)


def test_failed_split_request_stores_nothing_so_it_is_retried() -> None:
    minio = _FakeMinio()
    store = SplitStore(minio)  # type: ignore[arg-type]

    with patch("auspex_backtesting.prices.splits.yf.Ticker", side_effect=RuntimeError("blocked")):
        assert store.ensure("ALPH").empty

    assert minio.puts == []


def test_preparing_prices_skips_splits_for_tickers_without_any_price_data() -> None:
    refresher, splits = MagicMock(), MagicMock()

    def refresh(ticker: str) -> None:
        if ticker == "GONE":
            raise PriceDataUnavailableError("GONE: no data from Yahoo or Stooq")
        if ticker == "RSPL":
            raise SnapshotDiscontinuityError("RSPL: re-adjusted")

    refresher.refresh.side_effect = refresh
    prices = SnapshotPrices(refresher, MagicMock(), splits)

    failed = prices.prepare(["ALPH", "GONE", "RSPL"])

    assert set(failed) == {"GONE", "RSPL"}
    assert [c.args[0] for c in splits.ensure.call_args_list] == ["ALPH", "RSPL"]


# --- build job ---------------------------------------------------------------------------------


def _bars(start: str, end: str) -> pd.DataFrame:
    sessions = MarketCalendar().sessions_between(date.fromisoformat(start), date.fromisoformat(end))
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in sessions], tz="UTC", name="date")
    return pd.DataFrame(
        {"open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0, "volume": 100_000.0}, index=idx
    )


class _Filings:
    def __init__(self) -> None:
        self.loads = 0

    def load(
        self, sic_codes: frozenset[str]
    ) -> tuple[Sequence[CompanyRecord], Mapping[str, Sequence[ShareCount]]]:
        self.loads += 1
        alpha = CompanyRecord(
            "0000000001", "Alpha", "2836", ("Nasdaq",), ("ALPH",),
            (Filing("8-A12B", date(2019, 5, 1)),),
        )
        gone = CompanyRecord(
            "0000000002", "Gone", "2834", (), (),
            (
                Filing("8-A12B", date(2019, 5, 1)),
                Filing("10-Q", date(2023, 11, 10), (), "gone-20230930.htm"),
                Filing("25-NSE", date(2024, 2, 15)),
            ),
        )
        shares = {c.cik: [ShareCount(20_000_000, date(2023, 11, 1), date(2023, 11, 10))]
                  for c in (alpha, gone)}
        return [alpha, gone], shares


class _Prices:
    def __init__(self) -> None:
        self.prepared: list[str] = []

    def prepare(self, tickers: Sequence[str]) -> dict[str, str]:
        self.prepared = list(tickers)
        return {"GONE": "no data"}

    def bars(self, ticker: str) -> pd.DataFrame | None:
        return _bars("2023-11-01", "2024-03-28") if ticker == "ALPH" else None

    def splits(self, ticker: str) -> pd.Series:
        return pd.Series(dtype=float)


def _job(tmp_path: Path, minio: _FakeMinio, filings: _Filings, today: date) -> UniverseBuildJob:
    rules = tmp_path / "rules.yaml"
    if not rules.exists():
        rules.write_text(_RULES_YAML, encoding="utf-8")
    return UniverseBuildJob(
        UniverseStore(minio),  # type: ignore[arg-type]
        rules,
        filings,
        _Prices(),
        today=lambda: today,
    )


def test_build_job_writes_each_due_month_once_with_coverage_and_backfill_scope(
    tmp_path: Path,
) -> None:
    minio, filings = _FakeMinio(), _Filings()

    summary = _job(tmp_path, minio, filings, date(2024, 3, 1)).run()

    assert [b["month"] for b in summary.built] == ["2024-01", "2024-02", "2024-03"]
    assert [b["members"] for b in summary.built] == [2, 2, 1]
    assert summary.price_failures == 1
    assert summary.coverage["members"] == 2
    assert summary.coverage["none"] == 1
    scope = yaml.safe_load(minio.objects["universe/1/backfill_scope.yaml"])
    assert [c["cik"] for c in scope["companies"]] == ["0000000001", "0000000002"]
    assert json.loads(minio.objects["universe/1/coverage.json"])["delisted"] == 1
    assert "universe/1/rules.yaml" in minio.objects


def test_build_job_with_every_month_stored_downloads_nothing(tmp_path: Path) -> None:
    minio, filings = _FakeMinio(), _Filings()
    _job(tmp_path, minio, filings, date(2024, 3, 1)).run()

    summary = _job(tmp_path, minio, filings, date(2024, 3, 28)).run()

    assert filings.loads == 1
    assert summary.built == ()
    assert summary.already_stored == 3


def test_build_job_prices_every_company_listed_in_the_window_including_delisted(
    tmp_path: Path,
) -> None:
    prices = _Prices()
    job = _job(tmp_path, _FakeMinio(), _Filings(), date(2024, 3, 1))
    job._prices = prices  # type: ignore[assignment]

    job.run()

    assert prices.prepared == ["ALPH", "GONE"]


def test_months_due_stop_at_the_last_rebalance_on_or_before_today() -> None:
    rules = parse_rules(_RULES_YAML)
    cal = MarketCalendar()

    assert months_due(rules, date(2024, 3, 1), cal) == ["2024-01", "2024-02", "2024-03"]
    assert months_due(rules, date(2024, 2, 29), cal) == ["2024-01", "2024-02"]
    # Saturday 2024-06-01: June's first session is Monday the 3rd.
    assert months_due(rules, date(2024, 6, 1), cal)[-1] == "2024-05"
    bounded = parse_rules(_RULES_YAML.replace("end: null", "end: 2024-01-31"))
    assert months_due(bounded, date(2024, 6, 3), cal) == ["2024-01"]


def test_rules_without_monthly_rebalance_are_refused() -> None:
    with pytest.raises(ValueError, match="weekly"):
        parse_rules(_RULES_YAML.replace("rebalance: monthly", "rebalance: weekly"))


# --- HTTP API ----------------------------------------------------------------------------------


def _client(job: MagicMock):  # type: ignore[no-untyped-def]
    return create_app(refresher=MagicMock(), tickers=[], universe_job=lambda: job).test_client()


def test_universe_build_endpoint_returns_the_build_summary() -> None:
    job = MagicMock()
    job.run.return_value.as_dict.return_value = {"rules_version": 1, "built": []}

    resp = _client(job).post("/universe/build")

    assert resp.status_code == 200
    assert resp.get_json() == {"rules_version": 1, "built": []}


def test_universe_build_endpoint_reports_an_unreachable_source_as_bad_gateway() -> None:
    job = MagicMock()
    job.run.side_effect = OSError("sec.gov unreachable")

    resp = _client(job).post("/universe/build")

    assert resp.status_code == 502
    assert "sec.gov" in resp.get_json()["error"]


def test_universe_build_endpoint_refuses_edited_rules_without_a_version_bump() -> None:
    job = MagicMock()
    job.run.side_effect = RulesVersionError("rules.yaml changed but is still version 1")

    resp = _client(job).post("/universe/build")

    assert resp.status_code == 409


def test_build_job_stores_latest_listings_that_a_backtest_loads_as_membership(
    tmp_path: Path,
) -> None:
    from auspex_backtesting.backtest.membership import load_membership

    minio = _ListingMinio()
    _job(tmp_path, minio, _Filings(), date(2024, 3, 1)).run()

    membership = load_membership(UniverseStore(minio), 1)  # type: ignore[arg-type]

    assert membership.as_of == date(2024, 3, 1)
    gone = membership.member("GONE", date(2024, 2, 5))
    assert gone is not None and gone.exited_on == date(2024, 2, 15)
    assert membership.member("GONE", date(2024, 3, 4)) is None
    assert membership.member("ALPH", date(2024, 3, 4)) is not None


def test_backtest_membership_without_stored_listings_is_refused() -> None:
    from auspex_backtesting.backtest.membership import load_membership

    with pytest.raises(LookupError, match="listings"):
        load_membership(UniverseStore(_ListingMinio()), 1)  # type: ignore[arg-type]


def test_listings_carry_an_exit_that_happened_after_a_month_was_stored(tmp_path: Path) -> None:
    from auspex_backtesting.universe import UniverseBuilder, coverage_report
    from auspex_backtesting.universe.rules import parse_rules

    rules = parse_rules(_RULES_YAML)
    listed = CompanyRecord("1", "Late", "2836", ("Nasdaq",), ("LATE",),
                           (Filing("8-A12B", date(2019, 5, 1)),))
    acquired = CompanyRecord("1", "Late", "2836", (), (), (
        Filing("8-A12B", date(2019, 5, 1)),
        Filing("10-Q", date(2024, 2, 10), (), "late-20231231.htm"),
        Filing("8-K", date(2024, 4, 9), ("5.01",)),
        Filing("25-NSE", date(2024, 4, 10)),
    ))
    prices = _Prices()
    march = UniverseBuilder(rules, [listed], {}, prices, as_of=date(2024, 3, 1)).build("2024-03")
    later = UniverseBuilder(rules, [acquired], {}, prices, as_of=date(2024, 5, 1)).listings()

    (row,) = later
    assert row.exited_on == date(2024, 4, 10) and row.exit_reason == "acquired"
    report = coverage_report([march], later)
    assert report.delisted == 1


def test_listings_leave_out_spans_that_ended_before_the_window() -> None:
    from auspex_backtesting.universe import UniverseBuilder
    from auspex_backtesting.universe.rules import parse_rules

    relisted = CompanyRecord("1", "Back", "2836", ("Nasdaq",), ("BACK",), (
        Filing("8-A12B", date(2015, 5, 1)),
        Filing("25-NSE", date(2018, 6, 1)),
        Filing("8-A12B", date(2023, 6, 1)),
    ))

    rows = UniverseBuilder(
        parse_rules(_RULES_YAML), [relisted], {}, _Prices(), as_of=date(2024, 3, 1)
    ).listings()

    assert [r.entered_on for r in rows] == [date(2023, 6, 1)]


class _ListingMinio(_FakeMinio):
    def list_objects(self, bucket: str, prefix: str) -> list[MagicMock]:
        objects = []
        for key in sorted(self.objects):
            if key.startswith(prefix):
                obj = MagicMock()
                obj.object_name = key
                objects.append(obj)
        return objects
