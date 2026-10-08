from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


@dataclass(frozen=True)
class UniverseRules:
    """Admission rules for the point-in-time universe, read from `config/universe/rules.yaml`.

    Dollar floors are in USD. `window_end` of None means the window runs to the current month.
    """

    version: int
    sic_codes: frozenset[str]
    exchanges: frozenset[str]
    min_market_cap_usd: float
    min_median_dollar_volume_usd: float
    liquidity_sessions: int
    window_start: date
    window_end: date | None


def load_rules(path: Path) -> UniverseRules:
    return parse_rules(path.read_text(encoding="utf-8"))


def parse_rules(text: str) -> UniverseRules:
    raw: dict[str, Any] = yaml.safe_load(text)
    if raw.get("rebalance") != "monthly":
        raise ValueError(f"unsupported rebalance frequency {raw.get('rebalance')!r}")
    window = raw["window"]
    return UniverseRules(
        version=int(raw["version"]),
        sic_codes=frozenset(str(s) for s in raw["sic_codes"]),
        exchanges=frozenset(str(e) for e in raw["exchanges"]),
        min_market_cap_usd=float(raw["min_market_cap_usd"]),
        min_median_dollar_volume_usd=float(raw["min_median_dollar_volume_usd"]),
        liquidity_sessions=int(raw["liquidity_sessions"]),
        window_start=_as_date(window["start"]),
        window_end=_as_date(window["end"]) if window.get("end") is not None else None,
    )


def _as_date(value: object) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))
