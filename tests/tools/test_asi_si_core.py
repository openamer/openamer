"""Tests for tools/asi/si_core.py — the goal executor's behavioural probe.

The desire engine hands goals to the SI core; the core is the only thing that
turns them into work. Nothing in the heartbeat watched it (measured 2026-11-06),
so this probe has to answer two questions at once:

  * is it answering on :8123, and
  * is it CONSUMING — has the `done` counter in goals.json moved?

Liveness alone is the false positive this file exists to prevent: a process that
returns /status 200 while its queue stands still would otherwise look healthy.

Everything is hermetic: no network, a temp home, and the restart path patched.
"""

from __future__ import annotations

import datetime
import importlib
import json
import sys
from pathlib import Path

import pytest


def _load(home: Path, monkeypatch):
    monkeypatch.setenv("OPENAMER_HOME", str(home))
    sys.modules.pop("tools.asi.si_core", None)
    return importlib.import_module("tools.asi.si_core")


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / "memory" / "si").mkdir(parents=True)
    return home


def _goals(home: Path, *, done: int, active_ages_minutes=()):
    now = datetime.datetime.now(datetime.timezone.utc)
    rows = [{"id": f"d{i}", "desc": "done thing", "status": "done"}
            for i in range(done)]
    for i, age in enumerate(active_ages_minutes):
        created = (now - datetime.timedelta(minutes=age)).isoformat()
        rows.append({"id": f"a{i}", "desc": f"active {i}", "status": "active",
                     "created": created})
    (home / "memory" / "si" / "goals.json").write_text(json.dumps(rows), encoding="utf-8")


class TestAliveAndConsuming:
    def test_alive_with_moving_counter_is_healthy(self, tmp_path, monkeypatch):
        home = _home(tmp_path)
        _goals(home, done=10)
        mod = _load(home, monkeypatch)
        monkeypatch.setattr(mod, "_alive", lambda: True)
        # a previous probe with a LOWER counter
        mod.BASELINE.write_text(json.dumps({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "done": 8, "alive": True}), encoding="utf-8")
        r = mod.health()
        assert r["success"] is True
        assert r["done_delta"] == 2

    def test_dead_core_fails_and_attempts_one_restart(self, tmp_path, monkeypatch):
        home = _home(tmp_path)
        _goals(home, done=3)
        mod = _load(home, monkeypatch)
        monkeypatch.setattr(mod, "_alive", lambda: False)
        calls = {"n": 0}

        def _fake_restart():
            calls["n"] += 1
            return "restart attempted (rc=0)"

        monkeypatch.setattr(mod, "_restart", _fake_restart)
        r = mod.health()
        assert r["success"] is False
        assert r["alive"] is False
        assert calls["n"] == 1
        assert any("not answering" in x for x in r["reasons"])


class TestBehaviourNotLiveness:
    def test_active_goal_stuck_past_the_threshold_fails_the_probe(self, tmp_path, monkeypatch):
        home = _home(tmp_path)
        _goals(home, done=5, active_ages_minutes=(240,))
        mod = _load(home, monkeypatch)
        monkeypatch.setattr(mod, "_alive", lambda: True)
        mod.BASELINE.write_text(json.dumps({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "done": 5, "alive": True}), encoding="utf-8")
        r = mod.health()
        assert r["success"] is False
        assert r["stale_active"], "the stuck goal must be named"
        assert r["stale_active"][0]["age_minutes"] >= 240

    def test_fresh_active_goal_is_not_a_failure(self, tmp_path, monkeypatch):
        home = _home(tmp_path)
        _goals(home, done=5, active_ages_minutes=(5,))
        mod = _load(home, monkeypatch)
        monkeypatch.setattr(mod, "_alive", lambda: True)
        mod.BASELINE.write_text(json.dumps({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "done": 5, "alive": True}), encoding="utf-8")
        r = mod.health()
        assert r["success"] is True
        assert r["active"] == 1
        assert r["stale_active"] == []

    def test_idle_without_work_is_reported_but_not_failed(self, tmp_path, monkeypatch):
        """Nothing active and nothing moving is fine on an idle machine."""
        home = _home(tmp_path)
        _goals(home, done=7)
        mod = _load(home, monkeypatch)
        monkeypatch.setattr(mod, "_alive", lambda: True)
        old = (datetime.datetime.now(datetime.timezone.utc)
               - datetime.timedelta(minutes=300)).isoformat()
        mod.BASELINE.write_text(json.dumps({"ts": old, "done": 7, "alive": True}),
                                encoding="utf-8")
        r = mod.health()
        assert r["success"] is True
        assert any("idle" in x for x in r["reasons"])

    def test_baseline_is_written_so_the_next_probe_has_a_delta(self, tmp_path, monkeypatch):
        home = _home(tmp_path)
        _goals(home, done=4)
        mod = _load(home, monkeypatch)
        monkeypatch.setattr(mod, "_alive", lambda: True)
        mod.health()
        saved = json.loads(mod.BASELINE.read_text(encoding="utf-8"))
        assert saved["done"] == 4
        assert saved["ts"]


def test_the_heartbeat_owns_the_executor_as_a_native_subsystem():
    """The cron was retired; the heartbeat must be the one watching it now."""
    from tools.asi.heartbeat import Heartbeat, _resolve_native

    h = Heartbeat()
    sub = h.subsystems.get("si_core")
    assert sub is not None, "no subsystem watches the goal executor"
    assert sub.native is True
    assert callable(_resolve_native("tools.asi.si_core.health"))