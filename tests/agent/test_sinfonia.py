"""Tests for scripts/sinfonia.py - session-history symphony engine."""
import json
import sqlite3
import sys
import wave
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import sinfonia  # noqa: E402


@pytest.fixture
def tmp_db(tmp_path):
    db = tmp_path / "state.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY, started_at TEXT, title TEXT,
            message_count INTEGER, tool_call_count INTEGER,
            input_tokens INTEGER, output_tokens INTEGER,
            estimated_cost_usd REAL
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY, session_id INTEGER, role TEXT,
            content TEXT, tool_name TEXT, token_count INTEGER,
            timestamp TEXT, active INTEGER DEFAULT 1
        );
        """
    )
    con.execute(
        "INSERT INTO sessions VALUES (1,'2026-08-30T10:00:00','Build x',3,1,100,50,0.01)"
    )
    con.executemany(
        "INSERT INTO messages (session_id, role, content, tool_name, token_count, timestamp) VALUES (?,?,?,?,?,?)",
        [
            (1, "user", "hello world", None, 10, "2026-08-30T10:00:01"),
            (1, "tool", "error: traceback failed", "terminal", 20, "2026-08-30T10:00:02"),
            (1, "assistant", "all fixed and done", None, 30, "2026-08-30T10:00:03"),
        ],
    )
    con.commit()
    con.close()
    return db


def test_deterministic(tmp_db, tmp_path):
    outs = []
    for i in (1, 2):
        out = tmp_path / f"s{i}"
        sinfonia.main.__wrapped__ if hasattr(sinfonia.main, "__wrapped__") else None
        sinfonia.compose_and_render(tmp_db, out, sessions=1)
        outs.append(out.with_suffix(".wav").read_bytes())
    assert outs[0] == outs[1], "same DB must produce identical WAV"


def test_error_counts_and_dissonance_bias(tmp_db):
    movs = sinfonia.load_history(tmp_db, 5)
    events, meta = sinfonia.compose_movement(movs[0], 57, 96, "k")
    assert meta is not None
    assert meta["messages"] == 3
    assert meta["errors"] == 1  # the tool message contains 'error'


def test_render_audio_health(tmp_db, tmp_path):
    out = tmp_path / "s"
    dur = sinfonia.compose_and_render(tmp_db, out, sessions=1)
    with wave.open(str(out.with_suffix(".wav"))) as w:
        frames = w.readframes(w.getnframes())
        peak = max(abs(int.from_bytes(frames[i : i + 2], "little", signed=True)) for i in range(0, len(frames), 2))
    assert dur > 0
    assert peak < 32000, "no clipping"
    payload = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["movements"][0]["errors"] == 1
