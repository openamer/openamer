"""Contract: the watchdog feeds the swarm and stays quiet otherwise.

A worker wave owns one locale each and exits cleanly, so the fleet idles between
waves unless something starts the next one. Two properties matter and both are
easy to get wrong:

* it must count HALF-translated locales too — `--only-empty` skips them, so a
  watchdog that only counted empty caches would strand every partial locale the
  moment the last empty one fills;
* it must print nothing when there is nothing to do, because it runs every ten
  minutes and a chatty no-op job is worse than no job.
"""
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def watchdog(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "cron_swarm", REPO / "scripts" / "cron_translation_swarm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "CACHE", tmp_path)
    monkeypatch.setattr(module, "REPO", REPO)
    return module


def write_cache(directory: Path, code: str, filled: int) -> None:
    payload = {f"k{i}": f"v{i}" for i in range(filled)}
    (directory / f"desktop_{code}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_half_translated_locales_are_open(watchdog, tmp_path):
    write_cache(tmp_path, "aa", 0)        # empty
    write_cache(tmp_path, "ab", 10)       # barely started
    write_cache(tmp_path, "ac", 5000)     # done
    codes = watchdog.open_locale_codes()
    assert "aa" in codes
    assert "ab" in codes, "a partial locale must not be stranded"
    assert "ac" not in codes


def test_unreadable_cache_counts_as_open(watchdog, tmp_path):
    (tmp_path / "desktop_zz.json").write_text("{ broken", encoding="utf-8")
    assert "zz" in watchdog.open_locale_codes()


def test_silent_when_a_wave_is_running(watchdog, monkeypatch, capsys):
    monkeypatch.setattr(watchdog, "alive", lambda: 3)
    assert watchdog.main() == 0
    assert capsys.readouterr().out == ""


def test_silent_when_everything_is_translated(watchdog, monkeypatch, capsys):
    monkeypatch.setattr(watchdog, "alive", lambda: 0)
    monkeypatch.setattr(watchdog, "open_locale_codes", lambda: [])
    assert watchdog.main() == 0
    assert capsys.readouterr().out == ""


def test_launches_with_explicit_locale_codes(watchdog, monkeypatch, capsys):
    seen: dict = {}

    class FakeProc:
        returncode = 0
        stdout = "12 swarm workers for 2 locales across 3 backends\n"

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(watchdog, "alive", lambda: 0)
    monkeypatch.setattr(watchdog, "open_locale_codes", lambda: ["aa", "ab"])
    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)
    assert watchdog.main() == 0
    assert "--locales" in seen["cmd"]
    assert seen["cmd"][-2:] == ["aa", "ab"], "partial locales must be named explicitly"
    assert "2 open locales" in capsys.readouterr().out


def test_stalled_wave_is_killed_and_replaced(watchdog, monkeypatch):
    """One hung worker must not freeze the fleet.

    Observed in production: 1 worker alive, cache frozen for ten minutes, 194k
    strings open, and the watchdog silent because a PID was alive.
    """
    killed: list[bool] = []

    class FakeProc:
        returncode = 0
        stdout = "9 swarm workers for 1 locales across 3 backends\n"

    monkeypatch.setattr(watchdog, "alive", lambda: 1)
    monkeypatch.setattr(watchdog, "cache_total", lambda: 500)
    monkeypatch.setattr(watchdog, "open_locale_codes", lambda: ["aa"])
    monkeypatch.setattr(watchdog, "read_progress", lambda: (500, time.time() - 700))
    monkeypatch.setattr(watchdog, "kill_wave", lambda: killed.append(True) or 1)
    monkeypatch.setattr(watchdog.subprocess, "run", lambda cmd, **kw: FakeProc())
    assert watchdog.main() == 0
    assert killed == [True], "a stalled wave must be terminated"


def test_growing_cache_keeps_the_wave(watchdog, monkeypatch):
    """Progress is the signal: a slow wave that is still filling must survive."""
    killed: list[bool] = []
    monkeypatch.setattr(watchdog, "alive", lambda: 2)
    monkeypatch.setattr(watchdog, "cache_total", lambda: 900)
    monkeypatch.setattr(watchdog, "read_progress", lambda: (500, time.time() - 700))
    monkeypatch.setattr(watchdog, "kill_wave", lambda: killed.append(True) or 1)
    assert watchdog.main() == 0
    assert killed == [], "a wave that still adds strings must not be killed"
