"""Tests for tools/asi/darwin.py — the Darwin native-import wiring.

Why this exists: ``darwin.py`` searched for ``darwin_engine`` under
``OPENAMER_HOME/scripts``, but the module lives under
``OPENAMER_HOME/openamer-agent/scripts``. Every native Darwin call therefore
raised ModuleNotFoundError and silently fell back to spawning a subprocess,
so the "native, in-process" integration was never actually in use.
"""
from __future__ import annotations

from tools.asi import darwin


def test_the_tree_holding_darwin_engine_is_on_sys_path():
    """The tree that actually holds darwin_engine.py must be importable.

    Asserted by locating the module, not by naming a laptop path: on a
    checkout the engine is under <repo>/scripts, and AGENT_SCRIPTS_DIR
    (an install-tree path) cannot exist there. Naming it made this test
    unfalsifiable off the laptop rather than wrong.
    """
    import sys
    from pathlib import Path
    importlib_paths = [Path(p) for p in sys.path if p]
    holder = next((d for d in importlib_paths if (d / "darwin_engine.py").is_file()), None)
    assert holder is not None, f"no sys.path entry holds darwin_engine.py: {importlib_paths[:8]}"
    assert str(holder) in sys.path


def test_import_darwin_resolves_the_real_module():
    """_import_darwin must return the engine, not raise ModuleNotFoundError."""
    mod = darwin._import_darwin()
    assert mod.__name__ == "darwin_engine"
    assert hasattr(mod, "start_trial")


def test_autopilot_reports_success_without_subprocess_fallback():
    """A native call must not silently degrade to a subprocess."""
    result = darwin.autopilot()
    assert isinstance(result, dict)
    assert result.get("success") is True, result
