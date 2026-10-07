import io

import pandas as pd
from minio import Minio
from minio.error import S3Error

PRICES_BUCKET = "auspex-prices"


class PriceSnapshotStore:
    """Read-only access to the OHLCV Parquet snapshots in MinIO. Never touches the network
    beyond MinIO; a missing snapshot is None, not a fetch."""

    def __init__(self, minio_client: Minio, bucket: str = PRICES_BUCKET) -> None:
        self._minio = minio_client
        self._bucket = bucket

    def load(self, ticker: str) -> pd.DataFrame | None:
        try:
            resp = self._minio.get_object(self._bucket, snapshot_key(ticker))
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise
        try:
            return pd.read_parquet(io.BytesIO(resp.read()))
        finally:
            resp.close()
            resp.release_conn()


def snapshot_key(ticker: str) -> str:
    return f"{ticker}.parquet"
