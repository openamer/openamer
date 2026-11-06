"""DIR-16 — evaluate the directives and propose mutations when blocked.

The directive says the system evaluates the efficiency of these protocols and
mutates them autonomously when blocked. Two halves, and this module is
deliberately only the first one *and* the proposal:

* ``evaluate`` reads the ``agent.directive_engine`` audit and turns each
  directive into a verdict — is it backed by code, does its check pass, is it
  blocked?
* ``propose`` derives one mutation per blocked directive.

It does **not** rewrite the constitution. A module that silently edits its own
governing rules is not self-legislation, it is an unauditable side effect: the
next reader cannot tell which rules the system chose and which it inherited.
Proposals are data, they carry a rationale, and applying one is a separate,
visible act.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from agent.directive_engine import ENFORCED, GATED, NOT_IMPLEMENTED, PARTIAL, RESEARCH

REPAIR = "REPAIR"
IMPLEMENT = "IMPLEMENT"
RETIRE = "RETIRE"

#: Directives whose stated mechanism is not reachable by code in this install.
#:
#: Empty by default, and that is the measured state: every one of the 24 now has
#: code, and the three that used to live here (DIR-10/14/15) are ``GATED`` — the
#: hardware is missing, not the implementation, so retiring them would throw away
#: code that starts working the day the lab/fabricator/vehicle arrives. A caller
#: may still pass its own map when a directive really is beyond code.
NOT_CODE_REACHABLE: Dict[str, str] = {}


@dataclass(frozen=True)
class Verdict:
    directive_id: str
    status: str
    blocked: bool
    reason: str


@dataclass(frozen=True)
class Proposal:
    directive_id: str
    action: str
    rationale: str


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


def propose(audit_result: dict, not_code_reachable: Optional[Dict[str, str]] = None) -> List[Proposal]:
    """One proposal per blocked directive, ordered by id.

    ``REPAIR`` beats ``RETIRE``: a directive whose code exists but whose check
    fails is a bug, not a dead idea, and deleting it would hide the bug.
    """
    unreachable = NOT_CODE_REACHABLE if not_code_reachable is None else not_code_reachable
    proposals: List[Proposal] = []

    for verdict in evaluate(audit_result):
        row = next((r for r in audit_result.get("rows", []) if r["id"] == verdict.directive_id), None)
        checked_failed = row is not None and row.get("checked") is False

        if not verdict.blocked and not checked_failed:
            continue
        if checked_failed:
            proposals.append(
                Proposal(
                    verdict.directive_id,
                    REPAIR,
                    f"code exists but its check fails ({verdict.reason}) — repair the "
                    "mechanism before reconsidering the directive",
                )
            )
            continue
        reason = unreachable.get(verdict.directive_id)
        if reason:
            proposals.append(
                Proposal(
                    verdict.directive_id,
                    RETIRE,
                    f"not reachable by code in this install: {reason}",
                )
            )
        else:
            proposals.append(
                Proposal(
                    verdict.directive_id,
                    IMPLEMENT,
                    "no code backs this directive yet and nothing makes it "
                    "unreachable — implement the mechanism or state why not",
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
