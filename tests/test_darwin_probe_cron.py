"""Contract tests for the Darwin probe cron wrapper.

The wrapper lives in the runtime scripts directory
(%LOCALAPPDATA%\\openamer-laptop\\scripts) because cron scripts must, so the repo
suite would otherwise never touch it — a watchdog whose silence contract is
untested is a watchdog nobody notices has died.

The contract worth pinning is the quiet one: a no-agent cron delivers its stdout
verbatim and stays silent on empty output, so "silent unless something is
broken" is the actual behaviour being relied on. Both halves are asserted.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

WRAPPER = Path(
    r"C:\Users\damir\AppData\Local\openamer-laptop\scripts\darwin-probe-cron.py"
)

pytestmark = pytest.mark.skipif(
    not WRAPPER.is_file(),
    reason="runtime cron wrapper only exists on this checkout's machine",
)


@pytest.fixture()
def wrapper(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("darwin_probe_cron", WRAPPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    fake_probe = tmp_path / "darwin_skill_probe.py"
    fake_probe.write_text("# stand-in\n", encoding="utf-8")
    monkeypatch.setattr(mod, "PROBE", fake_probe)
    monkeypatch.setattr(mod, "REPORT", tmp_path / "darwin-probe.json")
    return mod


def _run(monkeypatch, mod, *, returncode: int, skills: dict) -> int:
    class _Proc:
        def __init__(self, rc: int):
            self.returncode = rc
            self.stdout = ""
            self.stderr = "boom" if rc else ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _Proc(returncode))
    mod.REPORT.write_text(json.dumps({"skills": skills}), encoding="utf-8")
    return mod.main()


def test_silent_when_every_reference_resolves(wrapper, monkeypatch, capsys):
    """Healthy population -> empty stdout -> the cron sends nothing."""
    rc = _run(monkeypatch, wrapper, returncode=0, skills={"ok-skill": {"missing": []}})

    assert rc == 0
    assert capsys.readouterr().out == ""


def test_speaks_up_when_a_reference_is_gone(wrapper, monkeypatch, capsys):
    """The one case worth a message: a skill points at a missing artifact."""
    rc = _run(
        monkeypatch,
        wrapper,
        returncode=0,
        skills={"broken-skill": {"missing": ["ghost.py"]}},
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "broken-skill" in out and "ghost.py" in out


def test_reports_a_failed_probe_instead_of_staying_silent(wrapper, monkeypatch, capsys):
    """A watchdog must not fail silently: non-zero exit and a real message."""
    rc = _run(monkeypatch, wrapper, returncode=2, skills={})

    out = capsys.readouterr().out
    assert rc == 2
    assert "failed" in out.lower()
