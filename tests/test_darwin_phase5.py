"""Phase-5 tests: tournament auto-trialing with guards."""
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
    for name in ("top-skill", "mid-skill", "lonely-skill"):
        d = skills / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")

    home = tmp_path / "home"
    cron = home / "cron"
    cron.mkdir(parents=True)
    jobs = {"jobs": [
        {"id": "jobA", "name": "top-job", "enabled": True, "skills": ["top-skill"]},
        {"id": "jobB", "name": "mid-job", "enabled": True, "skills": ["mid-skill"]},
        # lonely-skill has NO job -> its children must never be trialed
    ]}
    (cron / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    db = cron / "executions.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE executions (id TEXT, job_id TEXT, status TEXT)")
    conn.commit()
    conn.close()

    off = home / "darwin" / "offspring"
    off.mkdir(parents=True)
    for child, parent in (("top-skill__mutadd_pitfall", "top-skill"),
                          ("mid-skill__mutbroaden_trigger", "mid-skill"),
                          ("lonely-skill__mutadd_pitfall", "lonely-skill")):
        (off / child).mkdir()
        (off / child / "SKILL.md").write_text(f"# {child}\n", encoding="utf-8")
        (off / f"{child}.json").write_text(json.dumps(
            {"child": child, "parent": parent, "op": child.split("__mut")[1],
             "status": "candidate"}), encoding="utf-8")

    fitness = {
        "top-skill": {"fitness": 30, "usage": 5, "health": 1, "age_days": 1,
                      "mutations_won": 0, "mutations_lost": 0},
        "mid-skill": {"fitness": 15, "usage": 2, "health": 1, "age_days": 2,
                      "mutations_won": 0, "mutations_lost": 0},
        "lonely-skill": {"fitness": 8, "usage": 1, "health": 1, "age_days": 3,
                         "mutations_won": 0, "mutations_lost": 0},
    }

    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "LINEAGE_FILE", home / "darwin" / "lineage.json")
    monkeypatch.setattr(darwin, "ROLLBACK_LOG", home / "darwin" / "rollback-log.json")
    monkeypatch.setattr(darwin, "CRON_JOBS_FILE", cron / "jobs.json")
    return {"skills": skills, "cron": cron, "fitness": fitness, "home": home}


def test_tournament_trials_best_candidates(fake_world):
    started = darwin.tournament(fake_world["fitness"], max_trials=2)
    children = [s["child"] for s in started]
    assert "top-skill__mutadd_pitfall" in children      # best parent first
    assert "mid-skill__mutbroaden_trigger" in children
    # lonely child never trialed (parent has no cron job)
    assert all(not c.startswith("lonely") for c in children)
    # jobs actually swapped
    jobs = json.loads((fake_world["cron"] / "jobs.json").read_text(encoding="utf-8"))
    swapped = {j["id"]: j["skills"] for j in jobs["jobs"]}
    assert "top-skill__mutadd_pitfall" in swapped["jobA"]
    assert "mid-skill__mutbroaden_trigger" in swapped["jobB"]


def test_tournament_respects_max_trials(fake_world):
    started = darwin.tournament(fake_world["fitness"], max_trials=1)
    assert len(started) == 1
    assert started[0]["child"] == "top-skill__mutadd_pitfall"


def test_tournament_never_double_books(fake_world):
    darwin.tournament(fake_world["fitness"], max_trials=2)
    # second run: all jobs busy -> nothing new
    started = darwin.tournament(fake_world["fitness"], max_trials=2)
    assert started == []


def test_tournament_skips_lost_candidates(fake_world):
    # mark all candidates as lost -> no trials
    off = fake_world["home"] / "darwin" / "offspring"
    for mp in off.glob("*.json"):
        meta = json.loads(mp.read_text(encoding="utf-8"))
        meta["status"] = "lost"
        mp.write_text(json.dumps(meta), encoding="utf-8")
    assert darwin.tournament(fake_world["fitness"], max_trials=2) == []


def test_autopilot_includes_tournament(fake_world, capsys):
    code = darwin.autopilot(min_executions=2)
    out = capsys.readouterr().out
    assert "[autopilot] tournament:" in out or "[autopilot] fitness" in out
    assert code in (0, 2)
