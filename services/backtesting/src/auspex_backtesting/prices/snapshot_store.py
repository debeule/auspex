import io
from datetime import date

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error

PRICES_BUCKET = "auspex-prices"

# `DataFrame.attrs` key, and Parquet metadata key, for the UTC date the snapshot's split
# adjustment was taken: its closes are on the share basis of that day.
ADJUSTED_THROUGH = "adjusted_through"
_ADJUSTED_THROUGH_META = b"auspex.adjusted_through"


class PriceSnapshotStore:
    """Read-only access to the OHLCV Parquet snapshots in MinIO. Never touches the network
    beyond MinIO; a missing snapshot is None, not a fetch."""

    def __init__(self, minio_client: Minio, bucket: str = PRICES_BUCKET) -> None:
        self._minio = minio_client
        self._bucket = bucket

    def load(self, ticker: str) -> pd.DataFrame | None:
        """The snapshot, with `attrs[ADJUSTED_THROUGH]` set when it was recorded."""
        try:
            resp = self._minio.get_object(self._bucket, snapshot_key(ticker))
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise
        try:
            data = resp.read()
        finally:
            resp.close()
            resp.release_conn()
        df = pd.read_parquet(io.BytesIO(data))
        recorded = (pq.read_schema(io.BytesIO(data)).metadata or {}).get(_ADJUSTED_THROUGH_META)
        if recorded is not None:
            df.attrs[ADJUSTED_THROUGH] = date.fromisoformat(recorded.decode())
        return df


def adjusted_through(df: pd.DataFrame) -> date | None:
    value = df.attrs.get(ADJUSTED_THROUGH)
    return value if isinstance(value, date) else None


def snapshot_parquet(df: pd.DataFrame, adjusted: date | None) -> bytes:
    table = pa.Table.from_pandas(df)
    if adjusted is not None:
        table = table.replace_schema_metadata(
            {**(table.schema.metadata or {}), _ADJUSTED_THROUGH_META: adjusted.isoformat().encode()}
        )
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()


def snapshot_key(ticker: str) -> str:
    return f"{ticker}.parquet"
