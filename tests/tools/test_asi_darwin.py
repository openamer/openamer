"""Tests for tools/asi/darwin.py — the Darwin native-import wiring.

Why this exists: ``darwin.py`` searched for ``darwin_engine`` under
``OPENAMER_HOME/scripts``, but the module lives under
``OPENAMER_HOME/openamer-agent/scripts``. Every native Darwin call therefore
raised ModuleNotFoundError and silently fell back to spawning a subprocess,
so the "native, in-process" integration was never actually in use.
"""
from __future__ import annotations

from tools.asi import darwin


def test_agent_scripts_dir_is_on_sys_path():
    """The tree that actually holds darwin_engine.py must be importable."""
    import sys
    assert str(darwin.AGENT_SCRIPTS_DIR) in sys.path


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
