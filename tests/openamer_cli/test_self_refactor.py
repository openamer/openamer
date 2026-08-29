"""Hermetic tests for scripts/self_refactor.py safety mechanics.

No network. We exercise the AST scan and the safety gates (refusing modules
without a passing test target) against temp files.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import self_refactor as sr  # noqa: E402


def test_scan_detects_duplicate_import(tmp_path):
    m = tmp_path / "m.py"
    m.write_text("import os\nimport os\nimport json\n", encoding="utf-8")
    opps = sr._analyze(m)
    assert any("duplicate-import" in o and "os" in o for o in opps)


def test_scan_detects_large_function(tmp_path):
    body = "\n".join(f"    x{i}=1" for i in range(200))
    m = tmp_path / "big.py"
    m.write_text(f"def huge():\n{body}\n", encoding="utf-8")
    opps = sr._analyze(m)
    assert any("large-func" in o for o in opps)


def test_apply_safe_collapses_blank_lines_and_trailing_ws(tmp_path):
    m = tmp_path / "c.py"
    m.write_text("a = 1  \n\n\n\nb = 2\n", encoding="utf-8")
    n = sr._apply_safe(m, drop_comments=False)
    assert n == 1
    out = m.read_text(encoding="utf-8")
    assert "  \n" not in out           # no trailing whitespace
    assert "\n\n\n" not in out         # no >1 blank line runs


def test_apply_safe_noop_when_clean(tmp_path):
    m = tmp_path / "clean.py"
    m.write_text("a = 1\nb = 2\n", encoding="utf-8")
    assert sr._apply_safe(m, drop_comments=False) == 0


def test_refactor_refuses_without_test(tmp_path, monkeypatch):
    m = tmp_path / "untested.py"
    m.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(sr, "REPO", tmp_path.parent)
    # point _run_tests at a non-existent test -> gate refuses
    assert sr._run_tests(m, target=str(tmp_path / "nope.py")) is False


# ── anti-test-poisoning: AST-logic hash ───────────────────────────────────

def test_logic_hash_stable_across_whitespace(tmp_path):
    m = tmp_path / "w.py"
    m.write_text("def f():\n    return 1\n", encoding="utf-8")
    h1 = sr._logic_hash(m)
    # trailing whitespace + blank-line churn must NOT change the logic hash
    m.write_text("def f():\n    return 1  \n\n\n", encoding="utf-8")
    h2 = sr._logic_hash(m)
    assert h1 == h2


def test_logic_hash_changes_on_logic_edit(tmp_path):
    m = tmp_path / "l.py"
    m.write_text("def f():\n    return 1\n", encoding="utf-8")
    h1 = sr._logic_hash(m)
    m.write_text("def f():\n    return 999\n", encoding="utf-8")
    h2 = sr._logic_hash(m)
    assert h1 != h2