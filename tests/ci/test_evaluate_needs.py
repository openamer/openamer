"""Verdict rules for the ``all-checks-pass`` gate (scripts/ci/evaluate_needs.py).

The gate's job is to be the one check branch protection requires, so a wrong
verdict here is worth more than any other CI bug: it decides whether an
unvalidated commit is allowed to look validated.

The regression these tests pin: the gate failed only on ``failure``, so this
needs map reported success —

    detect  cancelled
    13 other lanes  skipped

— i.e. "✅ All required checks pass" on a run where the classifier never ran and
nothing was tested.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "evaluate_needs.py"
_spec = importlib.util.spec_from_file_location("evaluate_needs", _PATH)
if _spec is None or _spec.loader is None:  # pragma: no cover - broken checkout
    raise ImportError("Failed to load evaluate_needs.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["evaluate_needs"] = _mod
_spec.loader.exec_module(_mod)


def _needs(**results: str) -> dict[str, dict[str, str]]:
    return {name: {"result": result} for name, result in results.items()}


def test_a_clean_run_passes() -> None:
    needs = _needs(detect="success", tests="success", lint="skipped", docker="success")
    blocking = _mod.verdict(needs)
    assert blocking == []


def test_a_failed_lane_blocks() -> None:
    needs = _needs(detect="success", tests="failure", lint="success")
    blocking = _mod.verdict(needs)
    assert blocking == ["tests"]


def test_a_cancelled_lane_blocks() -> None:
    """This is the case that used to slip through as green."""
    needs = _needs(detect="cancelled", tests="skipped", lint="skipped")
    blocking = _mod.verdict(needs)
    assert "detect" in blocking
    assert blocking == ["detect"]


def test_a_cancelled_non_prerequisite_lane_blocks_too() -> None:
    needs = _needs(detect="success", tests="skipped", docs_site="cancelled")
    blocking = _mod.verdict(needs)
    assert blocking == ["docs_site"]


def test_a_skipped_classifier_blocks() -> None:
    """Every lane is gated on detect's outputs; without it nothing is proven."""
    needs = _needs(detect="skipped", tests="success")
    blocking = _mod.verdict(needs)
    assert blocking == ["detect"]


def test_skipped_lanes_alone_do_not_block() -> None:
    """Path-based lane gating is legitimate — it must not turn the gate red."""
    needs = _needs(
        detect="success",
        tests="skipped",
        lint="skipped",
        **{"js-tests": "skipped", "e2e-desktop": "skipped"},
    )
    blocking = _mod.verdict(needs)
    assert blocking == []


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ({"detect": "success", "tests": "failure"}, 1),
        ({"detect": "cancelled", "tests": "skipped"}, 1),
        ({"detect": "skipped", "tests": "skipped"}, 1),
        ({"detect": "success", "tests": "success", "lint": "skipped"}, 0),
    ],
)
def test_main_exit_code(tmp_path: Path, results: dict[str, str], expected: int) -> None:
    """End-to-end: the exit code is what makes the check red or green."""
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "NEEDS": json.dumps(_needs(**results)),
        "GITHUB_OUTPUT": str(output),
    }
    proc = subprocess.run([sys.executable, str(_PATH)], capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == expected, proc.stdout + proc.stderr
    body = output.read_text(encoding="utf-8")
    assert "needs-json=" in body, "the review-comment assembler reads needs-json from this step"


def test_missing_needs_is_an_error_not_a_pass() -> None:
    proc = subprocess.run(
        [sys.executable, str(_PATH)],
        capture_output=True,
        text=True,
        env={**os.environ, "NEEDS": ""},
        timeout=60,
    )
    assert proc.returncode == 1, "an empty needs map must never read as success"
