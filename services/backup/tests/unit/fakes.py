"""Recording stand-ins for the MinIO client, the Neo4j driver and the command runner."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Self


@dataclass
class FakeObject:
    object_name: str
    etag: str
    size: int


class FakeMinio:
    """Buckets of `key -> bytes`; records every method called on it."""

    def __init__(self, buckets: dict[str, dict[str, bytes]] | None = None) -> None:
        self.buckets: dict[str, dict[str, bytes]] = buckets or {}
        self.calls: list[str] = []
        self.downloads: list[tuple[str, str]] = []

    @staticmethod
    def etag_of(data: bytes) -> str:
        import hashlib

        return hashlib.md5(data, usedforsecurity=False).hexdigest()

    def list_objects(self, bucket: str, recursive: bool = False) -> Iterator[FakeObject]:
        self.calls.append("list_objects")
        for key, data in sorted(self.buckets.get(bucket, {}).items()):
            yield FakeObject(key, self.etag_of(data), len(data))

    def fget_object(self, bucket: str, key: str, path: str) -> None:
        self.calls.append("fget_object")
        self.downloads.append((bucket, key))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(self.buckets[bucket][key])

    def fput_object(self, bucket: str, key: str, path: str) -> None:
        self.calls.append("fput_object")
        self.buckets.setdefault(bucket, {})[key] = Path(path).read_bytes()

    def __getattr__(self, name: str) -> Callable[..., Any]:
        def record(*args: Any, **kwargs: Any) -> None:
            self.calls.append(name)

        return record


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._rows)

    def single(self) -> dict[str, Any]:
        return self._rows[0]

    def consume(self) -> None:
        return None


@dataclass
class FakeTx:
    graph: FakeGraph
    queries: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def run(self, query: str, parameters: dict[str, Any] | None = None, **kw: Any) -> FakeResult:
        params = {**(parameters or {}), **kw}
        self.queries.append((query, params))
        return FakeResult(self.graph.answer(query, params))


class FakeGraph:
    """Answers the export's two reads and the emptiness count from fixed nodes and rels."""

    def __init__(
        self, nodes: list[dict[str, Any]] | None = None, rels: list[dict[str, Any]] | None = None
    ) -> None:
        self.nodes = nodes or []
        self.rels = rels or []
        self.reads = 0
        self.writes = 0
        self.queries: list[tuple[str, dict[str, Any]]] = []

    def answer(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.queries.append((query, params))
        if "count(n)" in query:
            return [{"count": len(self.nodes)}]
        if "MATCH (n)" in query:
            return [
                {"id": n["id"], "labels": n["labels"], "properties": n["properties"]}
                for n in self.nodes
            ]
        if "MATCH (a)-[r]->(b)" in query:
            return [
                {
                    "id": r["id"],
                    "type": r["type"],
                    "start": r["start"],
                    "end": r["end"],
                    "properties": r["properties"],
                }
                for r in self.rels
            ]
        if "UNWIND $rows" in query and "CREATE (n" in query:
            return [{"old": row["id"], "new": f"new-{row['id']}"} for row in params["rows"]]
        return []


class FakeSession:
    def __init__(self, graph: FakeGraph) -> None:
        self.graph = graph

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None
    ) -> None:
        return None

    def execute_read(self, work: Callable[..., Any], *args: Any) -> Any:
        self.graph.reads += 1
        return work(FakeTx(self.graph), *args)

    def execute_write(self, work: Callable[..., Any], *args: Any) -> Any:
        self.graph.writes += 1
        return work(FakeTx(self.graph), *args)


class FakeDriver:
    def __init__(self, graph: FakeGraph) -> None:
        self.graph = graph

    def session(self, **kwargs: Any) -> FakeSession:
        return FakeSession(self.graph)


@dataclass
class Call:
    argv: list[str]
    env: dict[str, str]
    stdin: Path | None
    stdout: Path | None


class FakeRunner:
    """Records each command; writes `output` to `stdout` when one is given, else returns it."""

    def __init__(self, output: bytes = b"PGDMP-fake", fail_on: str | None = None) -> None:
        self.calls: list[Call] = []
        self.output = output
        self.fail_on = fail_on

    def __call__(
        self,
        argv: Sequence[str],
        env: Mapping[str, str],
        *,
        stdin: Path | None = None,
        stdout: Path | None = None,
    ) -> bytes:
        self.calls.append(Call(list(argv), dict(env), stdin, stdout))
        if self.fail_on and any(self.fail_on in a for a in argv):
            if stdout is not None:
                stdout.write_bytes(self.output[:3])  # a dump cut off part-way
            raise RuntimeError(f"{argv[0]} failed")
        if stdout is not None:
            stdout.write_bytes(self.output)
            return b""
        return self.output
