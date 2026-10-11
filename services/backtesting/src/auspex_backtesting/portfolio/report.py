"""A portfolio evaluation as plain JSON files: the report, and the verdict beside it."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from auspex_backtesting.portfolio.engine import PortfolioResult
from auspex_backtesting.portfolio.verdict import PortfolioReport


def result_dict(result: PortfolioResult) -> dict[str, Any]:
    data = {
        f.name: getattr(result, f.name)
        for f in dataclasses.fields(result)
        if f.name not in {"rule", "months", "decisions", "trades", "closeouts", "quintiles"}
    }
    return {
        **data,
        "rule": {**dataclasses.asdict(result.rule), "cell": dict(result.rule.cell)},
        "months": [
            {
                **dataclasses.asdict(m),
                "excess_over_xbi": m.excess_over_xbi,
                "excess_over_universe_ew": m.excess_over_universe_ew,
                "excess_over_invested_universe_ew": m.excess_over_invested_universe_ew,
            }
            for m in result.months
        ],
        "decisions": [dataclasses.asdict(d) for d in result.decisions],
        "trades": [dataclasses.asdict(t) for t in result.trades],
        "closeouts": [dataclasses.asdict(c) for c in result.closeouts],
        "quintiles": [{**dataclasses.asdict(q), "spread": q.spread} for q in result.quintiles],
        "delisting_bound_months": list(result.delisting_bound_months),
        "unpriced_member_month_share": result.unpriced_member_month_share,
    }


def write_report(report: PortfolioReport, out_dir: Path) -> list[Path]:
    """Writes `<hypothesis>-<run id>.json` and `<hypothesis>-<run id>-verdict.json`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{report.verdict.hypothesis_id}-{report.run_id}"
    body = {
        "run_id": report.run_id,
        "cell": dict(report.cell),
        "in_sample": {str(t): result_dict(r) for t, r in report.in_sample.items()},
        "holdout": {str(t): result_dict(r) for t, r in report.holdout.items()},
    }
    paths = [out_dir / f"{stem}.json", out_dir / f"{stem}-verdict.json"]
    paths[0].write_text(json.dumps(body, indent=2, default=str), encoding="utf-8")
    paths[1].write_text(
        json.dumps(
            {"run_id": report.run_id, "cell": dict(report.cell), **report.verdict.to_report()},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return paths
