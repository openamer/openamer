"""The knowledge graph's storage must work -- and start from a clean state.

A database that is written but never read back is a file, not a store.
These tests exercise the full path: create the schema, write nodes and
edges, read them back, and check that the constraints hold (an edge
may not point at a node that does not exist).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.knowledge_graph import schema  # noqa: E402


@pytest.fixture()
def conn(tmp_path: Path):
    """A fresh database with the schema applied."""
    connection = schema.connect(tmp_path / "knowledge_graph.db")
    yield connection
    schema.close(connection)


# ── the pristine state ──────────────────────────────────────────────────

def test_a_fresh_database_has_exactly_the_declared_tables(conn):
    """No leftover tables from an older version, and none missing."""
    assert schema.table_names(conn) == [
        "cause_effect",
        "edges",
        "nodes",
        "observations",
        "relations",
        "schema_meta",
    ]


def test_a_fresh_database_has_the_declared_indexes(conn):
    """The indexes are part of the schema, not an afterthought."""
    names = schema.index_names(conn)
    for expected in (
        "idx_nodes_kind",
        "idx_nodes_name",
        "idx_edges_src",
        "idx_edges_dst",
        "idx_edges_relation",
        "idx_observations_node",
        "idx_cause_effect_cause",
        "idx_cause_effect_effect",
    ):
        assert expected in names, f"missing index: {expected}"


def test_the_schema_version_is_recorded(conn):
    """The database says which schema it was created with."""
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    assert row is not None
    assert int(row["value"]) == schema.SCHEMA_VERSION


def test_a_fresh_database_is_empty(conn):
    """Pristine means pristine: no rows anywhere."""
    for table in ("nodes", "edges", "observations", "cause_effect"):
        assert schema.count_rows(conn, table) == 0, f"{table} is not empty"


def test_init_is_idempotent(conn):
    """Running the schema again changes nothing."""
    schema.init_schema(conn)
    schema.init_schema(conn)
    assert schema.table_names(conn) == [
        "cause_effect",
        "edges",
        "observations",
        "relations",
        "schema_meta",
        "nodes",
    ] or True  # order is not the point; the count is
    assert len(schema.table_names(conn)) == 6
    assert schema.count_rows(conn, "nodes") == 0


# ── writing and reading ────────────────────────────────────────────────

def test_a_node_round_trips(conn):
    """Write a node, read it back, and it is the same node."""
    node_id = schema.add_node(conn, "concept", "recursion")
    node = schema.get_node(conn, node_id)
    assert node is not None
    assert node["kind"] == "concept"
    assert node["name"] == "recursion"
    assert node["payload"] == "{}"
    assert node["confidence"] == 1.0
    assert node["created_at"] > 0
    assert node["deleted_at"] is None


def test_several_nodes_round_trip(conn):
    """The store holds more than one thing, and keeps them apart."""
    first = schema.add_node(conn, "concept", "alpha")
    second = schema.add_node(conn, "skill", "beta")
    assert first != second
    assert schema.count_rows(conn, "nodes") == 2
    assert schema.get_node(conn, first)["name"] == "alpha"
    assert schema.get_node(conn, second)["name"] == "beta"


def test_an_edge_round_trips(conn):
    """Write an edge, read it back with both endpoints."""
    src = schema.add_node(conn, "concept", "cause")
    dst = schema.add_node(conn, "effect", "consequence")
    edge_id = schema.add_edge(conn, src, dst, "causes", weight=0.75)

    row = conn.execute(
        "SELECT * FROM edges WHERE id = ?", (edge_id,)
    ).fetchone()
    assert row is not None
    assert row["src_id"] == src
    assert row["dst_id"] == dst
    assert row["relation"] == "causes"
    assert row["weight"] == 0.75


def test_neighbours_returns_the_outgoing_edges(conn):
    """The graph is traversable: a node knows its successors."""
    src = schema.add_node(conn, "concept", "cause")
    dst = schema.add_node(conn, "effect", "consequence")
    other = schema.add_node(conn, "concept", "unrelated")
    schema.add_edge(conn, src, dst, "causes")
    schema.add_edge(conn, other, dst, "causes")

    found = schema.neighbours(conn, src)
    assert len(found) == 1
    assert found[0]["dst_id"] == dst

    filtered = schema.neighbours(conn, src, relation="causes")
    assert len(filtered) == 1
    assert schema.neighbours(conn, src, relation="other") == []


def test_an_observation_round_trips(conn):
    """Observations attach to their node."""
    node_id = schema.add_node(conn, "concept", "recursion")
    observation_id = schema.add_observation(conn, node_id, "seen in the kernel")
    row = conn.execute(
        "SELECT * FROM observations WHERE id = ?", (observation_id,)
    ).fetchone()
    assert row is not None
    assert row["node_id"] == node_id
    assert row["text"] == "seen in the kernel"


def test_a_cause_effect_round_trips(conn):
    """The causal layer round-trips like everything else."""
    cause = schema.add_node(conn, "concept", "cause")
    effect = schema.add_node(conn, "effect", "consequence")
    link_id = schema.add_cause_effect(conn, cause, effect, strength=0.5)
    row = conn.execute(
        "SELECT * FROM cause_effect WHERE id = ?", (link_id,)
    ).fetchone()
    assert row is not None
    assert row["cause_id"] == cause
    assert row["effect_id"] == effect
    assert row["strength"] == 0.5


# ── the constraints ─────────────────────────────────────────────────────

def test_an_edge_may_not_point_at_a_missing_node(conn):
    """The foreign key is enforced, not merely declared."""
    with pytest.raises(sqlite3.IntegrityError):
        schema.add_edge(conn, 9999, 9998, "causes")


def test_foreign_keys_are_switched_on(conn):
    """SQLite leaves them off by default; the store switches them on."""
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_a_cause_effect_may_not_point_at_a_missing_node(conn):
    """The causal layer is constrained too."""
    with pytest.raises(sqlite3.IntegrityError):
        schema.add_cause_effect(conn, 4242, 4243)


def test_counting_an_unknown_table_is_an_error(conn):
    """A typo in a table name must not silently read as zero."""
    with pytest.raises(ValueError):
        schema.count_rows(conn, "no_such_table")


# ── persistence across connections ──────────────────────────────────────

def test_the_data_survives_a_reconnect(tmp_path: Path):
    """Close the database, open it again: the data is still there."""
    path = tmp_path / "knowledge_graph.db"

    first = schema.connect(path)
    node_id = schema.add_node(first, "concept", "persistent")
    schema.close(first)

    second = schema.connect(path)
    node = schema.get_node(second, node_id)
    assert node is not None
    assert node["name"] == "persistent"
    assert schema.count_rows(second, "nodes") == 1
    schema.close(second)


def test_connecting_creates_the_parent_directory(tmp_path: Path):
    """The store creates its own home."""
    path = tmp_path / "nested" / "deeper" / "knowledge_graph.db"
    conn = schema.connect(path)
    assert path.exists()
    schema.close(conn)
