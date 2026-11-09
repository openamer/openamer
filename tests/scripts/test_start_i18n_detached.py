"""Tests for the detached translation launcher.

The launcher exists because session-scoped workers died with the agent. Its own
failure mode would be silent: workers that never started, or a PID file that
claims life for a dead process. Both are testable without spawning anything.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / "scripts" / "start_i18n_detached.py"


def _load():
    spec = importlib.util.spec_from_file_location("i18n_launcher", LAUNCHER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def launcher():
    return _load()


def test_pid_alive_true_for_self(launcher):
    assert launcher._pid_alive(os.getpid()) is True


def test_pid_alive_false_for_dead_pid(launcher):
    # Spawn and reap a child so the pid is definitely gone.
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    assert launcher._pid_alive(proc.pid) is False


def test_status_without_pidfile_reports_none(launcher, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(launcher, "PIDFILE", tmp_path / "missing.json")
    assert launcher.status() == 1
    assert "no detached translation recorded" in capsys.readouterr().out


def test_status_counts_dead_workers(launcher, monkeypatch, tmp_path, capsys):
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    pidfile = tmp_path / "i18n.pid.json"
    pidfile.write_text(json.dumps({
        "started": "2026-11-09T21:46:07",
        "workers": [{"pid": proc.pid, "locales": ["aa", "ab"], "log": str(tmp_path / "w.log")}],
    }), encoding="utf-8")
    monkeypatch.setattr(launcher, "PIDFILE", pidfile)

    assert launcher.status() == 1  # no worker alive -> non-zero
    out = capsys.readouterr().out
    assert "dead" in out
    assert "0/1 workers alive" in out


def test_status_counts_live_workers(launcher, monkeypatch, tmp_path, capsys):
    pidfile = tmp_path / "i18n.pid.json"
    pidfile.write_text(json.dumps({
        "started": "2026-11-09T21:46:07",
        "workers": [{"pid": os.getpid(), "locales": ["aa"], "log": str(tmp_path / "w.log")}],
    }), encoding="utf-8")
    monkeypatch.setattr(launcher, "PIDFILE", pidfile)

    assert launcher.status() == 0
    assert "1/1 workers alive" in capsys.readouterr().out


def test_round_robin_never_drops_or_duplicates(launcher):
    """The queue split must cover every pending locale exactly once."""
    todo = [f"x{i}" for i in range(23)]
    queues = [[] for _ in range(4)]
    for i, code in enumerate(todo):
        queues[i % 4].append(code)
    flat = [c for q in queues for c in q]
    assert sorted(flat) == sorted(todo)
    assert len(flat) == len(todo)
    assert max(len(q) for q in queues) - min(len(q) for q in queues) <= 1
