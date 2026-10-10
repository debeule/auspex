from __future__ import annotations

import enum
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from auspex_strategy.models import (
    Direction,
    ExitOnSignal,
    FixedDays,
    HoldingRule,
    StopLossPct,
    TradeIntent,
)
from auspex_strategy.runtime.store import ObjectStore


class BookMode(enum.Enum):
    """`backtest` books hold replay fills, so a replay never writes into the forward paper
    ledger. `live` is the real portfolio; its rows carry the originating strategy's name."""

    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE_CONFIRM = "live-confirm"
    LIVE_AUTO = "live-auto"
    LIVE = "live"


_SCHEMA = pa.schema([
    ("row_id", pa.string()),
    ("kind", pa.string()),
    ("recorded_at", pa.string()),
    ("strategy_name", pa.string()),
    ("mode", pa.string()),
    ("order_id", pa.string()),
    ("position_id", pa.string()),
    ("intent_id", pa.string()),
    ("ticker", pa.string()),
    ("direction", pa.string()),
    ("holding_kind", pa.string()),
    ("holding_value", pa.float64()),
    ("capital_eur", pa.float64()),
    ("shares", pa.int64()),
    ("entry_date", pa.string()),
    ("entry_price", pa.float64()),
    ("exit_date", pa.string()),
    ("exit_price", pa.float64()),
    ("exit_reason", pa.string()),
    ("costs_usd", pa.float64()),
    ("pnl_usd", pa.float64()),
    ("pnl_eur", pa.float64()),
    ("reason", pa.string()),
    ("is_correction", pa.bool_()),
])


@dataclass(frozen=True)
class PendingOrder:
    order_id: str
    intent_id: str
    ticker: str
    direction: Direction
    holding_rule: HoldingRule
    capital_eur: float
    entry_date: date


@dataclass(frozen=True)
class OpenPosition:
    position_id: str
    order_id: str
    intent_id: str
    ticker: str
    direction: Direction
    holding_rule: HoldingRule
    shares: int
    entry_date: date
    entry_price: float


@dataclass(frozen=True)
class ClosedTrade:
    position_id: str
    ticker: str
    direction: Direction
    shares: int
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    exit_reason: str
    costs_usd: float
    pnl_usd: float
    pnl_eur: float


@dataclass(frozen=True)
class BookSnapshot:
    pending_orders: list[PendingOrder]
    open_positions: list[OpenPosition]
    closed_trades: list[ClosedTrade]

    def is_empty(self) -> bool:
        return not (self.pending_orders or self.open_positions or self.closed_trades)


