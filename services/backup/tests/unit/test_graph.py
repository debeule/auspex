import json
from datetime import UTC
from pathlib import Path

import pytest
from fakes import FakeDriver, FakeGraph
from neo4j.time import Date, DateTime

from auspex_backup.graph import InvalidIdentifierError, export_graph, replay_graph

_NODES = [
    {
        "id": "4:x:1",
        "labels": ["Company"],
        "properties": {"name": "acme", "ticker": "ACME", "aliases": ["acme inc"]},
    },
    {
        "id": "4:x:2",
        "labels": ["Signal", "Corroborated"],
        "properties": {
            "event_id": "e-1",
            "confidence_score": 0.875,
            "published_date": Date(2026, 9, 1),
            "corroborated_at": DateTime(2026, 9, 2, 14, 30, 0, tzinfo=UTC),
        },
    },
]
_RELS = [
    {"id": "5:x:9", "type": "MENTIONS", "start": "4:x:2", "end": "4:x:1", "properties": {"w": 1}},
]


def _lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_neo4j_export_writes_every_node_and_relationship_with_labels_and_properties(
    tmp_path: Path,
) -> None:
    graph = FakeGraph(_NODES, _RELS)
    path = tmp_path / "neo4j" / "2026-10-10" / "graph.jsonl"

    counts = export_graph(FakeDriver(graph), path)

    assert (counts.nodes, counts.relationships) == (2, 1)
    assert graph.reads == 1, "nodes and relationships must come from one read transaction"
    lines = _lines(path)
    assert lines[0] == {
        "kind": "node",
        "id": "4:x:1",
        "labels": ["Company"],
        "properties": {"name": "acme", "ticker": "ACME", "aliases": ["acme inc"]},
    }
    signal = lines[1]
    assert signal["labels"] == ["Signal", "Corroborated"]
    assert signal["properties"]["confidence_score"] == 0.875
    assert signal["properties"]["published_date"] == {"$date": "2026-09-01"}
    assert signal["properties"]["corroborated_at"] == {
        "$datetime": "2026-09-02T14:30:00.000000000+00:00"
    }
    assert lines[2] == {
        "kind": "relationship",
        "id": "5:x:9",
        "type": "MENTIONS",
        "start": "4:x:2",
        "end": "4:x:1",
        "properties": {"w": 1},
    }


def test_neo4j_replay_creates_nodes_then_relationships_between_the_new_ids(
    tmp_path: Path,
) -> None:
    path = tmp_path / "graph.jsonl"
    export_graph(FakeDriver(FakeGraph(_NODES, _RELS)), path)
    target = FakeGraph()

    counts = replay_graph(FakeDriver(target), path)

    assert (counts.nodes, counts.relationships) == (2, 1)
    creates = [(q, p) for q, p in target.queries if "CREATE" in q]
    assert "CREATE (n:`Company`)" in creates[0][0]
    assert "CREATE (n:`Signal`:`Corroborated`)" in creates[1][0]
    signal_props = creates[1][1]["rows"][0]["properties"]
    assert signal_props["published_date"] == Date(2026, 9, 1)
    assert signal_props["corroborated_at"] == DateTime(2026, 9, 2, 14, 30, 0, tzinfo=UTC)
    rel_query, rel_params = creates[2]
    assert "[r:`MENTIONS`]" in rel_query
    assert rel_params["rows"] == [{"start": "new-4:x:2", "end": "new-4:x:1", "properties": {"w": 1}}]


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "node", "id": "1", "labels": ["Company`) DETACH DELETE (m"], "properties": {}},
        {"kind": "node", "id": "1", "labels": ["has space"], "properties": {}},
        {"kind": "relationship", "id": "2", "type": "X]->() //", "start": "1", "end": "1",
         "properties": {}},
    ],
)
def test_neo4j_replay_rejects_a_label_that_is_not_a_plain_identifier(
    tmp_path: Path, bad: dict[str, object]
) -> None:
    path = tmp_path / "graph.jsonl"
    good = {"kind": "node", "id": "0", "labels": ["Company"], "properties": {}}
    path.write_text(json.dumps(good) + "\n" + json.dumps(bad) + "\n")
    target = FakeGraph()

    with pytest.raises(InvalidIdentifierError):
        replay_graph(FakeDriver(target), path)
    assert target.writes == 0, "nothing may be written before the whole file is checked"
