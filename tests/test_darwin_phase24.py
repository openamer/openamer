"""Phase-24 tests: metacognition + civilization seeds."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "darwin_metacognition", REPO / "scripts" / "darwin_metacognition.py")
meta = importlib.util.module_from_spec(spec)
sys.modules["darwin_metacognition"] = meta
spec.loader.exec_module(meta)


@pytest.fixture
def fake_world(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "reports").mkdir(parents=True)
    (home / "skills").mkdir()
    (home / "cron").mkdir()
    (home / "cron" / "jobs.json").write_text(json.dumps({"jobs": []}),
                                             encoding="utf-8")
    (tmp_path / "reports").mkdir(exist_ok=True)
    monkeypatch.setattr(meta, "HOME", home)
    monkeypatch.setattr(meta, "INTROSPECTION_FILE",
                        home / "darwin" / "introspection.json")
    monkeypatch.setattr(meta, "SEED_FILE",
                        home / "darwin" / "civilization-seed.json")
    monkeypatch.setattr(meta, "GAP_BLUEPRINTS_FILE",
                        home / "darwin" / "gap-blueprints.json")
    monkeypatch.setattr(meta, "darwin", _patch_darwin(home, tmp_path))
    monkeypatch.setattr(meta, "swarm", _patch_swarm(home, tmp_path))
    return home


def _patch_darwin(home, tmp_path):
    import darwin_engine
    monkeypatch_attrs = {
        "HOME": home, "SKILLS_DIR": home / "skills",
        "DARWIN_DIR": home / "darwin",
        "FITNESS_FILE": home / "reports" / "darwin-fitness.json",
        "LINEAGE_FILE": home / "darwin" / "lineage.json",
        "POPULATION_FILE": home / "darwin" / "population.json",
        "HISTORY_FILE": home / "reports" / "darwin-history.jsonl",
        "CRON_JOBS_FILE": home / "cron" / "jobs.json",
    }
    for k, v in monkeypatch_attrs.items():
        setattr(darwin_engine, k, v)
    return darwin_engine


def _patch_swarm(home, tmp_path):
    import swarm_os
    swarm_os = sys.modules["swarm_os"]
    swarm_os.SWARM_FILE = home / "darwin" / "swarm.json"
    swarm_os.TASKS_FILE = home / "darwin" / "swarm-tasks.json"
    swarm_os.SWARM_KNOWLEDGE_FILE = home / "darwin" / "swarm-knowledge.json"
    swarm_os.TERRITORIES_FILE = home / "darwin" / "territories.json"
    return swarm_os


def _seed_fitness(home, strong=True):
    (home / "reports" / "darwin-fitness.json").write_text(json.dumps({
        "updated": "2026-01-01", "skills": {
            "strong-skill": {"fitness": 40 if strong else 5, "usage": 5,
                             "health": 1, "age_days": 1,
                             "mutations_won": 0, "mutations_lost": 0},
            "weak-skill": {"fitness": 4, "usage": 0, "health": 1,
                           "age_days": 9, "mutations_won": 0,
                           "mutations_lost": 0}}}),
        encoding="utf-8")


def test_introspect_identifies_strengths_and_weaknesses(fake_world):
    _seed_fitness(fake_world)
    img = meta.introspect()
    names_s = [s["skill"] for s in img["strengths"]]
    names_w = [s["skill"] for s in img["weaknesses"]]
    assert "strong-skill" in names_s
    assert "weak-skill" in names_w
    assert img["self_assessment"]  # an honest sentence exists


def test_introspect_detects_stagnation(fake_world):
    _seed_fitness(fake_world)
    # fake stale timestamps: set age high via fitness file (age_days 9)
    img = meta.introspect()
    assert img["aging"]["stagnation_ratio"] >= 0.5
    gap_types = [g["type"] for g in img["gaps"]]
    assert "stagnation" in gap_types
    assert "weak-population" in gap_types


def test_introspect_losing_record_gap(fake_world):
    _seed_fitness(fake_world)
    meta.darwin.POPULATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    meta.darwin.POPULATION_FILE.write_text(json.dumps({
        "s": {"wins": 1, "losses": 4}}), encoding="utf-8")
    img = meta.introspect()
    gap_types = [g["type"] for g in img["gaps"]]
    assert "losing-record" in gap_types


def test_evolve_toward_gaps_creates_species(fake_world):
    _seed_fitness(fake_world)
    img = meta.introspect()
    created = meta.evolve_toward_gaps(img, apply=True)
    assert created, "gaps exist -> species created"
    for c in created:
        md = (meta.darwin.DARWIN_DIR / "species" / c["name"] / "SKILL.md")
        assert md.exists()
        assert "gap-closure" in md.read_text(encoding="utf-8")
    lineage = json.loads(meta.darwin.LINEAGE_FILE.read_text(encoding="utf-8"))
    assert any(e["kind"] == "gap-closure" for e in lineage["events"])


def test_civilization_seed_roundtrip(fake_world, tmp_path):
    # build a civilization: fitness, lineage, species, swarm, knowledge
    _seed_fitness(fake_world)
    meta.introspect()
    d = meta.darwin.DARWIN_DIR
    d.mkdir(parents=True, exist_ok=True)
    meta.darwin._save_json(meta.darwin.LINEAGE_FILE, {"events": [
        {"parent": "a", "child": "b", "kind": "mutation", "when": "2026"}]})
    meta.darwin._save_json(meta.darwin.POPULATION_FILE,
                           {"s1": {"wins": 3, "losses": 1}})
    sp = d / "species"
    sp.mkdir(exist_ok=True)
    (sp / "my-species").mkdir()
    (sp / "my-species" / "SKILL.md").write_text("# s", encoding="utf-8")
    (sp / "my-species.json").write_text(json.dumps(
        {"child": "my-species", "status": "installed"}), encoding="utf-8")
    meta.swarm.register_worker("worker-1", ["code"], 25.0)
    meta.swarm._save(meta.swarm.SWARM_KNOWLEDGE_FILE,
                     {"teachers": [{"teacher": "t1"}]})

    seed_path = meta.export_civilization_seed()
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    assert seed["swarm"]["workers"]["worker-1"]["genome_fitness"] == 25.0
    assert "my-species" in seed["species_metas"]
    assert "my-species" in seed["species_files"]

    # wipe local state, import the seed into a fresh machine
    fresh = tmp_path / "fresh-machine"
    fresh.mkdir()
    (fresh / "reports").mkdir()
    (fresh / "cron").mkdir()
    (fresh / "cron" / "jobs.json").write_text("{}", encoding="utf-8")
    monkeypatch2 = {
        "HOME": fresh, "SKILLS_DIR": fresh / "skills",
        "DARWIN_DIR": fresh / "darwin",
        "FITNESS_FILE": fresh / "reports" / "darwin-fitness.json",
        "LINEAGE_FILE": fresh / "darwin" / "lineage.json",
        "POPULATION_FILE": fresh / "darwin" / "population.json",
    }
    saved = {}
    for k, v in monkeypatch2.items():
        saved[k] = getattr(meta.darwin, k)
        setattr(meta.darwin, k, v)
    saved_sw = {}
    for k in ("SWARM_FILE", "SWARM_KNOWLEDGE_FILE", "TERRITORIES_FILE"):
        saved_sw[k] = getattr(meta.swarm, k)
    meta.swarm.SWARM_FILE = fresh / "darwin" / "swarm.json"
    meta.swarm.SWARM_KNOWLEDGE_FILE = fresh / "darwin" / "knowledge.json"
    meta.swarm.TERRITORIES_FILE = fresh / "darwin" / "territories.json"
    try:
        result = meta.import_civilization_seed(seed_path, dry_run=False)
        assert result["imported"] is True
        assert result["swarm_workers"] == 1
        assert result["species"] == 1
        assert result["teachers"] == 1
        assert (fresh / "darwin" / "species" / "my-species").exists()
        assert (fresh / "darwin" / "swarm.json").exists()
    finally:
        for k, v in saved.items():
            setattr(meta.darwin, k, v)
        for k, v in saved_sw.items():
            setattr(meta.swarm, k, v)


def test_import_seed_dry_run_counts(fake_world, tmp_path):
    seed = {"genome": {"population": {"a": {"wins": 1}}},
            "lineage": {"events": [{"parent": "a", "child": "b"}]},
            "species": {}, "swarm": {"workers": {"w": {}}},
            "knowledge": {"teachers": []}, "territories": {}}
    p = tmp_path / "seed.json"
    p.write_text(json.dumps(seed), encoding="utf-8")
    r = meta.import_civilization_seed(p, dry_run=True)
    assert r["dry_run"] is True
    assert r["genome_skills"] == 1
    assert r["lineage_events"] == 1
    assert r["swarm_workers"] == 1
