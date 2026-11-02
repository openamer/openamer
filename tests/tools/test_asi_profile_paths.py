"""Regression: profile-correct paths and environment for supervised work.

Three defects, each measured:

1. ``tools/asi/cognition.py`` lost its ``import os`` while still calling
   ``os.replace`` -- every state save raised ``NameError``.
2. ``Cognition`` and ``Heartbeat`` froze the home at IMPORT time, so a
   context override after import put the state file in one profile while the
   world-model store landed in another.
3. The supervisor started children without an explicit environment, so a
   service inherited the supervisor's process home instead of the profile the
   supervisor serves.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.asi._training import load_training_module

ROOT = Path(__file__).resolve().parents[2]


def test_cognition_state_save_works(tmp_path, monkeypatch):
    """The state save must not raise NameError."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    from tools.asi.cognition import Cognition

    cognition = Cognition()
    cognition._save_state({"probe": True})
    assert json.loads(cognition.state_file.read_text(encoding="utf-8"))["probe"] is True


def test_cognition_state_file_follows_the_active_profile(tmp_path, monkeypatch):
    """The state file belongs to the profile that is active at use time."""
    from openamer_constants import (
        reset_openamer_home_override,
        set_openamer_home_override,
    )

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(first))

    from tools.asi import cognition

    token = set_openamer_home_override(str(second))
    try:
        instance = cognition.Cognition()
        assert instance.home == second
        assert instance.state_file.parent == second / "memory"
        # The training loader resolves the SAME profile, so state and store
        # cannot end up in different profiles.
        store = load_training_module("world_model")
        assert Path(store.WM).parent == second / "memory"
    finally:
        reset_openamer_home_override(token)


def test_scoped_getenv_does_not_leak_the_process_home(tmp_path, monkeypatch):
    """os.getenv inside a loaded script must see the loading profile."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    training = tmp_path / "scripts" / "training"
    training.mkdir(parents=True)
    (training / "probe_env.py").write_text(
        "import os\n"
        "SEEN = os.getenv('OPENAMER_HOME')\n"
        "ENV_SEEN = os.environ.get('OPENAMER_HOME')\n"
    )
    mod = load_training_module("probe_env")
    assert mod.SEEN == str(tmp_path)
    assert mod.ENV_SEEN == str(tmp_path)
    # The process environment itself is untouched.
    assert os.environ["OPENAMER_HOME"] == str(tmp_path)


def test_supervised_child_sees_the_supervised_profile(tmp_path, monkeypatch):
    """A started service must inherit the profile the supervisor serves."""
    from openamer_cli.supervisor import Supervisor

    served = tmp_path / "served"
    served.mkdir()
    marker = tmp_path / "child-home.txt"

    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path / "process-home"))
    supervisor = Supervisor(home=served)
    supervisor.init()
    service = {
        "name": "fixture",
        "observe_only": False,
        "start": {
            "argv": [
                sys.executable,
                "-c",
                (
                    "import os, pathlib, sys;"
                    f"pathlib.Path(sys.argv[1]).write_text("
                    "os.environ.get('OPENAMER_HOME', ''), encoding='utf-8')"
                ),
                str(marker),
            ]
        },
        "probe": {"kind": "tcp", "host": "127.0.0.1", "port": 1, "timeout_s": 0.1},
        "ready_timeout_s": 3,
        "restart_budget_per_hour": 2,
    }
    supervisor.registry.write_text(
        json.dumps({"version": 1, "services": [service]}), encoding="utf-8"
    )
    supervisor.execute(once=True)

    assert marker.exists(), "the child never ran"
    assert marker.read_text(encoding="utf-8").strip() == str(served)
