"""Phase-16 tests: predation - finding and consuming redundant skills."""
import importlib.util
import json
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
    # predator (strong) and prey (weak, redundant name tokens)
    for name, body in (("git-workflow", "echo strong"),
                       ("git-workflow-helper", "echo weak")):
        d = skills / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}\n```bash\n{body}\n```\n",
                                    encoding="utf-8")
    # unrelated skill (no overlap)
    d = skills / "cooking-recipes"
    d.mkdir()
    (d / "SKILL.md").write_text("# cooking\n", encoding="utf-8")

    home = tmp_path / "home"
    (home / "reports").mkdir(parents=True)
    cron = home / "cron"
    cron.mkdir(parents=True)
    (cron / "jobs.json").write_text(json.dumps({"jobs": []}), encoding="utf-8")

    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE",
                        home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "LINEAGE_FILE", home / "darwin" / "lineage.json")
    monkeypatch.setattr(darwin, "PREDATION_LOG",
                        home / "darwin" / "predation-log.json")
    monkeypatch.setattr(darwin, "ROLLBACK_LOG", home / "darwin" / "rollback-log.json")
    monkeypatch.setattr(darwin, "CRON_JOBS_FILE", cron / "jobs.json")
    return {"skills": skills, "home": home}


FITNESS = {
    "git-workflow": {"fitness": 30, "usage": 5, "health": 1, "age_days": 1,
                     "mutations_won": 0, "mutations_lost": 0},
    "git-workflow-helper": {"fitness": 8, "usage": 1, "health": 1, "age_days": 2,
                            "mutations_won": 0, "mutations_lost": 0},
    "cooking-recipes": {"fitness": 12, "usage": 2, "health": 1, "age_days": 1,
                        "mutations_won": 0, "mutations_lost": 0},
}


def test_find_prey_detects_overlap(fake_world):
    prey = darwin.find_prey(FITNESS, min_overlap=0.6)
    pairs = [(p["predator"], p["prey"]) for p in prey]
    assert ("git-workflow", "git-workflow-helper") in pairs
    # cooking has no token overlap -> never prey
    assert all(p["prey"] != "cooking-recipes" for p in prey)
    # stronger skill is always the predator
    p = next(p for p in prey if p["prey"] == "git-workflow-helper")
    assert p["predator"] == "git-workflow"
    assert p["overlap"] >= 0.6


def test_find_prey_never_targets_cron_protected(fake_world):
    (fake_world["home"] / "cron" / "jobs.json").write_text(json.dumps(
        {"jobs": [{"id": "j", "name": "j", "enabled": True,
                   "skills": ["git-workflow-helper"]}]}), encoding="utf-8")
    prey = darwin.find_prey(FITNESS, min_overlap=0.6)
    assert all(p["prey"] != "git-workflow-helper" for p in prey)


def test_predate_dry_run_absorbs_nothing(fake_world):
    prey = darwin.find_prey(FITNESS, min_overlap=0.6)
    results = darwin.predate(prey, dry_run=True)
    assert all(r["status"] == "would-absorb" for r in results)
    assert (fake_world["skills"] / "git-workflow-helper").exists()


def test_predate_absorbs_and_inherits_trigger(fake_world):
    prey = darwin.find_prey(FITNESS, min_overlap=0.6)
    results = darwin.predate(prey, dry_run=False)
    absorbed = [r for r in results if r["status"] == "absorbed"]
    assert absorbed, "predator should win the duel (echo strong vs echo weak)"
    # prey removed from live population, archived
    assert not (fake_world["skills"] / "git-workflow-helper").exists()
    archives = list((darwin.DARWIN_DIR / "archive").iterdir())
    assert any("git-workflow-helper" in a.name for a in archives)
    # predator inherited the trigger
    md = (fake_world["skills"] / "git-workflow" / "SKILL.md").read_text(encoding="utf-8")
    assert "git-workflow-helper" in md
    # genome: predator got a win
    pop = json.loads(darwin.POPULATION_FILE.read_text(encoding="utf-8"))
    assert pop["git-workflow"]["wins"] >= 1
    # lineage recorded
    graph = json.loads(darwin.LINEAGE_FILE.read_text(encoding="utf-8"))
    assert any(e["kind"] == "predation" for e in graph["events"])


def test_predation_cycle_no_prey(fake_world):
    fitness = {"lone-skill": {"fitness": 5, "usage": 1}}
    assert darwin.predation_cycle(fitness) == [{"status": "no-prey"}]
