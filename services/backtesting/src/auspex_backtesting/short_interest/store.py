"""Short interest per ticker in MinIO, `auspex-prices/short_interest/{ticker}.parquet`.

A ticker's file grows by whole settlement periods: a stored period is never changed or
replaced, and FINRA's later revisions of a period are not taken in.
"""

import io
from collections.abc import Sequence
from datetime import date
from typing import Protocol

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error

from auspex_backtesting.ownership.reference import FactorMissing
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET
from auspex_backtesting.short_interest.model import (
    ChangeMissing,
    PctMissing,
    ShortInterestFeatures,
    ShortInterestRecord,
)
from auspex_backtesting.universe.model import ShareCount

PREFIX = "short_interest/"

SCHEMA = pa.schema([
    ("ticker", pa.string()),
    ("settlement_date", pa.date32()),
    ("publication_date", pa.date32()),
    ("reported", pa.bool_()),
    ("short_interest_shares", pa.int64()),
    ("average_daily_volume", pa.int64()),
    ("days_to_cover", pa.float64()),
])


class PeriodExistsError(Exception):
    """A settlement period is stored once per ticker; this one already is."""


class TickerShareBasis(Protocol):
    """Share counts and split factors by ticker, as `ownership.reference` gives them by CIK:
    shares counted on `after` times `factor(ticker, after, through)` are shares on `through`'s
    basis, and a None factor comes with `missing_reason`."""

    def share_count(self, ticker: str, as_of: date) -> ShareCount | None: ...

    def factor(self, ticker: str, after: date, through: date) -> float | None: ...

    def missing_reason(self, ticker: str, after: date, through: date) -> FactorMissing | None: ...


class ShortInterestStore:
    def __init__(self, minio_client: Minio, bucket: str = PRICES_BUCKET) -> None:
        self._minio = minio_client
        self._bucket = bucket

    def read(self, ticker: str) -> pd.DataFrame:
        """Stored periods for `ticker` in settlement order; empty when none are."""
        try:
            resp = self._minio.get_object(self._bucket, _key(ticker))
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return SCHEMA.empty_table().to_pandas()
            raise
        try:
            data = bytes(resp.read())
        finally:
            resp.close()
            resp.release_conn()
        return pq.read_table(io.BytesIO(data), schema=SCHEMA).to_pandas()

    def settlement_dates(self, ticker: str) -> set[date]:
        return set(self.read(ticker)["settlement_date"])

    def append(self, ticker: str, records: Sequence[ShortInterestRecord]) -> None:
        """Adds new periods after the stored ones; raises `PeriodExistsError`, writing nothing,
        if any of them is already stored."""
        if not records:
            return
        existing = self.read(ticker)
        new = pa.Table.from_pylist(
            [_row(r) for r in sorted(records, key=lambda r: r.settlement_date)], schema=SCHEMA
        ).to_pandas()
        clash = set(existing["settlement_date"]) & set(new["settlement_date"])
        if clash or new["settlement_date"].duplicated().any():
            raise PeriodExistsError(f"{ticker}: {sorted(clash) or 'duplicate periods'}")
        combined = new if existing.empty else pd.concat([existing, new], ignore_index=True)
        table = pa.Table.from_pandas(combined, schema=SCHEMA, preserve_index=False)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        content = buf.getvalue()
        self._minio.put_object(
            self._bucket, _key(ticker), io.BytesIO(content), len(content),
            content_type="application/octet-stream",
        )

    def records(self, ticker: str) -> list[ShortInterestRecord]:
        frame = self.read(ticker).sort_values("settlement_date")
        return [_record(row) for row in frame.to_dict("records")]

    def as_of(self, ticker: str, as_of: date) -> ShortInterestRecord | None:
        """The latest period published on or before `as_of`, so known by the end of that day.
        A caller deciding before the close of `as_of` must ask for the session before it:
        FINRA's publication time of day is not part of the schedule."""
        known = [r for r in self.records(ticker) if r.publication_date <= as_of]
        return known[-1] if known else None

    def features(
        self, ticker: str, as_of: date, basis: TickerShareBasis | None
    ) -> ShortInterestFeatures | None:
        """Short interest is counted on its settlement date and a share count on its `end`;
        both are restated to `as_of`'s basis before they are divided, so a split in between
        does not distort the share. The change since the previous period restates the
        previous count to the current settlement date's basis. Without `basis`, no split can
        be ruled out and both figures are missing."""
        known = [r for r in self.records(ticker) if r.publication_date <= as_of]
        if not known:
            return None
        current = known[-1]
        previous = known[-2] if len(known) > 1 else None
        pct, pct_missing = _pct_of_shares(current, as_of, basis)
        change, change_missing = _change(current, previous, basis)
        return ShortInterestFeatures(current, pct, pct_missing, change, change_missing)

    def tickers(self) -> list[str]:
        objects = self._minio.list_objects(self._bucket, prefix=PREFIX)
        return sorted(
            name[len(PREFIX):-len(".parquet")]
            for o in objects
            if (name := o.object_name or "").endswith(".parquet")
        )


