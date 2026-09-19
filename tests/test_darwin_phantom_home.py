"""Regression test: a scratch OPENAMER_HOME must never be adopted as the install.

Bug (observed live 2026-09-19): the cron shell exported
``OPENAMER_HOME=/c/tmp/oa-home`` -- an empty scratch directory that merely
EXISTED. ``_resolve_home()`` accepted any existing directory, so the autopilot
cycle resolved its whole world into that scratch dir:

* ``compute_fitness()`` scored ZERO skills while the real home held 110,
* ``main()`` hit its "fresh install" branch and created a brand-new
  ``C:/tmp/oa-home/skills``,
* the run then reported ``exit 2`` / "5 mutations generated" / "2 species
  promoted" against the phantom population -- a green evolution report for work
  that never touched the real 110 skills,
* the empty snapshot was appended to the append-only history ledger and, because
  ``fitness_trend()`` compares first vs last, made the ecosystem look like it had
  collapsed: ``auto_tune()`` flipped to "declining -> exploit winners, prune
  faster".

The same scratch dir was reached by ``scripts/autonomous_loop.py``, which
reported "0 tasks, everything clean" while running against an empty population.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "scripts" / "darwin_engine.py"


def _load_fresh(monkeypatch, env_home: str | None):
    """Import darwin_engine under a controlled OPENAMER_HOME."""
    if env_home is None:
        monkeypatch.delenv("OPENAMER_HOME", raising=False)
    else:
        monkeypatch.setenv("OPENAMER_HOME", env_home)
    spec = importlib.util.spec_from_file_location(
        "darwin_engine_phantom_probe", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scratch_home_is_not_adopted(tmp_path, monkeypatch):
    """A dir that exists but carries no install markers falls back to default."""
    scratch = tmp_path / "oa-home"
    (scratch / "skills").mkdir(parents=True)  # exists, but is not an install

    mod = _load_fresh(monkeypatch, "/c" + str(scratch).replace("\\", "/").lstrip("C:"))

    assert mod.HOME != scratch, "scratch dir adopted as OPENAMER_HOME"
    assert mod._is_install_root(mod.HOME), "fallback home is not a real install"
    assert (mod.HOME / "skills").is_dir()


def test_real_install_root_is_respected(tmp_path, monkeypatch):
    """A genuine home (carries config.yaml) is still honoured."""
    real = tmp_path / "real-home"
    (real / "skills").mkdir(parents=True)
    (real / "config.yaml").write_text("model: {}\n", encoding="utf-8")

    mod = _load_fresh(monkeypatch, str(real))
    assert mod.HOME == real


@pytest.mark.parametrize("marker", ["config.yaml", ".env", "cron", "memories",
                                    "openamer-agent"])
def test_every_install_marker_counts(tmp_path, marker):
    """Each documented marker alone identifies an install root."""
    home = tmp_path / "home"
    home.mkdir()
    target = home / marker
    target.mkdir() if "." not in marker else target.write_text("x",
                                                               encoding="utf-8")
    mod = _load_fresh_without_import(marker_home=home)
    assert mod._is_install_root(home) is True


def _load_fresh_without_import(marker_home: Path):
    """Load the module purely to exercise its markers (env untouched)."""
    spec = importlib.util.spec_from_file_location(
        "darwin_engine_marker_probe", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_autopilot_refuses_non_install_home(tmp_path, monkeypatch, capsys):
    """Even with an empty skills dir, a non-install home must not report success."""
    mod = _load_fresh(monkeypatch, None)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "skills").mkdir()
    monkeypatch.setattr(mod, "HOME", scratch)
    monkeypatch.setattr(mod, "SKILLS_DIR", scratch / "skills")
    monkeypatch.setattr(mod, "DARWIN_DIR", scratch / "darwin")
    monkeypatch.setattr(mod, "REPORTS_DIR", scratch / "reports")
    monkeypatch.setattr(mod, "FITNESS_FILE", scratch / "reports" / "f.json")
    monkeypatch.setattr(mod, "HISTORY_FILE", scratch / "reports" / "h.jsonl")
    monkeypatch.setattr(mod, "REPORT_FILE", scratch / "reports" / "r.md")
    monkeypatch.setattr(mod, "PROBE_FILE", scratch / "reports" / "p.json")
    monkeypatch.setattr(mod, "TUNING_FILE", scratch / "darwin" / "tuning.json")

    code = mod.autopilot(min_executions=2)
    out = capsys.readouterr().out
    assert code == 1, "phantom home reported a successful evolution cycle"
    assert "REFUSING" in out


def test_empty_snapshots_excluded_from_trend(tmp_path, monkeypatch):
    """A zero-skill snapshot must not make the ecosystem look collapsed."""
    mod = _load_fresh(monkeypatch, None)
    hist = tmp_path / "hist.jsonl"
    import json
    rows = [
        {"when": "t1", "skills": {"a": 10.0, "b": 5.0}},
        {"when": "t2", "skills": {}},          # phantom-home snapshot
        {"when": "t3", "skills": {"a": 12.0, "b": 6.0}},
    ]
    hist.write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                    encoding="utf-8")
    monkeypatch.setattr(mod, "HISTORY_FILE", hist)

    trend = mod.fitness_trend()
    assert trend["population_trend"] == "rising", trend
    assert trend["measured"] == 2


def test_cron_wrapper_reaches_real_population():
    """End-to-end: the poisoned env still yields a 110-skill population."""
    proc = subprocess.run(
        [sys.executable, str(ENGINE), "--autopilot"],
        cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=420,
        env={"OPENAMER_HOME": "C:/tmp/oa-home",
             "PATH": __import__("os").environ.get("PATH", ""),
             "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
    )
    out = proc.stdout + proc.stderr
    assert "fitness computed for 0 skills" not in out, out
    assert "REFUSING" not in out, out
