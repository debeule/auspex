"""Additive mirror of a MinIO bucket into a folder.

An object is downloaded when it is new, or its ETag or size changed since the last mirror. An
object deleted from MinIO stays in the mirror, so the mirror can recover it.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class _Object(Protocol):
    object_name: str | None
    etag: str | None
    size: int | None


class MinioReader(Protocol):
    def list_objects(self, bucket_name: str, *, recursive: bool = ...) -> Iterable[_Object]: ...

    def fget_object(self, bucket_name: str, object_name: str, file_path: str) -> object: ...


@dataclass(frozen=True)
class MirrorResult:
    objects: int
    copied: int
    bytes: int


def mirror_bucket(client: MinioReader, bucket: str, root: Path) -> MirrorResult:
    """Mirrors `bucket` into `root/<bucket>/`, keeping its index in `root/.index/<bucket>.json`."""
    target = (root / bucket).resolve()
    index_path = root / ".index" / f"{bucket}.json"
    index: dict[str, dict[str, object]] = (
        json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    )
    objects = copied = total = 0
    for obj in client.list_objects(bucket, recursive=True):
        key = obj.object_name or ""
        local = (target / key).resolve()
        if not local.is_relative_to(target) or local == target:
            raise ValueError(f"object key {key!r} in {bucket} escapes the mirror folder")
        objects += 1
        total += obj.size or 0
        seen: dict[str, object] = {"etag": obj.etag, "size": obj.size}
        if index.get(key) == seen and local.exists():
            continue
        client.fget_object(bucket, key, str(local))
        index[key] = seen
        copied += 1
    _write_atomically(index_path, json.dumps(index, sort_keys=True))
    return MirrorResult(objects, copied, total)


def _write_atomically(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)
