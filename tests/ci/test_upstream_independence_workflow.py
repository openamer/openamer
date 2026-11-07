"""Contract: the upstream-independence gate is wired into CI correctly.

The independence claim is only worth something if it is enforced. This test
pins the wiring: the workflow must exist, be valid YAML, run the three
checks, and be listed as a required lane in the gate.

A typo in the workflow YAML would otherwise only surface when CI runs.
"""

from __future__ import annotations

import pathlib
import re

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
INDEPENDENCE = WORKFLOWS / "upstream-independence.yml"
CI = WORKFLOWS / "ci.yml"


def _load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_the_workflow_exists_and_is_valid_yaml():
    assert INDEPENDENCE.is_file(), f"missing workflow: {INDEPENDENCE}"
    data = _load(INDEPENDENCE)
    assert isinstance(data, dict)
    assert "jobs" in data


def test_the_workflow_runs_the_three_checks():
    data = _load(INDEPENDENCE)
    steps = data["jobs"]["independence"]["steps"]
    run = "\n".join(str(s.get("run", "")) for s in steps)
    assert "scripts/audit_upstream_coupling.py --fail-on-findings" in run
    assert "scripts/port_from_upstream.py --check-only" in run
    assert "test_upstream_provenance.py" in run


def test_the_workflow_is_callable_and_pins_its_action():
    """Reusable workflows must use ``workflow_call`` and pinned actions."""
    data = _load(INDEPENDENCE)
    # ``on:`` is parsed by yaml as the boolean True -- that is yaml 1.1, not a
    # mistake in the workflow.
    triggers = data.get("on", data.get(True))
    assert "workflow_call" in triggers, triggers
    for step in data["jobs"]["independence"]["steps"]:
        uses = step.get("uses")
        if uses and not uses.startswith("./"):
            # action@sha or action@vN -- either is a pin, no trailing space required
            assert re.search(r"@[0-9a-f]{40}(?:\s|$)|@v\d+", uses), f"unpinned action: {uses}"


def test_the_lane_is_listed_in_the_gate():
    """``all-checks-pass`` must wait for the independence lane."""
    ci = _load(CI)
    gate = ci["jobs"]["all-checks-pass"]
    assert "upstream-independence" in gate["needs"], gate["needs"]


def test_the_lane_is_not_path_gated():
    """The independence lane must run on every change, not only on some lanes.

    A new upstream import can arrive through any file, so gating this lane
    behind the Python/frontend classifier would let coupling in unnoticed.
    """
    ci = _load(CI)
    lane = ci["jobs"]["upstream-independence"]
    assert "if" not in lane, f"independence lane must not be skipped: {lane.get('if')}"
    # yaml gives a bare scalar for a single-entry needs list
    needs = lane["needs"]
    if isinstance(needs, str):
        needs = [needs]
    assert needs == ["detect"]


def test_the_evaluate_needs_gate_treats_a_failure_as_blocking():
    """The verdict script must fail the gate when the lane fails."""
    script = (REPO / "scripts" / "ci" / "evaluate_needs.py").read_text(encoding="utf-8")
    assert '"failure"' in script
    assert '"cancelled"' in script
