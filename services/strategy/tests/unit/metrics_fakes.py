import io
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import yaml
from auspex_backtesting.evaluation import TrialLedger
from minio.error import S3Error

from auspex_strategy.metrics import MetricsService
from auspex_strategy.models import (
    Direction,
    FixedDays,
    IntentRationale,
    TradeIntent,
)
from auspex_strategy.registry import RegistryEntry, StrategyRegistry
from auspex_strategy.runtime import BookMode, MinioObjectStore, ObjectStore, VirtualBook
from auspex_strategy.testing import InMemoryObjectStore

from .runtime_fakes import ohlcv, price_store, strategy_class

PROTOCOL: dict[str, Any] = yaml.safe_load(
    (Path(__file__).resolve().parents[4] / "config/hypotheses/protocol.yaml").read_text()
)
HYPOTHESES: dict[str, dict[str, Any]] = {
    "h1": {"id": "h1", "role": "promotable", "known_at_delay_days": [1]},
    "h4": {"id": "h4", "role": "promotable", "known_at_delay_days": [1]},
}

# Every price path starts here; the benchmark's estimation window holds fewer sessions than
# the protocol's minimum, so each trade uses the market-adjusted model (alpha 0, beta 1).
_FIRST_SESSION = date(2026, 1, 15)
_LAST_SESSION = date(2026, 12, 31)
ENTRY = date(2026, 3, 2)
EUR_PER_USD = 0.8


def sessions() -> list[date]:
    return [d.date() for d in pd.bdate_range(_FIRST_SESSION, _LAST_SESSION)]


def flat_path(price: float = 100.0) -> pd.DataFrame:
    return ohlcv({d.isoformat(): (price, price, price, price) for d in sessions()})


def step_path(step_on: date, after: float, before: float = 100.0) -> pd.DataFrame:
    """Closes at `before` until the session before `step_on`, at `after` from it on."""
    rows = {}
    for d in sessions():
        p = after if d >= step_on else before
        rows[d.isoformat()] = (p, p, p, p)
    return ohlcv(rows)


def session_after(start: date, n: int) -> date:
    days = sessions()
    return days[days.index(start) + n]


class FakeMinio:
    """The two `Minio` calls `MinioObjectStore` makes, over a dict, so the store's own
    read and write path runs without a server."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def get_object(self, bucket: str, key: str) -> MagicMock:
        if (bucket, key) not in self.objects:
            raise S3Error(MagicMock(), "NoSuchKey", "The specified key does not exist.", key,
                          "", "")
        response = MagicMock()
        response.read.return_value = self.objects[(bucket, key)]
        return response

    def put_object(self, bucket: str, key: str, data: io.BytesIO, length: int) -> None:
        self.objects[(bucket, key)] = data.read(length)


def minio_store() -> MinioObjectStore:
    return MinioObjectStore(FakeMinio())  # type: ignore[arg-type]


@dataclass
class ToyMarket:
    """Books trades whose abnormal return is known by construction: the benchmark is flat and
    each ticker's close steps once, two sessions after entry, inside the return window."""

    objects: ObjectStore = field(default_factory=InMemoryObjectStore)
    snapshots: dict[str, pd.DataFrame] = field(default_factory=lambda: {"XBI": flat_path()})

    def trade(
        self,
        strategy: str,
        version: str,
        mode: BookMode,
        *,
        ticker: str,
        exit_price: float,
        direction: Direction = Direction.LONG,
        costs_usd: float = 20.0,
        entry: date = ENTRY,
        holding_sessions: int = 5,
        shares: int = 100,
    ) -> None:
        self.snapshots[ticker] = step_path(session_after(entry, 2), exit_price)
        book = VirtualBook(self.objects, strategy, mode)
        book.place_order(intent(strategy, version, ticker, direction), 10_000.0, entry)
        order = next(o for o in book.snapshot().pending_orders if o.ticker == ticker)
        book.open_position(order, shares, 100.0)
        position = next(p for p in book.open_positions() if p.ticker == ticker)
        book.close_position(
            position,
            exit_date=session_after(entry, holding_sessions),
            exit_price=exit_price,
            exit_reason="holding_period",
            costs_usd=costs_usd,
            eur_per_usd=EUR_PER_USD,
        )

    def service(
        self,
        registry: StrategyRegistry,
        trials_dir: Path,
        *,
        min_trades: int = 20,
    ) -> MetricsService:
        return MetricsService(
            self.objects,
            price_store(self.snapshots),
            registry,
            protocol=PROTOCOL,
            hypotheses=HYPOTHESES,
            ledger=TrialLedger(trials_dir, PROTOCOL, HYPOTHESES),
            min_trades=min_trades,
            clock=lambda: datetime(2026, 10, 11, tzinfo=UTC),
        )


def intent(strategy: str, version: str, ticker: str, direction: Direction) -> TradeIntent:
    as_of = datetime(2026, 2, 27, 21, 0, tzinfo=UTC)
    return TradeIntent(
        ticker=ticker,
        direction=direction,
        conviction=0.5,
        holding_rule=FixedDays(5),
        exit_conditions=(),
        rationale=IntentRationale(
            corroboration_id=f"{ticker}-corroboration",
            entity_key=ticker,
            as_of=as_of,
            source_types=frozenset({"biorxiv", "clinicaltrials"}),
            directionality="positive",
            confidence_scores=(0.9,),
        ),
        strategy_name=strategy,
        strategy_version=version,
        hypothesis_id="h1",
        as_of=as_of,
    )


def registry(*entries: tuple[str, str, str, str]) -> StrategyRegistry:
    """Entries are (name, version, hypothesis_id, status)."""
    built = []
    for name, version, hypothesis_id, status in entries:
        cls = strategy_class(name, decide=lambda s, c, t: [], hypothesis_id=hypothesis_id)
        built.append(RegistryEntry(
            name=name,
            module="tests.unit.runtime_fakes",
            class_name=cls.__name__,
            version=version,
            hypothesis_id=hypothesis_id,
            status=status,
            parameters_file=None,
            strategy_class=cls,
        ))
    return StrategyRegistry(built)


def write_trials(trials_dir: Path, hypothesis_id: str, n_cells: int) -> None:
    trials_dir.mkdir(parents=True, exist_ok=True)
    cells = [{"holding_period_days": 5 * (i + 1)} for i in range(n_cells)]
    line = {"run_id": f"{hypothesis_id}-run", "hypothesis_id": hypothesis_id, "cells": cells}
    (trials_dir / f"{hypothesis_id}.jsonl").write_text(json.dumps(line) + "\n")
