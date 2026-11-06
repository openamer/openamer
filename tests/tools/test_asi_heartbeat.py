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


# â”€â”€ Native resolution: a dotted path into a flat module â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#
# The map is written "tools.asi.cognition.cycle", but tools/asi/cognition.py is a
# MODULE â€” splitting on the last dot asked Python for
# "tools.asi.cognition.cycle" (impossible) and EVERY "native" subsystem silently
# fell back to spawning a subprocess. Measured 2026-11-06: all four probed specs
# failed to import, so nothing was ever native.

def test_dotted_native_spec_resolves_into_a_flat_module():
    from tools.asi.heartbeat import _resolve_native

    for spec in ("tools.asi.cognition.cycle", "tools.asi.a2a.server_health",
                 "tools.asi.swarm.cycle", "tools.asi.darwin.grid_sync"):
        fn = _resolve_native(spec)
        assert callable(fn), f"{spec} must resolve to a callable"


def test_unresolvable_native_spec_returns_none_not_a_wrong_callable():
    from tools.asi.heartbeat import _resolve_native

    assert _resolve_native("tools.asi.does.not.exist") is None
    assert _resolve_native("no_such_module.at_all") is None


# â”€â”€ The outcome must be persisted, not just the timestamp â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_failed_script_is_recorded_as_failure(hb):
    """A missing script must leave evidence, not a fresh last_run."""
    sub = Subsystem(name="broken", category="test", cadence_minutes=0,
                    scripts=["definitely-not-a-script.py"], description="fails")
    hb.subsystems["broken"] = sub
    out = sub.tick(force=True)
    assert out["any_success"] is False
    rec = sub._state["last_result"]
    assert rec["ok"] is False
    assert "not found" in rec["detail"].lower() or rec["detail"]
    assert sub._state["consecutive_failures"] == 1


def test_successful_script_is_recorded_and_resets_the_counter(hb):
    sub = Subsystem(name="fine", category="test", cadence_minutes=0,
                    scripts=["whatever.py"], description="ok")
    sub._state["consecutive_failures"] = 2
    sub._run_script = lambda name: {"success": True, "stdout": "done"}
    sub.tick(force=True)
    assert sub._state["last_result"]["ok"] is True
    assert sub._state["consecutive_failures"] == 0


def test_state_file_carries_the_outcome(hb):
    """asi_heartbeat.json must let a reader tell a working organ from a dead one."""
    sub = Subsystem(name="fine", category="test", cadence_minutes=0,
                    scripts=["whatever.py"], description="ok")
    sub._run_script = lambda name: {"success": True, "stdout": "done"}
    hb.subsystems["fine"] = sub
    sub.tick(force=True)
    hb._save_state()
    state = json.loads(hb.STATE_FILE.read_text(encoding="utf-8"))
    entry = state["subsystems"]["fine"]
    assert entry["last_result"]["ok"] is True
    assert entry["consecutive_failures"] == 0


def test_cognition_subystem_runs_the_error_correction_step():
    """The integrated cycle only READS facts; predict_validate scores them.

    Measured 2026-11-06: predict_validate.py belonged to NO subsystem, so the
    error-correction half of the loop had not run since 2026-10-31 while the
    cycle kept reporting "nothing new to process". A cycle that reads without
    scoring cannot get better.
    """
    h = Heartbeat()
    scripts = h.subsystems["cognition"].scripts
    assert "cognition_cycle.py" in scripts
    assert "training/predict_validate.py" in scripts
    # ... and the lessons the core injects into its own prompts
    assert "si_learner.py" in scripts
