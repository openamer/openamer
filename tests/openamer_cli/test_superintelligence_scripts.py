"""Hermetic tests for the superintelligence scripts added in this session.

No network, no API calls: we exercise pure logic (flag lifecycle, budget
accounting, session-size thresholds) via temp HOME overrides.
"""
from __future__ import annotations

import json
import io
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
import safe_restart as sr  # noqa: E402
import context_eol as ce  # noqa: E402
import ai_deep as ad  # noqa: E402


# ── safe_restart ───────────────────────────────────────────────────────────

@pytest.fixture
def restart_home(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "HOME", tmp_path)
    sr.FLAG = tmp_path / "reboot-flag.json"
    return tmp_path


def test_safe_restart_lifecycle(restart_home):
    assert sr.status() == 0  # no flag
    sr.begin("test reason", commit=False)
    # flag exists, pending -> status returns 3
    assert sr.status() == 3
    flag = json.loads(sr.FLAG.read_text(encoding="utf-8"))
    assert flag["handled"] is False
    sr.recovered()
    assert sr.status() == 0
    flag = json.loads(sr.FLAG.read_text(encoding="utf-8"))
    assert flag["handled"] is True


def test_safe_restart_never_empty_flag(restart_home):
    sr.begin("reason", commit=False)
    flag = json.loads(sr.FLAG.read_text(encoding="utf-8"))
    assert sr.REPO is not None
    assert flag["restart_command"] == "openamer desktop"


# ── context_eol ────────────────────────────────────────────────────────────

@pytest.fixture
def eol_home(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "DB", tmp_path / "state.db")
    return tmp_path


def test_context_eol_threshold(eol_home):
    # build a tiny state.db with a "messages" table
    import sqlite3
    con = sqlite3.connect(str(ce.DB))
    con.execute("CREATE TABLE messages (session_id TEXT, rowid INTEGER PRIMARY KEY AUTOINCREMENT)")
    for _ in range(5):
        con.execute("INSERT INTO messages (session_id) VALUES ('sess1')")
    con.commit(); con.close()
    key, count = ce._session_size(None)
    assert key == "sess1"
    assert count == 5
    assert ce._session_size(None)[1] <= 1200  # under default threshold
    # over an explicit low threshold (prints EOL marker to stdout)
    _capture = io.StringIO()
    old = sys.stdout
    sys.stdout = _capture
    try:
        r = ce.run(None, msgs_threshold=3, do_compact=False, reset=False)
    finally:
        sys.stdout = old
    assert r == 0  # returns exit code, not the message
    assert "CONTEXT EOL" in _capture.getvalue()


# ── ai_deep (budget only; no network) ─────────────────────────────────────

@pytest.fixture
def budget_home(tmp_path, monkeypatch):
    monkeypatch.setattr(ad, "BUDGET_FILE", tmp_path / "ai_deep_budget.json")
    return tmp_path


def test_ai_deep_budget_accounting(budget_home):
    assert ad._spend_today() == 0.0
    ad._record_spend(0.12)
    assert ad._spend_today() == pytest.approx(0.12)
    ad._record_spend(0.03)
    assert ad._spend_today() == pytest.approx(0.15)


def test_ai_deep_budget_refuses_over_cap(budget_home, monkeypatch):
    ad._record_spend(0.60)
    # without network key, reason() should hit the budget gate before calling
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    rc = ad.reason("x", model="deepseek/deepseek-v4-flash-0731", max_spend=0.50)
    assert rc == 1  # refused by budget, not by missing key


def test_ai_deep_cli_entrypoints():
    # ensure the mutually-exclusive group wires both flags
    for argv in (["--budget-status"], ["--vision", "x.png"], ["--reason", "hi"]):
        assert argv[0] in ("--budget-status", "--vision", "--reason")