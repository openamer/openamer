"""The test suite must not starve the machine it runs on.

Measured 2026-11-27 on the 8-core laptop: a full nightly run held the CPU at
96-100% for ~65 minutes. Everything else on the box -- desktop, gateway,
learning daemon -- was starved for that whole window, and the growth loop stayed
paused the entire time. The fix is the scheduling class: the suite keeps every
cycle nobody else wants but loses every contest against interactive work.

These tests pin the *measured* effect, not the intent. The first attempt at this
returned "below-normal" while SetPriorityClass had actually failed with err=0
(ctypes truncated the pseudo-handle to 32 bits), so a claim-only test would have
gone green over a no-op. Every assertion here reads the real priority class back
out of the OS, from a throwaway subprocess so the pytest process itself is never
re-prioritised.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_tests_parallel.py"
WATCHDOG = REPO / "scripts" / "test-suite-watchdog.py"

# Reads the priority class before and after calling the helper, in this process.
# Windows: GetPriorityClass returns 0x20 (NORMAL) / 0x4000 (BELOW_NORMAL).
# POSIX: os.nice(0) returns the current nice value (higher = lower priority).
_PROBE = textwrap.dedent(
    """
    import importlib.util, json, os, sys

    path, module_name = sys.argv[1], sys.argv[2]
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)


    def read_priority():
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32")
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            kernel32.GetPriorityClass.argtypes = [wintypes.HANDLE]
            kernel32.GetPriorityClass.restype = wintypes.DWORD
            return kernel32.GetPriorityClass(kernel32.GetCurrentProcess())
        return os.nice(0)


    def reset_to_normal():
        # This probe is spawned by a runner that has already dropped itself to
        # BELOW_NORMAL, and Windows children inherit the class — so the baseline
        # has to be re-established or "before" reads 0x4000 and the measurement
        # proves nothing. POSIX nice can only be raised, so there is no reset
        # there; the assertion compares to the probed baseline instead.
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32")
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel32.SetPriorityClass.restype = wintypes.BOOL
            kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00000020)


    reset_to_normal()
    before = read_priority()
    note = mod._lower_own_priority()
    after = read_priority()
    print(json.dumps({"before": before, "after": after, "note": note}))
    """
)


def _probe(module_path: Path, env_extra: dict[str, str] | None = None) -> dict:
    env = dict(os.environ)
    env.pop("OPENAMER_TEST_LOW_PRIORITY", None)
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE, str(module_path), "prio_probe"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, f"probe failed: {proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _assert_lowered(sample: dict) -> None:
    """The OS must report a genuinely lower class after the call."""
    if os.name == "nt":
        assert sample["before"] != sample["after"], (
            f"priority class unchanged ({sample['before']}) — the note "
            f"{sample['note']!r} is a claim, not an effect"
        )
        assert sample["after"] == 0x00004000, f"expected BELOW_NORMAL, got {hex(sample['after'])}"
        assert "below-normal" in sample["note"]
    else:
        # POSIX nice is bounded to [-20, 19]: on a CI runner the parent runner
        # has already nicened itself, so the probe starts at e.g. 10 and
        # nice(10) lands on the 19 floor — measured 2026-11-27 as "10 -> 19".
        # Assert the clamped value, and skip only when there is no headroom left
        # to observe a change at all.
        if sample["before"] >= 19:
            import pytest

            pytest.skip(f"nice already at the floor ({sample['before']}); change unobservable")
        assert sample["after"] == min(sample["before"] + 10, 19), (
            f"expected nice +10 (clamped at 19), got {sample['before']} -> {sample['after']}"
        )
        assert "nice+10" in sample["note"]


def test_runner_lowers_its_own_priority():
    """scripts/run_tests_parallel.py drops below normal, measurably."""
    _assert_lowered(_probe(RUNNER))


def test_watchdog_lowers_its_own_priority():
    """The nightly watchdog does the same, so bash and the runner inherit it."""
    _assert_lowered(_probe(WATCHDOG))


def test_opt_out_leaves_priority_untouched():
    """OPENAMER_TEST_LOW_PRIORITY=0 keeps the class as it was (dedicated CI)."""
    for module_path in (RUNNER, WATCHDOG):
        sample = _probe(module_path, {"OPENAMER_TEST_LOW_PRIORITY": "0"})
        assert sample["before"] == sample["after"], sample
        assert sample["note"].startswith("normal ("), sample["note"]


def test_helper_never_raises_on_broken_platform(monkeypatch):
    """A scheduling nicety must not fail a test run."""
    spec = importlib.util.spec_from_file_location("rtp_no_raise", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if os.name == "nt":
        import ctypes

        def boom(*_a, **_k):
            raise OSError("simulated kernel32 failure")

        monkeypatch.setattr(ctypes, "WinDLL", boom)
    else:
        def boom(_n):
            raise OSError("simulated nice failure")

        monkeypatch.setattr(os, "nice", boom)

    note = mod._lower_own_priority()
    assert note.startswith("normal ("), note
    assert "could not lower priority" in note
