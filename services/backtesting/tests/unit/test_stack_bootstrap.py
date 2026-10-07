from unittest.mock import MagicMock

from auspex_backtesting.prices.price_refresher import (
    PriceDataUnavailableError,
    RefreshResult,
    SnapshotDiscontinuityError,
)
from auspex_backtesting.stack_bootstrap import ensure_buckets, fill_prices


def _minio(existing: set[str]) -> MagicMock:
    minio = MagicMock()
    minio.bucket_exists.side_effect = lambda b: b in existing
    return minio


def test_missing_buckets_are_created_and_existing_ones_left_alone() -> None:
    minio = _minio({"auspex-raw"})

    ensure_buckets(minio, ["auspex-raw", "auspex-prices"])

    minio.make_bucket.assert_called_once_with("auspex-prices")


def test_ticker_without_any_snapshot_fails_the_bootstrap() -> None:
    refresher = MagicMock()
    refresher.refresh.side_effect = PriceDataUnavailableError("XBI: no data from Yahoo or Stooq")

    assert not fill_prices(refresher, ["XBI"])


def test_snapshot_that_could_not_be_extended_does_not_fail_the_bootstrap() -> None:
    # The data the stack needs exists; the scheduled refresh keeps retrying the extension.
    refresher = MagicMock()
    refresher.refresh.side_effect = SnapshotDiscontinuityError("CAPR: history was re-adjusted")

    assert fill_prices(refresher, ["CAPR"])


def test_filled_and_current_snapshots_succeed() -> None:
    refresher = MagicMock()
    refresher.refresh.side_effect = lambda t: RefreshResult(t, 0, "2026-10-07")

    assert fill_prices(refresher, ["XBI", "EURUSD=X"])
