import os
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from holdings_support import CONFIG_DIR, REBALANCE, RULES_VERSION, accepted, member, snapshot
from minio import Minio
from testcontainers.core.container import DockerContainer

from auspex_backtesting.ownership import OwnershipStore
from auspex_backtesting.ownership.reference import SHARES_OUTSTANDING_KEY, counts_frame
from auspex_backtesting.portfolio.scores import ScoreStore
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET
from auspex_backtesting.scores.job import holdings_score_build
from auspex_backtesting.short_interest import ShortInterestRecord, ShortInterestStore
from auspex_backtesting.universe import ShareCount, UniverseStore

pytestmark = [pytest.mark.integration, pytest.mark.enable_socket]

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
_LOCALSTACK_IMAGE = "localstack/localstack:4.9.2"
_FINRA_CALENDAR = (
    Path(__file__).resolve().parents[4] / "config" / "short_interest" / "finra_calendar.csv"
)
_CIK = "0000000001"


@pytest.fixture(scope="module")
def s3() -> Iterator[Minio]:
    container = DockerContainer(_LOCALSTACK_IMAGE).with_exposed_ports(4566).with_env("SERVICES", "s3")
    with container:
        for _ in range(60):
            try:
                port = container.get_exposed_port(4566)
                client = Minio(
                    f"{container.get_container_host_ip()}:{port}",
                    access_key="test", secret_key="test", secure=False,
                )
                client.list_buckets()
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            pytest.fail("LocalStack never became ready")
        client.make_bucket(PRICES_BUCKET)
        yield client


def test_h9_scores_round_trip_through_object_storage_once(s3: Minio) -> None:
    UniverseStore(s3).write(snapshot([member(_CIK, "TA")]))
    OwnershipStore(s3).write(
        SHARES_OUTSTANDING_KEY,
        counts_frame({_CIK: [ShareCount(10e6, date(2024, 3, 31), date(2024, 5, 10))]}),
    )
    ShortInterestStore(s3).append("TA", [ShortInterestRecord.from_counts(
        "TA", date(2024, 5, 15), date(2024, 5, 24), short_interest_shares=200_000,
        average_daily_volume=100_000,
    )])

    def run() -> dict[str, object]:
        return holdings_score_build(
            s3, RULES_VERSION, _FINRA_CALENDAR, floor=True, config_dir=CONFIG_DIR,
            registry_path=CONFIG_DIR / "registry.jsonl", today=date(2024, 7, 1),
        ).run()

    first, second = run(), run()

    assert (first["snapshots_written"], second["snapshots_written"]) == (1, 0)
    assert first["variant"] == "two_component"
    stored = ScoreStore(s3).read("h9", "1", REBALANCE)
    assert stored is not None
    stored.validate()
    row = stored.rows.iloc[0]
    assert (row["cik"], row["variant"], row["components"]) == (_CIK, "two_component", 2)
    assert pd.Timestamp(row["known_at_max"]) == accepted(date(2024, 5, 10))
