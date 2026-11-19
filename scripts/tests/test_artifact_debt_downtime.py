"""A machine that was asleep is not a broken job.

Measured 2026-11-19: the artifact-debt check ran at 21:25 after 15.3 hours of
standby and reported five STALE rows — `active-learning-loop` among them, a job
that runs every 7 minutes and had worked perfectly for every hour the machine
was awake. Every artifact was "old" because the machine was off, not because a
job failed.

Five false rows an hour is how you learn to ignore an alarm. This pins the
correction: the check measures its own gap to the previous run, treats the
excess over a normal cadence as downtime, and subtracts it from every age.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "verify-job-artifacts.py"


def _load(tmp_path: Path, monkeypatch):
    spec = importlib.util.spec_from_file_location("verify_job_artifacts", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_job_artifacts"] = mod
    spec.loader.exec_module(mod)
    state = tmp_path / "state.json"
    monkeypatch.setattr(mod, "_STATE", state)
    monkeypatch.setattr(mod, "HOME", tmp_path)
    monkeypatch.setattr(mod, "_job_enabled", lambda job_id: True)
    return mod, state


def test_no_state_means_no_downtime(tmp_path, monkeypatch):
    mod, _ = _load(tmp_path, monkeypatch)
    assert mod._machine_downtime_minutes() == 0.0


def test_normal_hourly_gap_is_not_downtime(tmp_path, monkeypatch):
    mod, state = _load(tmp_path, monkeypatch)
    state.write_text(json.dumps({"last_run": time.time() - 61 * 60}), encoding="utf-8")
    assert mod._machine_downtime_minutes() == 0.0


def test_fifteen_hour_gap_counts_as_downtime(tmp_path, monkeypatch):
    mod, state = _load(tmp_path, monkeypatch)
    state.write_text(json.dumps({"last_run": time.time() - 16 * 3600}), encoding="utf-8")
    down = mod._machine_downtime_minutes()
    assert 14 * 60 < down < 15 * 60, down   # 16h minus the 90-minute grace


def test_corrupt_state_is_not_fatal(tmp_path, monkeypatch):
    mod, state = _load(tmp_path, monkeypatch)
    state.write_text("{not json", encoding="utf-8")
    assert mod._machine_downtime_minutes() == 0.0


def test_stale_artifact_is_cleared_by_downtime_and_still_flagged_without_it(tmp_path, monkeypatch):
    """The same 15h-old artifact: debt when the machine was up, fine when it was off."""
    mod, _ = _load(tmp_path, monkeypatch)
    art = tmp_path / "cron" / "output" / "job1"
    art.mkdir(parents=True)
    f = art / "run.md"
    f.write_text("x", encoding="utf-8")
    old = time.time() - 15 * 3600
    import os
    os.utime(f, (old, old))

    registry = {"job1": {
        "label": "job-one", "artifact": "cron/output/job1",
        "max_age_minutes": 120, "kind": "ran",
    }}

    judged_without = mod.check(registry, [])
    assert any("STALE" in line for line in judged_without), judged_without

    judged_with = mod.check(registry, [], downtime_min=14.5 * 60)
    assert not any("STALE" in line for line in judged_with), judged_with


def test_record_own_run_writes_the_state(tmp_path, monkeypatch):
    mod, state = _load(tmp_path, monkeypatch)
    mod._record_own_run()
    assert json.loads(state.read_text(encoding="utf-8"))["last_run"] > time.time() - 5
