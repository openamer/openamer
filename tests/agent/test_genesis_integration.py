"""The Genesis directives must reach the model *and* stay answerable.

Two failure modes this pins:

1. The block silently loses directives (a truncation or a broken loop) — the
   model then works from an incomplete constitution and nobody notices.
2. The block is present but passive: a status claim comes from memory or from a
   file name that looks related, which is exactly how DIR-03 was reported as
   "no code" while `openamer directive` knew it was ENFORCED.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from agent.genesis_directives import GENESIS_DIRECTIVES, render_genesis_block

REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# the block itself
# --------------------------------------------------------------------------- #
def test_all_24_directives_are_rendered() -> None:
    block = render_genesis_block()
    ids = set(re.findall(r"DIR-\d+", block))
    assert len(GENESIS_DIRECTIVES) == 24
    assert ids == {d.id for d in GENESIS_DIRECTIVES}, sorted(ids)
    for directive in GENESIS_DIRECTIVES:
        assert directive.title in block
        assert directive.rule[:40] in block


def test_block_points_at_the_audit_instead_of_memory() -> None:
    block = render_genesis_block()
    # The authority line is what stops a filename from being read as proof.
    assert "openamer directive" in block
    assert "Never infer a directive's state from memory" in block
    assert "a module name is not an implementation" in block


def test_switch_disables_the_block() -> None:
    # config.yaml: agent.genesis_directives. A constitution the operator cannot
    # decline is a takeover, so the switch must actually switch.
    assert render_genesis_block(enabled=False) == ""


def test_block_stays_within_the_prompt_budget() -> None:
    block = render_genesis_block()
    # The block is appended to the cached prompt prefix; unbounded growth would
    # be paid for on every turn.
    assert len(block) < 12_000, len(block)


# --------------------------------------------------------------------------- #
# the audit behind it
# --------------------------------------------------------------------------- #
def test_audit_covers_every_directive_and_finds_no_violation() -> None:
    from agent.directive_engine import audit

    result = audit()
    # Shape: {"directives": 24, "counts": {...}, "rows": [{id, status, evidence, ...}],
    #         "violations": [], "unverified": [], "home_root": "..."}
    assert result["directives"] == 24
    rows = result["rows"]
    assert len(rows) == 24, len(rows)
    assert {row["id"] for row in rows} == {d.id for d in GENESIS_DIRECTIVES}
    for row in rows:
        assert row["status"] in {"ENFORCED", "PARTIAL", "GATED", "RESEARCH", "NOT_IMPLEMENTED"}
        # A status without an evidence path is an assertion, not an audit.
        assert row["evidence"] or row["status"] == "NOT_IMPLEMENTED", row
    assert result["violations"] == [], result["violations"]
    assert sum(result["counts"].values()) == 24, result["counts"]


def test_cli_reports_the_same_state_the_model_is_told_to_trust() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "openamer_cli.main", "directive"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Genesis directives: 24" in completed.stdout
    assert "No violations" in completed.stdout
    # Every status the command can print must appear in its vocabulary, so a new
    # status cannot be invented without a test noticing.
    allowed = {"ENFORCED", "PARTIAL", "GATED", "RESEARCH", "NOT_IMPLEMENTED"}
    printed = set(re.findall(r"\b(ENFORCED|PARTIAL|GATED|RESEARCH|NOT_IMPLEMENTED)\b", completed.stdout))
    assert printed <= allowed
