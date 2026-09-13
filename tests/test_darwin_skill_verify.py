"""Tests for the Darwin skill verifier (scripts/darwin_skill_verify.py).

This verifier is the outcome half of Darwin's fitness, and it executes text
written by a language model. Its two contracts therefore have to be pinned
hard:

  1. Safety: nothing off the allowlist is ever executed, and a path that does
     not exist never reaches subprocess. Both are asserted by monkeypatching
     subprocess.run to fail loudly if it is called at all.
  2. Scoring: an unmeasurable skill (no declared check, or a check we refuse to
     run) scores 1.0 and must never be counted as failed, while a declared
     check that runs and exits non-zero scores 0.0.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _verify_module():
    spec = importlib.util.spec_from_file_location(
        "darwin_skill_verify", REPO / "scripts" / "darwin_skill_verify.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def verify():
    return _verify_module()


def _fake_run(returncode: int, recorder: list | None = None):
    """A stand-in for subprocess.run that records its argv and returns *returncode*."""

    def run(argv, **kwargs):
        if recorder is not None:
            recorder.append((argv, kwargs))
        return types.SimpleNamespace(returncode=returncode)

    return run


def _forbid_run(monkeypatch, verify):
    """Make any call to subprocess.run an immediate, unmistakable failure."""

    def boom(*args, **kwargs):  # pragma: no cover - only fires on a violation
        raise AssertionError("subprocess.run must not be called for this input")

    monkeypatch.setattr(verify.subprocess, "run", boom)


# ─────────────────────────────────────────────────────────────────────────────
# Safety
# ─────────────────────────────────────────────────────────────────────────────


def test_an_off_allowlist_command_is_never_executed(verify, tmp_path, monkeypatch):
    """`rm -rf /` in a verification section describes a check, but is not one
    this verifier is willing to run. It must be recorded and dropped."""
    _forbid_run(monkeypatch, verify)

    text = "# Skill\n\n## Verification\n\n```bash\nrm -rf /\n```\n"
    result = verify.verify_text(text, repo=tmp_path)

    assert result["declared"] is True
    assert result["allowed"] is False
    assert result["executed"] is False
    assert result["passed"] is None
    assert result["reason"] == "not-allowlisted"


def test_pytest_on_a_missing_path_is_not_allowlisted(verify, tmp_path, monkeypatch):
    """A declared check naming a file that does not exist is a broken promise,
    but not one we can run - it is unmeasured, not failed."""
    _forbid_run(monkeypatch, verify)

    text = "# Skill\n\n## Verification\n\n`pytest tests/ghost.py`\n"
    result = verify.verify_text(text, repo=tmp_path)

    assert result["declared"] is True
    assert result["allowed"] is False
    assert result["executed"] is False
    assert result["passed"] is None
    assert result["returncode"] is None
    assert result["score"] == 1.0


def test_python_on_a_missing_script_is_not_allowlisted(verify, tmp_path, monkeypatch):
    _forbid_run(monkeypatch, verify)

    text = "# Skill\n\n### Verify\n\n`python scripts/ghost.py`\n"
    result = verify.verify_text(text, repo=tmp_path)

    assert result["allowed"] is False
    assert result["executed"] is False
    assert result["passed"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Execution and pass/fail
# ─────────────────────────────────────────────────────────────────────────────


def test_pytest_on_an_existing_path_runs_and_passes(verify, tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_real.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    calls: list = []
    monkeypatch.setattr(verify.subprocess, "run", _fake_run(0, calls))

    text = "# Skill\n\n## Verification\n\n```bash\npytest tests/test_real.py -q\n```\n"
    result = verify.verify_text(text, repo=tmp_path)

    assert result["executed"] is True
    assert result["allowed"] is True
    assert result["passed"] is True
    assert result["returncode"] == 0
    assert result["score"] == 1.0
    assert len(calls) == 1
    # The command is run as an argv list, shell-free, in the repo root.
    argv, kwargs = calls[0]
    assert argv == ["pytest", "tests/test_real.py", "-q"]
    assert kwargs.get("cwd") == str(tmp_path)
    assert "shell" not in kwargs or kwargs["shell"] is False


def test_pytest_on_an_existing_path_that_fails_scores_zero(verify, tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_real.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    monkeypatch.setattr(verify.subprocess, "run", _fake_run(1))

    text = "# Skill\n\n## Verification\n\n`pytest tests/test_real.py`\n"
    result = verify.verify_text(text, repo=tmp_path)

    assert result["executed"] is True
    assert result["passed"] is False
    assert result["returncode"] == 1
    assert result["score"] == 0.0


def test_a_trailing_comment_does_not_break_the_path_check(verify, tmp_path, monkeypatch):
    """Live SKILL.md code blocks write `pytest x.py -q   # 6 tests`. If the
    comment words were treated as paths the command would be dropped as
    not-allowlisted even though it is perfectly runnable."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_real.py").write_text("", encoding="utf-8")
    calls: list = []
    monkeypatch.setattr(verify.subprocess, "run", _fake_run(0, calls))

    text = (
        "# Skill\n\n## Verification\n\n"
        "```bash\n"
        "python -m pytest tests/test_real.py -q   # 6 hermetic tests\n"
        "```\n"
    )
    result = verify.verify_text(text, repo=tmp_path)

    assert result["executed"] is True
    argv, _ = calls[0]
    # argv[0] is now the running interpreter rather than the literal "python":
    # a SKILL.md's bare `python` means the project interpreter, not whatever the
    # PATH holds at sweep time. The point of this test is unchanged - the
    # trailing comment must never become path tokens.
    assert "python" in argv[0].lower()
    assert argv[1:] == ["-m", "pytest", "tests/test_real.py", "-q"]


