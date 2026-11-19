"""A killed test run must leave a trace.

Background: the nightly suite takes over an hour here. On 2026-11-19 the cron
run started at 04:00, reached 37% of ~47k tests, and the process was killed by
a stack restart. Nothing was written at the end — the state file still described
the *previous* night, the log had no 2026-11-19 line at all, and the cron row
reported nothing. A watchdog that disappears without a trace cannot be trusted
to say "green".

`_announce_run` writes an in-flight marker before the suite starts; the next
tick turns a leftover marker into an explicit "previous run never finished"
report instead of silently starting over.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "test-suite-watchdog.py"


def _load():
    spec = importlib.util.spec_from_file_location("test_suite_watchdog", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["test_suite_watchdog"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def wd():
    return _load()


def test_announce_writes_an_in_flight_marker(wd, tmp_path):
    state = tmp_path / "state.json"
    wd._announce_run(state, "tests/")
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["status"] == "running"
    assert data["target"] == "tests/"
    assert data["pid"]
    assert abs(data["started_epoch"] - int(time.time())) < 5


def test_previous_was_killed_detects_a_stale_run(wd, tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"status": "running", "target": "tests/",
                                 "started_epoch": 1, "pid": 42}), encoding="utf-8")
    stale = wd._previous_was_killed(state)
    assert stale["pid"] == 42
    assert stale["target"] == "tests/"


@pytest.mark.parametrize("status", ["green", "red", "timeout", "incomplete"])
def test_previous_was_killed_ignores_finished_runs(wd, tmp_path, status):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"status": status}), encoding="utf-8")
    assert wd._previous_was_killed(state) == {}


def test_previous_was_killed_tolerates_no_state(wd, tmp_path):
    assert wd._previous_was_killed(tmp_path / "missing.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert wd._previous_was_killed(bad) == {}


def test_kill_handler_records_the_signal(wd, tmp_path, monkeypatch):
    """The handler must write state + log, then exit — not just die."""
    state = tmp_path / "state.json"
    log = tmp_path / "log.txt"
    wd._install_kill_handlers(state, log, "tests/", time.time() - 30)

    sig = getattr(__import__("signal"), "SIGTERM")
    with pytest.raises(SystemExit):
        wd.signal.getsignal(sig)(sig, None)

    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["status"] == "killed"
    assert data["signal"] == int(sig)
    assert data["elapsed_s"] >= 30
    assert "KILLED by signal" in log.read_text(encoding="utf-8")
