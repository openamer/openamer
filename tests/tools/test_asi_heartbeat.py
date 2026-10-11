"""Tests for tools/asi/heartbeat.py — the ASI heartbeat's hang guard.

Why this exists: a subsystem whose tick blocks on a network call with no
timeout used to hang the WHOLE heartbeat, so `_save_state()` never ran and the
state file silently froze for 9 days *while the cron kept reporting "ok"*.
These tests pin the two fixes that unblocked it:

  * ``_tick_with_timeout`` — a hung subsystem is abandoned, not waited on.
  * ``_save_state`` still runs after a hung tick, so the heartbeat stays
    observable instead of freezing behind a green cron.

Everything is hermetic: a dummy subsystem replaces the real ones and the state
file is redirected into ``tmp_path``.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from tools.asi.heartbeat import Heartbeat, Subsystem


class _Blocking(Subsystem):
    """A subsystem whose tick never returns (simulates a blocking network call)."""
    def __init__(self, seconds: float = 30.0):
        super().__init__(name="blocker", category="test", cadence_minutes=0,
                         scripts=[], description="hangs on purpose")
        self._seconds = seconds

    def tick(self, force: bool = False):
        time.sleep(self._seconds)
        return {"success": True}


class _Ok(Subsystem):
    def __init__(self):
        super().__init__(name="ok", category="test", cadence_minutes=0,
                         scripts=[], description="instant")

    def tick(self, force: bool = False):
        return {"success": True, "done": True}


@pytest.fixture
def hb(tmp_path, monkeypatch):
    """A Heartbeat with dummy subsystems and no real state on disk."""
    h = Heartbeat()
    monkeypatch.setattr(h, "STATE_FILE", tmp_path / "asi_heartbeat.json")
    h.subsystems = {}
    monkeypatch.setattr(h, "TICK_TIMEOUT", 0.5)
    return h


def test_hung_subsystem_is_abandoned_not_waited_on(hb):
    """The whole point: a blocked tick must not stall the heartbeat for its full duration."""
    hb.subsystems["blocker"] = _Blocking(seconds=5.0)
    t0 = time.time()
    result = hb.tick(system="blocker", force=True)
    elapsed = time.time() - t0
    assert result["results"]["blocker"].get("timeout") is True, "hung tick was not flagged"
    assert elapsed < 2.0, f"heartbeat waited {elapsed:.1f}s on a blocked subsystem"


def test_state_is_saved_even_when_a_subsystem_hangs(hb):
    """The 9-day freeze bug: a hang must not stop _save_state()."""
    hb.subsystems["blocker"] = _Blocking(seconds=5.0)
    hb.tick(system="blocker", force=True)
    assert hb.STATE_FILE.exists(), "state file not written after a hung tick"
    state = json.loads(hb.STATE_FILE.read_text(encoding="utf-8"))
    assert "updated_at" in state and state["updated_at"]


def test_hung_subsystem_is_not_marked_as_run(hb):
    """A timed-out subsystem stays due, so it is retried next tick (not silently skipped)."""
    hb.subsystems["blocker"] = _Blocking(seconds=5.0)
    hb.tick(system="blocker", force=True)
    assert hb.subsystems["blocker"].last_run is None


def test_healthy_subsystem_still_runs_and_is_recorded(hb):
    hb.subsystems["ok"] = _Ok()
    result = hb.tick(system="ok", force=True)
    assert result["results"]["ok"]["success"] is True
    assert hb.subsystems["ok"].last_run is not None


def test_no_args_ticks_instead_of_printing_help(hb, monkeypatch, capsys):
    """The cron runs a bare no-arg script. That must TICK, not print --help and
    exit 0 — the silent no-op that froze the heartbeat for 9 days."""
    import sys
    seen = {}
    monkeypatch.setattr(hb, "tick", lambda **kw: (seen.update(kw), {"systems_ticked": 0, "results": {}})[1])
    monkeypatch.setattr("tools.asi.heartbeat.get_heartbeat", lambda: hb)
    monkeypatch.setattr(sys, "argv", ["asi_heartbeat.py"])  # no flags, like cron
    from tools.asi.heartbeat import main
    main()
    assert "system" in seen, "no-arg invocation did not tick (it printed help instead)"


def test_per_subsystem_timeout_overrides_default(hb, monkeypatch):
    """A subsystem with its own budget (e.g. learning=300s) gets that, not 60s."""
    hb.subsystems["blocker"] = _Blocking(seconds=5.0)
    hb.subsystems["blocker"].timeout = 0.5   # explicit per-subsystem budget
    monkeypatch.setattr(hb, "TICK_TIMEOUT", 99.0)  # default is larger...
    t0 = time.time()
    r = hb.tick(system="blocker", force=True)
    assert time.time() - t0 < 2.0, "per-subsystem timeout did not win over default"
    assert r["results"]["blocker"].get("timeout") is True


def test_a2a_server_is_health_checked_not_started():
    """a2a_server.py is a blocking serve_forever; the tick must only check it.
    Importing it hung the heartbeat forever."""
    from tools.asi import a2a
    assert hasattr(a2a, "server_health")
    # down -> a fast, honest failure (not a hang)
    r = a2a.server_health(url="http://127.0.0.1:9/a2a/health", timeout=1.0)
    assert r["success"] is False and "down" in r["error"]


def test_as_result_does_not_invent_success():
    """A dict's own success flag must win — the heartbeat may not upgrade it.

    Live 2026-10-11 the native route returned ``{"success": True}``
    unconditionally, so a swarm subsystem read green while both its scripts
    had errored. Pin the mapping so a failed module can never look green.
    """
    from tools.asi.heartbeat import _as_result

    assert _as_result({"success": False, "error": "boom"})["success"] is False
    assert _as_result({"success": False, "error": "boom"})["error"] == "boom"
    assert _as_result({"success": True})["success"] is True
    assert _as_result({"ok": 1})["success"] is True        # no flag -> assume ok
    assert _as_result(0)["success"] is True                # process rc
    assert _as_result(2)["success"] is False               # non-zero rc
    assert _as_result(None)["success"] is True             # uneventful run


def test_missing_script_is_a_failure_not_a_false_pass(monkeypatch):
    """A script that does not exist must make the subsystem red, not green."""
    sub = Subsystem(name="ghost", category="test", cadence_minutes=0,
                    scripts=["does_not_exist_xyz.py"])
    r = sub.tick()
    assert r["any_success"] is False, "a missing script was reported green"
    assert r["results"][0]["success"] is False


def test_cadence_minutes_parses_both_schedule_shapes():
    from tools.asi.heartbeat import _cadence_minutes

    assert _cadence_minutes({"kind": "interval", "minutes": 240}) == 240
    assert _cadence_minutes({"kind": "cron", "expr": "*/15 * * * *"}) == 15
    assert _cadence_minutes({"kind": "cron", "expr": "*/5 * * * *"}) == 5
    assert _cadence_minutes({"kind": "cron", "expr": "0 * * * *"}) == 60
    assert _cadence_minutes({"kind": "cron", "expr": "0 */6 * * *"}) == 360
    assert _cadence_minutes({"kind": "cron", "expr": "30 3 * * *"}) == 1440
    assert _cadence_minutes({"kind": "cron", "expr": "0 6 * * 0"}) == 7 * 24 * 60
    assert _cadence_minutes({"kind": "cron", "expr": "garbage"}) is None
    assert _cadence_minutes("nope") is None


def test_slow_script_is_not_stormed_by_a_fast_sibling(monkeypatch):
    """A 5m script must not drag its 8h sibling along on every tick."""
    ran = []
    sub = Subsystem(name="mix", category="test", cadence_minutes=5,
                    scripts=["fast.py", "slow.py"])
    sub.script_cadence = {"fast.py": 5, "slow.py": 480}
    monkeypatch.setattr(
        sub, "_run_script", lambda s: (ran.append(s), {"success": True})[1]
    )

    now = time.time()
    sub._state["script_last_run"] = {"fast.py": now - 6 * 60, "slow.py": now - 60}
    sub.tick()
    assert ran == ["fast.py"], f"slow script was stormed: {ran}"

    ran.clear()
    sub.tick(force=True)
    assert set(ran) == {"fast.py", "slow.py"}, "force must run everything"


def test_engine_only_adopts_retired_jobs(tmp_path, monkeypatch):
    """Handoff: adopt a retired job's script, never one a live cron still owns,
    so a side effect is never doubled."""
    import json

    from tools.asi import heartbeat as hbm

    jobs = {"jobs": [
        {"id": "keep", "name": "Keep", "script": "owned.py", "enabled": True,
         "schedule": {"kind": "interval", "minutes": 5}},
        {"id": "retired", "name": "Retired", "script": "retired.py", "enabled": False,
         "schedule": {"kind": "interval", "minutes": 30}},
    ]}
    f = tmp_path / "jobs.json"
    f.write_text(json.dumps(jobs), encoding="utf-8")
    monkeypatch.setattr(hbm, "JOBS_FILE", f)
    monkeypatch.setattr(hbm, "_script_path", lambda name: hbm.Path("/x") / name)
    monkeypatch.setenv("OPENAMER_HEARTBEAT_OWN", "1")

    hb = hbm.Heartbeat()
    sub = hbm.Subsystem(name="t", category="t", cadence_minutes=99, scripts=[])
    sub.cron_ids = ["keep", "retired"]
    hb.subsystems = {"t": sub}
    hb._reconcile_scripts()

    assert sub.scripts == ["retired.py"], sub.scripts
    assert sub.script_cadence == {"retired.py": 30}
    assert sub.cadence_minutes == 30


def test_wrapper_owned_script_is_never_adopted(tmp_path, monkeypatch):
    """internet_learner runs under the live Growth Loop wrapper. Its own job is
    retired, but the engine must still not run it — that would double the work."""
    import json

    from tools.asi import heartbeat as hbm

    jobs = {"jobs": [
        {"id": "il", "name": "internet-learner", "script": "internet_learner.py",
         "enabled": False, "schedule": {"kind": "interval", "minutes": 5}},
    ]}
    f = tmp_path / "jobs.json"
    f.write_text(json.dumps(jobs), encoding="utf-8")
    monkeypatch.setattr(hbm, "JOBS_FILE", f)
    monkeypatch.setattr(hbm, "_script_path", lambda name: hbm.Path("/x") / name)
    monkeypatch.setenv("OPENAMER_HEARTBEAT_OWN", "1")

    hb = hbm.Heartbeat()
    sub = hbm.Subsystem(name="t", category="t", cadence_minutes=99, scripts=[])
    sub.cron_ids = ["il"]
    hb.subsystems = {"t": sub}
    hb._reconcile_scripts()
    assert sub.scripts == [], sub.scripts


def test_broken_explicit_name_is_dropped(monkeypatch):
    """A registry entry that names a job or bakes args into a filename must
    never be adopted as a runnable script."""
    from tools.asi import heartbeat as hbm

    monkeypatch.setenv("OPENAMER_HEARTBEAT_OWN", "1")
    sub = hbm.Subsystem(name="t", category="t", cadence_minutes=5,
                        scripts=["smart-cache.py --clean", "darwin-grid.py", "asi-audit"])
    hb = hbm.Heartbeat()
    hb.subsystems = {"t": sub}
    hb._reconcile_scripts()
    assert sub.scripts == [], sub.scripts


def test_ownership_is_explicit(tmp_path, monkeypatch):
    """No marker -> own nothing. An id in the marker -> own exactly that job.
    "*" -> own every retired job but never a live one. Ownership is named, never
    implied."""
    import json

    from tools.asi import heartbeat as hbm

    jobs = {"jobs": [
        {"id": "r1", "name": "R1", "script": "r1.py", "enabled": False,
         "schedule": {"kind": "interval", "minutes": 10}},
        {"id": "r2", "name": "R2", "script": "r2.py", "enabled": True,
         "schedule": {"kind": "interval", "minutes": 10}},
    ]}
    jf = tmp_path / "jobs.json"
    jf.write_text(json.dumps(jobs), encoding="utf-8")
    monkeypatch.setattr(hbm, "JOBS_FILE", jf)
    monkeypatch.setattr(hbm, "_script_path", lambda name: hbm.Path("/x") / name)
    monkeypatch.delenv("OPENAMER_HEARTBEAT_OWN", raising=False)
    marker = tmp_path / "own.enabled"
    monkeypatch.setattr(hbm, "OWN_MARKER", marker)

    def build():
        hb = hbm.Heartbeat()
        sub = hbm.Subsystem(name="t", category="t", cadence_minutes=99, scripts=[])
        sub.cron_ids = ["r1", "r2"]
        hb.subsystems = {"t": sub}
        hb._reconcile_scripts()
        return sub

    assert build().scripts == [], "no marker must own nothing"
    marker.write_text("", encoding="utf-8")
    assert build().scripts == [], "empty marker must own nothing"
    marker.write_text("r2\n", encoding="utf-8")
    assert build().scripts == ["r2.py"], "a named id must be owned even if live"
    marker.write_text("*\n", encoding="utf-8")
    assert build().scripts == ["r1.py"], "'*' must own retired jobs only"







