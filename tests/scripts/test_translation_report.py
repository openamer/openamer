"""Contract: the progress report says what it measured, and is safe to schedule.

Three things would make this reporter worse than none: misclassifying a locale
(a "complete" locale that is not, or vice versa), crashing on the emoji when
cron pipes stdout as cp1252, and announcing completion over and over.

The HTML snapshot is the only channel that actually reaches the user on this
install (no gateway channel, desktop toasts fail), so it must be written even
when nobody reads stdout.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def report(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "translation_report", REPO / "scripts" / "translation_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cache = tmp_path / "tmp"
    logs = tmp_path / "logs"
    cache.mkdir()
    logs.mkdir()
    monkeypatch.setattr(module, "CACHE", cache)
    monkeypatch.setattr(module, "LOGDIR", logs)
    monkeypatch.setattr(module, "STATE", logs / "state.json")
    monkeypatch.setattr(module, "DONE_MARKER", logs / "done")
    monkeypatch.setattr(module, "PIDFILE", logs / "swarm.pid.json")
    monkeypatch.setattr(module, "alive", lambda: 0)
    monkeypatch.setattr(module, "notify", lambda message: None)
    return module


def write_locale(cache: Path, code: str, filled: int) -> None:
    payload = {f"k{i}": f"v{i}" for i in range(filled)}
    (cache / f"desktop_{code}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_scan_classifies_complete_partial_and_empty(report):
    write_locale(report.CACHE, "aa", report.FULL)      # complete
    write_locale(report.CACHE, "ab", 10)               # partial
    write_locale(report.CACHE, "ac", 0)                # empty
    total, full, partial, empty = report.scan()
    assert (full, partial, empty) == (1, 1, 1)
    assert total == report.FULL + 10


def test_unreadable_cache_counts_as_empty(report):
    (report.CACHE / "desktop_zz.json").write_text("{ broken", encoding="utf-8")
    _, _, _, empty = report.scan()
    assert empty == 1


def test_german_thousands_separator(report):
    assert report.de(246494) == "246.494"
    assert report.de(999) == "999"


def test_html_snapshot_is_written_and_self_refreshing(report, capsys):
    write_locale(report.CACHE, "aa", 10)
    assert report.main() == 0
    html = (report.LOGDIR / "translation-report.html").read_text(encoding="utf-8")
    assert 'http-equiv="refresh"' in html, "the pane must reload without a manual refresh"
    assert "10" in html
    assert "Strings im Cache" in html
    assert "📊" in capsys.readouterr().out, "stdout keeps the text report for cron logs"


def test_second_run_reports_the_delta(report, capsys):
    write_locale(report.CACHE, "aa", 10)
    report.main()
    capsys.readouterr()
    write_locale(report.CACHE, "aa", 40)
    report.main()
    out = capsys.readouterr().out
    assert "+30" in out, "delta against the previous snapshot must be reported"


def test_completion_is_announced_once(report, capsys, monkeypatch):
    monkeypatch.setattr(report, "TARGET", 0)
    assert report.main() == 0
    assert "Alle Sprachen abgedeckt" in capsys.readouterr().out
    assert report.main() == 0
    assert capsys.readouterr().out == "", "a finished job must not repeat itself"
