"""Tests for the ASI heartbeat's organ wiring (heartbeat.py).

Three real organs — homeostasis, calibration, metacognition — existed as
runnable scripts but were ORPHANED: no cron ran them, and no heartbeat
subsystem listed them, so they were effectively dead body parts. This pins
that they (and the conscience) are wired into the `meta` subsystem, and that
the subsystem's timeout was raised so it does not get cut off mid-organ.
"""
from __future__ import annotations

import sys
from pathlib import Path

AGENT = Path.home() / "AppData" / "Local" / "openamer-laptop" / "openamer-agent"
sys.path.insert(0, str(AGENT))

from tools.asi.heartbeat import Heartbeat  # noqa: E402


def _meta():
    return Heartbeat().subsystems["meta"]


def test_orphaned_organs_are_wired_into_meta():
    scripts = _meta().scripts
    for organ in ("homeostasis.py", "calibration.py", "metacognition.py",
                  "training/conscience.py"):
        assert organ in scripts, f"{organ} is orphaned (not in the meta subsystem)"


def test_meta_timeout_covers_its_new_organs():
    sub = _meta()
    assert sub.timeout is not None and sub.timeout >= 180, \
        "meta needs a per-subsystem timeout; 15 scripts exceed the 60s default"


def test_conscience_runs_with_no_args():
    """A no-arg call must do the meaningful thing (self-audit), not print help."""
    import subprocess
    conscience = (Path.home() / "AppData" / "Local" / "openamer-laptop"
                  / "scripts" / "training" / "conscience.py")
    r = subprocess.run([sys.executable, str(conscience)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    # silent while clean; when it speaks, it is valid JSON about blocked goals
    if r.stdout.strip():
        import json
        json.loads(r.stdout)
