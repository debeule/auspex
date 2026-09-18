import io
from datetime import date

import pandas as pd
import yfinance as yf
from minio import Minio
from minio.error import S3Error

_BUCKET = "auspex-prices"
_REQUIRED_COLS = ["open", "high", "low", "close", "volume"]


class PriceFetcher:
    def __init__(self, minio_client: Minio, bucket: str = _BUCKET) -> None:
        self._minio = minio_client
        self._bucket = bucket

    def fetch(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        key = f"{ticker}.parquet"
        cached = self._load(key)
        if cached is not None:
            return cached

        df = _from_yahoo(ticker, start, end)
        if df is None:
            df = _from_stooq(ticker, start, end)

        if df is None or df.empty:
            return pd.DataFrame(columns=_REQUIRED_COLS)

        normalised = _normalize(df)
        self._store(key, normalised)
        return normalised

    def _load(self, key: str) -> pd.DataFrame | None:
        try:
            resp = self._minio.get_object(self._bucket, key)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise
        try:
            data = resp.read()
            return pd.read_parquet(io.BytesIO(data))
        finally:
            resp.close()
            resp.release_conn()

    def _store(self, key: str, df: pd.DataFrame) -> None:
        buf = io.BytesIO()
        df.to_parquet(buf)
        length = buf.tell()
        buf.seek(0)
        self._minio.put_object(
            self._bucket, key, buf, length,
            content_type="application/octet-stream",
        )


def _from_yahoo(ticker: str, start: date, end: date) -> pd.DataFrame | None:
    # Returns None on any exception so the caller falls back to Stooq
    try:
        df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return None


def _from_stooq(ticker: str, start: date, end: date) -> pd.DataFrame | None:
    try:
        import pandas_datareader.data as pdr  # noqa: PLC0415
        return pdr.DataReader(ticker, "stooq", start=start, end=end)
    except Exception:
        return None


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = pd.Index([str(c).lower() for c in df.columns])
    available = [c for c in _REQUIRED_COLS if c in df.columns]
    df = df[available]
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    df.index.name = "date"
    return df
