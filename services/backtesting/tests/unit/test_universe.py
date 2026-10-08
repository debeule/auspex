import io
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from minio.error import S3Error

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.universe import (
    CompanyRecord,
    Filing,
    RulesVersionError,
    ShareCount,
    SnapshotExistsError,
    UniverseBuilder,
    UniverseMember,
    UniverseRules,
    UniverseSnapshot,
    UniverseStore,
    backfill_scope,
    coverage_report,
    load_rules,
    rebalance_date,
)

_CAL = MarketCalendar()

_RULES = UniverseRules(
    version=1,
    sic_codes=frozenset({"2834", "2836", "8731"}),
    exchanges=frozenset({"NYSE", "Nasdaq", "NYSE American"}),
    min_market_cap_usd=50_000_000.0,
    min_median_dollar_volume_usd=500_000.0,
    liquidity_sessions=20,
    window_start=date(2024, 1, 1),
    window_end=None,
)

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


def _filing(form: str, filed: str, items: str = "", document: str = "") -> Filing:
    return Filing(
        form=form,
        filed=date.fromisoformat(filed),
        items=tuple(i for i in items.split(",") if i),
        primary_document=document,
    )


def _company(
    cik: str = "0000000001",
    *,
    name: str = "Alpha Therapeutics",
    sic: str = "2836",
    exchanges: tuple[str, ...] = ("Nasdaq",),
    tickers: tuple[str, ...] = ("ALPH",),
    filings: Iterable[Filing] = (),
) -> CompanyRecord:
    return CompanyRecord(
        cik=cik,
        name=name,
        sic=sic,
        exchanges=exchanges,
        tickers=tickers,
        filings=tuple(filings) or (_filing("8-A12B", "2019-05-01"),),
    )


def _bars(start: str, end: str, close: float = 10.0, volume: float = 100_000.0) -> pd.DataFrame:
    sessions = _CAL.sessions_between(date.fromisoformat(start), date.fromisoformat(end))
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in sessions], tz="UTC", name="date")
    n = len(sessions)
    return pd.DataFrame(
        {"open": [close] * n, "high": [close] * n, "low": [close] * n,
         "close": [close] * n, "volume": [volume] * n},
        index=idx,
    )


class _Prices:
    def __init__(
        self,
        bars: dict[str, pd.DataFrame],
        splits: dict[str, pd.Series] | None = None,
    ) -> None:
        self._bars = bars
        self._splits = splits or {}

    def bars(self, ticker: str) -> pd.DataFrame | None:
        return self._bars.get(ticker)

    def splits(self, ticker: str) -> pd.Series:
        return self._splits.get(ticker, pd.Series(dtype=float))


def _shares(filed: str, value: float, end: str | None = None) -> ShareCount:
    return ShareCount(
        value=value,
        end=date.fromisoformat(end or filed),
        filed=date.fromisoformat(filed),
    )


def _builder(
    companies: list[CompanyRecord],
    bars: dict[str, pd.DataFrame],
    shares: dict[str, list[ShareCount]] | None = None,
    *,
    as_of: date = date(2024, 9, 30),
    splits: dict[str, pd.Series] | None = None,
) -> UniverseBuilder:
    default_shares = {c.cik: [_shares("2023-11-10", 20_000_000)] for c in companies}
    return UniverseBuilder(
        _RULES,
        companies,
        shares if shares is not None else default_shares,
        _Prices(bars, splits),
        as_of=as_of,
    )


def _members(snapshot: UniverseSnapshot) -> dict[str, UniverseMember]:
    return {m.cik: m for m in snapshot.members}


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


# --- admission rules -------------------------------------------------------------------------


def test_member_admitted_only_with_data_public_on_rebalance_date() -> None:
    # Rebalance 2024-03-01. The 50M-share fact is filed the next day and must not be used.
    company = _company()
    shares = {company.cik: [_shares("2024-02-10", 10_000_000), _shares("2024-03-02", 50_000_000)]}
    bars = {"ALPH": _bars("2023-12-01", "2024-09-30", close=10.0)}

    member = _members(_builder([company], bars, shares).build("2024-03"))[company.cik]

    assert member.market_cap_usd == pytest.approx(100_000_000.0)


