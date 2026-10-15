"""`scripts/run_portfolio_backtest.py` end to end, over an in-memory MinIO filled through the
real universe, score and price stores."""

import importlib.util
import io
import json
from datetime import date
from pathlib import Path

import pytest
from ownership_fakes import FakeMinio
from portfolio_support import (
    RUN_START,
    SCORE,
    plant_top_quintile_edge,
    registered_config,
    world,
)

from auspex_backtesting.portfolio import InputsNotPinnedError, ScoreSnapshot, ScoreStore
from auspex_backtesting.prices.snapshot_store import snapshot_key, snapshot_parquet
from auspex_backtesting.universe.store import UniverseStore

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_portfolio_backtest.py"


def _script():
    spec = importlib.util.spec_from_file_location("run_portfolio_backtest", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stocked_minio():
    w = world(100, score_fn=lambda i, d: -float(i))
    plant_top_quintile_edge(w, 0.01, RUN_START, date(2022, 12, 31))
    minio = FakeMinio()
    for ticker, frame in w.prices.frames.items():
        data = snapshot_parquet(frame, None)
        minio.put_object("auspex-prices", snapshot_key(ticker), io.BytesIO(data), len(data))
    universe = UniverseStore(minio)
    for month in w.universe.months:
        universe.write(w.universe.read(1, month))
    universe.write_listings(1, w.universe.members, w.universe.read_listings(1)[1])
    scores = ScoreStore(minio)
    for d in w.scores.dates(SCORE.hypothesis_id, SCORE.version):
        rows = w.scores.read(SCORE.hypothesis_id, SCORE.version, d).rows
        scores.write(ScoreSnapshot(SCORE.hypothesis_id, SCORE.version, d, rows))
    return minio


@pytest.fixture
def env(monkeypatch):
    for name, value in {
        "MINIO_ENDPOINT": "minio:9000",
        "MINIO_ACCESS_KEY": "key",
        "MINIO_SECRET_KEY": "secret",
        "PAPER_CAPITAL_TIERS_EUR": "10000,50000",
        "IBKR_PRICING": "tiered",
    }.items():
        monkeypatch.setenv(name, value)


def test_script_runs_the_primary_cell_at_every_tier_and_writes_report_and_verdict(
    tmp_path, env, capsys
):
    config_dir, _ = registered_config(tmp_path)
    module = _script()
    minio = _stocked_minio()
    module.Minio = lambda *a, **k: minio
    out = tmp_path / "out"
    module.main(
        [
            "h9",
            "--score-version",
            SCORE.version,
            "--universe-version",
            "1",
            "--config-dir",
            str(config_dir),
            "--out-dir",
            str(out),
        ]
    )

    printed = json.loads(capsys.readouterr().out)
    assert printed["verdict"]["status"] == "in_sample_passed"
    report_path, verdict_path = (Path(p) for p in printed["files"])
    assert report_path.parent == verdict_path.parent == out
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["cell"] == {"cadence": "monthly_top15", "catalyst_guard": "none"}
    assert set(report["in_sample"]) == {"10000.0", "50000.0"}
    assert report["holdout"] == {}
    assert json.loads(verdict_path.read_text(encoding="utf-8"))["holdout_read"] is False
    (ledger_line,) = (config_dir / "trials" / "h9.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(ledger_line)["cells"] == [report["cell"]]


def test_script_cell_override_and_final_run_without_manifests(tmp_path, env):
    config_dir, _ = registered_config(tmp_path)
    module = _script()
    minio = _stocked_minio()
    module.Minio = lambda *a, **k: minio
    args = [
        "h9",
        "--score-version",
        SCORE.version,
        "--universe-version",
        "1",
        "--config-dir",
        str(config_dir),
        "--out-dir",
        str(tmp_path / "out"),
    ]
    with pytest.raises(InputsNotPinnedError):
        module.main([*args, "--final"])
    assert not (config_dir / "trials" / "h9.jsonl").exists()

    module.main([*args, "--cell", "catalyst_guard=skip_entry"])
    (line,) = (config_dir / "trials" / "h9.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(line)["cells"] == [
        {"cadence": "monthly_top15", "catalyst_guard": "skip_entry"}
    ]
