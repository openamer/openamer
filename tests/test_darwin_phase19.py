"""Phase-19 tests: Memory Darwinism - memories compete for survival."""
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

spec2 = importlib.util.spec_from_file_location(
    "memory_darwinism", REPO / "scripts" / "memory_darwinism.py")
mem = importlib.util.module_from_spec(spec2)
sys.modules["memory_darwinism"] = mem
spec2.loader.exec_module(mem)


@pytest.fixture
def fake_world(tmp_path, monkeypatch):
    monkeypatch.setattr(mem, "DARWIN_DIR", tmp_path / "darwin")
    monkeypatch.setattr(mem, "MEMORY_POP",
                        tmp_path / "darwin" / "memory-population.json")
    monkeypatch.setattr(mem, "LESSONS_DB", tmp_path / "nonexistent.db")
    monkeypatch.setattr(mem, "STATE_DB", tmp_path / "nonexistent2.db")
    return tmp_path


def _seed(pop_dir, memories):
    pop_dir.mkdir(parents=True, exist_ok=True)
    (pop_dir / "memory-population.json").write_text(
        json.dumps({"memories": memories}), encoding="utf-8")


def test_memory_fitness_scoring():
    assert mem.memory_fitness({"wins": 2, "losses": 0, "success": True}) == 5
    assert mem.memory_fitness({"wins": 0, "losses": 2, "success": False}) == -7


def test_duel_contradictions_fitter_wins(fake_world):
    _seed(fake_world / "darwin", {
        "m1": {"text": "always use deepseek-v4-flash model for tasks",
               "wins": 3, "losses": 0, "success": True},
        "m2": {"text": "never use deepseek-v4-flash model for tasks",
               "wins": 0, "losses": 1, "success": False},
    })
    duels = mem.duel_contradictions()
    assert len(duels) == 1
    assert duels[0]["winner"] == "m1"  # fitter memory wins
    pop = json.loads((fake_world / "darwin" / "memory-population.json")
                     .read_text(encoding="utf-8"))
    assert pop["memories"]["m1"]["wins"] == 4
    assert pop["memories"]["m2"]["losses"] == 2
    assert pop["memories"]["m2"]["fitness"] < -2  # now below survival


def test_duel_same_polarity_no_contradiction(fake_world):
    _seed(fake_world / "darwin", {
        "m1": {"text": "always use deepseek model", "wins": 1,
               "success": True},
        "m2": {"text": "always prefer deepseek model", "wins": 1,
               "success": True},
    })
    assert mem.duel_contradictions() == []


def test_cull_dry_run_spares(fake_world):
    _seed(fake_world / "darwin", {
        "weak": {"text": "some wrong belief", "wins": 0, "losses": 5,
                 "success": False},
        "strong": {"text": "a proven lesson", "wins": 3, "losses": 0,
                   "success": True},
    })
    dead = mem.cull_weak(dry_run=True)
    assert [d["key"] for d in dead] == ["weak"]
    # population untouched in dry run
    pop = json.loads((fake_world / "darwin" / "memory-population.json")
                     .read_text(encoding="utf-8"))
    assert len(pop["memories"]) == 2


def test_cull_apply_moves_to_graveyard(fake_world):
    _seed(fake_world / "darwin", {
        "weak": {"text": "some wrong belief", "wins": 0, "losses": 5,
                 "success": False},
        "strong": {"text": "a proven lesson", "wins": 3, "losses": 0,
                   "success": True},
    })
    dead = mem.cull_weak(dry_run=False)
    assert [d["key"] for d in dead] == ["weak"]
    pop = json.loads((fake_world / "darwin" / "memory-population.json")
                     .read_text(encoding="utf-8"))
    assert "weak" not in pop["memories"]
    assert "strong" in pop["memories"]
    grave = json.loads((fake_world / "darwin" / "memory-graveyard.json")
                       .read_text(encoding="utf-8"))
    assert grave[0]["key"] == "weak"


def test_memory_stats_shape(fake_world):
    _seed(fake_world / "darwin", {
        "m1": {"text": "proven pattern", "wins": 2, "losses": 0,
               "success": True, "source": "lessons"},
    })
    s = mem.memory_stats()
    assert s["population"] == 1
    assert s["avg_fitness"] == 5.0  # 2*2 - 0*3 + 1(success) = 5
    assert s["sources"] == {"lessons": 1}