def test_share_count_filed_on_the_rebalance_date_itself_is_not_used() -> None:
    # A date-only filing could have been accepted after the open, so it counts from the next day.
    company = _company()
    shares = {company.cik: [_shares("2024-02-10", 10_000_000), _shares("2024-03-01", 50_000_000)]}
    bars = {"ALPH": _bars("2023-12-01", "2024-09-30", close=10.0)}

    member = _members(_builder([company], bars, shares).build("2024-03"))[company.cik]

    assert member.market_cap_usd == pytest.approx(100_000_000.0)


def test_market_cap_uses_the_last_close_before_the_rebalance_session() -> None:
    company = _company()
    bars = _bars("2023-12-01", "2024-02-29", close=10.0)
    bars = pd.concat([bars, _bars("2024-03-01", "2024-09-30", close=1.0)])

    member = _members(_builder([company], {"ALPH": bars}).build("2024-03"))[company.cik]

    assert member.market_cap_usd == pytest.approx(200_000_000.0)


def test_market_cap_restates_pre_split_share_counts_onto_the_adjusted_price_basis() -> None:
    # Adjusted closes are on today's share basis. A 1-for-10 reverse split after the count date
    # turns 100M reported shares into 10M, so cap = 10M x $10, not 100M x $10.
    company = _company()
    shares = {company.cik: [_shares("2024-02-10", 100_000_000, end="2024-02-05")]}
    splits = {"ALPH": pd.Series([0.1], index=pd.DatetimeIndex(["2024-06-03"], tz="UTC"))}
    bars = {"ALPH": _bars("2023-12-01", "2024-09-30", close=10.0)}

    member = _members(_builder([company], bars, shares, splits=splits).build("2024-03"))[company.cik]

    assert member.market_cap_usd == pytest.approx(100_000_000.0)


def test_split_between_the_count_date_and_the_rebalance_is_applied_to_the_count() -> None:
    # 100M shares counted on 2024-01-31, then a 1-for-10 reverse split before the March rebalance.
    company = _company()
    shares = {company.cik: [_shares("2024-02-10", 100_000_000, end="2024-01-31")]}
    splits = {"ALPH": pd.Series([0.1], index=pd.DatetimeIndex(["2024-02-20"], tz="UTC"))}
    bars = {"ALPH": _bars("2023-12-01", "2024-09-30", close=10.0)}

    member = _members(_builder([company], bars, shares, splits=splits).build("2024-03"))[company.cik]

    assert member.market_cap_usd == pytest.approx(100_000_000.0)


def test_company_below_market_cap_floor_is_excluded() -> None:
    small = _company("0000000002", tickers=("SMAL",))
    shares = {small.cik: [_shares("2024-02-10", 4_000_000)]}  # 4M x $10 = $40M
    bars = {"SMAL": _bars("2023-12-01", "2024-09-30", close=10.0)}

    snapshot = _builder([small], bars, shares).build("2024-03")

    assert small.cik not in _members(snapshot)


def test_company_below_liquidity_floor_is_excluded() -> None:
    thin = _company("0000000003", tickers=("THIN",))
    bars = {"THIN": _bars("2023-12-01", "2024-09-30", close=10.0, volume=40_000.0)}  # $400k/day

    snapshot = _builder([thin], bars).build("2024-03")

    assert thin.cik not in _members(snapshot)


