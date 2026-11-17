"""The push rejection must be detectable, or nothing downstream means anything.

Measured 2026-11-17: git printed `hint: Note about fast-forwards` and exited 1,
but the run continued, the PR was opened against a stale remote branch, GitHub
answered `merged: True`, and the code never reached main — three times in one
evening. `push_was_rejected()` is the check that makes that impossible.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "ship.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("ship", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("output", [
    "To https://github.com/openamer/openamer.git\n"
    " ! [rejected]        HEAD -> chore/x (non-fast-forward)\n"
    "error: failed to push some refs to 'https://github.com/openamer/openamer.git'\n"
    "hint: Updates were rejected because the tip of your current branch is behind\n"
    "hint: See the 'Note about fast-forwards' in 'git push --help' for details.\n",
    "! [rejected] HEAD -> main (fetch first)",
    "error: failed to push some refs to 'origin'",
    "hint: Updates were rejected because a pushed branch tip is behind its remote",
])
def test_rejection_shapes_are_detected(mod, output):
    assert mod.push_was_rejected(output) is True


@pytest.mark.parametrize("output", [
    "To https://github.com/openamer/openamer.git\n"
    " * [new branch]              HEAD -> fix/i18n-retry\n",
    "   3b2c1d4..9f8e7d6  HEAD -> main\n",
    "Everything up-to-date\n",
])
def test_successful_push_is_not_flagged(mod, output):
    assert mod.push_was_rejected(output) is False


def test_ship_refuses_to_continue_after_a_rejected_push(mod, monkeypatch, tmp_path, capsys):
    """A rejected push must stop the run before any PR is created."""
    calls = {"pr": 0}

    def fake_run(*a, **kw):
        class R:
            returncode = 1
            stdout = ""
            stderr = (" ! [rejected]  HEAD -> chore/x (non-fast-forward)\n"
                      "hint: See the 'Note about fast-forwards' in 'git push --help'\n")
        return R()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod, "token", lambda: "t")
    monkeypatch.setattr(mod.GitHub, "call",
                        lambda self, m, p, b=None: (calls.__setitem__("pr", calls["pr"] + 1), (500, {}))[1])

    body = tmp_path / "body.md"
    body.write_text("x", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "ship.py", "--branch", "fix/x", "--title", "t", "--body-file", str(body)])

    assert mod.main() == 2
    assert calls["pr"] == 0, "es darf kein PR angelegt werden, wenn der Push abgelehnt wurde"
    assert "abgelehnt" in capsys.readouterr().err
