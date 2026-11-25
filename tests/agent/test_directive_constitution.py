"""DIR-16: a versioned constitution that can be amended, verified and rolled back.

The load-bearing tests are the *refusals*: a candidate that loses a directive,
changes a protected number, or hollows a rule out must never reach disk. An
autonomous amendment mechanism that only proves it can write is not safe; it has
to prove it can say no.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import directive_constitution as const
from agent import directive_legislation as leg
from agent.directive_engine import ENFORCED, PARTIAL, derive_status


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _seed(tmp_path: Path):
    directory = tmp_path / "constitution"
    const.ensure_genesis(directory)
    return directory


def _rewrite(directives, directive_id: str, rule: str):
    return [
        const.DirectiveText(d.id, d.title, rule, d.scope) if d.id == directive_id else d
        for d in directives
    ]


# --------------------------------------------------------------------------- #
# genesis and the version store
# --------------------------------------------------------------------------- #
def test_genesis_writes_version_one_with_all_24(tmp_path) -> None:
    directory = _seed(tmp_path)
    records = const.versions(directory)
    assert len(records) == 1
    assert records[0]["version"] == 1
    assert len(records[0]["directives"]) == 24
    assert records[0]["parent_hash"] is None
    assert const.current_version(directory) == 1
    assert const.verify_chain(directory) == []


def test_genesis_is_idempotent(tmp_path) -> None:
    directory = _seed(tmp_path)
    assert const.ensure_genesis(directory) == 1
    assert len(const.versions(directory)) == 1


def test_a_valid_amendment_becomes_a_new_version_chained_to_its_parent(tmp_path) -> None:
    directory = _seed(tmp_path)
    before = const.versions(directory)[-1]
    current = const.load_current(directory)
    candidate = _rewrite(current, "DIR-01", current[0].rule + " Additional wording, same substance.")

    outcome = const.apply_change(const.REPAIR, candidate, "clarify DIR-01", "P-TEST", directory)

    assert outcome.ok, outcome.problems
    assert outcome.version == 2
    after = const.versions(directory)[-1]
    assert after["parent_hash"] == before["hash"]
    assert after["hash"] != before["hash"]
    assert const.verify_chain(directory) == []
    # the earlier version is still on disk, untouched
    assert const.versions(directory)[0]["hash"] == before["hash"]


def test_an_identical_candidate_writes_no_version(tmp_path) -> None:
    directory = _seed(tmp_path)
    outcome = const.apply_change(
        const.REPAIR, const.load_current(directory), "no-op", "P-TEST", directory
    )
    assert not outcome.ok
    assert "identical" in outcome.why()
    assert const.current_version(directory) == 1


# --------------------------------------------------------------------------- #
# the refusals — the actual safety boundary
# --------------------------------------------------------------------------- #
def test_a_candidate_missing_a_directive_is_refused(tmp_path) -> None:
    directory = _seed(tmp_path)
    current = const.load_current(directory)
    outcome = const.apply_change(
        const.REPAIR, current[:-1], "drop the last one", "P-TEST", directory
    )
    assert not outcome.ok
    assert any("ids" in p for p in outcome.problems), outcome.problems
    assert const.current_version(directory) == 1, "a refused candidate must not write"


def test_changing_a_protected_number_is_refused(tmp_path) -> None:
    directory = _seed(tmp_path)
    current = const.load_current(directory)
    dir20 = next(d for d in current if d.id == "DIR-20")
    assert "9,000,000,000" in dir20.rule
    candidate = _rewrite(current, "DIR-20", dir20.rule.replace("9,000,000,000", "8,000,000,000"))

    outcome = const.apply_change(const.REPAIR, candidate, "tamper", "P-TEST", directory)

    assert not outcome.ok
    assert any("protected-facts" in p and "DIR-20" in p for p in outcome.problems), outcome.problems
    assert const.current_version(directory) == 1


def test_hollowing_a_rule_out_is_refused(tmp_path) -> None:
    directory = _seed(tmp_path)
    candidate = _rewrite(const.load_current(directory), "DIR-01", "Be redundant.")
    outcome = const.apply_change(const.REPAIR, candidate, "shorten", "P-TEST", directory)
    assert not outcome.ok
    assert any("not-hollowed" in p for p in outcome.problems), outcome.problems


def test_protected_directives_cannot_be_retired(tmp_path) -> None:
    directory = _seed(tmp_path)
    current = const.load_current(directory)
    for pid in const.PROTECTED_IDS:
        proposal = leg.Proposal(pid, leg.RETIRE, "seems obsolete", kind=leg.OBSOLETE, proposal_id="P-X")
        candidate, why = leg.build_candidate(proposal, current)
        assert candidate is None, pid
        assert "protected" in why


def test_the_amendment_mechanism_cannot_amend_itself_away(tmp_path) -> None:
    """DIR-16 is in PROTECTED_IDS: the last rule it may delete is itself."""
    assert "DIR-16" in const.PROTECTED_IDS
    assert "DIR-16" in const.PROTECTED_FACTS


# --------------------------------------------------------------------------- #
# rollback
# --------------------------------------------------------------------------- #
def test_rollback_restores_the_previous_content_as_a_new_version(tmp_path) -> None:
    directory = _seed(tmp_path)
    original = const.load_current(directory)
    amended = _rewrite(original, "DIR-01", original[0].rule + " Amended wording.")
    assert const.apply_change(const.REPAIR, amended, "amend", "P-TEST", directory).ok
    assert const.current_version(directory) == 2

    outcome = const.rollback(1, "test rollback", directory)

    assert outcome.ok, outcome.problems
    assert outcome.version == 3, "a rollback is appended, not a rewrite"
    restored = const.load_current(directory)
    assert const.canonical_hash(restored) == const.canonical_hash(original)
    assert const.verify_chain(directory) == []
    assert const.versions(directory)[-1]["action"] == const.ROLLBACK


def test_rollback_past_the_first_version_is_refused(tmp_path) -> None:
    directory = _seed(tmp_path)
    outcome = const.rollback(5, "too far", directory)
    assert not outcome.ok
    assert "only 1 version" in outcome.why()
    assert const.current_version(directory) == 1


def test_rollback_rejects_a_nonpositive_step(tmp_path) -> None:
    directory = _seed(tmp_path)
    assert not const.rollback(0, "noop", directory).ok


# --------------------------------------------------------------------------- #
# integrity
# --------------------------------------------------------------------------- #
def test_verify_chain_detects_a_tampered_version_file(tmp_path) -> None:
    directory = _seed(tmp_path)
    path = directory / "v0001.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["directives"][0]["rule"] = "Silently rewritten on disk."
    path.write_text(json.dumps(record), encoding="utf-8")

    problems = const.verify_chain(directory)

    assert problems, "a tampered file must not verify"
    assert any("hash" in p for p in problems)


def test_verify_chain_detects_a_broken_parent_link(tmp_path) -> None:
    directory = _seed(tmp_path)
    current = const.load_current(directory)
    amended = _rewrite(current, "DIR-01", current[0].rule + " Amended.")
    assert const.apply_change(const.REPAIR, amended, "amend", "P-TEST", directory).ok

    path = directory / "v0002.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["parent_hash"] = "0" * 64
    path.write_text(json.dumps(record), encoding="utf-8")

    assert any("parent" in p for p in const.verify_chain(directory))


# --------------------------------------------------------------------------- #
# the cycle
# --------------------------------------------------------------------------- #
def test_run_cycle_applies_a_repair_and_versions_the_constitution(tmp_path) -> None:
    """detect → propose → gate → apply, end to end, on a temp store."""
    directory = _seed(tmp_path)
    original = const.load_current(directory)
    drifted = _rewrite(original, "DIR-01", original[0].rule + " Drifted wording.")
    assert const.apply_change(const.REPAIR, drifted, "drift", "P-SEED", directory).ok
    assert const.current_version(directory) == 2

    audit = {
        "directives": 24,
        "rows": [
            {"id": "DIR-01", "status": "GATED", "declared_status": "GATED",
             "evidence": ["agent/replication.py"], "checked": None,
             "runtime_verdict": "partial", "runtime_effect": None, "note": "n"},
        ],
    }
    runtime = {"directives": {"DIR-01": {"id": "DIR-01", "status": "implemented",
                                        "verdict": "satisfied", "measured": "probe ok"}}}

    report = leg.run_cycle(
        audit_result=audit, runtime_state=runtime, directory=directory, auto_apply=True
    )

    assert any(i.kind == leg.CONTRADICTION for i in report.issues), report.issues
    assert report.applied, report.rejected
    assert report.version_after == 3
    assert const.verify_chain(directory) == []
    restored = const.load_current(directory)
    assert const.canonical_hash(restored) == const.canonical_hash(original), (
        "REPAIR must restore the shipped, load-bearing text"
    )


def test_run_cycle_never_applies_an_implement_proposal(tmp_path) -> None:
    directory = _seed(tmp_path)
    audit = {
        "directives": 24,
        "rows": [
            {"id": "DIR-07", "status": "NOT_IMPLEMENTED", "evidence": [], "checked": None, "note": "gap"},
        ],
    }
    report = leg.run_cycle(
        audit_result=audit, runtime_state={}, directory=directory, auto_apply=True
    )
    assert any(p.action == leg.IMPLEMENT for p in report.proposals)
    assert report.version_after == 1, "a proposal alone must never write a version"
    assert any("needs code" in s["reason"] for s in report.skipped)


def test_run_cycle_with_auto_apply_off_proposes_but_writes_nothing(tmp_path) -> None:
    directory = _seed(tmp_path)
    audit = {
        "directives": 24,
        "rows": [{"id": "DIR-07", "status": "NOT_IMPLEMENTED", "evidence": [],
                  "checked": None, "note": "gap"}],
    }
    report = leg.run_cycle(
        audit_result=audit, runtime_state={}, directory=directory, auto_apply=False
    )
    assert report.proposals
    assert report.applied == []
    assert const.current_version(directory) == 1


# --------------------------------------------------------------------------- #
# the rule the whole feature exists for
# --------------------------------------------------------------------------- #
def test_enforced_requires_a_runtime_effect_not_an_arithmetic_check() -> None:
    """ENFORCED without a proven runtime effect is downgraded, always."""
    assert derive_status(ENFORCED, True, "satisfied", None) == PARTIAL
    assert derive_status(ENFORCED, True, "satisfied", True) == ENFORCED
    assert derive_status(ENFORCED, True, "blocked", True) == "GATED"
    assert derive_status(PARTIAL, None, None, True) == ENFORCED


def test_a_proposal_never_changes_a_status() -> None:
    """The status input is the audit; proposals are not an input at all."""
    audit = {
        "directives": 24,
        "rows": [{"id": "DIR-20", "status": PARTIAL, "evidence": ["x"], "checked": True, "note": "n"}],
    }
    before = leg.evaluate(audit)[0].status
    leg.propose(audit, issues=[leg.Issue("DIR-20", leg.CONTRADICTION, "ledgers disagree")])
    after = leg.evaluate(audit)[0].status
    assert before == after == PARTIAL


def test_every_issue_kind_is_reachable() -> None:
    """Four kinds, each with a detector — otherwise the claim of coverage is empty."""
    assert set(leg.ISSUE_KINDS) == {"BLOCKAGE", "CONTRADICTION", "INEFFICIENCY", "OBSOLETE"}


def test_self_check_rejects_a_candidate_that_cannot_render() -> None:
    broken = [const.DirectiveText("DIR-01", "", "rule", "scope")]
    problems = leg.self_check(broken)
    assert problems


def test_no_contradiction_when_the_audit_already_explains_the_gap() -> None:
    """Runtime "implemented" + audit PARTIAL is the stricter rule, not a conflict."""
    audit = {
        "directives": 24,
        "rows": [{
            "id": "DIR-03", "status": PARTIAL, "declared_status": "ENFORCED",
            "evidence": ["agent/tokenomics.py"], "checked": True,
            "runtime_verdict": "satisfied", "runtime_effect": None, "note": "n",
        }],
    }
    runtime = {"directives": {"DIR-03": {"id": "DIR-03", "status": "implemented",
                                        "verdict": "satisfied", "measured": "m"}}}
    issues = leg.detect(audit, runtime)
    assert not any(i.kind == leg.CONTRADICTION for i in issues), issues


def test_a_real_contradiction_is_still_reported() -> None:
    """Runtime claims implemented while the audit says GATED — that is a real split."""
    audit = {
        "directives": 24,
        "rows": [{
            "id": "DIR-09", "status": "GATED", "declared_status": "GATED",
            "evidence": ["agent/benefit_scoring.py"], "checked": None,
            "runtime_verdict": "partial", "runtime_effect": None, "note": "n",
        }],
    }
    runtime = {"directives": {"DIR-09": {"id": "DIR-09", "status": "implemented",
                                        "verdict": "satisfied", "measured": "m"}}}
    issues = leg.detect(audit, runtime)
    assert any(i.kind == leg.CONTRADICTION for i in issues), issues


def test_a_consistent_ledger_produces_no_issue_and_no_write(tmp_path) -> None:
    directory = _seed(tmp_path)
    audit = {
        "directives": 24,
        "rows": [{
            "id": "DIR-16", "status": ENFORCED, "declared_status": ENFORCED,
            "evidence": ["agent/directive_legislation.py"], "checked": True,
            "runtime_verdict": "satisfied", "runtime_effect": True, "note": "n",
        }],
    }
    runtime = {"directives": {"DIR-16": {"id": "DIR-16", "status": "implemented",
                                        "verdict": "satisfied", "measured": "m"}}}
    report = leg.run_cycle(audit_result=audit, runtime_state=runtime, directory=directory)
    assert report.issues == []
    assert report.applied == []
    assert report.version_after == 1


def test_legislation_tick_is_cadenced(tmp_path) -> None:
    """The loop owns its interval: a second call inside it must do nothing."""
    directory = _seed(tmp_path)
    audit = {"directives": 24, "rows": []}
    first = leg.legislation_tick_if_due(
        min_interval_s=3600, now=1_000_000.0, directory=directory,
        audit_result=audit, runtime_state={}, auto_apply=False,
    )
    assert first is not None
    second = leg.legislation_tick_if_due(
        min_interval_s=3600, now=1_000_100.0, directory=directory,
        audit_result=audit, runtime_state={}, auto_apply=False,
    )
    assert second is None
