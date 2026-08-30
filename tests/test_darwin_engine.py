"""Tests for the Darwin Engine (evolutionary skill ecosystem)."""
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
def fake_skills(tmp_path, monkeypatch):
    skills = tmp_path / "skills"
    for name in ("alpha", "beta"):
        d = skills / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"# {name}\n\n## Trigger\nRun when X.\n", encoding="utf-8")
    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "DARWIN_DIR", tmp_path / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", tmp_path / "darwin" / "population.json")
    return skills


def test_fitness_scores_all_skills(fake_skills):
    fitness = darwin.compute_fitness()
    assert set(fitness) == {"alpha", "beta"}
    for s in fitness.values():
        assert "fitness" in s and "usage" in s and "age_days" in s


def test_mutation_creates_child_variant(fake_skills):
    fitness = {"alpha": {"fitness": 10}, "beta": {"fitness": 5}}
    offspring = darwin.mutate(fitness, top_n=2, apply=True)
    assert len(offspring) == 2
    assert all(o["applied"] for o in offspring)
    child_dir = darwin.DARWIN_DIR / "offspring"
    metas = list(child_dir.glob("*.json"))
    assert len(metas) == 2
    # child SKILL.md exists for each meta
    for m in metas:
        meta = json.loads(m.read_text(encoding="utf-8"))
        assert (child_dir / meta["child"] / "SKILL.md").exists()


def test_mutation_ops_change_text(fake_skills):
    text = "# skill\n"
    for op in darwin.MUTATION_OPS:
        mutated = darwin._mutate_skill_md(text, op)
        assert mutated != text, f"op {op} produced no change"
        assert "## " in mutated


def test_crossover_combines_parents(fake_skills):
    res = darwin.crossover("alpha", "beta", apply=True)
    assert res is not None
    assert res["parents"] == ["alpha", "beta"]
    child_md = darwin.DARWIN_DIR / "offspring" / res["child"] / "SKILL.md"
    assert child_md.exists()
    assert "## Trigger" in child_md.read_text(encoding="utf-8")


def test_crossover_missing_skill_returns_none(fake_skills):
    assert darwin.crossover("alpha", "does-not-exist") is None


def test_compete_no_candidates(fake_skills):
    assert darwin.compete() == []


def test_report_renders_markdown(fake_skills):
    fitness = {"alpha": {"fitness": 9, "usage": 1, "age_days": 2,
                         "mutations_won": 0, "mutations_lost": 0,
                         "health": 1}}
    md = darwin.report(fitness, [], [])
    assert "# Darwin Engine Report" in md
    assert "alpha" in md
