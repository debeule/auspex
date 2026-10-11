"""Score snapshots: the input contract between a score and the portfolio engine.

One Parquet per score and rebalance date, `scores/{hypothesis_id}/{version}/{yyyy-mm-dd}.parquet`
in the prices bucket, written once. Columns `cik`, `ticker`, `score` and `known_at_max` (the
latest UTC time any input of the row became known), plus any component columns. Higher scores
rank higher.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date

import pandas as pd
from minio import Minio
from minio.error import S3Error

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET

REQUIRED_COLUMNS = ("cik", "ticker", "score", "known_at_max")
_DATE_KEY = re.compile(r"(\d{4}-\d{2}-\d{2})\.parquet")


class ScoreLookaheadError(ValueError):
    """A score row used an input that was not known before the rebalance session opened."""


class ScoreSnapshotExistsError(Exception):
    pass


@dataclass(frozen=True)
class ScoreSnapshot:
    hypothesis_id: str
    version: str
    rebalance_date: date
    rows: pd.DataFrame

    @property
    def key(self) -> str:
        return score_key(self.hypothesis_id, self.version, self.rebalance_date)

    def validate(self, calendar: MarketCalendar | None = None) -> None:
        """Raise `ScoreLookaheadError` unless every row was known before the rebalance open."""
        missing = [c for c in REQUIRED_COLUMNS if c not in self.rows.columns]
        if missing:
            raise ValueError(f"{self.key}: missing columns {missing}")
        opens = (calendar or MarketCalendar()).session_open(self.rebalance_date)
        known = pd.to_datetime(self.rows["known_at_max"], utc=True)
        late = self.rows[known.isna() | (known >= pd.Timestamp(opens))]
        if not late.empty:
            raise ScoreLookaheadError(
                f"{self.key}: {len(late)} rows known at or after the {opens.isoformat()} open "
                f"(first: {late.iloc[0]['cik']})"
            )


def score_key(hypothesis_id: str, version: str, rebalance_date: date) -> str:
    return f"scores/{hypothesis_id}/{version}/{rebalance_date.isoformat()}.parquet"


class ScoreStore:
    def __init__(
        self,
        minio_client: Minio,
        bucket: str = PRICES_BUCKET,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self._minio = minio_client
        self._bucket = bucket
        self._calendar = calendar or MarketCalendar()

    def write(self, snapshot: ScoreSnapshot) -> None:
        snapshot.validate(self._calendar)
        if self.read(snapshot.hypothesis_id, snapshot.version, snapshot.rebalance_date):
            raise ScoreSnapshotExistsError(snapshot.key)
        buf = io.BytesIO()
        snapshot.rows.to_parquet(buf, index=False)
        data = buf.getvalue()
        self._minio.put_object(
            self._bucket,
            snapshot.key,
            io.BytesIO(data),
            len(data),
            content_type="application/octet-stream",
        )

    def dates(self, hypothesis_id: str, version: str) -> list[date]:
        prefix = f"scores/{hypothesis_id}/{version}/"
        names = (
            (o.object_name or "").rsplit("/", 1)[-1]
            for o in self._minio.list_objects(self._bucket, prefix=prefix)
        )
        return sorted(
            date.fromisoformat(m.group(1)) for n in names if (m := _DATE_KEY.fullmatch(n))
        )

    def read(self, hypothesis_id: str, version: str, rebalance_date: date) -> ScoreSnapshot | None:
        key = score_key(hypothesis_id, version, rebalance_date)
        try:
            resp = self._minio.get_object(self._bucket, key)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return None
            raise
        try:
            data = bytes(resp.read())
        finally:
            resp.close()
            resp.release_conn()
        return ScoreSnapshot(
            hypothesis_id, version, rebalance_date, pd.read_parquet(io.BytesIO(data))
        )
