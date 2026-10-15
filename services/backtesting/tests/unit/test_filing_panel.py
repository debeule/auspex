from datetime import date

from catalyst_support import FakeWeb
from filing_support import (
    ACME,
    ARCHIVES,
    BETA,
    FULL_INDEX,
    TODAY,
    USER_AGENT,
    StoreMinio,
    filing_index,
    filing_pages,
    member,
    quarter_index,
    risk_document,
)

from auspex_backtesting.catalysts import HttpSource
from auspex_backtesting.filings import FilingPanelBuild, FilingSectionArchive, score_version
from auspex_backtesting.portfolio.scores import ScoreStore
from auspex_backtesting.universe import UniverseSnapshot, UniverseStore


def _web(refuse_after: int | None = None) -> tuple[FakeWeb, dict[str, str]]:
    k22, k23, k23a = f"{ACME}-23-000001", f"{ACME}-24-000001", f"{ACME}-24-000002"
    other = f"{BETA}-24-000001"
    pages = {
        **filing_pages(ACME, k22, "10-K", "2023-03-01 16:05:00", "2022-12-31",
                       risk_document("10-K", "Our trials may fail.")),
        **filing_pages(ACME, k23, "10-K", "2024-02-28 16:05:00", "2023-12-31",
                       risk_document("10-K", "Our trials may fail and we need capital.")),
        f"{FULL_INDEX}/2023/QTR1/master.idx": quarter_index([(ACME, "10-K", "2023-03-01", k22)]),
        f"{FULL_INDEX}/2024/QTR1/master.idx": quarter_index([
            (ACME, "10-K", "2024-02-28", k23),
            (ACME, "10-K/A", "2024-03-15", k23a),
            (BETA, "10-K", "2024-02-20", other),
        ]),
    }
    return FakeWeb(pages, refuse_after=refuse_after), pages


def _build(web: FakeWeb, minio: StoreMinio) -> FilingPanelBuild:
    universe = UniverseStore(minio)  # type: ignore[arg-type]
    for month, rebalance in (("2024-03", date(2024, 3, 1)), ("2024-04", date(2024, 4, 1))):
        if not universe.exists(1, month):
            universe.write(UniverseSnapshot(1, month, rebalance, (member(ACME, "ACME"),)))
    sec = HttpSource(USER_AGENT, 0.0, fetch=web, sleep=lambda _: None)
    return FilingPanelBuild(
        filing_index(web, minio),
        FilingSectionArchive(minio, ARCHIVES, sec),  # type: ignore[arg-type]
        universe,
        1,
        ScoreStore(minio),  # type: ignore[arg-type]
        "h10",
        score_version(1, universe.universe),
        today=lambda: TODAY,
    )


def test_panel_build_writes_a_snapshot_per_universe_month_and_reports_coverage() -> None:
    web, _ = _web()
    minio = StoreMinio()

    summary = _build(web, minio).run()

    assert summary["complete"] is True
    assert summary["filings_found"] == 3
    assert summary["amendments_not_cut"] == 1
    assert summary["sections"] == {"cut": 2}
    assert summary["scores"] == 1
    assert summary["unscored"] == {"no_comparison": 1}
    assert [m["month"] for m in summary["months"]] == ["2024-03", "2024-04"]
    assert all(m["scored"] == 1 and m["left_out"] == 0 for m in summary["months"])
    snapshot = ScoreStore(minio).read("h10", "1", date(2024, 3, 1))  # type: ignore[arg-type]
    assert snapshot is not None and snapshot.rows["cik"].tolist() == [ACME]


def test_panel_build_run_again_fetches_nothing_and_rewrites_no_snapshot() -> None:
    web, _ = _web()
    minio = StoreMinio()
    _build(web, minio).run()
    requested = len(web.requested)

    summary = _build(web, minio).run()

    assert summary["snapshots_written"] == 0
    assert summary["snapshots_already_stored"] == 2
    # Only quarters with no stored rows (here: unpublished ones) are asked for again.
    again = web.requested[requested:]
    assert again and all(url.endswith("master.idx") for url in again)
    assert f"{FULL_INDEX}/2024/QTR1/master.idx" not in again


def test_panel_build_stopped_by_sec_writes_no_snapshot() -> None:
    web, _ = _web(refuse_after=4)
    minio = StoreMinio()

    summary = _build(web, minio).run()

    assert summary["complete"] is False
    assert not any(k.startswith("scores/") for k in minio.objects)
