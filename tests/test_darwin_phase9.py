"""Phase-9 tests: knowledge harvesting from sessions, blueprint pool growth."""
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
def fake_world(tmp_path, monkeypatch):
    skills = tmp_path / "skills"
    skills.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir(parents=True)
    # session DB with recurring error patterns
    db = home / "state.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE messages (role TEXT, content TEXT)")
    msgs = []
    for i in range(5):  # 5 hits -> above min_hits=3
        msgs.append(("assistant",
                     "FileNotFoundError: 'C:/work/config.yaml' missing. "
                     "Fix: check OPENAMER_HOME path resolution first."))
    for i in range(2):  # 2 hits -> below threshold
        msgs.append(("assistant",
                     "ModuleNotFoundError: 'no module named requests'. "
                     "Fix: retry with backoff."))
    conn.executemany("INSERT INTO messages VALUES (?, ?)", msgs)
    conn.commit()
    conn.close()

    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "LINEAGE_FILE", home / "darwin" / "lineage.json")
    monkeypatch.setattr(darwin, "SYNTHESIS_LOG", home / "darwin" / "synthesis-log.json")
    monkeypatch.setattr(darwin, "HARVESTED_FILE",
                        home / "darwin" / "harvested-blueprints.json")
    monkeypatch.setattr(darwin, "_STATE_DB_CANDIDATES", ("state.db",))
    return home


def test_harvest_finds_recurring_pattern(fake_world):
    found = darwin.harvest_knowledge(min_hits=3)
    topics = [b["topic"] for b in found]
    assert any("config.yaml" in t for t in topics)
    # the 2-hit pattern must NOT appear
    assert not any("requests" in t for t in topics)
    # fix hint captured
    b = next(b for b in found if "config" in b["topic"])
    assert b["hits"] == 5


def test_harvest_dedupes_across_runs(fake_world):
    first = darwin.harvest_knowledge(min_hits=3)
    second = darwin.harvest_knowledge(min_hits=3)
    assert first and not second  # second run: everything already harvested


def test_all_blueprints_includes_harvested(fake_world):
    darwin.harvest_knowledge(min_hits=3)
    names = {bp["name"] for bp in darwin.all_blueprints()}
    assert len(names) == len(darwin.BLUEPRINTS) + 1
    assert any(n.startswith("darwin-harvested-") for n in names)
    # harvested blueprint has all required fields
    bp = next(bp for bp in darwin.all_blueprints()
              if bp["name"].startswith("darwin-harvested-"))
    assert all(k in bp for k in ("description", "trigger", "body", "pitfall"))


def test_speciate_v2_uses_harvested_pool(fake_world):
    fitness = {"some-skill": {"fitness": 10, "usage": 1, "health": 1,
                              "age_days": 1, "mutations_won": 0,
                              "mutations_lost": 0}}
    darwin.harvest_knowledge(min_hits=3)
    created = darwin.synthesize_species_v2(fitness, max_new=5, apply=True)
    names = [c["name"] for c in created]
    assert any(n.startswith("darwin-harvested-") for n in names)
    # the created species SKILL.md is valid and executable
    for n in names:
        md = darwin.DARWIN_DIR / "species" / n / "SKILL.md"
        assert "## Verification" in md.read_text(encoding="utf-8")


def test_harvest_no_db_returns_empty(fake_world):
    (fake_world / "state.db").unlink()
    assert darwin.harvest_knowledge() == []
