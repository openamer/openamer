"""Translation helpers query process existence without sending OS signals."""
import importlib.util
from pathlib import Path

import psutil
import pytest


@pytest.mark.parametrize("script", ["start_i18n_detached.py", "fill_desktop_locales.py"])
def test_process_liveness_uses_portable_process_query(script, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "scripts" / script
    spec = importlib.util.spec_from_file_location("translation_liveness", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    queried = []

    def exists(pid):
        queried.append(pid)
        return pid == 17

    def forbid_signal(*args):
        pytest.fail("Liveness queries must never send process signals")

    monkeypatch.setattr(psutil, "pid_exists", exists)
    monkeypatch.setattr(module.os, "kill", forbid_signal)
    assert module._pid_alive(17)
    assert not module._pid_alive(18)
    assert not module._pid_alive(0)
    assert not module._pid_alive(-1)
    assert queried == [17, 18]
