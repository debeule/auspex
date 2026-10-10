from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta

from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore

from auspex_strategy.abc import AsOfContext
from auspex_strategy.errors import AsOfViolationError, PriceLookAheadError
from auspex_strategy.models import CorroborationRecord, SignalRecord

PriceReader = Callable[[str, date], float]
TradingDayCheck = Callable[[date], bool]


class SnapshotPrices:
    """Daily closes from the MinIO OHLCV snapshots."""

    def __init__(self, store: PriceSnapshotStore) -> None:
        self._store = store

    def close(self, ticker: str, d: date) -> float:
        df = self._store.load(ticker)
        if df is None or df.empty:
            raise LookupError(f"no price snapshot for {ticker}")
        for stamp, row in df.iterrows():
            if stamp.date() == d:
                return float(row["close"])
        raise LookupError(f"no price bar for {ticker} on {d.isoformat()}")


class _RecordContext(AsOfContext):
    """An as-of view over records the caller has already seen.

    Holding a record whose known-at time is after `as_of` is not an error, reading it is: the
    filter below only returns known records, and `price` refuses any session that has not
    closed before `as_of`.
    """

    def __init__(
        self,
        as_of: datetime,
        records: Sequence[CorroborationRecord],
        *,
        known_at_delay_days: int,
        signals: Sequence[SignalRecord] = (),
        price_close: PriceReader | None = None,
        is_trading_day: TradingDayCheck | None = None,
    ) -> None:
        self._as_of = as_of
        self._delay = timedelta(days=known_at_delay_days)
        self._records = [r for r in records if r.corroborated_at + self._delay <= as_of]
        self._signals = [s for s in signals if s.published_at <= as_of]
        self._price_close = price_close
        self._is_trading_day = is_trading_day

    @property
    def as_of(self) -> datetime:
        return self._as_of

    def corroborations(
        self,
        *,
        ticker: str | None = None,
        entity_key: str | None = None,
        min_source_count: int = 2,
    ) -> list[CorroborationRecord]:
        result = []
        for r in self._records:
            known_at = r.corroborated_at + self._delay
            if known_at > self._as_of:
                raise AsOfViolationError(r.corroborated_at, self._as_of, known_at)
            if ticker is not None and r.ticker != ticker:
                continue
            if entity_key is not None and r.entity_key != entity_key:
                continue
            if r.source_count < min_source_count:
                continue
            result.append(r)
        return result

    def signals(
        self,
        *,
        entity_key: str | None = None,
        source_type: str | None = None,
    ) -> list[SignalRecord]:
        return [
            s for s in self._signals
            if (entity_key is None or s.entity_key == entity_key)
            and (source_type is None or s.source_type == source_type)
        ]

    def price(self, ticker: str, date: date) -> float:
        if date >= self._as_of.date():
            raise PriceLookAheadError(ticker, date, self._as_of)
        if self._price_close is None:
            raise LookupError("this context has no price source")
        return self._price_close(ticker, date)

    def prior_corroborations(self, ticker: str, entity_key: str) -> int:
        return sum(
            1 for r in self._records
            if r.ticker == ticker
            and r.entity_key == entity_key
            and r.corroborated_at + self._delay < self._as_of
        )

    def is_trading_day(self, date: date) -> bool:
        if self._is_trading_day is None:
            raise LookupError("this context has no trading calendar")
        return self._is_trading_day(date)


class BacktestAsOfContext(_RecordContext):
    """As-of view for a replay: the records are the replayed sequence up to the current event."""


class LiveAsOfContext(_RecordContext):
    """As-of view for the streaming runtime: the records are what it has consumed so far."""
