"""Phase-23 tests: teaching before death + territoriality."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "swarm_os", REPO / "scripts" / "swarm_os.py")
swarm = importlib.util.module_from_spec(spec)
sys.modules["swarm_os"] = swarm
spec.loader.exec_module(swarm)


@pytest.fixture
def fake_world(tmp_path, monkeypatch):
    monkeypatch.setattr(swarm, "SWARM_FILE", tmp_path / "swarm.json")
    monkeypatch.setattr(swarm, "TASKS_FILE", tmp_path / "tasks.json")
    monkeypatch.setattr(swarm, "SWARM_KNOWLEDGE_FILE",
                        tmp_path / "darwin" / "swarm-knowledge.json")
    monkeypatch.setattr(swarm, "TERRITORIES_FILE",
                        tmp_path / "darwin" / "territories.json")
    return tmp_path


def _register_pair(fake_world):
    """dying: has unique capabilities, no energy. heir: fittest survivor."""
    swarm.register_worker("dying-teacher",
                          ["code", "network", "memory"],
                          genome_fitness=8.0, starting_energy=0.0)
    swarm.register_worker("fittest-heir",
                          ["code"], genome_fitness=50.0,
                          starting_energy=80.0)


def test_teach_before_death_transfers_capabilities(fake_world):
    _register_pair(fake_world)
    swarm_w = swarm.load_swarm()
    r = swarm.teach_before_death(swarm_w, "dying-teacher")
    swarm.save_swarm(swarm_w)
    assert r["heir"] == "fittest-heir"
    heir = swarm_w["workers"]["fittest-heir"]
    assert "network" in heir["capabilities"]
    assert "memory" in heir["capabilities"]
    assert r["fitness_grant"] == 0.0  # dying had 0 wins -> small grant
    # knowledge base remembers the teacher
    kb = json.loads((fake_world / "darwin" / "swarm-knowledge.json")
                    .read_text(encoding="utf-8"))
    assert kb["teachers"][0]["teacher"] == "dying-teacher"


def test_tick_starved_worker_teaches_first(fake_world):
    swarm.register_worker("dying-teacher",
                          ["code", "network"], starting_energy=0.0)
    swarm.register_worker("heir", ["code"], genome_fitness=30.0,
                          starting_energy=80.0)
    t = swarm.tick()
    assert len(t["starved"]) == 1
    entry = t["starved"][0]
    assert entry["worker"] == "dying-teacher"
    assert entry["taught"]["heir"] == "heir"
    assert "network" in swarm.load_swarm()["workers"]["heir"]["capabilities"]


def test_teaching_grant_proportional_to_wins(fake_world):
    swarm.register_worker("wise-dying", ["code", "evolution"],
                          genome_fitness=0, starting_energy=0.0)
    swarm_w = swarm.load_swarm()
    swarm_w["workers"]["wise-dying"]["wins"] = 6
    swarm_w["workers"]["wise-heir"] = {
        "born": swarm._now(), "wins": 0, "losses": 0, "children": 0,
        "capabilities": ["code"], "genome_fitness": 40.0,
        "energy": 50.0, "generation": 1,
    }
    r = swarm.teach_before_death(swarm_w, "wise-dying")
    swarm.save_swarm(swarm_w)
    assert r["fitness_grant"] == 3.0  # 6 wins * 0.5
    heir = swarm_w["workers"]["wise-heir"]
    assert heir["genome_fitness"] == 43.0


def test_claim_territory(fake_world):
    r = swarm.claim_territory("code-review", "worker-a")
    assert r["claimed"] is True
    territories = json.loads((fake_world / "darwin" / "territories.json")
                             .read_text(encoding="utf-8"))
    assert territories["code-review"]["holder"] == "local"


def test_claim_foreign_territory_refused(fake_world):
    (fake_world / "darwin").mkdir(parents=True, exist_ok=True)
    (fake_world / "darwin" / "territories.json").write_text(json.dumps(
        {"code-review": {"holder": "foreign", "worker": "alien"}}),
        encoding="utf-8")
    r = swarm.claim_territory("code-review", "worker-a")
    assert r["claimed"] is False
    assert r["holder"] == "foreign"


def test_contest_lost_territory_goes_foreign(fake_world, monkeypatch):
    (fake_world / "darwin").mkdir(parents=True, exist_ok=True)
    (fake_world / "darwin" / "territories.json").write_text(json.dumps(
        {"domain-x": {"holder": "local", "worker": "our-champ"}}),
        encoding="utf-8")
    # foreign champion executes fine, local champion fails -> we lose
    skills = fake_world / "skills"
    skills.mkdir(exist_ok=True)
    (skills / "our-champ").mkdir()
    (skills / "our-champ" / "SKILL.md").write_text(
        "# c\n```bash\nexit 3\n```\n", encoding="utf-8")
    foreign_dir = fake_world / "darwin" / "offspring" / "alien-champ"
    foreign_dir.mkdir(parents=True)
    (foreign_dir / "SKILL.md").write_text(
        "# a\n```bash\necho ok\n```\n", encoding="utf-8")
    monkeypatch.setattr(swarm.darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(swarm.darwin, "DARWIN_DIR",
                        fake_world / "darwin")
    r = swarm.contest_territory("domain-x", "alien-champ", "our-champ")
    assert r["contested"] is True and r["won"] is False
    territories = json.loads((fake_world / "darwin" / "territories.json")
                             .read_text(encoding="utf-8"))
    assert territories["domain-x"]["holder"] == "foreign"
