"""Tests for tools/asi/cognition.py — the integrated cognitive cycle.

Why this exists: the world model held 168 predictions and ZERO corrections,
because ``training/predict_validate.py`` and ``training/self_model.py`` were
ticked SEPARATELY — nothing ever turned a failed prediction into a correction.
This cycle chains world_model + prediction + self_model in ONE run and writes
the correction edge.

These tests are structural and hermetic: they never start an embedding server
and never touch the live world model.
"""
from __future__ import annotations

import inspect

from tools.asi.heartbeat import Heartbeat, Subsystem


def test_module_exposes_its_entrypoints():
    """The heartbeat and the CLI both need module-level callables."""
    from tools.asi import cognition

    for name in ("Cognition", "get_cognition", "cycle", "status"):
        assert hasattr(cognition, name), f"missing entrypoint: {name}"


def test_cycle_is_a_module_level_callable():
    """native_map resolves 'tools.asi.cognition.cycle' and calls it with no args."""
    from tools.asi import cognition

    assert callable(cognition.cycle)
    sig = inspect.signature(cognition.cycle)
    # every positional/named parameter must be optional: the heartbeat calls it bare
    for p in sig.parameters.values():
        if p.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
            continue
        assert p.default is not inspect.Parameter.empty, f"{p.name} must have a default"


def test_heartbeat_registers_cognition_as_native():
    """Cognition must not depend on a cron job — it is a native subsystem."""
    hb = Heartbeat()
    sub = hb.subsystems.get("cognition")
    assert sub is not None, "cognition subsystem is not registered"
    assert sub.native is True, "cognition must be native (no cron behind it)"
    # a native subsystem survives _reconcile_scripts() with its script intact
    assert "cognition_cycle.py" in sub.scripts, (
        "native subsystem lost its script during reconciliation"
    )


def test_heartbeat_routes_the_cycle_in_process():
    """The cycle runs via native_map (DirectImport), never as a subprocess."""
    src = inspect.getsource(Subsystem._run_script)
    assert "cognition_cycle.py" in src, "no native route for the cycle"
    assert "tools.asi.cognition.cycle" in src, "route must point at the cycle"


def test_native_subsystems_keep_their_scripts():
    """_reconcile_scripts must skip native subsystems (no jobs.json to derive from)."""
    src = inspect.getsource(Heartbeat._reconcile_scripts)
    assert "sub.native" in src, "reconciliation ignores the native flag"


def test_native_subsystems_survive_the_dormant_path(monkeypatch):
    """With ownership OFF, a native subsystem must keep its script.

    This is the state every FRESH install boots in: ``_owned_ids()`` returns None
    until an ownership marker exists. The dormant branch used to empty the script
    list for *every* subsystem — native ones included — and ``return``ed before
    the ``if sub.native: continue`` guard below it could ever run. The heartbeat
    then reported a registered cognition subsystem that could not execute, so the
    integrated cycle silently never ran on a default install.

    Forced explicitly (\u201cno marker\u201d) so the assertion does not depend on whether
    the machine running the tests happens to have an ownership marker.
    """
    from tools.asi import heartbeat as hbmod

    monkeypatch.setattr(hbmod, "_owned_ids", lambda: None)

    hb = Heartbeat()
    sub = hb.subsystems["cognition"]

    assert sub.native is True
    assert "cognition_cycle.py" in sub.scripts, (
        "the dormant path emptied a native subsystem's scripts"
    )