def test_liquidity_is_the_median_dollar_volume_of_the_twenty_sessions_before_rebalance() -> None:
    company = _company()
    early = _bars("2023-12-01", "2024-01-31", close=10.0, volume=10_000.0)
    recent = _bars("2024-02-01", "2024-02-29", close=10.0, volume=60_000.0)
    later = _bars("2024-03-01", "2024-09-30", close=10.0, volume=1.0)
    bars = {"ALPH": pd.concat([early, recent, later])}

    member = _members(_builder([company], bars).build("2024-03"))[company.cik]

    assert member.median_dollar_volume_20d == pytest.approx(600_000.0)


def test_company_with_excluded_sic_code_is_excluded() -> None:
    devices = _company("0000000004", sic="3841", tickers=("DEVC",))
    bars = {"DEVC": _bars("2023-12-01", "2024-09-30")}

    assert devices.cik not in _members(_builder([devices], bars).build("2024-03"))


def test_company_listed_only_over_the_counter_is_excluded() -> None:
    otc = _company(
        "0000000005", exchanges=("OTC",), tickers=("OTCX",),
        filings=[_filing("10-K", "2023-03-01")],
    )
    bars = {"OTCX": _bars("2023-12-01", "2024-09-30")}

    assert otc.cik not in _members(_builder([otc], bars).build("2024-03"))


def test_twelve_g_deregistration_without_exchange_listing_never_makes_a_member() -> None:
    # 15-12G ends a 12(g) registration (OTC); without an 8-A12B the company was never listed.
    otc = _company(
        "0000000006", exchanges=(), tickers=(),
        filings=[_filing("10-K", "2022-03-01"), _filing("15-12G", "2024-06-01")],
    )

    assert otc.cik not in _members(_builder([otc], {}).build("2024-03"))


# --- listing history ---------------------------------------------------------------------------


def test_delisted_company_is_a_member_until_its_delisting_notice() -> None:
    gone = _company(
        exchanges=(), tickers=(),
        filings=[
            _filing("8-A12B", "2019-05-01"),
            _filing("10-Q", "2023-11-10", document="gone-20230930.htm"),
            _filing("25-NSE", "2024-03-15"),
        ],
    )
    bars = {"GONE": _bars("2023-12-01", "2024-03-14")}
    builder = _builder([gone], bars)

    march = _members(builder.build("2024-03"))
    april = _members(builder.build("2024-04"))

    assert march[gone.cik].exited_on == date(2024, 3, 15)
    assert march[gone.cik].exit_reason == "delisted"
    assert gone.cik not in april


def test_delisting_after_a_change_of_control_report_is_an_acquisition() -> None:
    bought = _company(
        exchanges=(), tickers=(),
        filings=[
            _filing("8-A12B", "2019-05-01"),
            _filing("10-Q", "2023-11-10", document="buy-20230930.htm"),
            _filing("8-K", "2024-03-14", items="2.01,3.01,5.01,9.01"),
            _filing("25-NSE", "2024-03-15"),
            _filing("15-12B", "2024-03-25"),
        ],
    )
    bars = {"BUY": _bars("2023-12-01", "2024-03-14")}

    member = _members(_builder([bought], bars).build("2024-03"))[bought.cik]

    assert member.exited_on == date(2024, 3, 15)
    assert member.exit_reason == "acquired"


def test_ipo_company_enters_on_first_rebalance_after_listing() -> None:
    ipo = _company(
        tickers=("NEWB",),
        filings=[_filing("8-A12B", "2024-02-14"), _filing("424B4", "2024-02-16")],
    )
    bars = {"NEWB": _bars("2024-02-15", "2024-09-30")}
    builder = _builder([ipo], bars, {ipo.cik: []})

    assert ipo.cik not in _members(builder.build("2024-02"))
    member = _members(builder.build("2024-03"))[ipo.cik]
    assert member.entered_on == date(2024, 2, 14)


