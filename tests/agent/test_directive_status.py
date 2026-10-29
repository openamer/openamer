"""The directive ledger must be complete, honest, and self-checking.

``agent/genesis_directives.py`` renders 24 rules into the system prompt. Until
``agent/directive_status.py`` existed, nothing said which of them had code, so
"what is the state of the directives?" was answered from memory. These tests pin
the two properties that make the ledger trustworthy:

* **complete** — every directive in the constitution has exactly one entry, and
  no entry refers to a directive that does not exist;
* **honest** — an ``implemented``/``partial`` claim must cite at least one path
  that exists on disk, and a ``gated`` entry must name the prerequisite that
  blocks it, so nothing can be filed as "impossible" without a stated reason.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from agent import directive_status as ds  # noqa: E402
from agent.genesis_directives import GENESIS_DIRECTIVES  # noqa: E402


def test_every_directive_has_exactly_one_entry() -> None:
    ids = [d.id for d in GENESIS_DIRECTIVES]
    assert len(ids) == 24, f"the constitution is 24 directives, found {len(ids)}"
    assert len(set(ids)) == len(ids), "duplicate directive ids in the constitution"
    assert set(ds.DIRECTIVE_STATUS) == set(ids), (
        "ledger and constitution disagree: "
        f"missing={sorted(set(ids) - set(ds.DIRECTIVE_STATUS))} "
        f"unknown={sorted(set(ds.DIRECTIVE_STATUS) - set(ids))}"
    )


def test_status_vocabulary_is_closed() -> None:
    for entry in ds.DIRECTIVE_STATUS.values():
        assert entry.status in ds._STATUSES, f"{entry.id}: unknown status {entry.status!r}"


def test_implemented_and_partial_claims_cite_existing_evidence() -> None:
    """A claim without a file behind it is a rumour, not a status."""
    for entry in ds.DIRECTIVE_STATUS.values():
        if entry.status in (ds.IMPLEMENTED, ds.PARTIAL):
            assert entry.evidence, f"{entry.id} is {entry.status} but cites no evidence"
            missing = [p for p in entry.evidence if not (REPO_ROOT / p).exists()]
            assert not missing, f"{entry.id} cites paths that do not exist: {missing}"


def test_every_gated_directive_declares_its_prerequisite() -> None:
    for entry in ds.DIRECTIVE_STATUS.values():
        if entry.status == ds.GATED:
            assert entry.prerequisite and entry.prerequisite.strip(), (
                f"{entry.id} is gated without a stated prerequisite — a directive may be "
                "blocked, never merely written off"
            )


def test_measure_downgrades_a_claim_whose_evidence_disappeared(tmp_path: Path) -> None:
    """stat() the evidence, so a rename cannot leave a stale 'implemented' behind."""
    rows = ds.measure(tmp_path)  # empty root: nothing exists
    by_id = {row["id"]: row for row in rows}

    assert by_id["DIR-20"]["status"] == ds.GATED, "evidence is gone, so the claim must fall"
    assert by_id["DIR-20"]["missing_evidence"], "the missing paths must be named"
    assert by_id["DIR-03"]["status"] == ds.GATED
    # Gated entries that never claimed implementation stay gated.
    assert by_id["DIR-10"]["status"] == ds.GATED


def test_measure_against_the_real_tree_reports_a_full_table() -> None:
    rows = ds.measure(REPO_ROOT)
    assert len(rows) == 24
    assert not any(row["status"] == "missing" for row in rows)

    counts = ds.summary(rows)
    assert counts["total"] == 24
    assert (
        counts[ds.IMPLEMENTED] + counts[ds.PARTIAL] + counts[ds.GATED] == 24
    ), f"statuses do not add up: {counts}"
    # At least the encoded constitution-and-tokenomics work must be real.
    by_id = {row["id"]: row for row in rows}
    assert by_id["DIR-20"]["status"] == ds.IMPLEMENTED
    assert by_id["DIR-03"]["status"] == ds.IMPLEMENTED


def test_render_lists_every_directive_and_the_totals() -> None:
    rows = ds.measure(REPO_ROOT)
    text = ds.render(rows)
    for directive in GENESIS_DIRECTIVES:
        assert directive.id in text, f"{directive.id} missing from the table"
    assert "24 directives" in text
    counts = ds.summary(rows)
    assert f"{counts[ds.IMPLEMENTED]} implemented" in text


@pytest.mark.parametrize("status_filter", [ds.IMPLEMENTED, ds.PARTIAL, ds.GATED])
def test_each_status_is_actually_used(status_filter: str) -> None:
    """A vocabulary nobody uses is not a vocabulary: all three states occur."""
    used = {entry.status for entry in ds.DIRECTIVE_STATUS.values()}
    assert status_filter in used
