"""Tests for scripts/asi_audit.py.

The audit's whole value is that it cannot flatter: a capability is PROVEN only
when the implementation exists AND something actually runs it. These tests pin
exactly that, plus the ABSENT/PARTIAL boundaries — if the scoring ever loosens,
these fail.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "asi_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("asi_audit", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["asi_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


def _setup(tmp_path, monkeypatch, caps, jobs):
    mod = _load()
    home = tmp_path / "home"
    (home / "cron").mkdir(parents=True)
    (home / "cron" / "jobs.json").write_text(json.dumps({"jobs": jobs}), encoding="utf-8")
    monkeypatch.setattr(mod, "HOME", home)
    monkeypatch.setattr(mod, "REPO", tmp_path / "repo")
    monkeypatch.setattr(mod, "CAPABILITIES", caps)
    return mod, home


def _touch(home, rel):
    p = home / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")


def test_proven_requires_implementation_AND_a_live_runtime(tmp_path, monkeypatch):
    caps = [{"name": "c", "claim": "x",
             "evidence": ["impl.py"], "runtime": ["job-a"]}]
    jobs = [{"name": "job-a", "enabled": True, "last_status": "ok"}]
    mod, home = _setup(tmp_path, monkeypatch, caps, jobs)
    _touch(home, "impl.py")
    assert mod.audit()["capabilities"][0]["status"] == "PROVEN"


def test_implementation_without_running_runtime_is_only_PARTIAL(tmp_path, monkeypatch):
    """Built but not running is NOT a capability — the strict boundary."""
    caps = [{"name": "c", "claim": "x",
             "evidence": ["impl.py"], "runtime": ["job-a"]}]
    jobs = [{"name": "job-a", "enabled": True, "last_status": "error"}]
    mod, home = _setup(tmp_path, monkeypatch, caps, jobs)
    _touch(home, "impl.py")
    assert mod.audit()["capabilities"][0]["status"] == "PARTIAL"


def test_disabled_runtime_does_not_count(tmp_path, monkeypatch):
    caps = [{"name": "c", "claim": "x",
             "evidence": ["impl.py"], "runtime": ["job-a"]}]
    jobs = [{"name": "job-a", "enabled": False, "last_status": "ok"}]
    mod, home = _setup(tmp_path, monkeypatch, caps, jobs)
    _touch(home, "impl.py")
    assert mod.audit()["capabilities"][0]["status"] == "PARTIAL"


def test_missing_implementation_is_ABSENT(tmp_path, monkeypatch):
    caps = [{"name": "c", "claim": "x",
             "evidence": ["nope.py"], "runtime": ["job-a"]}]
    mod, home = _setup(tmp_path, monkeypatch, caps, [])
    r = mod.audit()["capabilities"][0]
    assert r["status"] == "ABSENT"
    assert r["evidence_missing"] == ["nope.py"]


def test_no_runtime_asserted_can_never_be_PROVEN(tmp_path, monkeypatch):
    """A capability nobody runs must not be reported as proven."""
    caps = [{"name": "c", "claim": "x", "evidence": ["impl.py"], "runtime": []}]
    mod, home = _setup(tmp_path, monkeypatch, caps, [])
    _touch(home, "impl.py")
    assert mod.audit()["capabilities"][0]["status"] == "PARTIAL"


def test_counts_and_report_are_honest(tmp_path, monkeypatch, capsys):
    caps = [
        {"name": "good", "claim": "a", "evidence": ["i.py"], "runtime": ["j"]},
        {"name": "shelf", "claim": "b", "evidence": ["i.py"], "runtime": ["gone"]},
        {"name": "nope", "claim": "c", "evidence": ["missing.py"], "runtime": []},
    ]
    jobs = [{"name": "j", "enabled": True, "last_status": "ok"}]
    mod, home = _setup(tmp_path, monkeypatch, caps, jobs)
    _touch(home, "i.py")
    result = mod.audit()
    assert result["counts"] == {"PROVEN": 1, "PARTIAL": 1, "ABSENT": 1}
    text = mod.report(result)
    assert "claim of super-intelligence" in text
    assert "shelf" in text and "nope" in text


def test_strict_exit_code_only_when_something_is_absent(tmp_path, monkeypatch):
    caps = [{"name": "c", "claim": "x", "evidence": ["impl.py"], "runtime": ["j"]}]
    jobs = [{"name": "j", "enabled": True, "last_status": "ok"}]
    mod, home = _setup(tmp_path, monkeypatch, caps, jobs)
    _touch(home, "impl.py")
    assert mod.main(["--strict"]) == 0
    (home / "impl.py").unlink()
    assert mod.main(["--strict"]) == 1


def test_real_repo_declares_every_capability_with_evidence_paths():
    """Guard against a typo'd path silently making a capability ABSENT.

    Checks against the REAL home/repo, not `mod.HOME`: under pytest the
    environment points OPENAMER_HOME at a temp dir, so the module-level HOME is
    not the machine's — the point of this guard is the machine's paths.
    """
    mod = _load()
    real_repo = Path(__file__).resolve().parents[2]          # openamer-repo
    real_home = Path(os.environ.get("USERPROFILE", r"C:\Users\damir")) \
        / "AppData" / "Local" / "openamer-laptop"
    missing = []
    for cap in mod.CAPABILITIES:
        assert cap["evidence"], f"{cap['name']} has no evidence"
        for rel in cap["evidence"]:
            if not ((real_home / rel).exists() or (real_repo / rel).exists()):
                missing.append(f"{cap['name']}: {rel}")
    assert not missing, f"evidence paths not found on this machine: {missing}"