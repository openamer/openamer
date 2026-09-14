"""Regression tests for scripts/training/swarm_intelligence.py.

Live 2026-09-14: a full cycle blocked for >60s and the cron job was killed by a
gateway shutdown mid-run. Two causes, both fixed here:

1. Two ssh probes to the powered-down GPU PC ran with no ``ConnectTimeout``, so
   each call hung until the subprocess kill.
2. ``discover_agents()`` was called twice per cycle (main + update_swarm_identity),
   doubling that cost. The agents are now discovered once and passed in.

Hermetic: urllib and subprocess are monkeypatched, and OPENAMER_HOME points at a
temp dir so the module's import-time ``makedirs`` stays off the real home.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "training" / "swarm_intelligence.py"


def _load():
    spec = importlib.util.spec_from_file_location("swarm_intelligence", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["swarm_intelligence"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def si(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    # No local tool server in the test env: make the laptop probe fail cleanly.
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("no server")))
    return _load()


class _Proc:
    def __init__(self, stdout="", returncode=255):
        self.stdout, self.returncode = stdout, returncode


def test_ssh_probe_carries_connect_timeout(monkeypatch, si):
    """A powered-down host must fail fast, not hang the whole cycle."""
    seen: dict = {}
    monkeypatch.setattr(si.subprocess, "run",
                        lambda cmd, **kw: seen.update(cmd=cmd) or _Proc())
    si.discover_agents()
    cmd = seen["cmd"]
    assert "ConnectTimeout=8" in cmd
    assert "-o" in cmd


def test_update_identity_reuses_passed_agents(monkeypatch, si):
    """Counting cycles must not re-probe the network every call."""
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        return []

    monkeypatch.setattr(si, "discover_agents", boom)
    si.update_swarm_identity([])          # agents supplied => no discovery
    assert calls["n"] == 0
    si.update_swarm_identity()            # agents omitted => discovery happens
    assert calls["n"] == 1


def test_static_route_also_carries_connect_timeout(monkeypatch, si):
    seen: dict = {}
    monkeypatch.setattr(si.subprocess, "run",
                        lambda cmd, **kw: seen.update(cmd=cmd) or _Proc())
    si.synthesize_knowledge("x", remote_insight=None)
    assert "ConnectTimeout=8" in seen["cmd"]