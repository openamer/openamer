"""Tests for scripts/demo_target.py — the demo window really comes up.

This is a GUI script, so the honest verification is an integration one: launch
it, wait for the window to exist on the real desktop, then shut it down. A unit
test of its Tk layout would assert nothing that matters; this asserts the thing
the demo depends on — that the window appears under the title the recorder looks
for.

Skips (not fails) when tkinter or a desktop session is unavailable, so the suite
stays honest on a headless box instead of pretending.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "scripts" / "demo_target.py"
RECT = REPO / "scripts" / "demo_window_rect.py"


def _load_rect():
    spec = importlib.util.spec_from_file_location("demo_window_rect", RECT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["demo_window_rect"] = mod
    spec.loader.exec_module(mod)
    return mod


def _no_display() -> bool:
    """True when a GUI cannot open at all.

    tkinter being importable is not enough: CI images ship tkinter and have no
    X display, so `demo_target.py` exited with rc=1 and this test failed with
    "demo window never appeared on the desktop" - a green import guarding an
    impossible expectation. On Linux a display means $DISPLAY or a Wayland
    socket; elsewhere assume it is available (macOS/Windows always have one).
    """
    if sys.platform.startswith("linux"):
        return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return False


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("tkinter") is None,
    reason="tkinter not available")
@pytest.mark.skipif(
    _no_display(),
    reason="no display server: a window can never appear here")
def test_demo_window_appears_and_shuts_down():
    rect_mod = _load_rect()
    proc = subprocess.Popen([sys.executable, str(TARGET)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        found = None
        for _ in range(20):
            time.sleep(0.5)
            if proc.poll() is not None:
                pytest.fail(f"demo_target exited early with rc={proc.returncode}")
            found = rect_mod.find_window()
            if found:
                break
        assert found is not None, "demo window never appeared on the desktop"
        x, y, w, h = found
        assert w > 0 and h > 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        assert proc.poll() is not None, "demo_target ignored terminate()"