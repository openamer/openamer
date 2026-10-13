#!/usr/bin/env python3
"""Regression guard: auto_retrain must not report RETRAIN_OK when the finetune
child aborted without saving an adapter.

Live bug (13.10): the nightly log read

    [finetune] ABORT: only 4.8 GB free RAM (need >= 6.0) ...
    HOT_SWAPPED: OK: swap queued (#11)
    RETRAIN_OK adapter updated        <- exit 0, but nothing was trained

``finetune_cpu.py`` aborts on its own RAM guard with ``sys.exit(0)`` and saves
no adapter on that path. auto_retrain only propagated nonzero exit codes, so a
no-op run burned the 24h ``.last_retrain`` marker, hot-swapped the STALE
adapter and printed the success verdict — which also silenced the cron
watchdog, since it only warns on SKIP/ABORT. The served adapter kept its old
mtime through the whole thing.

Hermetic: no training, no venv, no Windows required.
"""
import sys
from pathlib import Path

TRAIN_DIR = Path(__file__).resolve().parents[2] / "scripts" / "training"
sys.path.insert(0, str(TRAIN_DIR))
import auto_retrain as ar  # noqa: E402


def test_finetune_abort_must_not_report_success():
    """The adapter-saved side effect is required, and the guard must run before
    the marker write and the success print (ordering contract, not a snapshot)."""
    src = Path(ar.__file__).read_text(encoding="utf-8")
    assert '"ADAPTER_SAVED" not in out' in src, (
        "auto_retrain trusts the finetune exit code again — a RAM abort exits 0 "
        "without saving an adapter and would be reported as RETRAIN_OK"
    )
    guard = src.index('"ADAPTER_SAVED" not in out')
    marker_write = src.index("MARKER.write_text")
    ok_print = src.index('print("RETRAIN_OK')
    assert guard < marker_write < ok_print, (
        "the ADAPTER_SAVED guard must run BEFORE the marker write and the "
        "RETRAIN_OK print, otherwise a no-op run still burns the 24h window"
    )
    assert "sys.exit(1)" in src[guard:marker_write], (
        "the no-adapter path must exit nonzero so the cron watchdog reports it"
    )
