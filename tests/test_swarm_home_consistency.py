"""Regression test: every swarm/darwin script must resolve the SAME home.

Bug (observed live 2026-09-22): ``darwin_engine`` preferred an install that
actually carries a ``skills`` dir ("openamer-laptop" here, 183 skills) while the
7 sibling scripts that share a hand-copied ``_resolve_openamer_home`` fell back
to the bare platform default ("openamer", 27 skills). One autonomous-loop run
therefore read the real swarm (108 tasks, 1 worker) but wrote its own report --
and any task/worker mutation -- into the near-empty sibling home. The loop
reported a clean "0 tasks, everything clean" cycle while the real swarm was
never touched.

The split also made the cron summary untrustworthy: the same run's
``introspection` read the real home (population 154) while ``swarm_os`` used the
phantom one, so "gaps: []" and "tasks: 0" described two different installs.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

SIBLINGS = [
    "autonomous_loop.py",
    "swarm_os.py",
    "darwin_agents.py",
    "darwin_gate.py",
    "darwin_metacognition.py",
    "darwin_promote.py",
    "darwin_synthesize.py",
]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_siblings_match_darwin_engine(monkeypatch):
    """With OPENAMER_HOME unset, every script picks the same install root."""
    monkeypatch.delenv("OPENAMER_HOME", raising=False)
    engine = _load("engine_home_consistency_probe", "scripts/darwin_engine.py")
    target = str(engine.HOME)
    for f in SIBLINGS:
        mod = _load("probe_" + f.replace(".py", "").replace("-", "_"),
                    "scripts/" + f)
        home = getattr(mod, "HOME", None)
        if home is None:  # promote/synthesize expose SKILLS_DIR only
            home = mod.SKILLS_DIR.parent
        assert str(home) == target, f"{f} resolved {home}, expected {target}"


def test_siblings_reject_a_scratch_home(monkeypatch, tmp_path):
    """A mis-set OPENAMER_HOME pointing at a scratch dir must not be adopted."""
    scratch = tmp_path / "oa-scratch"
    (scratch / "skills").mkdir(parents=True)  # exists + has skills, not an install
    monkeypatch.setenv("OPENAMER_HOME", str(scratch))
    engine = _load("engine_scratch_probe", "scripts/darwin_engine.py")
    assert engine.HOME != scratch
    swarm = _load("swarm_scratch_probe", "scripts/swarm_os.py")
    assert swarm.HOME != scratch, "swarm_os adopted a scratch dir"
    assert str(swarm.HOME) == str(engine.HOME)
