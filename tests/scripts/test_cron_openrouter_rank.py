"""Regression test for scripts/cron-openrouter-rank.py.

Live 2026-09-14: the scheduler resolves a job's ``script`` field as a bare
filename and does NOT split arguments, so ``openrouter_rank_watch.py
--alert-only`` failed every daily run with
    Script not found: ...\\scripts\\openrouter_rank_watch.py --alert-only
The wrapper pins ``--alert-only`` without touching the watchdog's own CLI.

Hermetic: runpy is monkeypatched, so the target script (and its network calls)
never actually execute.
"""
from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / "scripts" / "cron-openrouter-rank.py"


def test_wrapper_pins_alert_only(monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(
        runpy, "run_path",
        lambda path, run_name=None: seen.update(argv=list(sys.argv), path=str(path)))

    spec = importlib.util.spec_from_file_location("cron_openrouter_rank", WRAPPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert seen["argv"][1:] == ["--alert-only"]
    assert seen["path"].endswith("openrouter_rank_watch.py")