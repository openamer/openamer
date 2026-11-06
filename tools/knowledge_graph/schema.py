"""The knowledge graph's storage layer.

A pristine SQLite schema for ``knowledge_graph.db``: the tables the
graph needs, created from scratch, with the indexes and constraints
that make it a graph rather than a pile of rows.

The schema is created here rather than by a migration chain on purpose.
A fresh install starts from a known state, and the tests assert that
the state is exactly what this module declares -- no orphaned tables
from an older version, no column that nothing reads.

The design rules:

  * every edge is directed and typed,
  * every edge names both endpoints, and the schema enforces it,
  * the timestamps are stored as integers (microseconds since the
    epoch), so they sort and compare without a collation surprise,
  * nothing is deleted implicitly: the soft-delete columns keep the
    history, because a knowledge graph that forgets is worse than one
    that grows.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Iterable, Optional

SCHEMA_VERSION = 1

# The tables, in dependency order. The foreign keys make the order
# load-bearing: a node must exist before an edge can point at it.
SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS nodes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        kind        TEXT    NOT NULL,
        name        TEXT    NOT NULL,
        payload     TEXT    NOT NULL DEFAULT '{}',
        confidence  REAL    NOT NULL DEFAULT 1.0,
        created_at  INTEGER NOT NULL,
        updated_at  INTEGER NOT NULL,
        deleted_at  INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edges (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        src_id      INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
        dst_id      INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
        relation    TEXT    NOT NULL,
        weight      REAL    NOT NULL DEFAULT 1.0,
        payload     TEXT    NOT NULL DEFAULT '{}',
        created_at  INTEGER NOT NULL,
        updated_at  INTEGER NOT NULL,
        deleted_at  INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS observations (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        node_id     INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
        text        TEXT    NOT NULL,
        created_at  INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS relations (
        name        TEXT PRIMARY KEY,
        description TEXT NOT NULL DEFAULT '',
        directed    INTEGER NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cause_effect (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        cause_id    INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
        effect_id   INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
        strength    REAL    NOT NULL DEFAULT 1.0,
        created_at  INTEGER NOT NULL,
        UNIQUE (cause_id, effect_id)
    )
    """,
)

INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_deleted ON nodes(deleted_at)",
    "CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_id)",
    "CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_id)",
    "CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation)",
    "CREATE INDEX IF NOT EXISTS idx_observations_node ON observations(node_id)",
    "CREATE INDEX IF NOT EXISTS idx_cause_effect_cause ON cause_effect(cause_id)",
    "CREATE INDEX IF NOT EXISTS idx_cause_effect_effect ON cause_effect(effect_id)",
)


def now_us() -> int:
    """The current time in microseconds since the epoch.

    Integer microseconds sort and compare as plain integers, which a
    float timestamp does not guarantee at the sizes a long-running
    agent reaches.
    """
    return int(time.time() * 1_000_000)


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the database and apply the schema.

    The foreign keys are switched on explicitly: SQLite leaves them off
    by default, and a graph whose edges may dangle is not a graph.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create the schema if it is not there yet.

    Idempotent: running it against an existing database changes
    nothing. That is what makes it safe to call on every connect.
    """
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    for statement in INDEX_STATEMENTS:
        conn.execute(statement)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()


def table_names(conn: sqlite3.Connection) -> list[str]:
    """The user tables in the database, sorted."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows]


def index_names(conn: sqlite3.Connection) -> list[str]:
    """The indexes in the database, sorted."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows]


def add_node(
    conn: sqlite3.Connection,
    kind: str,
    name: str,
    payload: str = "{}",
    confidence: float = 1.0,
) -> int:
    """Insert a node and return its id."""
    stamp = now_us()
    cursor = conn.execute(
        "INSERT INTO nodes (kind, name, payload, confidence, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (kind, name, payload, confidence, stamp, stamp),
    )
    conn.commit()
    return int(cursor.lastrowid)


def add_edge(
    conn: sqlite3.Connection,
    src_id: int,
    dst_id: int,
    relation: str,
    weight: float = 1.0,
    payload: str = "{}",
) -> int:
    """Insert an edge between two nodes and return its id."""
    stamp = now_us()
    cursor = conn.execute(
        "INSERT INTO edges (src_id, dst_id, relation, weight, payload, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (src_id, dst_id, relation, weight, payload, stamp, stamp),
    )
    conn.commit()
    return int(cursor.lastrowid)


def add_observation(
    conn: sqlite3.Connection, node_id: int, text: str
) -> int:
    """Attach an observation to a node and return its id."""
    cursor = conn.execute(
        "INSERT INTO observations (node_id, text, created_at) VALUES (?, ?, ?)",
        (node_id, text, now_us()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def add_cause_effect(
    conn: sqlite3.Connection, cause_id: int, effect_id: int, strength: float = 1.0
) -> int:
    """Record a causal relation and return its id."""
    cursor = conn.execute(
        "INSERT INTO cause_effect (cause_id, effect_id, strength, created_at) "
        "VALUES (?, ?, ?, ?)",
        (cause_id, effect_id, strength, now_us()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_node(conn: sqlite3.Connection, node_id: int) -> Optional[sqlite3.Row]:
    """One node, or None."""
    return conn.execute(
        "SELECT * FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()


def neighbours(
    conn: sqlite3.Connection, node_id: int, relation: Optional[str] = None
) -> list[sqlite3.Row]:
    """The edges leaving a node, optionally filtered by relation."""
    if relation is None:
        rows = conn.execute(
            "SELECT * FROM edges WHERE src_id = ? AND deleted_at IS NULL "
            "ORDER BY id",
            (node_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM edges WHERE src_id = ? AND relation = ? "
            "AND deleted_at IS NULL ORDER BY id",
            (node_id, relation),
        ).fetchall()
    return list(rows)


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    """How many rows a table has."""
    if table not in table_names(conn):
        raise ValueError(f"no such table: {table}")
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return int(row["n"])


def close(conn: sqlite3.Connection) -> None:
    """Close the connection, committing first."""
    try:
        conn.commit()
    finally:
        conn.close()
