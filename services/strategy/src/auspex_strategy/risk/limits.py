from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from auspex_backtesting.hypothesis import load_hypothesis, verify_hypothesis


class LimitMissingError(Exception):
    pass


class LimitAboveCeilingError(Exception):
    pass


@dataclass(frozen=True)
class RiskLimits:
    """Every limit the risk layer applies, one field per `.env` variable of the same name in
    upper case. Units: `*_pct` fields read as fractions of capital (0.03 is 3%), except
    `max_borrow_fee_annual_pct`, `max_short_interest_pct` and `short_hard_stop_pct`, which are
    percentages (3.0 is 3%), the units of their data sources. `daily_loss_limit_eur` is negative.

    `shorts_enabled` is not an `.env` value: it comes from the protocol's `instruments`
    ceiling, which only a re-registration can change.
    """

    kelly_shrinkage_factor: float
    kelly_fraction: float
    min_trades_for_kelly: int
    fallback_position_pct: float
    max_position_pct: float
    max_gross_exposure: float
    max_net_exposure: float
    max_positions_per_strategy: int
    max_positions_per_theme: int
    catalyst_guard_days: int
    max_borrow_fee_annual_pct: float
    max_short_interest_pct: float
    max_days_to_cover: float
    short_hard_stop_pct: float
    max_loss_per_short_eur: float
    daily_loss_limit_eur: float
    max_drawdown_pct: float
    daily_turnover_ceiling_pct: float
    shorts_enabled: bool

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str],
        *,
        protocol_dir: Path,
        registry_path: Path | None = None,
    ) -> RiskLimits:
        """Reads every limit from `env` and checks it against the registered protocol's
        `sizing` ceilings. The protocol file must match its registered hash."""
        registry = registry_path if registry_path is not None else protocol_dir / "registry.jsonl"
        verify_hypothesis("protocol", config_dir=protocol_dir, registry_path=registry)
        protocol = load_hypothesis("protocol", protocol_dir)
        values: dict[str, Any] = {}
        for field in fields(cls):
            if field.name == "shorts_enabled":
                continue
            values[field.name] = _read(env, field.name.upper(), int if field.type == "int" else float)
        limits = cls(**values, shorts_enabled=bool(protocol["instruments"]["shorts_enabled"]))
        _check_ceilings(limits, protocol["sizing"])
        return limits


def _read(env: Mapping[str, str], name: str, kind: type[int | float]) -> int | float:
    raw = env.get(name, "").strip()
    if not raw:
        raise LimitMissingError(f"{name} is not set; every risk limit must be set in .env")
    try:
        return kind(raw)
    except ValueError as exc:
        raise LimitMissingError(f"{name}={raw!r} is not a valid {kind.__name__}") from exc


def _check_ceilings(limits: RiskLimits, sizing: Mapping[str, Any]) -> None:
    at_most = {
        "KELLY_FRACTION": (limits.kelly_fraction, "max_kelly_fraction"),
        "MAX_POSITION_PCT": (limits.max_position_pct, "max_position_pct"),
        "FALLBACK_POSITION_PCT": (limits.fallback_position_pct, "max_position_pct"),
        "MAX_POSITIONS_PER_THEME": (limits.max_positions_per_theme, "max_positions_per_theme"),
    }
    for name, (value, key) in at_most.items():
        if value > sizing[key]:
            raise LimitAboveCeilingError(
                f"{name}={value} exceeds the protocol ceiling sizing.{key}={sizing[key]}"
            )
    # Fewer trades before Kelly is the looser direction for this one.
    floor = sizing["min_trades_for_kelly"]
    if limits.min_trades_for_kelly < floor:
        raise LimitAboveCeilingError(
            f"MIN_TRADES_FOR_KELLY={limits.min_trades_for_kelly} is below the protocol floor "
            f"sizing.min_trades_for_kelly={floor}"
        )
