"""Export of the Neo4j graph to JSON lines, and its replay into an empty database.

Community edition can only dump a stopped database, so the export reads every node and
relationship in one read transaction over bolt. Element ids in the file only link relationships to
nodes within it; replay creates new nodes and maps the old ids to the new ones.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from neo4j.time import Date, DateTime, Duration, Time

# Cypher cannot take a label or relationship type as a parameter, so they are written into the
# query; only plain identifiers get that far.
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BATCH = 1000

_NODES = "MATCH (n) RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS properties"
_RELATIONSHIPS = (
    "MATCH (a)-[r]->(b) RETURN elementId(r) AS id, type(r) AS type, "
    "elementId(a) AS start, elementId(b) AS end, properties(r) AS properties"
)
_COUNT = "MATCH (n) RETURN count(n) AS count"

_TEMPORAL_TAGS: dict[str, Callable[[str], Any]] = {
    "$date": Date.from_iso_format,
    "$datetime": DateTime.from_iso_format,
    "$time": Time.from_iso_format,
    "$duration": Duration.from_iso_format,
}


class Transaction(Protocol):
    def run(self, query: str, parameters: dict[str, Any] | None = None, **kw: Any) -> Any: ...


class Driver(Protocol):
    """The part of `neo4j.Driver` used here; `session()` gives a context-managed session with
    `execute_read` and `execute_write`."""

    def session(self) -> Any: ...


class InvalidIdentifierError(ValueError):
    """A label or relationship type in a graph file is not a plain identifier."""


@dataclass(frozen=True)
class GraphCounts:
    nodes: int
    relationships: int


def export_graph(driver: Driver, path: Path) -> GraphCounts:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")

    def work(tx: Transaction) -> GraphCounts:
        # A retried transaction starts the file again.
        nodes = relationships = 0
        with partial.open("w", encoding="utf-8") as out:
            for record in tx.run(_NODES):
                line = {
                    "kind": "node",
                    "id": record["id"],
                    "labels": list(record["labels"]),
                    "properties": _encode(dict(record["properties"])),
                }
                out.write(json.dumps(line) + "\n")
                nodes += 1
            for record in tx.run(_RELATIONSHIPS):
                line = {
                    "kind": "relationship",
                    "id": record["id"],
                    "type": record["type"],
                    "start": record["start"],
                    "end": record["end"],
                    "properties": _encode(dict(record["properties"])),
                }
                out.write(json.dumps(line) + "\n")
                relationships += 1
        return GraphCounts(nodes, relationships)

    try:
        with driver.session() as session:
            counts: GraphCounts = session.execute_read(work)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    os.replace(partial, path)
    return counts


def node_count(driver: Driver) -> int:
    with driver.session() as session:
        count: int = session.execute_read(lambda tx: tx.run(_COUNT).single()["count"])
    return count


def replay_graph(driver: Driver, path: Path) -> GraphCounts:
    """Creates every node, then every relationship, from `path` in the database behind `driver`.

    The whole file is checked before anything is written.
    """
    nodes: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    relationships: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in _read_lines(path):
        if line["kind"] == "node":
            labels = tuple(line["labels"])
            for label in labels:
                _check_identifier(label)
            nodes[labels].append({"id": line["id"], "properties": _decode(line["properties"])})
        else:
            _check_identifier(line["type"])
            relationships[line["type"]].append(line)

    new_ids: dict[str, str] = {}
    with driver.session() as session:
        for labels, rows in nodes.items():
            query = (
                "UNWIND $rows AS row CREATE (n"
                + "".join(f":`{label}`" for label in labels)
                + ") SET n = row.properties RETURN row.id AS old, elementId(n) AS new"
            )
            for batch in _batches(rows):
                created = session.execute_write(
                    lambda tx, q=query, b=batch: [(r["old"], r["new"]) for r in tx.run(q, rows=b)]
                )
                new_ids.update(created)
        for rel_type, lines in relationships.items():
            query = (
                "UNWIND $rows AS row "
                "MATCH (a) WHERE elementId(a) = row.start "
                "MATCH (b) WHERE elementId(b) = row.end "
                f"CREATE (a)-[r:`{rel_type}`]->(b) SET r = row.properties"
            )
            rows = [
                {
                    "start": new_ids[line["start"]],
                    "end": new_ids[line["end"]],
                    "properties": _decode(line["properties"]),
                }
                for line in lines
            ]
            for batch in _batches(rows):
                session.execute_write(lambda tx, q=query, b=batch: tx.run(q, rows=b).consume())
    return GraphCounts(
        sum(len(rows) for rows in nodes.values()),
        sum(len(lines) for lines in relationships.values()),
    )


def _check_identifier(name: object) -> None:
    if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
        raise InvalidIdentifierError(f"{name!r} is not a plain label or relationship type")


def _read_lines(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            if line.strip():
                yield json.loads(line)


def _batches(rows: list[dict[str, Any]]) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), _BATCH):
        yield rows[start : start + _BATCH]


def _encode(value: Any) -> Any:
    # Property values are scalars, temporals or lists of them; Neo4j has no map properties, so a
    # one-key tagged dict can only be an encoded temporal.
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_encode(v) for v in value]
    if isinstance(value, DateTime):
        return {"$datetime": value.iso_format()}
    if isinstance(value, Date):
        return {"$date": value.iso_format()}
    if isinstance(value, Time):
        return {"$time": value.iso_format()}
    if isinstance(value, Duration):
        return {"$duration": value.iso_format()}
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"cannot back up a property of type {type(value).__name__}")


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        if len(value) == 1:
            ((tag, text),) = value.items()
            if tag in _TEMPORAL_TAGS:
                return _TEMPORAL_TAGS[tag](text)
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value
