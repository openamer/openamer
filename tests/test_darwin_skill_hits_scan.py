"""Regression tests for the skill-mention scan behind compute_fitness.

Why this file exists
--------------------
`_session_skill_hits()` used to pull every user/assistant message body out of
state.db (141k rows / 116 MB of text out of a 2.2 GB database on this host) and
then run a `len(skills) x len(rows)` substring loop over it. Measured
2026-09-22 that was 164s on a cold page cache, which dominated the whole
autopilot cycle (compute_fitness alone 188s of a 409s run) and made the 420s
cron wrapper kill every cold run with `TIMEOUT after 420s`.

The scan is now incremental: a persisted watermark plus per-skill counts, so
each cycle reads only the messages newer than the last one. These tests pin the
three properties that make that safe -- equivalence with the old algorithm,
incremental accumulation, and the rescan that a newly installed skill forces.
"""
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(spec)
sys.modules["darwin_engine"] = darwin
spec.loader.exec_module(darwin)


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A sandbox home with a real sqlite state.db and two installed skills."""
    home = tmp_path / "home"
    skills = home / "skills"
    for name in ("alpha-skill", "beta-skill"):
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_text("# x", encoding="utf-8")
    db = home / "state.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " session_id TEXT, role TEXT, content TEXT, timestamp REAL)")
    rows = [
        ("user", "please run alpha-skill now"),
        ("assistant", "ok, alpha-skill done; also beta-skill"),
        ("user", "nothing relevant here"),
        ("assistant", "alpha-skill again and gamma-skill is not installed"),
        ("tool", "alpha-skill inside a tool row must never count"),
        ("user", None),
    ]
    con.executemany(
        "INSERT INTO messages (session_id, role, content, timestamp)"
        " VALUES ('s1', ?, ?, 1.0)", rows)
    con.commit()
    con.close()

    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "FITNESS_FILE", home / "reports" / "fitness.json")
    monkeypatch.setattr(darwin, "REPORTS_DIR", home / "reports")
    for _name in ("HISTORY_FILE", "REPORT_FILE", "PROBE_FILE", "TUNING_FILE",
                  "LINEAGE_FILE", "ARENA_FILE", "OP_STATS_FILE", "ROLLBACK_LOG",
                  "SYNTHESIS_LOG", "HARVESTED_FILE", "PREDATION_LOG",
                  "TRIAL_STATE_FILE", "CRON_JOBS_FILE"):
        monkeypatch.setattr(darwin, _name, home / "darwin" / f"{_name.lower()}.json",
                            raising=False)
    darwin._HITS_CACHE["hits"] = None
    darwin._HITS_CACHE["ts"] = 0.0
    return home


def _legacy_counts(home, skill_names):
    """The original algorithm, verbatim: fetch bodies, substring loop."""
    con = sqlite3.connect(str(home / "state.db"))
    rows = con.execute(
        "SELECT content FROM messages WHERE role='user' OR role='assistant'"
    ).fetchall()
    con.close()
    hits = {}
    for (content,) in rows:
        if not content:
            continue
        for name in skill_names:
            if name in content:
                hits[name] = hits.get(name, 0) + 1
    return hits


def test_matches_the_original_algorithm_exactly(world):
    """The incremental scan must reproduce the old counts byte for byte."""
    skills = sorted(d.name for d in (world / "skills").iterdir() if d.is_dir())
    assert darwin._session_skill_hits() == _legacy_counts(world, skills)


def test_only_user_and_assistant_rows_count(world):
    """A tool row mentioning a skill must not inflate demand."""
    hits = darwin._session_skill_hits()
    assert hits.get("alpha-skill") == 3   # two user rows + one assistant row
    assert hits.get("beta-skill") == 1


def test_second_call_accumulates_instead_of_rescanning(world):
    """New rows land via the incremental path, not a full rescan."""
    first = darwin._session_skill_hits()
    cache_file = darwin.DARWIN_DIR / "skill-hits-cache.json"
    assert cache_file.exists()
    watermark = json.loads(cache_file.read_text(encoding="utf-8"))["watermark"]

    con = sqlite3.connect(str(world / "state.db"))
    con.execute("INSERT INTO messages (session_id, role, content, timestamp)"
                " VALUES ('s1','user','beta-skill appeared again',2.0)")
    con.commit()
    con.close()

    darwin._HITS_CACHE["hits"] = None
    second = darwin._session_skill_hits()
    assert second["beta-skill"] == first["beta-skill"] + 1
    assert second["alpha-skill"] == first["alpha-skill"]
    after = json.loads(cache_file.read_text(encoding="utf-8"))
    assert after["watermark"] > watermark


def test_a_new_skill_forces_a_full_rescan(world):
    """A freshly installed skill must not inherit an empty count.

    This is the trap the first version of the fix fell into: keying the rescan
    decision off the hits dict, where a never-mentioned skill has no key at
    all, so the whole table was rescanned on every single cycle.
    """
    darwin._session_skill_hits()
    fresh = world / "skills" / "gamma-skill"
    fresh.mkdir()
    (fresh / "SKILL.md").write_text("# x", encoding="utf-8")

    # A mention that happened BEFORE the skill was installed. Nothing below the
    # watermark is re-read, so only a full rescan can still see it.
    con = sqlite3.connect(str(world / "state.db"))
    con.execute("INSERT INTO messages (session_id, role, content, timestamp)"
                " VALUES ('s1','user','we needed gamma-skill back then',1.5)")
    con.commit()
    con.close()

    darwin._HITS_CACHE["hits"] = None
    hits = darwin._session_skill_hits()
    cache = json.loads(
        (darwin.DARWIN_DIR / "skill-hits-cache.json").read_text(encoding="utf-8"))
    assert "gamma-skill" in cache["names"], "new skill missing from scan set"
    # 2, not 1: the fixture already contains an assistant row mentioning
    # "gamma-skill" (long before it was installed), so a correct full rescan
    # finds both mentions. Seeing only the post-install one would mean the
    # watermark suppressed history.
    assert hits.get("gamma-skill") == 2, (
        "a newly installed skill must trigger a full rescan, otherwise it keeps "
        "a zero usage count forever and looks dead to selection")


def test_missing_database_is_not_fatal(world, monkeypatch):
    """No state.db -> empty counts, never an exception."""
    monkeypatch.setattr(darwin, "HOME", world / "nonexistent")
    darwin._HITS_CACHE["hits"] = None
    assert darwin._session_skill_hits() == {}
