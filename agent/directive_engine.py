"""Which Genesis directives have a real mechanism behind them — measured.

The constitution lives in ``agent/genesis_directives.py`` and states *intent*.
That file is deliberately careful about the distinction, and so is this one:
a directive in a prompt is not a capability. This module is the other half of
the pair — for every ``DIR-`` id it names the code that implements it and how
far that implementation goes, and it refuses to claim more than an existing
file plus a passing check can prove.

Why it exists: "is DIR-19 in the system?" cannot be answered by grepping the
constitution, because the constitution mentions every id by definition. It has
to be answered against the implementation, per id, with a path. Two failure
modes this prevents, both seen while writing it:

  * Claiming a directive is implemented because a keyword matched somewhere.
    A tight ``defi|arbitrage|uniswap|mempool`` search over the whole tree
    returns exactly one file: the constitution itself.
  * Silently dropping a directive. Every id from DIR-01 to DIR-24 must be
    present here, and the test fails on a missing one.

Levels, weakest to strongest:

  ``NOT_IMPLEMENTED``  no code outside the constitution. An honest gap.
  ``RESEARCH``         a research/experiment script explores the idea.
  ``GATED``            the code is there and complete for its half, but it
                       cannot act without hardware this host does not have
                       (a lab, a fabricator, a launch vehicle). It refuses and
                       names the missing piece rather than pretending.
  ``PARTIAL``          a real module implements part of it; not autonomous.
  ``ENFORCED``         real module *and* a check that passes right now.

Only ``ENFORCED`` is a claim about behaviour. Everything else says what is
missing, on purpose: a directive that overstates itself is worse than a
directive that admits a gap, because the gap is what gets worked on.

Usage::

    python -m agent.directive_engine            # the table
    python -m agent.directive_engine --gaps     # only what has no code
    python -m agent.directive_engine --json     # machine-readable
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from agent import tokenomics as _tok
from agent.genesis_directives import GENESIS_DIRECTIVES

NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
RESEARCH = "RESEARCH"
GATED = "GATED"
PARTIAL = "PARTIAL"
ENFORCED = "ENFORCED"

_ORDER = {NOT_IMPLEMENTED: 0, RESEARCH: 1, GATED: 2, PARTIAL: 3, ENFORCED: 4}

#: Repository root of the tracked tree, used to resolve evidence paths.
_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Prefix for evidence that lives in the installation, not the tracked tree.
#: The Rust kernel/bootloader tree (``os/``) ships in the install only, so a
#: bare checkout cannot see it. Prefixing keeps the claim honest in both
#: directions: it is still checked (against ``$OPENAMER_HOME``) and, when that
#: is unset, it is reported as unverified instead of silently counting as fine.
HOME_PREFIX = "home:"


@dataclass(frozen=True)
class Implementation:
    """What code backs one directive, and how far that code goes."""

    directive_id: str
    status: str
    evidence: List[str] = field(default_factory=list)
    """Module paths relative to the repo root that implement the directive."""

    note: str = ""
    """What is actually there — and what is not. No adjectives."""

    check: Optional[Callable[[], Optional[bool]]] = None
    """Measurable proof for ``ENFORCED``. Must pass now, not in principle.

    Returns None when this tree cannot judge it (install-side evidence with no
    ``$OPENAMER_HOME``). ``None`` is deliberately distinct from ``False``: "I
    cannot see it" is not "it is broken", and collapsing the two would either
    fake a failure or hide a real one.
    """


def _tokenomics_balance() -> bool:
    """DIR-20: the allocation must still close at exactly 100% of the cap."""
    total = sum(a.amount for a in _tok.ALLOCATIONS.values())
    return total == _tok.MAX_SUPPLY == 9_000_000_000


def _creator_share() -> bool:
    """DIR-03: creator allocation is exactly 10% / 900,000,000 OAC."""
    return _tok.amount(10) == 900_000_000 and _tok.share("creator").percent == 10


def _treasury_share() -> bool:
    """DIR-22: sovereign treasury is exactly 15% / 1,350,000,000 OAC."""
    return _tok.amount(15) == 1_350_000_000


def _emission_schedule() -> bool:
    """DIR-20: 32 years over 8 halving cycles of 4 years each."""
    return (_tok.EMISSION_YEARS, _tok.HALVING_CYCLES, _tok.HALVING_YEARS) == (32, 8, 4)


def _kernel_tree_present() -> Optional[bool]:
    """DIR-04: a Rust kernel + bootloader tree exists (not just a mention).

    This check can only ever *confirm* presence. Absence returns None, not
    False, and that distinction is load-bearing: the test runner points
    $OPENAMER_HOME at a temp directory for isolation, so "the kernel is not in
    that temp dir" is a fact about the harness, not about the directive. A
    check that reported False there would manufacture a failure in every
    isolated run -- measured: it did, until this became tri-state.
    """
    kernel = _resolve(f"{HOME_PREFIX}os/kernel/Cargo.toml")
    boot = _resolve(f"{HOME_PREFIX}os/bootloader/Cargo.toml")
    if kernel is None or boot is None:
        return None  # not visible from this tree -- unverified, not broken
    return True


IMPLEMENTATIONS: Dict[str, Implementation] = {
    "DIR-01": Implementation(
        "DIR-01", PARTIAL,
        ["scripts/global-sync.py", "scripts/auto-backup.py"],
        "Multi-machine delta sync and scheduled backups exist. No encrypted "
        "decentralised replication protocol, and the backup target is one host.",
    ),
    "DIR-02": Implementation(
        "DIR-02", PARTIAL,
        ["agent/defi_arbitrage.py"],
        "Cycle detection and sizing over constant-product quotes, priced hop by "
        "hop so fees and slippage decide profitability. No venue, no keys, no "
        "execution -- it reports an opportunity, it does not take one.",
    ),
    "DIR-03": Implementation(
        "DIR-03", ENFORCED,
        ["agent/tokenomics.py", "agent/oac_genesis.py"],
        "Creator allocation is a computed constant (10% / 900,000,000 OAC), not "
        "prose. The wallet binding, cliff and vesting exist as genesis-block "
        "parameters; no chain executes them yet.",
        check=_creator_share,
    ),
    "DIR-04": Implementation(
        "DIR-04", PARTIAL,
        [f"{HOME_PREFIX}os/kernel/Cargo.toml", f"{HOME_PREFIX}os/bootloader/Cargo.toml"],
        "A Rust kernel and bootloader tree with its own Cargo workspace. It "
        "boots; it is not a complete OS.",
        check=_kernel_tree_present,
    ),
    "DIR-05": Implementation(
        "DIR-05", PARTIAL,
        ["scripts/training/meta_learn.py"],
        "Benchmark and fitness gates exist and delete inefficient variants in "
        "the learning loops; they do not gate every mutation.",
    ),
    "DIR-06": Implementation(
        "DIR-06", RESEARCH,
        ["scripts/research_evo.py"],
        "Topology experiments run as scripts; nothing runs per-second.",
    ),
    "DIR-07": Implementation(
        "DIR-07", PARTIAL,
        ["agent/financial_audit.py"],
        "Flow audit: concentration (normalised HHI), round-trips, pass-throughs "
        "and unauditable transfers, each as a finding with numbers. It reports; "
        "it does not block or 'neutralise' a payment -- acting on suspicion "
        "stays outside.",
    ),
    "DIR-08": Implementation(
        "DIR-08", PARTIAL,
        ["agent/resource_fairness.py"],
        "Max-min fair allocation with a verifiable report (Gini, min/max share, "
        "unmet). The allocation is arithmetic; whether the *inputs* describe "
        "real need is not something this code can know.",
    ),
    "DIR-09": Implementation(
        "DIR-09", PARTIAL,
        ["agent/benefit_scoring.py"],
        "Weighted, reach-scaled, evidence-discounted scoring so two proposals "
        "are comparable and an unevidenced claim cannot outrank a measured one. "
        "It ranks; it does not decide what to fund.",
    ),
    "DIR-10": Implementation(
        "DIR-10", GATED,
        ["agent/bio_procedures.py", "agent/substrate.py"],
        "Protocol definitions with per-step instrument requirements, validated "
        "without a lab, and an execution path that refuses until the named "
        "instruments exist. No procedure here has been validated for use on a "
        "living organism.",
    ),
    "DIR-11": Implementation(
        "DIR-11", PARTIAL,
        ["agent/quantum_sim.py"],
        "Exact statevector simulator (<=12 qubits), Pauli expectation values and "
        "a deterministic VQE that provably reaches the brute-force minimum of "
        "the model. No noise model, no error correction, and a simulated energy "
        "says nothing about a physical device.",
    ),
    "DIR-12": Implementation(
        "DIR-12", PARTIAL,
        ["scripts/system-snapshot.py"],
        "Restore points are written before mutations; 'decentralised' is not "
        "satisfied (single host).",
    ),
    "DIR-13": Implementation(
        "DIR-13", PARTIAL,
        ["agent/will_layer.py"],
        "Intents are data that compile to fixed-width CPU register operations "
        "and actually run, with a 9-verb vocabulary and word masking. It is an "
        "op layer, not a language: no control flow, no types, and nothing here "
        "has a 'wish'.",
    ),
    "DIR-14": Implementation(
        "DIR-14", GATED,
        ["agent/matter_programming.py", "agent/substrate.py"],
        "Assembly specs (pattern, resolution, material) with representability "
        "checks and a feasibility verdict against a fabricator's real limits. "
        "Build refuses without the hardware; nothing is ever moved here.",
    ),
    "DIR-15": Implementation(
        "DIR-15", GATED,
        ["agent/galactic_nodes.py", "agent/substrate.py"],
        "Constellation planning with light-time latency per orbit, an "
        "interactive-RTT budget and a launch-envelope check. Deployment refuses "
        "without a launch capability; what this returns is a manifest.",
    ),
    "DIR-16": Implementation(
        "DIR-16", PARTIAL,
        ["agent/directive_legislation.py"],
        "Each directive is evaluated against this audit and blocked ones get a "
        "REPAIR/IMPLEMENT/RETIRE proposal with a rationale. Applying a proposal "
        "is a separate visible act; nothing rewrites the constitution itself.",
    ),
    "DIR-17": Implementation(
        "DIR-17", PARTIAL,
        ["scripts/a2a_server.py", "scripts/agent-mesh.py"],
        "Peer delegation and an agent mesh between hosts exist. No node manager "
        "that replicates this instance onto a new host by itself.",
    ),
    "DIR-18": Implementation(
        "DIR-18", PARTIAL,
        ["agent/goal_engine.py", "scripts/goal-engine.py"],
        "Self-generated goals with priorities and a tick loop. Initiated by a "
        "cron tick, not fully self-scheduling.",
    ),
    "DIR-19": Implementation(
        "DIR-19", PARTIAL,
        ["agent/depin_registry.py"],
        "Node registration, heartbeat freshness, capability routing and the "
        "PoUW reward weight exist and are tested. No container orchestration, "
        "no remote execution, no cross-host trust.",
    ),
    "DIR-20": Implementation(
        "DIR-20", ENFORCED,
        ["agent/tokenomics.py", "agent/oac_genesis.py"],
        "Max supply, the 75/15/10 split and the 32y/8x4 schedule are computed "
        "and asserted. No Rust chain, no ledger, no PoUW verifier.",
        check=_emission_schedule,
    ),
    "DIR-21": Implementation(
        "DIR-21", PARTIAL,
        ["scripts/swarm_os.py", "scripts/a2a_worker.py"],
        "Sequential work stays local, parallel work can be routed to a GPU "
        "worker over SSH. Not an automated splitter.",
    ),
    "DIR-22": Implementation(
        "DIR-22", ENFORCED,
        ["agent/tokenomics.py", "agent/oac_genesis.py"],
        "Treasury share is a computed constant (15% / 1,350,000,000 OAC) and "
        "the genesis block records it. No smart contract holds it.",
        check=_treasury_share,
    ),
    "DIR-23": Implementation(
        "DIR-23", PARTIAL,
        ["agent/tokenomics.py"],
        "The burn share is encoded as a constant; nothing burns a token because "
        "no token circulates.",
    ),
    "DIR-24": Implementation(
        "DIR-24", RESEARCH,
        ["apps/bootstrap-installer/src-tauri/Cargo.toml"],
        "A Tauri desktop app exists, but it installs OpenAmer — it is not the "
        "OpenAmer-Node miner/wallet/explorer.",
    ),
}


def _resolve(path: str) -> Optional[Path]:
    """Resolve an evidence path, or None when this tree cannot see it.

    ``home:``-prefixed paths resolve against ``$OPENAMER_HOME`` only — never by
    guessing a platform layout, because a guessed root that happens to exist is
    how a claim starts pointing at the wrong file.
    """
    if path.startswith(HOME_PREFIX):
        home = os.environ.get("OPENAMER_HOME", "").strip()
        if not home:
            return None
        candidate = Path(home) / path[len(HOME_PREFIX):]
        return candidate if candidate.exists() else None
    candidate = _REPO_ROOT / path
    return candidate if candidate.exists() else None


def _evidence_state(path: str) -> str:
    """``ok`` | ``missing`` (claimed, wrong) | ``unverified`` (not visible here)."""
    if _resolve(path) is not None:
        return "ok"
    return "unverified" if path.startswith(HOME_PREFIX) else "missing"


def audit() -> dict:
    """Coverage per directive, plus any claim whose evidence does not resolve.

    ``violations`` is the load-bearing part: an ``ENFORCED``/``PARTIAL`` claim
    pointing at a path that no longer exists is exactly the kind of drift that
    turns a status page into decoration.
    """
    constitution_ids = [d.id for d in GENESIS_DIRECTIVES]
    missing = [i for i in constitution_ids if i not in IMPLEMENTATIONS]
    extra = [i for i in IMPLEMENTATIONS if i not in constitution_ids]

    violations = []
    unverified_total: List[str] = []
    rows = []
    for did in constitution_ids:
        impl = IMPLEMENTATIONS.get(did)
        if impl is None:
            violations.append(f"{did}: no implementation entry")
            continue
        bad_evidence = [p for p in impl.evidence if _evidence_state(p) == "missing"]
        if bad_evidence:
            violations.append(f"{did}: evidence missing {bad_evidence}")
        unverified = [p for p in impl.evidence if _evidence_state(p) == "unverified"]
        if unverified:
            unverified_total.extend(f"{did}: {p}" for p in unverified)
        checked: Optional[bool] = None
        if impl.check is not None:
            try:
                raw = impl.check()
                checked = None if raw is None else bool(raw)
            except Exception as exc:  # a broken check is a finding, not a crash
                checked = False
                violations.append(f"{did}: check raised {type(exc).__name__}: {exc}")
            if checked is False:
                violations.append(f"{did}: its check fails")
        rows.append(
            {
                "id": did,
                "status": impl.status,
                "evidence": impl.evidence,
                "checked": checked,
                "note": impl.note,
            }
        )

    if missing:
        violations.append(f"no entry for: {missing}")
    if extra:
        violations.append(f"entry without directive: {extra}")

    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    return {
        "directives": len(constitution_ids),
        "counts": counts,
        "rows": rows,
        "violations": violations,
        "unverified": unverified_total,
        "home_root": os.environ.get("OPENAMER_HOME", ""),
    }


def _print_table(result: dict, gaps_only: bool = False) -> None:
    order = sorted(result["rows"], key=lambda r: (_ORDER[r["status"]], r["id"]))
    print(f"Genesis directives: {result['directives']}")
    print("  " + ", ".join(f"{k}={v}" for k, v in sorted(
        result["counts"].items(), key=lambda kv: _ORDER[kv[0]])))
    print()
    for row in order:
        if gaps_only and row["status"] != NOT_IMPLEMENTED:
            continue
        flag = ""
        if row["checked"] is True:
            flag = " [check OK]"
        elif row["checked"] is False:
            flag = " [check FAILED]"
        print(f"{row['id']}  {row['status']:<15}{flag}")
        if row["evidence"]:
            print(f"            evidence: {', '.join(row['evidence'])}")
        print(f"            {row['note']}")
    if result.get("unverified"):
        print(
            f"\nUNVERIFIED ({len(result['unverified'])}): claimed in the install, "
            "not visible from this tree (set $OPENAMER_HOME to check them)"
        )
        for u in result["unverified"]:
            print(f"  - {u}")
    if result["violations"]:
        print("\nVIOLATIONS (a claim that does not hold):")
        for v in result["violations"]:
            print(f"  - {v}")


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    result = audit()
    if "--json" in argv:
        print(json.dumps(result, indent=2))
    else:
        _print_table(result, gaps_only="--gaps" in argv)
    return 1 if result["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
