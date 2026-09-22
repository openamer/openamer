"""Regression tests for scripts/test-suite-watchdog.py.

The watchdog exists so "the system works" stops being an assertion and becomes a
measurement that refreshes itself: it runs the canonical suite and stays SILENT
when green, speaking only when something is red. That inverted contract is the
whole point, and it is also what makes the job dangerous to get wrong — a
watchdog that fails loudly on success earns a mute, and a silent one that misses
a red run is worse than none.

Three properties are pinned here, all from real behaviour:

1. **Silence means success.** A green run must exit 0 with EMPTY stdout. This is
   the contract `no_agent` delivery depends on (empty stdout = nothing sent).
2. **Failure names the file.** A red run must exit 1 and say *which* file failed
   and how many tests in it. The first implementation split on the first "✗ " of
   the progress line and reported the running counter ("2]") instead of a
   filename — the glyph appears twice per line, as `✗ 45]` and `✗ tests\\p.py`.
3. **Recovery is announced exactly once.** Going red → green is worth one
   message; staying green is worth none. Otherwise a broken run is either
   forgotten or the user is spammed every night.

Hermetic: `main()`'s collaborators (the runner subprocess, state file, log) are
injected/monkeypatched — no 30-minute suite run inside the test process.
"""
from __future__ import annotations

import importlib.util
import json
import sys
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


@pytest.fixture(scope="module")
def wd():
    return _load()


# --- real runner output shapes ---------------------------------------------

# Copied verbatim from a live run; the first line is the failure that the
# original filename extraction got wrong.
LIVE_RED = r"""
[  1.9% |   855/~45517 | ✓858 | ✗ 45] ✗ tests\acp\test_session.py (25✓ 20✗, 253.7s)
[  4.7% |  2145/~45517 | ✓2253 | ✗  49] ✓ tests\agent\test_deepseek_anthropic_thinking.py (9✓, 27.1s)
[100.0% |  2145/~45517 | ✓2253 | ✗  49] ✗ tests\baz\test_qux.py (6✓ 2✗, 4.0s)

=== Summary: 3 files, 2253 tests passed, 49 failed (100% complete) in 300.0s (32 workers) ==="""

LIVE_GREEN = """
[100.0% |  2145/~45517 | ✓2145 | ✗ 0] ✓ tests\agent\test_deepseek_anthropic_thinking.py (9✓, 27.1s)

=== Summary: 1 files, 13 tests passed, 0 failed (100% complete) in 4.0s (32 workers) ==="""


# --- property 1: the summary parser -----------------------------------------

def test_summary_parses_the_runner_line(wd):
    assert wd.SUMMARY_RE.search(LIVE_GREEN).groups() == ("1", "13", "0")
    assert wd.SUMMARY_RE.search(LIVE_RED).groups() == ("3", "2253", "49")


def test_summary_absent_is_not_a_match(wd):
    """A crashed run has no summary — main() must notice, not assume green."""
    assert wd.SUMMARY_RE.search("No test files to run\n") is None


# --- property 2: failure attribution ---------------------------------------

def test_failures_name_files_and_counts(wd):
    """The bug this pins: splitting on the first '✗ ' yields '2]', not a path."""
    failures = wd._summarize_failures(LIVE_RED)

    assert len(failures) == 2
    assert "tests\\acp\\test_session.py" in failures[0]
    assert "(20 failing)" in failures[0]  # worst first
    assert "tests\\baz\\test_qux.py" in failures[1]
    assert all("2]" not in f for f in failures)


def test_passing_files_are_never_reported(wd):
    failures = " ".join(wd._summarize_failures(LIVE_RED))

    assert "test_deepseek_anthropic_thinking" not in failures


def test_failures_fall_back_to_names_without_counts(wd):
    """A summary line without per-file counts still yields paths."""
    out = r"[100.0% | 9/9] ✗ tests\x\test_y.py" + "\n=== Summary: 1 files, 0 passed, 1 failed ==="

    assert wd._summarize_failures(out) == [r"tests\x\test_y.py"]


# --- property 3: the state-driven message contract --------------------------
# main() is exercised with its subprocess call replaced, so the exit code,
# stdout, and state transition are the real ones.

class _Proc:
    def __init__(self, stdout: str, returncode: int):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


def _run_main(wd, monkeypatch, tmp_path, stdout, *, prior=None):
    """Drive main() with a scripted runner output and a temp state file."""
    state = tmp_path / "state.json"
    log = tmp_path / "wd.log"
    if prior is not None:
        state.write_text(json.dumps(prior), encoding="utf-8")
    monkeypatch.setenv("TEST_WATCHDOG_STATE", str(state))
    monkeypatch.setenv("TEST_WATCHDOG_LOG", str(log))
    monkeypatch.setattr(wd.subprocess, "run", lambda *a, **k: _Proc(stdout, 0))
    return wd.main(), state, log


