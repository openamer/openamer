"""Tests for agent/self_critique.py — the adversarial self-audit.

Every check exists because it caught a real, silent lie this system told about
itself on 2026-11-06:

  * a retired cron job whose loop nobody picked up (three organs were found this
    way, by accident — a sweep is the method),
  * a subsystem whose last tick failed while the state file still looked fresh,
  * evidence files that must be fresh and were three weeks old,
  * self-counts that disagreed with the file they were counting.

Hermetic: a temp home, no network, no heartbeat import.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from agent import self_critique as sc


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / "cron").mkdir(parents=True)
    (home / "memory" / "si").mkdir(parents=True)
    (home / "memory" / "self_model").mkdir(parents=True)
    (home / "logs").mkdir(parents=True)
    return home


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Dead organs
# ---------------------------------------------------------------------------

class TestDeadOrgans:
    def test_disabled_job_with_no_owner_is_reported(self, tmp_path):
        home = _home(tmp_path)
        _write(home / "cron" / "jobs.json", [
            {"name": "orphan", "script": "orphan.py", "enabled": False},
        ])
        _write(home / "memory" / "asi_heartbeat.json",
               {"subsystems": {"learning": {"scripts": {"other.py": 1.0}}}})
        findings, note = sc.check_dead_organs(home)
        assert note is None
        assert [f["subject"] for f in findings] == ["orphan"]
        assert findings[0]["severity"] == sc.WARNING

    def test_owned_script_is_not_reported(self, tmp_path):
        home = _home(tmp_path)
        _write(home / "cron" / "jobs.json", [
            {"name": "handed-over", "script": "loop.py", "enabled": False},
        ])
        _write(home / "memory" / "asi_heartbeat.json",
               {"subsystems": {"cognition": {"scripts": {"loop.py": 1.0}}}})
        findings, _ = sc.check_dead_organs(home)
        assert findings == []

    def test_enabled_job_is_not_a_dead_organ(self, tmp_path):
        home = _home(tmp_path)
        _write(home / "cron" / "jobs.json", [
            {"name": "running", "script": "live.py", "enabled": True},
        ])
        _write(home / "memory" / "asi_heartbeat.json", {"subsystems": {}})
        findings, _ = sc.check_dead_organs(home)
        assert findings == []

    def test_script_field_with_arguments_is_normalised(self, tmp_path):
        """A cron script field can carry args; the basename is the first token."""
        home = _home(tmp_path)
        _write(home / "cron" / "jobs.json", [
            {"name": "with-args", "script": "verifier_agent.py --days 1 --max 5",
             "enabled": False},
        ])
        _write(home / "memory" / "asi_heartbeat.json",
               {"subsystems": {"meta": {"scripts": {"verifier_agent.py": 1.0}}}})
        findings, _ = sc.check_dead_organs(home)
        assert findings == [], "an owned script must not be reported dead"


# ---------------------------------------------------------------------------
# 2. Silent failures
# ---------------------------------------------------------------------------

class TestSilentFailures:
    def test_failed_last_tick_is_critical(self, tmp_path):
        home = _home(tmp_path)
        _write(home / "memory" / "asi_heartbeat.json", {"subsystems": {
            "system": {"last_result": {"ok": False, "script": "service-watchdog.py",
                                       "detail": "exit_code=1"},
                       "consecutive_failures": 1},
        }})
        findings, _ = sc.check_silent_failures(home)
        assert findings and findings[0]["severity"] == sc.CRITICAL
        assert findings[0]["subject"] == "system"

    def test_ok_tick_is_silent(self, tmp_path):
        home = _home(tmp_path)
        _write(home / "memory" / "asi_heartbeat.json", {"subsystems": {
            "system": {"last_result": {"ok": True}, "consecutive_failures": 0},
        }})
        findings, _ = sc.check_silent_failures(home)
        assert findings == []


# ---------------------------------------------------------------------------
# 3. Red cron jobs
# ---------------------------------------------------------------------------

def test_failing_cron_is_critical(tmp_path):
    home = _home(tmp_path)
    _write(home / "cron" / "jobs.json", [
        {"name": "nightly", "enabled": True, "last_status": "error",
         "last_error": "Script exited with code 1\nmore detail"},
        {"name": "fine", "enabled": True, "last_status": "ok"},
    ])
    findings, _ = sc.check_failing_crons(home)
    assert len(findings) == 1
    assert findings[0]["subject"] == "nightly"
    assert findings[0]["severity"] == sc.CRITICAL


# ---------------------------------------------------------------------------
# 4. Zombie goals
# ---------------------------------------------------------------------------

def test_goal_active_past_the_window_is_reported(tmp_path):
    home = _home(tmp_path)
    old = (datetime.datetime.now(datetime.timezone.utc)
           - datetime.timedelta(minutes=sc.ZOMBIE_GOAL_MINUTES + 30)).isoformat()
    _write(home / "memory" / "si" / "goals.json", [
        {"id": "g1", "status": "active", "created": old, "desc": "stuck"},
        {"id": "g2", "status": "done", "created": old, "desc": "finished"},
    ])
    findings, _ = sc.check_zombie_goals(home)
    assert [f["subject"] for f in findings] == ["g1"]


def test_fresh_active_goal_is_not_a_zombie(tmp_path):
    home = _home(tmp_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _write(home / "memory" / "si" / "goals.json", [
        {"id": "g1", "status": "active", "created": now, "desc": "just started"},
    ])
    findings, _ = sc.check_zombie_goals(home)
    assert findings == []


# ---------------------------------------------------------------------------
# 5. Stale evidence — the symptom that actually bit
# ---------------------------------------------------------------------------

def test_stale_lessons_are_critical(tmp_path):
    """The executor prompts itself with these; three weeks old is a lie in effect."""
    import os
    import time

    home = _home(tmp_path)
    path = home / "memory" / "si" / "lessons.json"
    _write(path, {"rules": []})
    old = time.time() - 60 * 60 * 24 * 21
    os.utime(path, (old, old))
    findings, _ = sc.check_stale_evidence(home)
    kinds = [f for f in findings if f["subject"] == "memory/si/lessons.json"]
    assert kinds and kinds[0]["severity"] == sc.CRITICAL


def test_fresh_file_is_not_reported_and_missing_is_a_skip(tmp_path):
    home = _home(tmp_path)
    _write(home / "memory" / "si" / "lessons.json", {"rules": []})
    findings, note = sc.check_stale_evidence(home)
    assert not [f for f in findings if f["subject"] == "memory/si/lessons.json"]
    assert note and "no file yet" in note, "missing files must be a skip, not silence"


# ---------------------------------------------------------------------------
# 6. Self-model counts: lag is not a lie
# ---------------------------------------------------------------------------

def _self_model(home: Path, **fields):
    _write(home / "memory" / "self_model" / "current_state.json", fields)


def test_small_drift_is_lag_not_a_lie(tmp_path):
    home = _home(tmp_path)
    _self_model(home, memory_episodes=100)
    with open(home / "memory" / "longterm_episodes.jsonl", "w", encoding="utf-8") as fh:
        for i in range(102):
            fh.write(json.dumps({"i": i}) + "\n")
    findings, _ = sc.check_self_model_contradictions(home)
    assert findings and findings[0]["severity"] == sc.INFO
    assert findings[0]["kind"] == "self-model-lagging"


def test_large_drift_is_a_contradiction(tmp_path):
    home = _home(tmp_path)
    _self_model(home, memory_episodes=100)
    with open(home / "memory" / "longterm_episodes.jsonl", "w", encoding="utf-8") as fh:
        for i in range(400):
            fh.write(json.dumps({"i": i}) + "\n")
    findings, _ = sc.check_self_model_contradictions(home)
    assert findings and findings[0]["severity"] == sc.WARNING
    assert findings[0]["kind"] == "self-model-contradiction"


# ---------------------------------------------------------------------------
# The tool's own honesty: a broken check is a SKIP, never a pass
# ---------------------------------------------------------------------------

def test_audit_reports_skips_and_never_invents_a_clean_verdict(tmp_path, monkeypatch):
    home = _home(tmp_path)  # nothing exists -> every check should skip
    report = sc.audit(home)
    assert report["skipped"], "an unreadable home must produce skips"
    assert report["checks_ran"] < report["checks_total"]
    rendered = sc.render(report)
    assert "SKIPPED" in rendered


def test_audit_verdict_is_critical_when_a_critical_stands(tmp_path):
    home = _home(tmp_path)
    _write(home / "cron" / "jobs.json", [
        {"name": "nightly", "enabled": True, "last_status": "error",
         "last_error": "boom"},
    ])
    report = sc.audit(home)
    assert report["verdict"] == "critical"
    assert report["counts"]["critical"] >= 1


def test_render_always_prints_the_skips(tmp_path):
    report = sc.audit(_home(tmp_path))
    assert "SKIPPED" in sc.render(report)