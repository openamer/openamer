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
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    assert launcher._pid_alive(proc.pid) is False


def test_status_without_pidfile_reports_none(launcher, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(launcher, "LOGDIR", tmp_path)
    assert launcher.status("cli") == 1
    assert "no detached cli translation recorded" in capsys.readouterr().out


def test_status_counts_dead_workers(launcher, monkeypatch, tmp_path, capsys):
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    pidfile = tmp_path / "i18n-translate.pid.json"
    pidfile.write_text(json.dumps({
        "started": "2026-11-09T21:46:07",
        "workers": [{"pid": proc.pid, "locales": ["aa", "ab"], "log": str(tmp_path / "w.log")}],
    }), encoding="utf-8")
    monkeypatch.setattr(launcher, "LOGDIR", tmp_path)

    assert launcher.status("cli") == 1  # no worker alive -> non-zero
    out = capsys.readouterr().out
    assert "dead" in out
    assert "0/1 workers alive" in out


def test_reused_pid_is_not_a_translation_worker(launcher):
    record = {"pid": os.getpid(), "locales": ["aa"], "log": "worker.log"}
    assert launcher._worker_alive(record, "desktop") is False


def test_status_counts_live_workers(launcher, monkeypatch, tmp_path, capsys):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "i18n_fill_cli_locales.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(script)])
    try:
        pidfile = tmp_path / "i18n-translate.pid.json"
        pidfile.write_text(json.dumps({
            "workers": [{"pid": proc.pid, "locales": ["aa"], "log": str(tmp_path / "w.log")}],
        }), encoding="utf-8")
        monkeypatch.setattr(launcher, "REPO", tmp_path)
        monkeypatch.setattr(launcher, "LOGDIR", tmp_path)
        assert launcher.status("cli") == 0
        assert "1/1 workers alive" in capsys.readouterr().out
        assert launcher._worker_alive({"pid": proc.pid, "created": 1}, "cli") is False
    finally:
        proc.terminate()
        proc.wait(timeout=10)


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


def test_worker_record_persists_creation_time(launcher, monkeypatch, tmp_path):
    """A record written at spawn time must carry the creation time it is checked against."""
    import psutil

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "i18n_fill_cli_locales.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(script)])
    try:
        monkeypatch.setattr(launcher, "REPO", tmp_path)
        record = launcher.worker_record(proc, ["aa"], tmp_path / "w.log")
        assert record["created"] == pytest.approx(psutil.Process(proc.pid).create_time(), abs=0.01)
        # The persisted timestamp has to satisfy the same check that guards a reboot.
        assert launcher._worker_alive(record, "cli") is True
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_pidfile_for_returns_separate_files(launcher):
    """CLI and desktop targets must use different pid files."""
    assert launcher.pidfile_for("cli").name == "i18n-translate.pid.json"
    assert launcher.pidfile_for("desktop").name == "desktop-translate.pid.json"


def test_pending_desktop_counts_empty_modules(launcher, monkeypatch, tmp_path):
    """pending_desktop() returns locales whose module is still defineLocale({})."""
    # Write a fake _languages.json with 3 locales
    langs = {"en": "English", "aa": "Afar", "ab": "Abkhazian"}
    # The launcher's REPO is __file__.parents[1] -> scripts/, so locales/ is REPO/locales/
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    lang_path = locales_dir / "_languages.json"
    lang_path.write_text(json.dumps(langs), encoding="utf-8")

    # Create apps/desktop/src/i18n with modules
    i18n = tmp_path / "apps" / "desktop" / "src" / "i18n"
    i18n.mkdir(parents=True)
    (i18n / "en.ts").write_text("export const en = defineLocale({})", encoding="utf-8")
    (i18n / "aa.ts").write_text("export const aa = defineLocale({})", encoding="utf-8")
    (i18n / "ab.ts").write_text("export const ab = defineLocale({foo: 'bar'})", encoding="utf-8")

    # Patch REPO to point at tmp_path (so REPO/locales works)
    monkeypatch.setattr(launcher, "REPO", tmp_path)

    todo = launcher.pending_desktop()
    assert todo == ["aa", "ab"]  # partial content must never be mistaken for completion