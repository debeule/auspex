"""Run a registered portfolio hypothesis at every capital tier and write its report and verdict.

Reserves the cell in the family's trial ledger before any return is read, so every run spends
budget. Without `--cell` the hypothesis's primary cell runs. `--final` reads the holdout once,
after the in-sample verdict passes; it is refused while any universe or score snapshot the run
reads has no input manifest, which is every snapshot until the research input archive exists.
A `floor` axis is applied in the score, not here: pass the score version written for that floor.

Usage:
    uv run python scripts/run_portfolio_backtest.py h9 --score-version 1 --universe-version 1
    uv run python scripts/run_portfolio_backtest.py h9 --score-version 1 --universe-version 1 \\
        --cell cadence=quarterly_top15 --cell catalyst_guard=none --cell floor=floor \\
        --filter-score h10:1

Run from services/backtesting with the MinIO, cost and PAPER_CAPITAL_TIERS_EUR variables of
.env.example set. Writes `<hypothesis>-<run id>.json` (report) and `...-verdict.json` under
`--out-dir`, and prints the verdict. Record a final verdict in DECISIONS.md.
"""

import argparse
import json
import logging
import os
from pathlib import Path

import yaml
from minio import Minio

from auspex_backtesting.catalysts.panel import CatalystPanel
from auspex_backtesting.hypothesis import hypothesis_views
from auspex_backtesting.market_sim import CostModel, CostParameters, SpreadEstimator
from auspex_backtesting.portfolio import (
    EqualRiskSizer,
    HoldoutRecord,
    NoInputManifests,
    PortfolioBacktest,
    PortfolioEvaluation,
    PortfolioRule,
    ScoreRef,
    ScoreStore,
    write_report,
)
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore
from auspex_backtesting.protocol import EvaluationProtocol
from auspex_backtesting.universe.store import UniverseStore

_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "hypotheses"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("hypothesis_id")
    parser.add_argument("--use", help="the use to run, for a hypothesis with several")
    parser.add_argument("--score-version", required=True)
    parser.add_argument("--universe-version", type=int, required=True)
    parser.add_argument("--cell", action="append", default=[], metavar="AXIS=VALUE")
    parser.add_argument(
        "--filter-score",
        metavar="HYPOTHESIS:VERSION",
        help="score whose bottom quintile is excluded",
    )
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=Path("reports/portfolio"))
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=_CONFIG_DIR,
        help="registered hypotheses, trial ledger and holdout record",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    protocol = EvaluationProtocol(
        config_dir=args.config_dir, registry_path=args.config_dir / "registry.jsonl"
    )
    hypothesis = protocol.admit(args.hypothesis_id)
    view = next(v for v in hypothesis_views(hypothesis) if v.get("use") == args.use)
    cell = dict(view["primary_cell"])
    for item in args.cell:
        axis, value = item.split("=", 1)
        cell[axis] = yaml.safe_load(value)

    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    prices = PriceSnapshotStore(client)
    sizing = protocol.protocol["sizing"]
    engine = PortfolioBacktest(
        prices=prices,
        universe=UniverseStore(client),
        scores=ScoreStore(client),
        cost_model=CostModel(CostParameters.from_env(), SpreadEstimator(prices)),
        sizer=EqualRiskSizer(float(sizing["max_position_pct"]), int(sizing["min_names"])),
        catalysts=CatalystPanel(client),
    )
    exclusion = ScoreRef(*args.filter_score.split(":", 1)) if args.filter_score else None
    rule = PortfolioRule.from_hypothesis(
        view, cell, ScoreRef(args.hypothesis_id, args.score_version), exclusion
    )
    tiers = [float(t) for t in os.environ["PAPER_CAPITAL_TIERS_EUR"].split(",")]
    evaluation = PortfolioEvaluation(
        protocol, engine, NoInputManifests(), HoldoutRecord(args.config_dir / "holdout")
    )
    report = evaluation.run(
        args.hypothesis_id, cell, rule, args.universe_version, tiers, use=args.use, final=args.final
    )
    paths = write_report(report, args.out_dir)
    print(
        json.dumps(
            {"verdict": report.verdict.to_report(), "files": [str(p) for p in paths]},
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