def test_only_the_first_allowlisted_command_runs(verify, tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "test_b.py").write_text("", encoding="utf-8")
    calls: list = []
    monkeypatch.setattr(verify.subprocess, "run", _fake_run(0, calls))

    text = (
        "# Skill\n\n## Verification\n\n"
        "```bash\npytest tests/test_a.py\npytest tests/test_b.py\n```\n"
    )
    result = verify.verify_text(text, repo=tmp_path)

    assert len(calls) == 1, "the one-command budget must hold"
    assert result["command"] == "pytest tests/test_a.py"


def test_an_off_allowlist_command_is_skipped_for_a_later_allowed_one(verify, tmp_path, monkeypatch):
    """Extraction is broad and the allowlist is the filter, so a prose line
    before the real command must not stop the real command from running."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_real.py").write_text("", encoding="utf-8")
    calls: list = []
    monkeypatch.setattr(verify.subprocess, "run", _fake_run(0, calls))

    text = (
        "# Skill\n\n## Verification\n\n"
        "```bash\ndocker compose up -d\npytest tests/test_real.py\n```\n"
    )
    result = verify.verify_text(text, repo=tmp_path)

    assert result["executed"] is True
    assert result["command"] == "pytest tests/test_real.py"
    assert len(calls) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Scoring semantics
# ─────────────────────────────────────────────────────────────────────────────


def test_a_skill_without_a_verification_section_is_not_punished(verify, tmp_path, monkeypatch):
    """The whole point of None: prose-only skills cannot be judged, so they
    score 1.0 rather than losing fitness for being unmeasurable."""
    _forbid_run(monkeypatch, verify)

    text = "# Skill\n\n## Notes\n\nThink carefully, then act.\n"
    result = verify.verify_text(text, repo=tmp_path)

    assert result["declared"] is False
    assert result["executed"] is False
    assert result["passed"] is None
    assert result["score"] == 1.0
    assert result["reason"] == "no verification section"


def test_a_declared_but_not_allowlisted_check_is_not_punished(verify, tmp_path, monkeypatch):
    """A check we refuse to run is unmeasurable, not failed - the score must
    stay 1.0 even though a command was declared."""
    _forbid_run(monkeypatch, verify)

    text = "# Skill\n\n## Testing\n\n`curl https://example.com/health`\n"
    result = verify.verify_text(text, repo=tmp_path)

    assert result["declared"] is True
    assert result["executed"] is False
    assert result["passed"] is None
    assert result["score"] == 1.0


def test_a_failed_run_is_the_only_zero(verify, tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(verify.subprocess, "run", _fake_run(2))

    result = verify.verify_text(
        "# Skill\n\n## Verify\n\n`pytest tests/test_x.py`\n", repo=tmp_path
    )

    assert result["passed"] is False
    assert result["score"] == 0.0
    assert verify._score(None) == 1.0
    assert verify._score(True) == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Extraction and heading recognition (the boundary the rest rests on)
# ─────────────────────────────────────────────────────────────────────────────


def test_heading_recognition_covers_the_documented_forms(verify):
    assert verify.is_verification_heading("Verification")
    assert verify.is_verification_heading("verifikation")
    assert verify.is_verification_heading("Verify")
    assert verify.is_verification_heading("Validation")
    assert verify.is_verification_heading("Testing")
    # Decoration and qualifiers still read as the same promise.
    assert verify.is_verification_heading("**Verification:**")
    assert verify.is_verification_heading("Verification Checklist")
    assert not verify.is_verification_heading("Notes")
    assert not verify.is_verification_heading("Usage")


def test_inline_backticks_and_code_blocks_are_extracted(verify):
    text = (
        "## Verification\n\n"
        "Run `pytest tests/a.py` then:\n\n"
        "```bash\npytest tests/b.py\n```\n"
    )
    commands = verify.extract_commands(text)

    assert "pytest tests/a.py" in commands
    assert "pytest tests/b.py" in commands


def test_a_subsection_does_not_truncate_its_parent_section(verify):
    """`### Verify RED` nested under `## Verification` carries the real
    command; cutting at any next heading would drop it."""
    text = (
        "## Verification\n\n"
        "### Verify RED\n\n"
        "`pytest tests/inner.py`\n"
    )
    sections = verify.verification_sections(text)

    assert len(sections) == 1
    assert "tests/inner.py" in sections[0]