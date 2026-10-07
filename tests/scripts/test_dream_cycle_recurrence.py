"""Regression test: dream-cycle nightmare detection must actually fire.

Bug pinned here: the per-day motif map was stored only in an in-memory
`_motifs` key that was popped from dreams.json immediately before the file
was written, so `cross_day_recurrence()` always returned 0 and `nightmare`
(rec >= 3) could never become True -- no matter how often a motif recurred.
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import pathlib
import sqlite3
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "scripts" / "dream_cycle.py"


def _load():
    spec = importlib.util.spec_from_file_location("dream_cycle", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cross_day_recurrence_counts_prior_days():
    dc = _load()
    prior = [{"date": f"2026-09-{d:02d}", "motifs": {"timeout": 6}} for d in (19, 20, 21)]

    # the real threshold the nightmare branch uses
    assert dc.cross_day_recurrence(prior, "timeout") == 3
    assert dc.cross_day_recurrence(prior, "timeout") >= 3

    # legacy records that only carry the old in-memory key still count
    assert dc.cross_day_recurrence([{"date": "x", "_motifs": {"timeout": 1}}], "timeout") == 1

    # a record with neither key contributes nothing
    assert dc.cross_day_recurrence([{"date": "x"}], "timeout") == 0


def test_motifs_are_persisted_and_recurrence_is_nonzero():
    """End-to-end: dream() must write motif data so the next day can see it."""
    dc = _load()
    with tempfile.TemporaryDirectory() as td:
        home = pathlib.Path(td)
        (home / "reports").mkdir()

        con = sqlite3.connect(str(home / "state.db"))
        con.execute("CREATE TABLE messages (role TEXT, content TEXT, timestamp REAL)")
        ts = _dt.datetime(2026, 9, 22, 12, 0).timestamp()
        con.execute("INSERT INTO messages VALUES (?,?,?)",
                    ("assistant", "ERROR: request timeout after 30s", ts))
        con.commit()
        con.close()

        dc.BASE = home
        dc.STATE_DB = home / "state.db"
        dc.DREAMS = home / "dreams.json"
        dc.REPORTS = home / "reports"
        dc.DREAMS.write_text(json.dumps(
            [{"date": "2026-09-20", "motifs": {"timeout": 5}},
             {"date": "2026-09-21", "motifs": {"timeout": 4}}]), encoding="utf-8")

        rep_path = dc.dream("2026-09-22")
        on_disk = json.loads(dc.DREAMS.read_text(encoding="utf-8"))

        today = next(e for e in on_disk if e["date"] == "2026-09-22")
        assert today.get("motifs"), "motif map was not persisted -> recurrence stays 0"
        assert all("_motifs" not in e for e in on_disk), "legacy key leaked into the file"

        ins = next(i for i in today["insights"] if i["motif"] == "timeout")
        assert ins["recurrence_days"] == 2, ins
        assert "seen on 2 prior days" in pathlib.Path(rep_path).read_text(encoding="utf-8")
