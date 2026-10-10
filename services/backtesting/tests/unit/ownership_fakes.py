"""Fakes and builders shared by the ownership panel tests."""

import io
import zipfile
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from minio.error import S3Error

from auspex_backtesting.hypothesis import register_hypothesis
from auspex_backtesting.ownership import SecNotFoundError


class FakeMinio:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, bucket: str, key: str, data: io.BytesIO, length: int, **_: object) -> None:
        self.objects[key] = data.read(length)

    def stat_object(self, bucket: str, key: str) -> object:
        if key not in self.objects:
            raise S3Error(MagicMock(), "NoSuchKey", "missing", "/", "", "")
        return object()

    def get_object(self, bucket: str, key: str) -> MagicMock:
        if key not in self.objects:
            raise S3Error(MagicMock(), "NoSuchKey", "missing", "/", "", "")
        response = MagicMock()
        response.read.return_value = self.objects[key]
        return response

    def list_objects(self, bucket: str, prefix: str = "", recursive: bool = False) -> list[Any]:
        return [MagicMock(object_name=k) for k in sorted(self.objects) if k.startswith(prefix)]


class FakeSec:
    """Serves fixed bodies by URL and records every request."""

    def __init__(self, bodies: Mapping[str, bytes] | None = None) -> None:
        self.bodies = dict(bodies or {})
        self.requested: list[str] = []

    def get(self, url: str) -> bytes:
        self.requested.append(url)
        if url not in self.bodies:
            raise SecNotFoundError(url)
        return self.bodies[url]

    def download(self, url: str, dest: Path) -> Path:
        dest.write_bytes(self.get(url))
        return dest


class FixedMarketCaps:
    def __init__(self, caps: Mapping[str, float]) -> None:
        self.caps = caps

    def market_cap_usd(self, cik: str, as_of: date) -> float | None:
        return self.caps.get(cik)


def tsv(rows: Iterable[Mapping[str, object]]) -> bytes:
    rows = list(rows)
    header = list(rows[0])
    lines = ["\t".join(header)] + [
        "\t".join("" if r.get(h) is None else str(r[h]) for h in header) for r in rows
    ]
    return ("\n".join(lines) + "\n").encode()


def make_zip(files: Mapping[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


REPOSITORY_H9 = Path(__file__).resolve().parents[4] / "config" / "hypotheses" / "h9.yaml"


def h9_with_thresholds(healthcare_share: float, min_aum_usd: float) -> str:
    """The repository's H9 with other specialist thresholds, so it still passes shape checks."""
    text = REPOSITORY_H9.read_text()
    text = text.replace("SPECIALIST_HEALTHCARE_SHARE: 0.5", f"SPECIALIST_HEALTHCARE_SHARE: {healthcare_share}")
    return text.replace("SPECIALIST_MIN_AUM_USD: 100000000", f"SPECIALIST_MIN_AUM_USD: {min_aum_usd:.0f}")


def register_h9(config_dir: Path, *, healthcare_share: float, min_aum_usd: float) -> Path:
    """Registers an H9 with these thresholds under `config_dir`; returns the registry."""
    registry = config_dir / "registry.jsonl"
    register_hypothesis(
        "h9",
        h9_with_thresholds(healthcare_share, min_aum_usd),
        config_dir=config_dir,
        registry_path=registry,
    )
    return registry