def test_deregistration_filing_ends_membership_with_exit_reason_deregistered() -> None:
    quiet = _company(
        exchanges=(), tickers=(),
        filings=[
            _filing("8-A12B", "2019-05-01"),
            _filing("10-Q", "2023-11-10", document="qut-20230930.htm"),
            _filing("15-12B", "2024-03-20"),
        ],
    )
    builder = _builder([quiet], {"QUT": _bars("2023-12-01", "2024-03-19")})

    member = _members(builder.build("2024-03"))[quiet.cik]

    assert member.exit_reason == "deregistered"
    assert member.exited_on == date(2024, 3, 20)
    assert quiet.cik not in _members(builder.build("2024-04"))


def test_registration_filed_on_the_rebalance_date_waits_for_the_next_month() -> None:
    ipo = _company(tickers=("NEWB",), filings=[_filing("8-A12B", "2024-03-01")])
    builder = _builder([ipo], {"NEWB": _bars("2024-03-04", "2024-09-30")}, {ipo.cik: []})

    assert ipo.cik not in _members(builder.build("2024-03"))
    assert ipo.cik in _members(builder.build("2024-04"))


def test_delisting_notice_filed_on_the_rebalance_date_still_counts_that_month() -> None:
    gone = _company(
        exchanges=(), tickers=(),
        filings=[_filing("8-A12B", "2019-05-01"), _filing("25-NSE", "2024-03-01")],
    )

    assert gone.cik in _members(_builder([gone], {}).build("2024-03"))


def test_relisting_after_a_delisting_opens_a_new_membership_span() -> None:
    back = _company(
        filings=[
            _filing("8-A12B", "2015-05-01"),
            _filing("25-NSE", "2018-06-01"),
            _filing("8-A12B", "2024-02-20"),
        ],
    )
    builder = _builder([back], {"ALPH": _bars("2024-02-21", "2024-09-30")}, {back.cik: []})

    assert back.cik not in _members(builder.build("2024-02"))
    member = _members(builder.build("2024-03"))[back.cik]
    assert member.entered_on == date(2024, 2, 20)


def test_delisting_notice_for_another_class_does_not_end_a_listed_company() -> None:
    # Warrants delisted in 2023 while the common stock is still on Nasdaq today.
    listed = _company(filings=[_filing("8-A12B", "2019-05-01"), _filing("25-NSE", "2023-06-01")])

    member = _members(_builder([listed], {"ALPH": _bars("2023-12-01", "2024-09-30")}).build(
        "2024-03"))[listed.cik]

    assert member.exited_on is None


def test_company_listed_before_edgar_counts_from_its_first_filing() -> None:
    old = _company(filings=[_filing("10-K", "1996-03-01")])

    member = _members(_builder([old], {"ALPH": _bars("2023-12-01", "2024-09-30")}).build(
        "2024-03"))[old.cik]

    assert member.entered_on == date(1996, 3, 1)


def test_inactive_filer_without_exit_notice_leaves_at_its_last_filing() -> None:
    lapsed = _company(
        exchanges=(), tickers=(),
        filings=[
            _filing("8-A12B", "2019-05-01"),
            _filing("10-Q", "2024-05-10", document="lap-20240331.htm"),
        ],
    )
    builder = _builder([lapsed], {"LAP": _bars("2023-12-01", "2024-05-10")})

    member = _members(builder.build("2024-05"))[lapsed.cik]

    assert member.exited_on == date(2024, 5, 10)
    assert member.exit_reason == "deregistered"
    assert lapsed.cik not in _members(builder.build("2024-06"))


def test_rebalance_date_is_first_nyse_session_of_the_month() -> None:
    assert rebalance_date("2024-01") == date(2024, 1, 2)  # New Year's Day
    assert rebalance_date("2023-07") == date(2023, 7, 3)  # weekend
    assert rebalance_date("2024-03") == date(2024, 3, 1)
    snapshot = _builder([_company()], {"ALPH": _bars("2023-12-01", "2024-09-30")}).build("2024-01")
    assert snapshot.rebalance_date == date(2024, 1, 2)


# --- tickers and price coverage --------------------------------------------------------------


