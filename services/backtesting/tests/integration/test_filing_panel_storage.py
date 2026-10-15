import gzip
import json
import os
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from catalyst_support import FakeWeb
from filing_support import (
    ACME,
    ARCHIVES,
    FULL_INDEX,
    TODAY,
    USER_AGENT,
    filing_pages,
    member,
    quarter_index,
    risk_document,
)
from minio import Minio
from testcontainers.core.container import DockerContainer

from auspex_backtesting.catalysts import DocumentCache, HttpSource
from auspex_backtesting.filings import (
    FilingIndex,
    FilingPanelBuild,
    FilingSectionArchive,
    score_version,
)
from auspex_backtesting.portfolio.scores import ScoreStore
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET
from auspex_backtesting.universe import UniverseSnapshot, UniverseStore

pytestmark = [pytest.mark.integration, pytest.mark.enable_socket]

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
_LOCALSTACK_IMAGE = "localstack/localstack:4.9.2"


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


def _pages() -> dict[str, str]:
    k22, k23 = f"{ACME}-23-000001", f"{ACME}-24-000001"
    return {
        **filing_pages(ACME, k22, "10-K", "2023-03-01 16:05:00", "2022-12-31",
                       risk_document("10-K", "Our trials may fail.")),
        **filing_pages(ACME, k23, "10-K", "2024-02-28 16:05:00", "2023-12-31",
                       risk_document("10-K", "Our trials may fail and we need capital.")),
        f"{FULL_INDEX}/2023/QTR1/master.idx": quarter_index([(ACME, "10-K", "2023-03-01", k22)]),
        f"{FULL_INDEX}/2024/QTR1/master.idx": quarter_index([(ACME, "10-K", "2024-02-28", k23)]),
    }


def _build(s3: Minio, web: FakeWeb, rules_path: Path) -> FilingPanelBuild:
    sec = HttpSource(USER_AGENT, 0.0, fetch=web, sleep=lambda _: None)
    universe = UniverseStore.for_rules_file(s3, rules_path)
    return FilingPanelBuild(
        FilingIndex(s3, FULL_INDEX, sec, DocumentCache(s3), today=lambda: TODAY),
        FilingSectionArchive(s3, ARCHIVES, sec),
        universe,
        1,
        ScoreStore(s3),
        "h10",
        score_version(1, universe.universe),
        today=lambda: TODAY,
    )


def test_filing_panel_archives_sections_and_writes_snapshots_in_object_storage(
    s3: Minio, tmp_path: Path
) -> None:
    rules_path = tmp_path / "broad.yaml"
    rules_path.write_text("version: 1\n", encoding="utf-8")
    universe = UniverseStore.for_rules_file(s3, rules_path)
    universe.write(UniverseSnapshot(1, "2024-03", date(2024, 3, 1), (member(ACME, "ACME"),)))
    web = FakeWeb(_pages())

    summary = _build(s3, web, rules_path).run()
    requested = len(web.requested)
    again = _build(s3, web, rules_path).run()

    keys = {o.object_name for o in s3.list_objects(PRICES_BUCKET, recursive=True)}
    assert summary["complete"] and summary["snapshots_written"] == 1
    assert {
        "universe/broad/1/2024-03.parquet",
        "filings/index/2023-q1.json",
        "filings/index/2024-q1.json",
        f"filings/item1a/{ACME}/{ACME}-24-000001.json.gz",
        "scores/h10/1-broad/2024-03-01.parquet",
    } <= keys
    archived = s3.get_object(PRICES_BUCKET, f"filings/item1a/{ACME}/{ACME}-24-000001.json.gz")
    assert json.loads(gzip.decompress(archived.read()))["status"] == "cut"
    snapshot = ScoreStore(s3).read("h10", "1-broad", date(2024, 3, 1))
    assert snapshot is not None and snapshot.rows["cik"].tolist() == [ACME]
    snapshot.validate()
    assert again["snapshots_written"] == 0
    assert all(url.endswith("master.idx") for url in web.requested[requested:])
