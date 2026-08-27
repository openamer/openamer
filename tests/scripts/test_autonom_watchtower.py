"""Tests for scripts/autonom_watchtower.py (24/7 zero-cost guardian).

Offline/hermetic: no real Chrome, tasklist or state writes. Covers the decision
logic and the network/process helpers by monkeypatching the boundary.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import autonom_watchtower as W  # noqa: E402


def test_pid_alive_handles_missing_file(tmp_path):
    assert W._pid_alive(tmp_path / "nope.pid") is False


def test_pid_alive_matches_matching_tasklist(monkeypatch, tmp_path):
    pidf = tmp_path / "x.pid"
    pidf.write_text("4242")
    monkeypatch.setattr(
        W.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(
            ["tasklist"], 0, stdout=b"  python.exe  4242  Console\r\n", stderr=b""))
    assert W._pid_alive(pidf) is True


def test_pid_alive_tolerates_non_utf8_tasklist(monkeypatch, tmp_path):
    # Raw invalid-UTF-8 byte must not raise (mirrors session_to_brain fix).
    pidf = tmp_path / "x.pid"
    pidf.write_text("7777")
    monkeypatch.setattr(
        W.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(
            ["tasklist"], 0, stdout=b"\x81no-match", stderr=b""))
    assert W._pid_alive(pidf) is False


def test_chrome_cdp_rejects_headless(monkeypatch):
    class _Fake:
        def read(self):
            return b'{"Browser": "HeadlessChrome/151"}'
    monkeypatch.setattr(W.urllib.request, "urlopen", lambda *a, **k: _Fake())
    assert W._chrome_cdp_alive() is False


def test_chrome_cdp_accepts_real(monkeypatch):
    class _Fake:
        def read(self):
            return b'{"Browser": "Chrome/151.0.7922"}'
    monkeypatch.setattr(W.urllib.request, "urlopen", lambda *a, **k: _Fake())
    assert W._chrome_cdp_alive() is True


def _healthy_main_fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(W, "STATE", tmp_path / "autonom-state.json")
    monkeypatch.setattr(W, "_pid_alive", lambda p: True)
    monkeypatch.setattr(W, "_chrome_cdp_alive", lambda: True)
    monkeypatch.setattr(W, "_config_standard_ok", lambda: True)
    monkeypatch.setattr(W, "REPO", tmp_path)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "a2a-worker.yml").write_text("on:")


def test_main_stays_quiet_when_healthy(monkeypatch, tmp_path, capsys):
    _healthy_main_fixture(monkeypatch, tmp_path)
    rc = W.main()
    assert rc == 0
    state = json.loads((tmp_path / "autonom-state.json").read_text())
    assert state["healthy"] is True and not state["problems"]
    assert capsys.readouterr().out == ""          # silent watchdog


def test_main_reports_and_recovers(monkeypatch, tmp_path):
    monkeypatch.setattr(W, "STATE", tmp_path / "autonom-state.json")
    monkeypatch.setattr(W, "_pid_alive", lambda p: False)
    monkeypatch.setattr(W, "_chrome_cdp_alive", lambda: False)
    monkeypatch.setattr(W, "_config_standard_ok", lambda: True)
    monkeypatch.setattr(W, "REPO", tmp_path)
    monkeypatch.setattr(W, "_start_session_to_brain", lambda: True)
    monkeypatch.setattr(W, "_start_chrome", lambda: True)
    rc = W.main()
    state = json.loads((tmp_path / "autonom-state.json").read_text())
    assert state["healthy"] is False
    assert any("down" in p for p in state["problems"])
    assert state["actions"]                       # recovery attempted