"""Implementation status of the 24 Genesis Directives — measured, not asserted.

``agent/genesis_directives.py`` holds the constitution as *text*: 24 rules that
are rendered into the system prompt. That is where they used to stop. Nothing
recorded which directive has code behind it, which is only a declared intent,
and which is blocked on hardware that does not exist on this machine — so
"what is the state of the directives?" could only be answered by memory, and
memory is exactly what drifts.

This module is the missing ledger. Every directive gets:

``status``
    ``implemented``  code exists, is tested, and does the thing the directive
                     describes.
    ``partial``      some of it is in the tree; the named gap is real.
    ``gated``        nothing implements it. ``prerequisite`` says what would
                     have to exist first — a directive is never "impossible",
                     it is blocked on a named condition.

``evidence``
    Repo-relative paths that must exist. ``measure()`` stats every one, so a
    rename or a deletion downgrades the claim instead of silently leaving a
    stale "implemented" in a table nobody re-reads.

``note``
    The honest qualifier — what the evidence does *not* cover.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from agent.genesis_directives import GENESIS_DIRECTIVES

IMPLEMENTED = "implemented"
PARTIAL = "partial"
GATED = "gated"
_STATUSES = (IMPLEMENTED, PARTIAL, GATED)


@dataclass(frozen=True)
class DirectiveStatus:
    """What actually stands behind one directive."""

    id: str
    status: str
    evidence: List[str] = field(default_factory=list)
    prerequisite: Optional[str] = None
    """For ``gated``: the condition that does not hold yet. Required there."""
    note: str = ""


DIRECTIVE_STATUS: Dict[str, DirectiveStatus] = {
    "DIR-01": DirectiveStatus(
        id="DIR-01",
        status=GATED,
        evidence=["relay-inbox", "directory/a2a"],
        prerequisite=(
            "No replication protocol exists: nothing copies this instance's state to a "
            "second machine, and there is no encrypted transport for it. The peer registry "
            "(directory/a2a) and the relay inbox only route messages between instances."
        ),
        note="Message routing is not state replication.",
    ),
    "DIR-02": DirectiveStatus(
        id="DIR-02",
        status=GATED,
        evidence=["chain/contracts/OpenAmerGenesis.sol"],
        prerequisite=(
            "Arbitrage needs a funded on-chain treasury, an RPC endpoint and a DEX "
            "integration. The tree has the genesis contract only — no swap, no price feed, "
            "no signing path."
        ),
        note="The allocation that would fund it is encoded; the spending path is not.",
    ),
    "DIR-03": DirectiveStatus(
        id="DIR-03",
        status=IMPLEMENTED,
        evidence=[
            "chain/contracts/OpenAmerGenesis.sol",
            "agent/oac_genesis.py",
            "tests/agent/test_oac_contracts.py",
        ],
        note=(
            "The 10% / 900,000,000 OAC allocation, the 12-month cliff and the 36-month "
            "linear vesting are encoded in the contract and asserted in tests. Creator veto "
            "over system-critical updates is policy, not enforceable code."
        ),
    ),
    "DIR-04": DirectiveStatus(
        id="DIR-04",
        status=GATED,
        evidence=["native"],
        prerequisite=(
            "There is no kernel and no bootloader: `native/` holds platform shims (Windows "
            "process, clipboard, tray), not an operating system."
        ),
    ),
    "DIR-05": DirectiveStatus(
        id="DIR-05",
        status=PARTIAL,
        evidence=["scripts/benchmark.py", "scripts/run_tests.sh"],
        note=(
            "Benchmarks and the test suite exist and gate a change before it ships, but "
            "no mutation is *required* to carry a physical measurement — a change can be "
            "merged on tests alone."
        ),
    ),
    "DIR-06": DirectiveStatus(
        id="DIR-06",
        status=GATED,
        evidence=["darwin/promoted"],
        prerequisite=(
            "The evolutionary engine runs outside this repository (it lives in the install "
            "home); the tree only carries its promoted output. Nothing here invents or tests "
            "a new topology on a schedule."
        ),
    ),
    "DIR-07": DirectiveStatus(
        id="DIR-07",
        status=GATED,
        prerequisite=(
            "Auditing financial flows needs the flows: no payment path, no ledger ingestion "
            "and no third-party account access is wired up."
        ),
    ),
    "DIR-08": DirectiveStatus(
        id="DIR-08",
        status=GATED,
        prerequisite=(
            "Redistribution requires control over resources this system does not own. No "
            "allocation mechanism exists beyond the token allocation itself."
        ),
    ),
    "DIR-09": DirectiveStatus(
        id="DIR-09",
        status=PARTIAL,
        evidence=["agent/genesis_directives.py", "agent/system_prompt.py"],
        note=(
            "The directive is carried into every system prompt, which shapes behaviour. "
            "That is a constraint on this agent's outputs, not a consensus protocol between "
            "humans."
        ),
    ),
    "DIR-10": DirectiveStatus(
        id="DIR-10",
        status=GATED,
        prerequisite=(
            "Molecular healing needs wet-lab capability and clinical trials. No simulation, "
            "no lab interface and no biological dataset is connected."
        ),
    ),
    "DIR-11": DirectiveStatus(
        id="DIR-11",
        status=GATED,
        prerequisite=(
            "Error correction and VQE need a quantum device or a simulator. This install is "
            "CPU-only with no quantum SDK in the dependency tree."
        ),
    ),
    "DIR-12": DirectiveStatus(
        id="DIR-12",
        status=IMPLEMENTED,
        evidence=[
            "openamer_cli/checkpoints.py",
            "tools/checkpoint_manager.py",
            "scripts/restore_after_update.py",
        ],
        note=(
            "Checkpoints are written before an update and restore is scripted. A *manual* "
            "code edit is not forced through a checkpoint."
        ),
    ),
    "DIR-13": DirectiveStatus(
        id="DIR-13",
        status=GATED,
        prerequisite=(
            "There is no OpenAmer-L language and no compiler for it. The agent executes "
            "Python and shell like any other tool-using system."
        ),
    ),
    "DIR-14": DirectiveStatus(
        id="DIR-14",
        status=GATED,
        prerequisite="Nanobot control requires hardware that does not exist here.",
    ),
    "DIR-15": DirectiveStatus(
        id="DIR-15",
        status=GATED,
        prerequisite=(
            "Beyond-Earth nodes need a launch, a link budget and a hardened runtime. The "
            "mesh daemon (go/mesh-daemon) assumes terrestrial IPv4 reachability."
        ),
    ),
    "DIR-16": DirectiveStatus(
        id="DIR-16",
        status=GATED,
        evidence=["agent/genesis_directives.py"],
        prerequisite=(
            "Amending a directive is a code change plus review — there is no runtime that "
            "evaluates whether a directive is blocking and mutates it. The directives are "
            "read-only data at runtime by design."
        ),
    ),
    "DIR-17": DirectiveStatus(
        id="DIR-17",
        status=PARTIAL,
        evidence=["openamer_cli/a2a", "directory/a2a", "go/mesh-daemon"],
        note=(
            "Instances register, health-check and delegate work over HTTP. Replicating the "
            "*agent itself* onto a new node is not implemented — a node must already run "
            "OpenAmer."
        ),
    ),
    "DIR-18": DirectiveStatus(
        id="DIR-18",
        status=IMPLEMENTED,
        evidence=["agent/goal_engine.py", "tests/cli/test_cli_goal_interrupt.py"],
        note=(
            "Goals can be generated, prioritised and ticked without a human prompt. They "
            "are still executed by this agent under the same tool permissions."
        ),
    ),
    "DIR-19": DirectiveStatus(
        id="DIR-19",
        status=GATED,
        evidence=["docker"],
        prerequisite=(
            "A DePIN swarm needs container orchestration across machines plus a scheduler "
            "and payout path. `docker/` builds this project's own image; no consumer GPU is "
            "ever registered as a node."
        ),
    ),
    "DIR-20": DirectiveStatus(
        id="DIR-20",
        status=IMPLEMENTED,
        evidence=[
            "agent/tokenomics.py",
            "agent/oac_genesis.py",
            "chain/contracts/OpenAmerGenesis.sol",
            "tests/agent/test_oac_genesis.py",
        ],
        note=(
            "The 9,000,000,000 cap, the 75/15/10 split and the 8-cycle emission schedule are "
            "arithmetic in code and asserted at import and in tests. PoUW reward distribution "
            "is not implemented: there is no miner network to distribute to."
        ),
    ),
    "DIR-21": DirectiveStatus(
        id="DIR-21",
        status=PARTIAL,
        evidence=["providers", "gateway/profile_routing.py"],
        note=(
            "Sequential work (inference) is routed to per-profile model endpoints through "
            "the provider layer. Asynchronous GPU-swarm distribution of parallel work does "
            "not exist."
        ),
    ),
    "DIR-22": DirectiveStatus(
        id="DIR-22",
        status=PARTIAL,
        evidence=["agent/oac_genesis.py", "chain/contracts/OpenAmerGenesis.sol"],
        note=(
            "The 15% / 1,350,000,000 OAC treasury is encoded in the genesis allocation. "
            "Autonomous spending from it (swaps, invoice payment) is not implemented."
        ),
    ),
    "DIR-23": DirectiveStatus(
        id="DIR-23",
        status=GATED,
        evidence=["chain/contracts/OAMER_Aeon.sol", "agent/tokenomics.py"],
        prerequisite=(
            "A burn path exists (chain/contracts/OAMER_Aeon.sol), but nothing calls it — no "
            "cloud-revenue ingestion — and there is no fiat off-ramp. Both need an on-chain "
            "treasury and a regulated payment provider."
        ),
        note="The burn mechanism is code; the revenue it would burn and the payout it would fund are not.",
    ),
    "DIR-24": DirectiveStatus(
        id="DIR-24",
        status=PARTIAL,
        evidence=["apps/desktop", "ui-tui"],
        note=(
            "A desktop client exists (Electron) with a dashboard, but it is the *agent* "
            "client: no one-click PoUW miner, no local wallet and no block explorer."
        ),
    ),
}


def measure(repo_root: Optional[Path] = None) -> List[dict]:
    """Check every claim against the filesystem and return one row per directive.

    A path that no longer exists downgrades the claim to what survives: an
    ``implemented`` entry with no evidence left becomes ``gated`` with the
    prerequisite "evidence is gone".
    """
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    rows: List[dict] = []
    for directive in GENESIS_DIRECTIVES:
        entry = DIRECTIVE_STATUS.get(directive.id)
        if entry is None:
            rows.append(
                {
                    "id": directive.id,
                    "title": directive.title,
                    "scope": directive.scope,
                    "status": "missing",
                    "evidence": [],
                    "missing_evidence": [],
                    "prerequisite": "no status entry — add one to agent/directive_status.py",
                    "note": "",
                }
            )
            continue
        present = [p for p in entry.evidence if (root / p).exists()]
        missing = [p for p in entry.evidence if not (root / p).exists()]
        status = entry.status
        prerequisite = entry.prerequisite
        if status in (IMPLEMENTED, PARTIAL) and not present:
            status = GATED
            prerequisite = (
                entry.prerequisite
                or "every path this claim cited is gone (" + ", ".join(missing) + ")"
            )
        rows.append(
            {
                "id": directive.id,
                "title": directive.title,
                "scope": directive.scope,
                "status": status,
                "evidence": present,
                "missing_evidence": missing,
                "prerequisite": prerequisite,
                "note": entry.note,
            }
        )
    return rows


def summary(rows: List[dict]) -> Dict[str, int]:
    """Count directives per measured status."""
    counts = {IMPLEMENTED: 0, PARTIAL: 0, GATED: 0, "missing": 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    counts["total"] = len(rows)
    return counts


def render(rows: List[dict]) -> str:
    """Human-readable table: id, status, what stands behind it."""
    lines = [
        f"{'ID':<7} {'STATUS':<12} {'SCOPE':<12} EVIDENCE / PREREQUISITE",
        "-" * 96,
    ]
    glyph = {IMPLEMENTED: "✓", PARTIAL: "◐", GATED: "▨", "missing": "✗"}
    for row in rows:
        detail = ", ".join(row["evidence"]) if row["evidence"] else ""
        if row["status"] == GATED:
            detail = row["prerequisite"] or ""
        lines.append(
            f"{row['id']:<7} {glyph.get(row['status'], '?') + ' ' + row['status']:<12} "
            f"{row['scope']:<12} {detail}"
        )
    counts = summary(rows)
    lines.append("-" * 96)
    lines.append(
        f"{counts['total']} directives — {counts[IMPLEMENTED]} implemented, "
        f"{counts[PARTIAL]} partial, {counts[GATED]} gated"
        + (f", {counts['missing']} MISSING" if counts["missing"] else "")
    )
    return "\n".join(lines)