class VirtualBook:
    """One strategy's book in one mode, as append-only Parquet in MinIO.

    Rows are never rewritten or removed: an order row, then an `open` row once it fills (or a
    `rejected` row), then a `close` row. A correction is a new offsetting row with
    `is_correction` set.
    """

    def __init__(self, store: ObjectStore, strategy_name: str, mode: BookMode) -> None:
        self._store = store
        self.strategy_name = strategy_name
        self.mode = mode
        self.key = f"strategy/books/{strategy_name}/{mode.value}/trades.parquet"

    def place_order(self, intent: TradeIntent, capital_eur: float, entry_date: date) -> str:
        order_id = str(uuid4())
        kind, value = _holding_columns(intent.holding_rule)
        self._append({
            "kind": "order",
            "order_id": order_id,
            "intent_id": str(intent.intent_id),
            "ticker": intent.ticker,
            "direction": intent.direction.value,
            "holding_kind": kind,
            "holding_value": value,
            "capital_eur": capital_eur,
            "entry_date": entry_date.isoformat(),
        })
        return order_id

    def reject_order(self, order: PendingOrder, reason: str) -> None:
        self._append({"kind": "rejected", "order_id": order.order_id, "reason": reason})

    def open_position(self, order: PendingOrder, shares: int, entry_price: float) -> str:
        position_id = str(uuid4())
        kind, value = _holding_columns(order.holding_rule)
        self._append({
            "kind": "open",
            "order_id": order.order_id,
            "position_id": position_id,
            "intent_id": order.intent_id,
            "ticker": order.ticker,
            "direction": order.direction.value,
            "holding_kind": kind,
            "holding_value": value,
            "shares": shares,
            "entry_date": order.entry_date.isoformat(),
            "entry_price": entry_price,
        })
        return position_id

    def close_position(
        self,
        position: OpenPosition,
        *,
        exit_date: date,
        exit_price: float,
        exit_reason: str,
        costs_usd: float,
        eur_per_usd: float,
    ) -> ClosedTrade:
        sign = 1 if position.direction is Direction.LONG else -1
        pnl_usd = sign * (exit_price - position.entry_price) * position.shares - costs_usd
        pnl_eur = pnl_usd * eur_per_usd
        self._append({
            "kind": "close",
            "order_id": position.order_id,
            "position_id": position.position_id,
            "intent_id": position.intent_id,
            "ticker": position.ticker,
            "direction": position.direction.value,
            "shares": position.shares,
            "entry_date": position.entry_date.isoformat(),
            "entry_price": position.entry_price,
            "exit_date": exit_date.isoformat(),
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "costs_usd": float(costs_usd),
            "pnl_usd": pnl_usd,
            "pnl_eur": pnl_eur,
        })
        return ClosedTrade(
            position_id=position.position_id,
            ticker=position.ticker,
            direction=position.direction,
            shares=position.shares,
            entry_date=position.entry_date,
            entry_price=position.entry_price,
            exit_date=exit_date,
            exit_price=exit_price,
            exit_reason=exit_reason,
            costs_usd=float(costs_usd),
            pnl_usd=pnl_usd,
            pnl_eur=pnl_eur,
        )

    def snapshot(self) -> BookSnapshot:
        rows = self._rows()
        settled = {r["order_id"] for r in rows if r["kind"] in {"open", "rejected"}}
        closed = {r["position_id"] for r in rows if r["kind"] == "close"}
        return BookSnapshot(
            pending_orders=[
                _pending(r) for r in rows if r["kind"] == "order" and r["order_id"] not in settled
            ],
            open_positions=[
                _open(r) for r in rows if r["kind"] == "open" and r["position_id"] not in closed
            ],
            closed_trades=[_closed(r) for r in rows if r["kind"] == "close"],
        )

    def open_positions(self) -> list[OpenPosition]:
        return self.snapshot().open_positions

    def closed_trades(self) -> list[ClosedTrade]:
        return self.snapshot().closed_trades

    def _rows(self) -> list[dict[str, Any]]:
        data = self._store.get(self.key)
        if data is None:
            return []
        rows: list[dict[str, Any]] = pq.read_table(io.BytesIO(data)).to_pylist()
        return rows

    def _append(self, values: dict[str, Any]) -> None:
        row: dict[str, Any] = {name: None for name in _SCHEMA.names}
        row.update(values)
        row["row_id"] = str(uuid4())
        row["recorded_at"] = datetime.now(UTC).isoformat()
        row["strategy_name"] = self.strategy_name
        row["mode"] = self.mode.value
        row["is_correction"] = False
        table = pa.Table.from_pylist([*self._rows(), row], schema=_SCHEMA)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        self._store.put(self.key, buf.getvalue())


def _holding_columns(rule: HoldingRule) -> tuple[str, float | None]:
    match rule:
        case FixedDays(days=days):
            return "fixed_days", float(days)
        case StopLossPct(pct=pct):
            return "stop_loss_pct", pct
        case ExitOnSignal():
            return "exit_on_signal", None
    raise TypeError(f"unknown holding rule {rule!r}")


def _holding_rule(row: dict[str, Any]) -> HoldingRule:
    match row["holding_kind"]:
        case "fixed_days":
            return FixedDays(int(row["holding_value"]))
        case "stop_loss_pct":
            return StopLossPct(float(row["holding_value"]))
        case "exit_on_signal":
            return ExitOnSignal()
    raise ValueError(f"unknown holding rule {row['holding_kind']!r}")


def _pending(row: dict[str, Any]) -> PendingOrder:
    return PendingOrder(
        order_id=row["order_id"],
        intent_id=row["intent_id"],
        ticker=row["ticker"],
        direction=Direction(row["direction"]),
        holding_rule=_holding_rule(row),
        capital_eur=row["capital_eur"],
        entry_date=date.fromisoformat(row["entry_date"]),
    )


def _open(row: dict[str, Any]) -> OpenPosition:
    return OpenPosition(
        position_id=row["position_id"],
        order_id=row["order_id"],
        intent_id=row["intent_id"],
        ticker=row["ticker"],
        direction=Direction(row["direction"]),
        holding_rule=_holding_rule(row),
        shares=row["shares"],
        entry_date=date.fromisoformat(row["entry_date"]),
        entry_price=row["entry_price"],
    )


def _closed(row: dict[str, Any]) -> ClosedTrade:
    return ClosedTrade(
        position_id=row["position_id"],
        ticker=row["ticker"],
        direction=Direction(row["direction"]),
        shares=row["shares"],
        entry_date=date.fromisoformat(row["entry_date"]),
        entry_price=row["entry_price"],
        exit_date=date.fromisoformat(row["exit_date"]),
        exit_price=row["exit_price"],
        exit_reason=row["exit_reason"],
        costs_usd=row["costs_usd"],
        pnl_usd=row["pnl_usd"],
        pnl_eur=row["pnl_eur"],
    )