def test_ticker_without_filing_history_is_stamped_current() -> None:
    company = _company(filings=[_filing("8-A12B", "2019-05-01"), _filing("10-K", "2024-02-01")])

    member = _members(_builder([company], {"ALPH": _bars("2023-12-01", "2024-09-30")}).build(
        "2024-03"))[company.cik]

    assert member.ticker == "ALPH"
    assert member.ticker_source == "current"


def test_delisted_company_takes_its_ticker_from_filing_document_names() -> None:
    gone = _company(
        exchanges=(), tickers=(),
        filings=[
            _filing("8-A12B", "2019-05-01"),
            _filing("10-K", "2023-03-01", document="oldt-20221231.htm"),
            _filing("10-Q", "2023-11-10", document="gone-20230930.htm"),
            _filing("8-K", "2023-12-01", document="tm2331234d1_8k.htm"),
            _filing("25-NSE", "2024-05-15"),
        ],
    )

    member = _members(_builder([gone], {"GONE": _bars("2023-12-01", "2024-05-14")}).build(
        "2024-03"))[gone.cik]

    assert member.ticker == "GONE"
    assert member.ticker_source == "filing"


def test_member_without_any_ticker_stays_in_snapshot_unresolved() -> None:
    ghost = _company(
        exchanges=(), tickers=(),
        filings=[_filing("8-A12B", "2019-05-01"), _filing("25-NSE", "2024-05-15")],
    )

    member = _members(_builder([ghost], {}).build("2024-03"))[ghost.cik]

    assert member.ticker is None
    assert member.ticker_source == "unresolved"
    assert member.price_coverage == "none"


def test_member_without_price_history_stays_in_snapshot_with_coverage_none() -> None:
    gone = _company(
        exchanges=(), tickers=(),
        filings=[
            _filing("8-A12B", "2019-05-01"),
            _filing("10-Q", "2023-11-10", document="gone-20230930.htm"),
            _filing("25-NSE", "2024-05-15"),
        ],
    )

    member = _members(_builder([gone], {}).build("2024-03"))[gone.cik]

    assert member.price_coverage == "none"
    assert member.market_cap_usd is None
    assert member.median_dollar_volume_20d is None


def test_prices_continuing_after_exit_belong_to_a_reused_ticker_and_are_discarded() -> None:
    # Yahoo reassigns a delisted symbol; bars months after the exit are another issuer's.
    gone = _company(
        exchanges=(), tickers=(),
        filings=[
            _filing("8-A12B", "2019-05-01"),
            _filing("10-Q", "2023-11-10", document="gone-20230930.htm"),
            _filing("25-NSE", "2024-05-15"),
        ],
    )

    member = _members(_builder([gone], {"GONE": _bars("2023-12-01", "2024-09-30")}).build(
        "2024-03"))[gone.cik]

    assert member.price_coverage == "none"
    assert "reused" in member.coverage_note


def test_prices_starting_after_listing_give_partial_coverage() -> None:
    company = _company()

    member = _members(_builder([company], {"ALPH": _bars("2024-02-01", "2024-09-30")}).build(
        "2024-03"))[company.cik]

    assert member.price_coverage == "partial"


def test_coverage_report_lists_every_member_without_full_price_history() -> None:
    full = _company("0000000001", tickers=("FULL",))
    late = _company("0000000002", tickers=("LATE",))
    none = _company(
        "0000000003", exchanges=(), tickers=(),
        filings=[_filing("8-A12B", "2019-05-01"), _filing("25-NSE", "2024-05-15")],
    )
    bars = {"FULL": _bars("2023-12-01", "2024-09-30"), "LATE": _bars("2024-02-01", "2024-09-30")}
    builder = _builder([full, late, none], bars)

    report = coverage_report([builder.build("2024-03"), builder.build("2024-04")])

    assert report.members == 3
    assert report.complete == 1
    assert sorted(g.cik for g in report.gaps) == ["0000000002", "0000000003"]
    assert {g.cik: g.price_coverage for g in report.gaps} == {
        "0000000002": "partial", "0000000003": "none",
    }
    assert all(g.note for g in report.gaps)