def test_green_with_no_history_is_silent(wd, monkeypatch, tmp_path, capsys):
    rc, state, log = _run_main(wd, monkeypatch, tmp_path, LIVE_GREEN)

    assert rc == 0
    assert capsys.readouterr().out == ""  # silence IS the success signal
    assert json.loads(state.read_text(encoding="utf-8"))["failed"] == 0
    assert "GREEN" in log.read_text(encoding="utf-8")


def test_green_after_green_stays_silent(wd, monkeypatch, tmp_path, capsys):
    rc, _state, _log = _run_main(wd, monkeypatch, tmp_path, LIVE_GREEN, prior={"failed": 0})

    assert rc == 0
    assert capsys.readouterr().out == ""


def test_red_alerts_and_exits_nonzero(wd, monkeypatch, tmp_path, capsys):
    rc, state, log = _run_main(wd, monkeypatch, tmp_path, LIVE_RED)

    out = capsys.readouterr().out
    assert rc == 1
    assert "49 failing test(s)" in out
    assert r"tests\acp\test_session.py" in out
    assert json.loads(state.read_text(encoding="utf-8"))["failed"] == 49
    assert "RED" in log.read_text(encoding="utf-8")


def test_recovery_announced_once_after_red(wd, monkeypatch, tmp_path, capsys):
    rc, _state, _log = _run_main(wd, monkeypatch, tmp_path, LIVE_GREEN, prior={"failed": 49})

    out = capsys.readouterr().out
    assert rc == 0
    assert "recovered" in out
    assert "49" in out  # names what it recovered from


def test_missing_summary_is_an_alert_not_a_pass(wd, monkeypatch, tmp_path, capsys):
    """The dangerous failure mode: a run that produced nothing must not read green."""
    rc, _state, log = _run_main(wd, monkeypatch, tmp_path, "No test files to run\n")

    out = capsys.readouterr().out
    assert rc == 1
    assert "could not read a summary" in out
    assert "NO SUMMARY" in log.read_text(encoding="utf-8")


# --- the cron contract ------------------------------------------------------

def test_default_target_is_the_whole_suite(wd):
    """The cron invokes the script with no argv; that must mean everything."""
    assert wd.DEFAULT_TARGET == "tests/"
    assert wd.TIMEOUT_S >= 1800  # a full run measured >30 min


def test_missing_runner_alerts_with_paths(wd, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(wd, "RUNNER", tmp_path / "nope.sh")

    assert wd.main() == 1
    assert "missing" in capsys.readouterr().out


# --- the interpreter it runs the suite under -------------------------------

def test_bash_is_not_the_windowsapps_wsl_shim(wd):
    """A bare `bash` on PATH is the WSL shim on Windows and cannot read a
    /c/... path, so the runner died with exit 127 every night:

        /bin/bash: /c/.../run_tests.sh: No such file or directory

    The file existed. The shim just cannot see it. `_posix_bash()` must pick a
    bash that can, and must never settle for WindowsApps.
    """
    if wd.os.name != "nt":
        assert wd.BASH == "bash"  # POSIX: plain bash reads POSIX paths
        return

    assert wd.BASH != "bash", "resolved to the bare name instead of a real binary"
    assert Path(wd.BASH).exists(), f"BASH does not exist: {wd.BASH}"
    assert "WindowsApps" not in wd.BASH, "that is the WSL shim — it cannot read /c/... paths"
    assert Path(wd.BASH).name.lower() == "bash.exe"


def test_posix_bash_skips_the_windowsapps_entry(wd, monkeypatch, tmp_path):
    """Simulate the broken PATH: the shim comes first and nothing else is real,
    so the only acceptable outcome is that the shim is never returned."""
    shim_dir = tmp_path / "WindowsApps"
    shim_dir.mkdir()
    shim = shim_dir / ("bash.exe" if wd.os.name == "nt" else "bash")
    shim.write_text("#!/bin/sh\n", encoding="utf-8")

    real_dir = tmp_path / "git" / "usr" / "bin"
    real_dir.mkdir(parents=True)
    real = real_dir / shim.name
    real.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setenv("PATH", str(shim_dir) + wd.os.pathsep + str(real_dir))
    # Neutralise the `git --exec-path` branch so this exercises the PATH walk.
    monkeypatch.setattr(
        wd.subprocess, "run",
        lambda *a, **k: type("R", (), {"returncode": 1, "stdout": ""})(),
    )

    assert wd._posix_bash() == str(real), "must skip WindowsApps and take the next real bash"
