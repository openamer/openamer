"""Tests for scripts/self_modify.py — the test-gated self-modification gate.

These pin the safety contracts that make self-modification "does not break":
  1. The scope guard refuses any path outside the repo.
  2. The syntax gate rejects broken Python before any test runs.
  3. Kind detection routes skill/plugin/core to the right verifier.
  4. Skill validation rejects broken frontmatter.
  5. Plugin validation rejects a module that fails to import.
  6. main() rolls back byte-identically on a rejected change.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

import scripts.self_modify as sm


# ── Scope guard ──────────────────────────────────────────────────────────────


def test_resolve_target_rejects_outside_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(sm, "_repo_root", lambda: tmp_path)
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("x")
    with pytest.raises(SystemExit):
        sm._resolve_target("../outside.txt")


def test_resolve_target_rejects_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(sm, "_repo_root", lambda: tmp_path)
    with pytest.raises(SystemExit):
        sm._resolve_target("does-not-exist.txt")


def test_resolve_target_accepts_inside_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(sm, "_repo_root", lambda: tmp_path)
    target = tmp_path / "inside.txt"
    target.write_text("x")
    assert sm._resolve_target("inside.txt") == target.resolve()


# ── Syntax gate ──────────────────────────────────────────────────────────────


def test_syntax_check_rejects_broken_python(tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("this is not valid python !!!")
    ok, err = sm._syntax_check(f)
    assert not ok
    assert "syntax error" in err


def test_syntax_check_accepts_valid_python(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text("x = 1\n")
    ok, _ = sm._syntax_check(f)
    assert ok


def test_syntax_check_skips_non_python(tmp_path):
    f = tmp_path / "notes.md"
    f.write_text("not python")
    ok, _ = sm._syntax_check(f)
    assert ok  # non-.py files are not syntax-checked


# ── Kind detection ───────────────────────────────────────────────────────────


def test_detect_kind_skill(tmp_path):
    assert sm._detect_kind(tmp_path / "SKILL.md") == "skill"


def test_detect_kind_plugin(tmp_path):
    assert sm._detect_kind(tmp_path / "plugins" / "foo.py") == "plugin"


def test_detect_kind_core(tmp_path):
    assert sm._detect_kind(tmp_path / "agent" / "foo.py") == "core"


# ── Skill validation ─────────────────────────────────────────────────────────


def test_validate_skill_rejects_missing_frontmatter(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("no frontmatter here")
    ok, err = sm._validate_skill(f)
    assert not ok
    assert "frontmatter" in err.lower()


def test_validate_skill_accepts_valid_frontmatter(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text(
        "---\nname: test-skill\ndescription: A test skill.\n---\n\n# Body\n"
    )
    ok, _ = sm._validate_skill(f)
    assert ok


# ── Plugin validation ────────────────────────────────────────────────────────


def test_validate_plugin_rejects_bad_import(tmp_path):
    f = tmp_path / "bad_plugin.py"
    f.write_text("import nonexistent_module_xyz\n")
    ok, err = sm._validate_plugin(f)
    assert not ok
    assert "import failed" in err


def test_validate_plugin_accepts_valid_module(tmp_path):
    f = tmp_path / "good_plugin.py"
    f.write_text("VALUE = 42\n")
    ok, _ = sm._validate_plugin(f)
    assert ok


# ── main() rollback ──────────────────────────────────────────────────────────


def test_main_rolls_back_on_broken_change(monkeypatch, tmp_path, capsys):
    """A rejected change must leave the target byte-identical (CRLF preserved)."""
    target = tmp_path / "target.py"
    original = b"x = 1\r\n"  # CRLF, to prove byte-identity
    target.write_bytes(original)

    broken = tmp_path / "broken.py"
    broken.write_text("not valid python !!!")

    monkeypatch.setattr(sm, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["self_modify.py", "target.py", str(broken)])

    rc = sm.main()

    assert rc == 1  # rejected
    assert target.read_bytes() == original  # byte-identical rollback
    assert not target.with_suffix(".py.bak").exists()  # no leftover backup


def test_main_keeps_valid_change(monkeypatch, tmp_path, capsys):
    """A valid change (syntax ok, tests pass) must be kept."""
    target = tmp_path / "target.py"
    target.write_text("x = 1\n")

    good = tmp_path / "good.py"
    good.write_text("y = 2\n")

    monkeypatch.setattr(sm, "_repo_root", lambda: tmp_path)
    # Stub the test gate to always pass (we test the gate separately).
    monkeypatch.setattr(sm, "_run_tests", lambda scope=None: (True, ""))
    monkeypatch.setattr(sys, "argv", ["self_modify.py", "target.py", str(good)])

    rc = sm.main()

    assert rc == 0  # accepted
    assert target.read_text() == "y = 2\n"
    assert not target.with_suffix(".py.bak").exists()