# --- rules, storage, determinism, scope --------------------------------------------------------


def test_rules_file_loads_into_universe_rules(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(_RULES_YAML, encoding="utf-8")

    assert load_rules(path) == _RULES


def test_rules_file_change_without_version_bump_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    store = UniverseStore(_FakeMinio())
    path.write_text(_RULES_YAML, encoding="utf-8")
    store.lock_rules(path)

    path.write_text(_RULES_YAML.replace("50000000", "100000000"), encoding="utf-8")
    with pytest.raises(RulesVersionError, match="version 1"):
        store.lock_rules(path)

    path.write_text(
        _RULES_YAML.replace("50000000", "100000000").replace("version: 1", "version: 2"),
        encoding="utf-8",
    )
    store.lock_rules(path)


def test_snapshot_is_written_under_rules_version_and_never_overwritten() -> None:
    minio = _FakeMinio()
    store = UniverseStore(minio)
    builder = _builder([_company()], {"ALPH": _bars("2023-12-01", "2024-09-30")})
    snapshot = builder.build("2024-03")

    store.write(snapshot)
    with pytest.raises(SnapshotExistsError):
        store.write(snapshot)

    assert minio.puts == ["universe/1/2024-03.parquet"]
    assert store.exists(1, "2024-03")
    assert store.read(1, "2024-03") == snapshot


def test_universe_build_is_deterministic_for_the_same_inputs() -> None:
    companies = [_company(f"000000000{i}", tickers=(f"T{i}",)) for i in (3, 1, 2)]
    bars = {f"T{i}": _bars("2023-12-01", "2024-09-30") for i in (1, 2, 3)}

    first, second = _FakeMinio(), _FakeMinio()
    UniverseStore(first).write(_builder(companies, bars).build("2024-03"))
    UniverseStore(second).write(
        _builder(list(reversed(companies)), bars).build("2024-03")
    )

    assert first.objects == second.objects
    snapshot = _builder(companies, bars).build("2024-03")
    assert [m.cik for m in snapshot.members] == ["0000000001", "0000000002", "0000000003"]


def test_backfill_scope_export_is_the_union_of_members_over_the_window() -> None:
    a = _company("0000000001", name="A", tickers=("AAAA",))
    b = _company("0000000002", name="B", tickers=("BBBB",))
    late = _company(
        "0000000003", name="C", tickers=("CCCC",), filings=[_filing("8-A12B", "2024-02-14")]
    )
    gone = _company(
        "0000000004", name="D", exchanges=(), tickers=(),
        filings=[_filing("8-A12B", "2019-05-01"), _filing("25-NSE", "2024-01-20")],
    )
    bars = {t: _bars("2023-12-01", "2024-09-30") for t in ("AAAA", "BBBB", "CCCC")}
    builder = _builder([a, b, late, gone], bars, {c.cik: [] for c in (a, b, late, gone)})
    snapshots = [builder.build(m) for m in ("2024-01", "2024-02", "2024-03")]

    scope = backfill_scope(snapshots, start="2024-01", end="2024-02")

    assert scope["rules_version"] == 1
    assert scope["window"] == {"start": "2024-01", "end": "2024-02"}
    assert [c["cik"] for c in scope["companies"]] == ["0000000001", "0000000002", "0000000004"]
    assert scope["companies"][0] == {"cik": "0000000001", "ticker": "AAAA", "name": "A"}


def test_snapshot_month_before_the_rules_window_is_refused() -> None:
    with pytest.raises(ValueError, match="2023-12"):
        _builder([_company()], {}).build("2023-12")


def test_snapshot_month_whose_rebalance_is_after_as_of_is_refused() -> None:
    builder = _builder([_company()], {}, as_of=date(2024, 3, 1))

    builder.build("2024-03")
    with pytest.raises(ValueError, match="2024-04"):
        builder.build("2024-04")

