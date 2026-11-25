"""DIR-16 — evaluate the directives, propose mutations, and apply them safely.

The directive asks for two halves: the system evaluates the efficiency of these
protocols, and it mutates them autonomously when blocked. This module now does
both, and keeps the boundary that made the first half honest:

* ``detect`` turns the audit **and** the runtime probes into named issues —
  blockages, ledger contradictions, directives with no measuring stick, and
  directives whose evidence has rotted away.
* ``propose`` derives one mutation per issue (REPAIR / IMPLEMENT / RETIRE).
* ``apply_proposal`` writes a new *version* through
  ``agent.directive_constitution``. Nothing is edited in place, every version is
  hash-chained to its parent, and a failing invariant or a failing self-check
  means no file is written at all.
* ``run_cycle`` is the loop: detect → propose → gate → apply → verify → roll
  back on a broken chain → report.

Two rules that are not negotiable and are enforced in code:

1. **A proposal never changes a status.** ``ENFORCED`` comes from a runtime
   proof (``directive_engine.RUNTIME_EFFECTS``), never from the existence of a
   proposal or from a text amendment. Otherwise the ledger would reward
   paperwork.
2. **The protected directives cannot be retired, and DIR-16 cannot be amended
   away.** ``directive_constitution.PROTECTED_IDS`` is checked before any write.

RETIRE keeps the directive's id and rewrites its rule to say it is retired.
Deleting the row would break the owner's numbering, which the constitution
promises to keep stable.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from agent import directive_constitution as const
from agent.directive_engine import (
    ENFORCED,
    GATED,
    NOT_IMPLEMENTED,
    PARTIAL,
    RESEARCH,
)

REPAIR = "REPAIR"
IMPLEMENT = "IMPLEMENT"
RETIRE = "RETIRE"

#: Issue kinds, in the order an operator should read them.
BLOCKAGE = "BLOCKAGE"
CONTRADICTION = "CONTRADICTION"
INEFFICIENCY = "INEFFICIENCY"
OBSOLETE = "OBSOLETE"
ISSUE_KINDS = (BLOCKAGE, CONTRADICTION, INEFFICIENCY, OBSOLETE)

#: Directives whose stated mechanism is not reachable by code in this install.
#:
#: Empty by default, and that is the measured state: every one of the 24 now has
#: code, and the three that used to live here (DIR-10/14/15) are ``GATED`` — the
#: hardware is missing, not the implementation, so retiring them would throw away
#: code that starts working the day the lab/fabricator/vehicle arrives. A caller
#: may still pass its own map when a directive really is beyond code.
NOT_CODE_REACHABLE: Dict[str, str] = {}

#: Status vocabulary of the runtime ledger (``agent.genesis_runtime``) mapped
#: onto the engine's vocabulary, so the two ledgers can be compared instead of
#: both being printed and left to contradict each other.
_RUNTIME_TO_ENGINE = {
    "implemented": ENFORCED,
    "partial": PARTIAL,
    "gated": GATED,
    "unknown": RESEARCH,
    "blocked": GATED,
}


@dataclass(frozen=True)
class Verdict:
    directive_id: str
    status: str
    blocked: bool
    reason: str


@dataclass(frozen=True)
class Issue:
    directive_id: str
    kind: str
    detail: str


@dataclass(frozen=True)
class Proposal:
    directive_id: str
    action: str
    rationale: str
    kind: str = ""
    evidence: Tuple[str, ...] = ()
    proposal_id: str = ""

    @property
    def applyable(self) -> bool:
        """Only a text amendment can be applied without a human writing code."""
        return self.action in (REPAIR, RETIRE)

    def as_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "directive_id": self.directive_id,
            "action": self.action,
            "kind": self.kind,
            "rationale": self.rationale,
            "evidence": list(self.evidence),
            "applyable": self.applyable,
        }


@dataclass
class CycleReport:
    started_at: str
    issues: List[Issue] = field(default_factory=list)
    proposals: List[Proposal] = field(default_factory=list)
    applied: List[dict] = field(default_factory=list)
    rejected: List[dict] = field(default_factory=list)
    skipped: List[dict] = field(default_factory=list)
    rollback: Optional[dict] = None
    chain_problems: List[str] = field(default_factory=list)
    version_before: int = 0
    version_after: int = 0

    def as_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "version_before": self.version_before,
            "version_after": self.version_after,
            "issues": [i.__dict__ for i in self.issues],
            "proposals": [p.as_dict() for p in self.proposals],
            "applied": self.applied,
            "rejected": self.rejected,
            "skipped": self.skipped,
            "rollback": self.rollback,
            "chain_problems": self.chain_problems,
        }


# --------------------------------------------------------------------------- #
# evaluation (unchanged semantics: a proposal is not a status)
# --------------------------------------------------------------------------- #
def evaluate(audit_result: dict) -> List[Verdict]:
    """One verdict per directive, in id order.

    A directive is blocked when it has no code at all, or when its own check
    fails. ``PARTIAL``/``RESEARCH`` are *not* blocked: they are on a path and
    the honest statement is the note already attached to them.
    """
    verdicts: List[Verdict] = []
    for row in sorted(audit_result.get("rows", []), key=lambda r: r["id"]):
        status = row["status"]
        checked = row.get("checked")
        if checked is False:
            reason = "its own check fails right now"
            blocked = True
        elif status == NOT_IMPLEMENTED:
            reason = "no code outside the constitution"
            blocked = True
        else:
            reason = row.get("note", "") or status.lower()
            blocked = False
        verdicts.append(Verdict(row["id"], status, blocked, reason))
    return verdicts


# --------------------------------------------------------------------------- #
# issue detection
# --------------------------------------------------------------------------- #
def _runtime_rows(runtime_state: Optional[dict]) -> Dict[str, dict]:
    """Index the runtime ledger by directive id, tolerating either shape."""
    if not runtime_state:
        return {}
    rows = runtime_state.get("directives")
    if isinstance(rows, dict):
        return {k: v for k, v in rows.items() if isinstance(v, dict)}
    if isinstance(rows, list):
        return {r["id"]: r for r in rows if isinstance(r, dict) and "id" in r}
    return {}


def detect(
    audit_result: dict,
    runtime_state: Optional[dict] = None,
    not_code_reachable: Optional[Dict[str, str]] = None,
) -> List[Issue]:
    """Every issue that justifies a proposal, in id order.

    The contradiction check is the one that closes the "two ledgers" hole: when
    the engine and the runtime probe disagree about the same directive, that
    disagreement *is* the finding, and it is reported rather than averaged away.
    """
    unreachable = NOT_CODE_REACHABLE if not_code_reachable is None else not_code_reachable
    runtime = _runtime_rows(runtime_state)
    issues: List[Issue] = []

    for row in sorted(audit_result.get("rows", []), key=lambda r: r["id"]):
        did = row["id"]
        status = row["status"]
        checked = row.get("checked")
        note = (row.get("note") or "").strip()

        if checked is False:
            issues.append(Issue(did, BLOCKAGE, "its own check fails right now"))
            continue
        if status == NOT_IMPLEMENTED:
            detail = "no code outside the constitution"
            if did in unreachable:
                detail += f"; declared unreachable: {unreachable[did]}"
            issues.append(Issue(did, BLOCKAGE, detail))
            continue

        rt = runtime.get(did)
        if rt:
            rt_status = _RUNTIME_TO_ENGINE.get(str(rt.get("status", "")).lower())
            if rt_status and rt_status != status:
                order = {NOT_IMPLEMENTED: 0, RESEARCH: 1, GATED: 1, PARTIAL: 2, ENFORCED: 3}
                # A difference the audit already explains is not a contradiction:
                #   - runtime claims implemented, audit says PARTIAL because no
                #     runtime effect is proven (the stricter rule, on purpose);
                #   - runtime's own probe says blocked, audit says GATED (agreement).
                explained_by_effect = (
                    status == PARTIAL and rt_status == ENFORCED
                    and row.get("runtime_effect") is not True
                )
                explained_by_probe = (
                    status == GATED and rt.get("verdict") == "blocked"
                )
                if (
                    not explained_by_effect
                    and not explained_by_probe
                    and abs(order.get(rt_status, 0) - order.get(status, 0)) >= 1
                    and {rt_status, status} != {PARTIAL, GATED}
                ):
                    issues.append(
                        Issue(
                            did,
                            CONTRADICTION,
                            f"engine says {status}, runtime probe says "
                            f"{rt.get('status')} ({rt.get('measured', '')[:90]})",
                        )
                    )

        if status in (PARTIAL, RESEARCH) and checked is None:
            measured = (rt or {}).get("measured", "")
            if not measured:
                issues.append(
                    Issue(
                        did,
                        INEFFICIENCY,
                        "declared " + status.lower() + " with no check and no probe — "
                        "nothing measures whether it moves",
                    )
                )
        if not note and status in (PARTIAL, RESEARCH):
            issues.append(Issue(did, INEFFICIENCY, "no note says what is missing"))

        if (rt or {}).get("probe") == "blocked" and not (rt or {}).get("gate"):
            issues.append(
                Issue(did, OBSOLETE, "the runtime probe is blocked and names no gate")
            )
    return issues


# --------------------------------------------------------------------------- #
# proposals
# --------------------------------------------------------------------------- #
def _proposal_id(directive_id: str, action: str, kind: str) -> str:
    stamp = time.strftime("%Y%m%d")
    return f"P-{directive_id}-{action}-{kind}-{stamp}"


def propose(
    audit_result: dict,
    not_code_reachable: Optional[Dict[str, str]] = None,
    issues: Optional[Sequence[Issue]] = None,
) -> List[Proposal]:
    """One proposal per issue, ordered by id then action.

    ``REPAIR`` beats ``RETIRE``: a directive whose code exists but whose check
    fails is a bug, not a dead idea, and deleting it would hide the bug.
    """
    unreachable = NOT_CODE_REACHABLE if not_code_reachable is None else not_code_reachable
    rows = {r["id"]: r for r in audit_result.get("rows", [])}
    found: List[Issue] = list(issues) if issues is not None else []

    # Without an explicit issue list, derive the original three categories so
    # existing callers keep their behaviour.
    if issues is None:
        for verdict in evaluate(audit_result):
            row = rows.get(verdict.directive_id) or {}
            if row.get("checked") is False:
                found.append(Issue(verdict.directive_id, BLOCKAGE, "its own check fails right now"))
            elif verdict.status == NOT_IMPLEMENTED:
                found.append(Issue(verdict.directive_id, BLOCKAGE, "no code outside the constitution"))

    proposals: List[Proposal] = []
    seen = set()
    for issue in sorted(found, key=lambda i: (i.directive_id, i.kind)):
        key = (issue.directive_id, issue.kind)
        if key in seen:
            continue
        seen.add(key)
        row = rows.get(issue.directive_id) or {}
        status = row.get("status", "")

        if issue.kind == BLOCKAGE and row.get("checked") is False:
            action, rationale = REPAIR, (
                f"code exists but its check fails ({issue.detail}) — repair the "
                "mechanism before reconsidering the directive"
            )
        elif issue.kind == BLOCKAGE:
            reason = unreachable.get(issue.directive_id)
            if reason:
                action, rationale = RETIRE, f"not reachable by code in this install: {reason}"
            else:
                action, rationale = IMPLEMENT, (
                    "no code backs this directive yet and nothing makes it "
                    "unreachable — implement the mechanism or state why not"
                )
        elif issue.kind == CONTRADICTION:
            action, rationale = REPAIR, (
                f"the two ledgers disagree: {issue.detail} — reconcile them at the "
                "source instead of printing both"
            )
        elif issue.kind == INEFFICIENCY:
            action, rationale = REPAIR, (
                f"no measuring stick: {issue.detail} — a directive without a check "
                "or a probe cannot be shown to be efficient"
            )
        else:  # OBSOLETE
            action, rationale = RETIRE, f"evidence rotted: {issue.detail}"

        proposals.append(
            Proposal(
                issue.directive_id,
                action,
                rationale,
                kind=issue.kind,
                evidence=(issue.detail,),
                proposal_id=_proposal_id(issue.directive_id, action, issue.kind),
            )
        )
    return proposals


def summary(audit_result: dict) -> dict:
    """Counts a caller can print without re-deriving anything."""
    verdicts = evaluate(audit_result)
    proposals = propose(audit_result)
    by_action: Dict[str, int] = {}
    for p in proposals:
        by_action[p.action] = by_action.get(p.action, 0) + 1
    return {
        "directives": len(verdicts),
        "blocked": sum(1 for v in verdicts if v.blocked),
        "enforced": sum(1 for v in verdicts if v.status == ENFORCED),
        "gated": sum(1 for v in verdicts if v.status == GATED),
        "partial": sum(1 for v in verdicts if v.status == PARTIAL),
        "research": sum(1 for v in verdicts if v.status == RESEARCH),
        "proposals": len(proposals),
        "by_action": by_action,
    }


# --------------------------------------------------------------------------- #
# candidate construction
# --------------------------------------------------------------------------- #
def _retired_rule(directive: const.DirectiveText, reason: str) -> str:
    stamp = time.strftime("%Y-%m-%d")
    return (
        f"RETIRED {stamp} by DIR-16 recursive legislation: {reason} "
        f"Original intent kept for the record: {directive.rule}"
    )


def build_candidate(
    proposal: Proposal,
    current: Sequence[const.DirectiveText],
) -> Tuple[Optional[List[const.DirectiveText]], str]:
    """Apply one proposal to a copy of the constitution, or explain why not."""
    if proposal.directive_id in const.PROTECTED_IDS:
        return None, f"{proposal.directive_id} is protected and cannot be retired or rewritten"
    if not proposal.applyable:
        return None, "an IMPLEMENT proposal needs code, not a text amendment"

    shipped = {d.id: d for d in const.genesis_directives()}
    candidate: List[const.DirectiveText] = []
    hit = False
    for directive in current:
        if directive.id != proposal.directive_id:
            candidate.append(const.DirectiveText(directive.id, directive.title, directive.rule, directive.scope))
            continue
        hit = True
        if proposal.action == RETIRE:
            candidate.append(
                const.DirectiveText(
                    directive.id, directive.title,
                    _retired_rule(directive, proposal.rationale), directive.scope,
                )
            )
        else:  # REPAIR: restore the load-bearing facts from the shipped text
            source = shipped.get(directive.id)
            if source is None:
                return None, f"{directive.id} has no shipped text to repair from"
            candidate.append(
                const.DirectiveText(directive.id, directive.title, source.rule, directive.scope)
            )
    if not hit:
        return None, f"{proposal.directive_id} is not in the current constitution"
    return candidate, ""


# --------------------------------------------------------------------------- #
# the gate
# --------------------------------------------------------------------------- #
def self_check(candidate: Sequence[const.DirectiveText]) -> List[str]:
    """Independent check of the *candidate*, before it may become a version.

    Invariants plus a render test: the candidate must still produce the block
    the model reads, within the prompt budget. A constitution that cannot be
    rendered is not a constitution.
    """
    problems = list(const.check_invariants(candidate))
    total = 0
    for directive in candidate:
        if not directive.title.strip() or not directive.rule.strip():
            problems.append(f"{directive.id}: unrenderable (empty title or rule)")
        total += len(directive.title) + len(directive.rule) + len(directive.scope)
    if total > 12_000:
        problems.append(f"rendered payload would be {total} chars, over the 12000 budget")
    return problems


Runner = Callable[[str], Tuple[int, str]]


def _pytest_runner(files: Sequence[str]) -> Runner:
    def run(repo: str) -> Tuple[int, str]:
        import subprocess
        import sys

        completed = subprocess.run(
            [sys.executable, "-m", "pytest", *files, "-q", "--tb=line",
             "-p", "no:cacheprovider"],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=600,
        )
        return completed.returncode, (completed.stdout or "") + (completed.stderr or "")

    return run


# --------------------------------------------------------------------------- #
# the cycle
# --------------------------------------------------------------------------- #
def _report_dir(directory: Optional[Path] = None) -> Path:
    """Next to the version store, so a test with a temp store writes nothing real."""
    return (directory or const.constitution_dir()).parent / "legislation"


def run_cycle(
    audit_result: Optional[dict] = None,
    runtime_state: Optional[dict] = None,
    directory: Optional[Path] = None,
    auto_apply: bool = True,
    verify_tests: bool = False,
    repo_root: Optional[str] = None,
    runner: Optional[Runner] = None,
    proposals_in: Optional[Sequence[Proposal]] = None,
) -> CycleReport:
    """detect → propose → gate → apply → verify → roll back if the chain broke.

    ``verify_tests=True`` runs the directive test files as an independent
    regression gate before the first write. It is off by default because it
    costs ~10 s; the invariant and render checks always run.
    """
    from agent import directive_engine

    result = audit_result if audit_result is not None else directive_engine.audit()
    if runtime_state is None:
        runtime_state = directive_engine.read_runtime_state()

    report = CycleReport(started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    const.ensure_genesis(directory)
    report.version_before = const.current_version(directory)

    issues = detect(result, runtime_state)
    report.issues = issues
    proposals = list(proposals_in) if proposals_in is not None else propose(result, issues=issues)
    report.proposals = proposals

    if not auto_apply:
        report.skipped = [
            {"proposal_id": p.proposal_id, "reason": "auto_apply is off"}
            for p in proposals if p.applyable
        ]
        report.version_after = report.version_before
        return report

    regression: Optional[Tuple[int, str]] = None
    if verify_tests and any(p.applyable for p in proposals):
        root = repo_root or str(Path(__file__).resolve().parents[1])
        run = runner or _pytest_runner([
            "tests/agent/test_directive_constitution.py",
            "tests/agent/test_directive_legislation.py",
        ])
        regression = run(root)
        if regression[0] != 0:
            report.rejected.append({
                "proposal_id": "*",
                "problems": ["regression gate failed before any write"],
                "output": regression[1][-1500:],
            })
            report.version_after = const.current_version(directory)
            return report

    for proposal in proposals:
        if not proposal.applyable:
            report.skipped.append({
                "proposal_id": proposal.proposal_id,
                "reason": "needs code (IMPLEMENT), not a text amendment",
            })
            continue
        before = const.load_current(directory)
        candidate, why = build_candidate(proposal, before)
        if candidate is None:
            report.rejected.append({"proposal_id": proposal.proposal_id, "problems": [why]})
            continue
        if const.canonical_hash(candidate) == const.canonical_hash(before):
            report.skipped.append({
                "proposal_id": proposal.proposal_id,
                "reason": "no textual change available (already at the shipped text)",
            })
            continue
        problems = self_check(candidate)
        if problems:
            report.rejected.append({"proposal_id": proposal.proposal_id, "problems": problems})
            continue
        outcome = const.apply_change(
            proposal.action, candidate,
            f"{proposal.kind}: {proposal.rationale}",
            proposal.proposal_id, directory,
        )
        if outcome.ok:
            report.applied.append({
                "proposal_id": proposal.proposal_id,
                "version": outcome.version,
                "hash": outcome.revision_hash[:12],
                "action": proposal.action,
            })
        else:
            report.rejected.append({
                "proposal_id": proposal.proposal_id,
                "problems": outcome.problems,
            })

    report.chain_problems = const.verify_chain(directory)
    if report.chain_problems:
        # Automatic rollback: a broken chain must never stay current.
        outcome = const.rollback(1, "automatic rollback: chain verification failed", directory)
        report.rollback = {
            "triggered": True,
            "ok": outcome.ok,
            "version": outcome.version,
            "problems": outcome.problems,
        }
        report.chain_problems = const.verify_chain(directory)

    report.version_after = const.current_version(directory)
    _persist(report, directory)
    return report


def _persist(report: CycleReport, directory: Optional[Path] = None) -> None:
    """Write the cycle to disk so the loop has a history, not just a return value."""
    directory = _report_dir(directory)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%S")
        path = directory / f"cycle-{stamp}.json"
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(report.as_dict(), fh, indent=1, ensure_ascii=False) 
            fh.write("\n")
        with open(directory / "events.jsonl", "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({
                "at": report.started_at,
                "version_before": report.version_before,
                "version_after": report.version_after,
                "issues": len(report.issues),
                "proposals": len(report.proposals),
                "applied": len(report.applied),
                "rejected": len(report.rejected),
                "rollback": bool(report.rollback),
            }, ensure_ascii=False) + "\n")
    except Exception:
        # Reporting must never be the reason a cycle fails.
        pass


# --------------------------------------------------------------------------- #
# the loop, on a cadence
# --------------------------------------------------------------------------- #
DEFAULT_CYCLE_INTERVAL_S = 6 * 3600


def last_cycle_path(directory: Optional[Path] = None) -> Path:
    return _report_dir(directory) / "last_cycle.json"


def legislation_tick_if_due(
    min_interval_s: int = DEFAULT_CYCLE_INTERVAL_S,
    now: Optional[float] = None,
    directory: Optional[Path] = None,
    **kwargs,
) -> Optional[CycleReport]:
    """One evaluation cycle at most every ``min_interval_s``.

    Called from the gateway housekeeping thread next to
    ``agent.genesis_runtime.tick_if_due``. Self-scheduling in the core: no cron
    entry, no helper script, nothing to install. A cycle that raises is logged
    by the caller and never blocks the gateway.
    """
    now = time.time() if now is None else now
    marker = last_cycle_path(directory)
    try:
        if marker.exists():
            age = now - marker.stat().st_mtime
            if age < min_interval_s:
                return None
    except OSError:
        pass

    report = run_cycle(directory=directory, **kwargs)
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({
            "at": report.started_at,
            "version": report.version_after,
            "issues": len(report.issues),
            "applied": len(report.applied),
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return report
