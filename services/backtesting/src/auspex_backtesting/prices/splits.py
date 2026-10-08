"""Stock split history, snapshotted once per ticker next to its prices.

Price snapshots are split-adjusted to the basis of the day they were first fetched, and the
refresh refuses to extend a series whose history was re-adjusted since. Fetching splits once,
alongside, keeps both on the same basis. Stooq publishes no split history, so a ticker Yahoo
does not know is stored with none; a failed request stores nothing and is retried next time.
"""

import io

import pandas as pd
import yfinance as yf
from minio import Minio
from minio.error import S3Error

from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET


class SplitStore:
    def __init__(self, minio_client: Minio, bucket: str = PRICES_BUCKET) -> None:
        self._minio = minio_client
        self._bucket = bucket

    def load(self, ticker: str) -> pd.Series | None:
        try:
            resp = self._minio.get_object(self._bucket, splits_key(ticker))
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise
        try:
            return pd.read_parquet(io.BytesIO(resp.read()))["ratio"]
        finally:
            resp.close()
            resp.release_conn()

    def ensure(self, ticker: str) -> pd.Series:
        """The stored split history, fetched and stored first if this ticker has none yet."""
        stored = self.load(ticker)
        if stored is not None:
            return stored
        fetched = _from_yahoo(ticker)
        if fetched is None:
            return pd.Series(dtype=float)
        frame = pd.DataFrame({"ratio": fetched})
        frame.index.name = "date"
        buf = io.BytesIO()
        frame.to_parquet(buf)
        length = buf.tell()
        buf.seek(0)
        self._minio.put_object(
            self._bucket, splits_key(ticker), buf, length, content_type="application/octet-stream"
        )
        return frame["ratio"]


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
