"""Phase-7 tests: speciation - synthesizing genuinely new skills."""
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
    skills.mkdir(parents=True)
    home = tmp_path / "home"
    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "LINEAGE_FILE", home / "darwin" / "lineage.json")
    monkeypatch.setattr(darwin, "ROLLBACK_LOG", home / "darwin" / "rollback-log.json")
    monkeypatch.setattr(darwin, "SYNTHESIS_LOG", home / "darwin" / "synthesis-log.json")
    return {"skills": skills, "home": home}


FITNESS = {
    "champ-skill": {"fitness": 40, "usage": 9, "health": 1, "age_days": 1,
                    "mutations_won": 0, "mutations_lost": 0},
    "other": {"fitness": 10, "usage": 2, "health": 1, "age_days": 2,
              "mutations_won": 0, "mutations_lost": 0},
}


def test_synthesize_dry_run_creates_nothing(fake_world):
    created = darwin.synthesize_species(FITNESS, max_new=2, apply=False)
    assert len(created) == 2
    assert all(not c["applied"] for c in created)
    assert not (darwin.DARWIN_DIR / "species").exists()


def test_synthesize_applies_creates_valid_skills(fake_world):
    created = darwin.synthesize_species(FITNESS, max_new=2, apply=True)
    assert len(created) == 2
    assert created[0]["donor"] == "champ-skill"  # fittest is the donor
    for c in created:
        md = darwin.DARWIN_DIR / "species" / c["name"] / "SKILL.md"
        text = md.read_text(encoding="utf-8")
        assert "name: " in text
        assert "## Trigger" in text
        assert "## Verification" in text
        assert "```bash" in text  # executable block for head-to-head
    # lineage recorded
    graph = json.loads(darwin.LINEAGE_FILE.read_text(encoding="utf-8"))
    assert any(e["kind"] == "speciation" for e in graph["events"])


def test_synthesize_never_duplicates_existing(fake_world):
    fit = {**FITNESS, "darwin-evidence-hygiene": FITNESS["other"]}
    created = darwin.synthesize_species(fit, max_new=3, apply=False)
    names = [c["name"] for c in created]
    assert "darwin-evidence-hygiene" not in names


def test_promote_species_installs_into_population(fake_world):
    darwin.synthesize_species(FITNESS, max_new=1, apply=True)
    name = darwin.synthesize_species(FITNESS, max_new=1, apply=True)[0]["name"] \
        if False else "darwin-evidence-hygiene"
    ok = darwin.promote_species(name)
    assert ok is True
    live = fake_world["skills"] / name / "SKILL.md"
    assert live.exists()
    # second promotion refused (already exists)
    assert darwin.promote_species(name) is False


def test_promoted_species_passes_run_skill_check(fake_world):
    darwin.synthesize_species(FITNESS, max_new=1, apply=True)
    darwin.promote_species("darwin-evidence-hygiene")
    res = darwin.run_skill_check("darwin-evidence-hygiene")
    assert res["ok"] is True
    assert res["exit_code"] == 0
    assert "darwin-species-ok" in res["stdout_tail"]
