"""Stock split history, stored per ticker next to its prices.

A stored history vouches for splits up to its `covered_through` date, the UTC day it was
fetched, and says nothing about later ones; a read that needs a later date fetches again.
A failed request is `unavailable`, never "no splits": nothing new is stored, and the next
call retries. Stooq publishes no split history, so a ticker Yahoo answers for with none is
stored as `confirmed_empty`.
"""

import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yfinance as yf
from minio import Minio
from minio.error import S3Error

from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET

SplitStatus = Literal["available", "confirmed_empty", "unavailable"]

_COVERED_THROUGH_META = b"auspex.covered_through"


@dataclass(frozen=True)
class SplitHistory:
    """`ratios` holds new-shares-per-old-share ratios indexed by split date (UTC); it is empty
    unless `status` is `available`. `covered_through` is None when `unavailable`."""

    status: SplitStatus
    ratios: pd.Series
    covered_through: date | None


def _utc_today() -> date:
    return datetime.now(UTC).date()


class SplitStore:
    def __init__(
        self,
        minio_client: Minio,
        bucket: str = PRICES_BUCKET,
        today: Callable[[], date] = _utc_today,
    ) -> None:
        self._minio = minio_client
        self._bucket = bucket
        self._today = today

    def load(self, ticker: str) -> SplitHistory | None:
        try:
            resp = self._minio.get_object(self._bucket, splits_key(ticker))
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise
        try:
            data = resp.read()
        finally:
            resp.close()
            resp.release_conn()
        ratios = pd.read_parquet(io.BytesIO(data))["ratio"]
        covered = (pq.read_schema(io.BytesIO(data)).metadata or {})[_COVERED_THROUGH_META]
        return _history(ratios, date.fromisoformat(covered.decode()))

    def ensure(self, ticker: str, through: date) -> SplitHistory:
        """The split history covering every split up to `through`: the stored one when it
        does, otherwise fetched and stored first; `unavailable` when that fetch fails."""
        stored = self.load(ticker)
        if stored is not None and stored.covered_through and stored.covered_through >= through:
            return stored
        fetched = _from_yahoo(ticker)
        if fetched is None:
            return SplitHistory("unavailable", pd.Series(dtype=float), None)
        covered = self._today()
        frame = pd.DataFrame({"ratio": fetched})
        frame.index.name = "date"
        table = pa.Table.from_pandas(frame)
        table = table.replace_schema_metadata(
            {**(table.schema.metadata or {}), _COVERED_THROUGH_META: covered.isoformat().encode()}
        )
        buf = io.BytesIO()
        pq.write_table(table, buf)
        length = buf.tell()
        buf.seek(0)
        self._minio.put_object(
            self._bucket, splits_key(ticker), buf, length, content_type="application/octet-stream"
        )
        return _history(frame["ratio"], covered)


def _history(ratios: pd.Series, covered_through: date) -> SplitHistory:
    return SplitHistory(
        "available" if len(ratios) else "confirmed_empty", ratios, covered_through
    )


def splits_key(ticker: str) -> str:
    return f"splits/{ticker}.parquet"


def _from_yahoo(ticker: str) -> pd.Series | None:
    try:
        splits = yf.Ticker(ticker).splits
    except Exception:  # noqa: BLE001 - yfinance surfaces network and parse failures as anything
        return None
    index = pd.DatetimeIndex(splits.index)
    index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    return pd.Series(splits.to_numpy(dtype=float), index=index)
