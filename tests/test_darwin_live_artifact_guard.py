"""Regression test: a sandboxed darwin_engine must never write live artifacts.

Bug (observed 2026-09-17): darwin test fixtures redirect SKILLS_DIR to a tmp
population but left FITNESS_FILE / HISTORY_FILE / REPORT_FILE / TUNING_FILE
pointing at the repo's real ``reports/`` dir and HOME's ``darwin/`` dir. A
sandboxed run therefore overwrote reports/darwin-fitness.json, appended a
2-skill blob (alpha/dead-skill, lonely-skill/mid-skill/top-skill, known-skill)
to the append-only history ledger, and self-tuned the live constants.
fitness_trend() compares first vs last snapshot, so a single leaked snapshot
poisons every later trend/tuning decision.
"""
import importlib.util
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
def sandbox(tmp_path, monkeypatch):
    """A redirected population that deliberately keeps LIVE artifact paths."""
    home = tmp_path / "home"
    (home / "skills").mkdir(parents=True)
    monkeypatch.setattr(darwin, "SKILLS_DIR", home / "skills")
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    # Redirect every derived path too: this file deliberately exercises the
    # engine-level guard against the RECORDED live roots (_LIVE_*), so the
    # conftest net needs nothing to auto-redirect here.
    monkeypatch.setattr(darwin, "REPORTS_DIR", home / "reports")
    monkeypatch.setattr(darwin, "FITNESS_FILE", home / "reports" / "darwin-fitness.json")
    monkeypatch.setattr(darwin, "HISTORY_FILE", home / "reports" / "darwin-history.jsonl")
    monkeypatch.setattr(darwin, "REPORT_FILE", home / "reports" / "darwin-report.md")
    monkeypatch.setattr(darwin, "PROBE_FILE", home / "reports" / "darwin-probe.json")
    monkeypatch.setattr(darwin, "TUNING_FILE", home / "darwin" / "tuning.json")
    # The remaining derived artifacts. Redirected here rather than left to the
    # conftest net so this fixture is self-contained: the net must stay a
    # backstop for OTHER tests, not a dependency this one leans on.
    monkeypatch.setattr(darwin, "POPULATION_FILE", home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "LINEAGE_FILE", home / "darwin" / "lineage.json")
    monkeypatch.setattr(darwin, "ARENA_FILE", home / "darwin" / "arena.json")
    monkeypatch.setattr(darwin, "OP_STATS_FILE", home / "darwin" / "op-stats.json")
    monkeypatch.setattr(darwin, "ROLLBACK_LOG", home / "darwin" / "rollback-log.json")
    monkeypatch.setattr(darwin, "SYNTHESIS_LOG", home / "darwin" / "synthesis-log.json")
    monkeypatch.setattr(darwin, "HARVESTED_FILE", home / "darwin" / "harvested-blueprints.json")
    monkeypatch.setattr(darwin, "PREDATION_LOG", home / "darwin" / "predation-log.json")
    monkeypatch.setattr(darwin, "TRIAL_STATE_FILE", home / "darwin" / "trial-state.json")
    monkeypatch.setattr(darwin, "CRON_JOBS_FILE", home / "cron" / "jobs.json")
    return home


@pytest.mark.parametrize("name", [
    "REPORTS_DIR", "FITNESS_FILE", "HISTORY_FILE", "REPORT_FILE",
    "PROBE_FILE", "TUNING_FILE",
])
def test_live_artifact_write_is_refused(sandbox, name):
    """Every live artifact path raises instead of being overwritten."""
    live = getattr(darwin, "_LIVE_" + ("DARWIN_DIR" if name == "TUNING_FILE"
                                       else "REPORTS_DIR"))
    if name == "REPORTS_DIR":
        target = live
    elif name == "TUNING_FILE":
        target = live / "tuning.json"
    else:
        target = live / f"darwin-{name.split('_')[0].lower()}.json"
    with pytest.raises(RuntimeError, match="refusing to write live artifact"):
        darwin._save_json(target, {"probe": True})


def test_real_run_is_not_blocked(sandbox, monkeypatch):
    """Restoring the real SKILLS_DIR re-enables normal writes."""
    monkeypatch.setattr(darwin, "SKILLS_DIR", darwin._IMPORT_SKILLS_DIR)
    target = sandbox / "reports" / "ok.json"
    darwin._save_json(target, {"probe": True})
    assert target.exists()


def test_record_history_refuses_live_ledger(sandbox):
    """The append-only history ledger must never receive a sandbox snap."""
    live_history = darwin._LIVE_REPORTS_DIR / "darwin-history.jsonl"
    with pytest.raises(RuntimeError, match="refusing to write live artifact"):
        darwin._guard_live_artifact(live_history)


def test_sandbox_paths_still_work(sandbox):
    """Redirected (non-live) paths keep working -- the guard is not a blanket ban."""
    target = sandbox / "reports" / "darwin-history.jsonl"
    darwin._save_json(target, {"ok": True})
    assert target.exists()
