import json
from pathlib import Path

from fakes import FakeMinio

from auspex_backup.minio_mirror import mirror_bucket


def test_minio_mirror_copies_only_new_or_changed_objects(tmp_path: Path) -> None:
    client = FakeMinio({"auspex-raw": {"a/1.json": b"one", "a/2.json": b"two"}})
    first = mirror_bucket(client, "auspex-raw", tmp_path)
    assert (first.objects, first.copied, first.bytes) == (2, 2, 6)
    assert (tmp_path / "auspex-raw" / "a" / "1.json").read_bytes() == b"one"

    client.buckets["auspex-raw"]["a/2.json"] = b"two, revised"
    client.buckets["auspex-raw"]["a/3.json"] = b"three"
    client.downloads.clear()
    second = mirror_bucket(client, "auspex-raw", tmp_path)

    assert sorted(client.downloads) == [("auspex-raw", "a/2.json"), ("auspex-raw", "a/3.json")]
    assert (second.objects, second.copied) == (3, 2)
    assert (tmp_path / "auspex-raw" / "a" / "2.json").read_bytes() == b"two, revised"

    client.downloads.clear()
    assert mirror_bucket(client, "auspex-raw", tmp_path).copied == 0
    assert client.downloads == []


def test_minio_mirror_recopies_an_object_whose_mirror_file_is_missing(tmp_path: Path) -> None:
    client = FakeMinio({"auspex-prices": {"ohlcv/XBI.parquet": b"bars"}})
    mirror_bucket(client, "auspex-prices", tmp_path)
    (tmp_path / "auspex-prices" / "ohlcv" / "XBI.parquet").unlink()
    assert mirror_bucket(client, "auspex-prices", tmp_path).copied == 1


def test_minio_mirror_keeps_objects_deleted_from_minio(tmp_path: Path) -> None:
    client = FakeMinio({"auspex-raw": {"keep.json": b"k", "gone.json": b"g"}})
    mirror_bucket(client, "auspex-raw", tmp_path)

    del client.buckets["auspex-raw"]["gone.json"]
    result = mirror_bucket(client, "auspex-raw", tmp_path)

    assert result.objects == 1
    assert (tmp_path / "auspex-raw" / "gone.json").read_bytes() == b"g"
    index = json.loads((tmp_path / ".index" / "auspex-raw.json").read_text())
    assert "gone.json" in index


def test_minio_mirror_refuses_a_key_that_escapes_the_bucket_folder(tmp_path: Path) -> None:
    client = FakeMinio({"auspex-raw": {"../outside.json": b"x"}})
    try:
        mirror_bucket(client, "auspex-raw", tmp_path / "minio")
    except ValueError as exc:
        assert "outside.json" in str(exc)
    else:
        raise AssertionError("an escaping key was mirrored")
    assert not (tmp_path / "outside.json").exists()
