"""The directive registry must cover all 24 ids and never overstate a claim."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent.directive_engine import (
    ENFORCED,
    IMPLEMENTATIONS,
    NOT_IMPLEMENTED,
    PARTIAL,
    RESEARCH,
    _ORDER,
    _REPO_ROOT,
    audit,
    main,
)
from agent.genesis_directives import GENESIS_DIRECTIVES


def test_every_directive_has_exactly_one_entry() -> None:
    constitution = [d.id for d in GENESIS_DIRECTIVES]
    assert len(constitution) == 24
    assert sorted(IMPLEMENTATIONS) == sorted(constitution)


def test_no_claim_points_at_a_file_that_does_not_exist() -> None:
    """The load-bearing guard: a status page whose evidence vanished is decoration."""
    result = audit()
    missing = [v for v in result["violations"] if "evidence missing" in v]
    assert missing == []


def test_audit_reports_no_violations_at_all() -> None:
    result = audit()
    assert result["violations"] == []


def test_install_side_evidence_is_unverified_not_a_violation(monkeypatch) -> None:
    """A bare checkout cannot see the install tree; that must be stated, not faked.

    The Rust kernel lives in the installation, so ``home:``-prefixed evidence is
    unresolvable here. Three states, and collapsing any two of them lies:
    "missing" means the claim is wrong, "unverified" means this tree cannot
    judge it, and a check that cannot run must report None -- never False.
    """
    monkeypatch.delenv("OPENAMER_HOME", raising=False)
    result = audit()
    assert any(u.startswith("DIR-04") for u in result["unverified"])
    assert not any("DIR-04" in v for v in result["violations"])
    row = next(r for r in result["rows"] if r["id"] == "DIR-04")
    assert row["checked"] is None, row


def test_install_side_evidence_resolves_when_home_is_set(monkeypatch, tmp_path) -> None:
    (tmp_path / "os" / "kernel").mkdir(parents=True)
    (tmp_path / "os" / "bootloader").mkdir(parents=True)
    (tmp_path / "os" / "kernel" / "Cargo.toml").write_text("", encoding="utf-8")
    (tmp_path / "os" / "bootloader" / "Cargo.toml").write_text("", encoding="utf-8")
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    result = audit()
    assert not any(u.startswith("DIR-04") for u in result["unverified"])
    assert result["home_root"] == str(tmp_path)


def test_counts_cover_every_row() -> None:
    result = audit()
    assert sum(result["counts"].values()) == result["directives"] == 24
    assert set(result["counts"]) <= set(_ORDER)


def test_enforced_claims_have_a_passing_check() -> None:
    """Only ENFORCED is a claim about behaviour, so it must be measured."""
    enforced = [r for r in audit()["rows"] if r["status"] == ENFORCED]
    assert enforced, "at least one directive must be measurable"
    assert all(r["checked"] is True for r in enforced), enforced


def test_no_directive_is_left_without_code() -> None:
    """Measured 2026-10-25: every one of the 24 now carries an implementation.

    The three hardware-bound ones are GATED (code complete for their half, acts
    only with the hardware present), which is a different statement from "not
    implemented" — and the registry must never blur the two.
    """
    gaps = [r for r in audit()["rows"] if r["status"] == NOT_IMPLEMENTED]
    assert gaps == []
    assert audit()["counts"].get(NOT_IMPLEMENTED, 0) == 0


def test_a_gap_would_still_carry_no_evidence() -> None:
    """The shape rule survives the state change: a gap names no module."""
    from agent.directive_engine import Implementation

    gap = Implementation("DIR-99", NOT_IMPLEMENTED, [], "nothing here")
    assert gap.evidence == []


def test_every_non_gap_names_at_least_one_module() -> None:
    for row in audit()["rows"]:
        if row["status"] != NOT_IMPLEMENTED:
            assert row["evidence"], row


def test_every_note_says_what_is_missing() -> None:
    """A note that only praises is how a registry turns into marketing."""
    for row in audit()["rows"]:
        if row["status"] in (PARTIAL, RESEARCH, NOT_IMPLEMENTED):
            assert row["note"].strip(), row["id"]


def test_levels_are_ordered_weakest_to_strongest() -> None:
    assert _ORDER[NOT_IMPLEMENTED] < _ORDER[RESEARCH] < _ORDER[PARTIAL] < _ORDER[ENFORCED]


def test_cli_json_is_machine_readable() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "agent.directive_engine", "--json"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = json.loads(out.stdout)
    assert payload["directives"] == 24
    assert len(payload["rows"]) == 24


def test_cli_table_runs(capsys) -> None:
    assert main([]) == 0
    printed = capsys.readouterr().out
    assert "Genesis directives: 24" in printed
    assert "DIR-01" in printed


def test_gaps_view_is_empty_when_there_are_no_gaps(capsys) -> None:
    """With every directive backed by code, the gaps view must show no rows."""
    main(["--gaps"])
    printed = capsys.readouterr().out
    assert not any(line.startswith("DIR-") for line in printed.splitlines())