def _key(ticker: str) -> str:
    return f"{PREFIX}{ticker}.parquet"


def _row(r: ShortInterestRecord) -> dict[str, object]:
    return {
        "ticker": r.ticker,
        "settlement_date": r.settlement_date,
        "publication_date": r.publication_date,
        "reported": r.reported,
        "short_interest_shares": r.short_interest_shares,
        "average_daily_volume": r.average_daily_volume,
        "days_to_cover": r.days_to_cover,
    }


def _record(row: dict[str, object]) -> ShortInterestRecord:
    def _int(v: object) -> int | None:
        return None if v is None or pd.isna(v) else int(v)  # type: ignore[call-overload]

    days = row["days_to_cover"]
    return ShortInterestRecord(
        str(row["ticker"]),
        row["settlement_date"],  # type: ignore[arg-type]
        row["publication_date"],  # type: ignore[arg-type]
        bool(row["reported"]),
        _int(row["short_interest_shares"]),
        _int(row["average_daily_volume"]),
        None if days is None or pd.isna(days) else float(days),  # type: ignore[arg-type]
    )



def _pct_of_shares(
    current: ShortInterestRecord, as_of: date, basis: TickerShareBasis | None
) -> tuple[float | None, PctMissing | None]:
    if current.short_interest_shares is None:
        return None, "not_reported"
    count = basis.share_count(current.ticker, as_of) if basis is not None else None
    if basis is None or count is None or not count.value:
        return None, "no_share_count"
    short_factor = _factor(basis, current.ticker, current.settlement_date, as_of)
    if isinstance(short_factor, str):
        return None, short_factor
    count_factor = _factor(basis, current.ticker, count.end, as_of)
    if isinstance(count_factor, str):
        return None, count_factor
    return (
        100.0 * current.short_interest_shares * short_factor / (count.value * count_factor),
        None,
    )


def _change(
    current: ShortInterestRecord,
    previous: ShortInterestRecord | None,
    basis: TickerShareBasis | None,
) -> tuple[float | None, ChangeMissing | None]:
    if (
        previous is None
        or current.short_interest_shares is None
        or previous.short_interest_shares is None
    ):
        return None, "not_reported"
    if basis is None:
        return None, "split_history_unavailable"
    factor = _factor(basis, current.ticker, previous.settlement_date, current.settlement_date)
    if isinstance(factor, str):
        return None, factor
    return current.short_interest_shares - previous.short_interest_shares * factor, None


def _factor(
    basis: TickerShareBasis, ticker: str, after: date, through: date
) -> float | FactorMissing:
    factor = basis.factor(ticker, after, through)
    if factor is not None:
        return factor
    reason = basis.missing_reason(ticker, after, through)
    if reason is None:
        raise ValueError(f"split factor for {ticker} is missing without a reason")
    return reason
