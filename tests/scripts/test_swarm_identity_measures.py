"""The swarm's collective identity must MEASURE its stores too.

Sibling of ``test_self_model_measures.py``. ``swarm_intelligence.py`` used to
render "3012+ episodic memories" and "2400+ evolution events" as prose while
the local variable it should have used was initialised to 0 and never
assigned — a collective self-model stating numbers it never read.

The tests drive both stores to values that appear nowhere in the source.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE = (Path(__file__).resolve().parents[2] / "scripts" / "training"
          / "swarm_intelligence.py")


def _seed(tmp_home: Path, episodes: int, lineage_events: int) -> None:
    (tmp_home / "memory").mkdir(parents=True, exist_ok=True)
    (tmp_home / "darwin").mkdir(parents=True, exist_ok=True)
    with open(tmp_home / "memory" / "longterm_episodes.jsonl", "w",
              encoding="utf-8") as fh:
        for i in range(episodes):
            fh.write('{"n": %d}\n' % i)
    import json
    (tmp_home / "darwin" / "lineage.json").write_text(
        json.dumps({"events": [{"i": i} for i in range(lineage_events)]}),
        encoding="utf-8")


def _load(tmp_home: Path, monkeypatch):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_home))
    spec = importlib.util.spec_from_file_location("swarm_under_test", MODULE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert str(mod.SWARM_DIR).startswith(str(tmp_home)), (
        "swarm resolved SWARM_DIR outside the temp home: %s" % mod.SWARM_DIR)
    return mod


def test_swarm_identity_measures_both_stores(tmp_path, monkeypatch):
    _seed(tmp_path, episodes=7, lineage_events=5)
    mod = _load(tmp_path, monkeypatch)
    # agents=[] keeps discovery (and its SSH/HTTP probe) out of the test.
    mod.update_swarm_identity(agents=[])
    doc = (tmp_path / "memory" / "swarm" / "swarm_identity.md").read_text(
        encoding="utf-8")
    assert "- 7 episodic memories" in doc
    assert "- 5 evolution events" in doc


def test_swarm_identity_follows_the_stores(tmp_path, monkeypatch):
    _seed(tmp_path, episodes=11, lineage_events=2)
    mod = _load(tmp_path, monkeypatch)
    mod.update_swarm_identity(agents=[])
    doc = (tmp_path / "memory" / "swarm" / "swarm_identity.md").read_text(
        encoding="utf-8")
    assert "- 11 episodic memories" in doc
    assert "- 2 evolution events" in doc


def test_swarm_source_states_no_unread_constant():
    src = MODULE.read_text(encoding="utf-8")
    assert "3012+" not in src
    assert "2400+" not in src
