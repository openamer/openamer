"""Tests for scripts/session_to_brain.py — the session-to-brain-data pipeline."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

import scripts.session_to_brain as stb


def test_state_db_not_found(tmp_path, monkeypatch):
    """A missing state.db reports a clean error instead of crashing."""
    monkeypatch.setattr(stb, "_state_db", lambda: tmp_path / "nonexistent.db")
    monkeypatch.setattr(sys, "argv", ["session_to_brain.py"])
    rc = stb.main()
    assert rc == 1


def test_brain_dataset_writes_to_trajectories_dir(monkeypatch):
    """The brain dataset path must be ~/.openamer/trajectories/openamer-brain-trajectories.jsonl."""
    ds = stb._brain_dataset()
    assert "trajectories" in str(ds)
    assert ds.name == "openamer-brain-trajectories.jsonl"
    assert ds.parent.name == "trajectories"


def test_build_trajectory_fingerprint():
    """Each trajectory must have a unique fingerprint for dedup."""
    messages = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    r1 = stb._build_trajectory("sess1", "title", messages)
    r2 = stb._build_trajectory("sess1", "title", messages)
    r3 = stb._build_trajectory("sess2", "title", messages)
    assert r1["_fingerprint"] == r2["_fingerprint"]  # same session+content
    assert r1["_fingerprint"] != r3["_fingerprint"]  # different session


def test_build_trajectory_stats():
    """Stats count user/assistant/tool turns correctly."""
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello", "tool_calls": ["ls"]},
        {"role": "tool", "content": "result"},
        {"role": "assistant", "content": "done"},
    ]
    r = stb._build_trajectory("s1", "t", messages)
    assert r["stats"]["total_turns"] == 4
    assert r["stats"]["user_turns"] == 1
    assert r["stats"]["assistant_turns"] == 2
    assert r["stats"]["tool_turns"] == 1


def test_dry_run_does_not_write(tmp_path, monkeypatch):
    """--dry-run must not create the dataset file."""
    ds = tmp_path / "brain.jsonl"
    monkeypatch.setattr(stb, "_brain_dataset", lambda: ds)
    db = sqlite3.connect(str(tmp_path / "state.db"))
    db.execute("CREATE TABLE sessions (id TEXT, title TEXT, started_at REAL)")
    db.execute("INSERT INTO sessions VALUES ('s1', 'test', 1.0)")
    db.execute("CREATE TABLE messages (id INTEGER, session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, timestamp REAL)")
    db.execute("INSERT INTO messages VALUES (1, 's1', 'user', 'hi', NULL, 1.0)")
    db.execute("INSERT INTO messages VALUES (2, 's1', 'assistant', 'hello', '[]', 2.0)")
    db.commit()
    db.close()

    monkeypatch.setattr(sys, "argv", ["session_to_brain.py", "--dry-run"])
    monkeypatch.setattr(stb, "_state_db", lambda: tmp_path / "state.db")
    rc = stb.main()
    assert rc == 0
    assert not ds.exists()  # dry-run must not write