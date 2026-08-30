"""Phase-4 tests: lineage tracking, mermaid tree, genome export/import."""
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
    home = tmp_path / "home"
    (home / "skills").mkdir(parents=True)
    monkeypatch.setattr(darwin, "SKILLS_DIR", home / "skills")
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "LINEAGE_FILE", home / "darwin" / "lineage.json")
    monkeypatch.setattr(darwin, "ROLLBACK_LOG", home / "darwin" / "rollback-log.json")
    return home


def test_record_lineage_appends_events(fake_world):
    darwin.record_lineage("a", "a__mutX", "mutation", {"op": "add_pitfall"})
    darwin.record_lineage("b", "a+b", "crossover")
    graph = json.loads((darwin.LINEAGE_FILE).read_text(encoding="utf-8"))
    assert len(graph["events"]) == 2
    assert graph["events"][0]["kind"] == "mutation"
    assert graph["events"][1]["kind"] == "crossover"


def test_mermaid_renders_edges(fake_world):
    darwin.record_lineage("parent-skill", "child-skill", "mutation")
    tree = darwin.lineage_mermaid()
    assert "```mermaid" in tree
    assert 'parent-skill["parent-skill"] -->' in tree
    assert 'child-skill["child-skill"]' in tree


def test_mermaid_empty_lineage(fake_world):
    assert darwin.lineage_mermaid() == ""


def test_mermaid_escapes_quotes(fake_world):
    darwin.record_lineage('we"ird', 'chi"ld', "mutation")
    tree = darwin.lineage_mermaid()
    # quotes must be stripped from node names before wrapping in ["..."]
    body = tree.split("```mermaid")[1]
    assert 'weird["weird"]' in body
    assert 'child["child"]' in body


def test_export_genome_contains_all_state(fake_world):
    darwin.record_lineage("a", "a__mutX", "mutation")
    _save_pop = {"a": {"wins": 2, "losses": 1}}
    darwin.DARWIN_DIR.mkdir(parents=True, exist_ok=True)
    darwin.POPULATION_FILE.write_text(json.dumps(_save_pop), encoding="utf-8")
    out = darwin.export_genome(darwin.DARWIN_DIR / "genome.json")
    state = json.loads(out.read_text(encoding="utf-8"))
    assert state["population"] == _save_pop
    assert len(state["lineage"]["events"]) == 1


def test_import_genome_merges_higher_wl(fake_world, tmp_path):
    # local: 1 win
    darwin.DARWIN_DIR.mkdir(parents=True, exist_ok=True)
    darwin.POPULATION_FILE.write_text(
        json.dumps({"skillA": {"wins": 1, "losses": 0}}), encoding="utf-8")
    darwin.record_lineage("x", "x__mutLocal", "mutation")

    # incoming genome: skillA has 3 wins, plus a new lineage event + offspring
    incoming = {
        "population": {"skillA": {"wins": 3, "losses": 0}},
        "lineage": {"events": [{"parent": "y", "child": "y__mutRemote",
                                "kind": "mutation", "when": "2026-01-01"}]},
        "offspring": [{"child": "y__mutRemote", "parent": "y", "status": "candidate"}],
    }
    p = tmp_path / "remote-genome.json"
    p.write_text(json.dumps(incoming), encoding="utf-8")

    merged = darwin.import_genome(p)
    assert merged["population"] == 1   # 3 W > 1 W -> replaced
    assert merged["lineage"] == 1
    assert merged["offspring"] == 1

    pop = json.loads(darwin.POPULATION_FILE.read_text(encoding="utf-8"))
    assert pop["skillA"]["wins"] == 3
    lin = json.loads(darwin.LINEAGE_FILE.read_text(encoding="utf-8"))
    assert len(lin["events"]) == 2  # local + remote, no duplicate


def test_import_genome_keeps_local_on_lower_wl(fake_world, tmp_path):
    darwin.DARWIN_DIR.mkdir(parents=True, exist_ok=True)
    darwin.POPULATION_FILE.write_text(
        json.dumps({"skillA": {"wins": 5, "losses": 0}}), encoding="utf-8")
    incoming = {"population": {"skillA": {"wins": 1, "losses": 0}}}
    p = tmp_path / "remote.json"
    p.write_text(json.dumps(incoming), encoding="utf-8")
    merged = darwin.import_genome(p)
    assert merged["population"] == 0  # local 5 W kept
