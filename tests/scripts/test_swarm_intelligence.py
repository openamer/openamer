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


def test_no_hardcoded_remote_host_is_probed(monkeypatch, si):
    """Discovery must not shell out to ssh for a baked-in address.

    The GPU PC (192.168.178.23) was decommissioned on 2026-11-18. Its probe used
    to carry ConnectTimeout=8 so a powered-down box could not hang the cycle
    (observed 2026-09-14: >60 s block, cron killed mid-run). Both the host and
    the probe are gone, so that contract has nothing left to describe; what
    matters now is that discovery stays network-free and a remote node can only
    arrive by being registered.
    """
    seen: dict = {}
    monkeypatch.setattr(si.subprocess, "run",
                        lambda cmd, **kw: seen.update(cmd=cmd) or _Proc())

    si.discover_agents()

    assert "cmd" not in seen, f"discovery shelled out: {seen.get('cmd')!r}"

    source = Path(si.__file__).read_text(encoding="utf-8")
    assert "192.168." not in source, "a hardcoded LAN host is back in the routing table"
    assert "ConnectTimeout" not in source, (
        "an ssh probe came back without the fail-fast flags; bring back the "
        "2026-09-14 regression test with it"
    )


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


def test_knowledge_synthesis_needs_no_remote(monkeypatch, si):
    """Synthesis must work with no reachable remote at all.

    The old test asserted the static route carried an ssh ConnectTimeout; the
    route is local-only now, so the property worth pinning is that synthesis
    completes without touching the network.
    """
    seen: dict = {}
    monkeypatch.setattr(si.subprocess, "run",
                        lambda cmd, **kw: seen.update(cmd=cmd) or _Proc())

    si.synthesize_knowledge("x", remote_insight=None)

    assert "cmd" not in seen, f"synthesis shelled out: {seen.get('cmd')!r}"
