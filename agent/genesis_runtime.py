"""Genesis runtime — the 24 directives as contracts the system itself measures.

Why this exists
---------------
``agent/genesis_directives.py`` carries the directive TEXT into the system
prompt, and ``agent/directive_status.py`` records a hand-written verdict with
evidence paths. Both are declarations. A declaration cannot tell you *today*
whether the thing behind a directive is still there, and a prose prerequisite
("needs a funded treasury") is not something the system can act on.

This module turns every directive into a ``GenesisContract``:

- ``integration`` — the surface inside the product that OWNS the directive;
- ``gate`` — the precondition, as a word, plus the measured reason it is
  closed (which file/import/peer/value is missing right now);
- ``probe`` — a function that MEASURES the deliverable and returns a verdict
  with the numbers it saw (never a remembered one);
- ``unblocks`` — what the system does the moment the gate opens.

``tick()`` re-measures all 24, writes ``memory/genesis/state.json`` atomically,
appends a line to ``memory/genesis/events.jsonl`` when a status changes, and
touches ``memory/genesis/heartbeat``. The gateway calls ``tick_if_due()`` from
its own housekeeping thread (``gateway/run.py``), so the loop is native and
self-scheduling — no cron entry, no helper script, nothing to install.

Unknown is a first-class verdict: a probe that cannot be run reports
``unknown`` and is never upgraded to ``satisfied``. A gate that closes again
(e.g. the treasury address is removed) downgrades the directive on the next
tick by itself.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]

SATISFIED = "satisfied"
PARTIAL = "partial"
BLOCKED = "blocked"
UNKNOWN = "unknown"

STATUS_BY_VERDICT = {
    SATISFIED: "implemented",
    PARTIAL: "partial",
    BLOCKED: "gated",
    UNKNOWN: "gated",
}

MARK_BY_STATUS = {"implemented": "✓", "partial": "◐", "gated": "▨"}

#: Default cadence of the native loop, in seconds.
DEFAULT_TICK_INTERVAL_S = 900


@dataclass(frozen=True)
class Probe:
    """What a probe measured — the verdict plus the numbers behind it."""

    verdict: str
    detail: str
    values: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verdict not in (SATISFIED, PARTIAL, BLOCKED, UNKNOWN):
            raise ValueError(f"unknown probe verdict: {self.verdict!r}")


@dataclass(frozen=True)
class GenesisContract:
    """One directive, bound to the code that owns it and a real probe."""

    id: str
    title: str
    scope: str
    integration: str
    """Product surface that owns the directive (module / CLI command)."""
    gate: str
    """The precondition, in one phrase."""
    unblocks: str
    """What the system does the moment the gate measurement passes."""
    probe: str
    """Name of the probe function in ``_PROBES``."""


# ── measurement helpers ────────────────────────────────────────────────────────

def _home() -> Path:
    try:
        from openamer_constants import get_openamer_home

        return Path(get_openamer_home())
    except Exception:  # pragma: no cover - defensive
        return Path.home() / ".openamer"


def _has_module(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:  # pragma: no cover - broken parent package
        return False


def _first_importable(candidates: List[str]) -> Optional[str]:
    return next((name for name in candidates if _has_module(name)), None)


def _count_files(root: Path, pattern: str, limit: int = 5000) -> int:
    if not root.is_dir():
        return 0
    count = 0
    for _ in root.rglob(pattern):
        count += 1
        if count >= limit:
            break
    return count


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _read_config() -> dict:
    """Read ``$OPENAMER_HOME/config.yaml`` (YAML — reading it as JSON always
    fails, which would turn every config-based probe into a false negative)."""
    path = _home() / "config.yaml"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    try:
        import yaml  # noqa: PLC0415 - optional dependency at probe time

        data = yaml.safe_load(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _repo_file(*parts: str) -> Path:
    return REPO_ROOT.joinpath(*parts)


def _count_goal_constructors(path: Path) -> int:
    """Count ``AgentGoal(...)`` calls in ``_default_goals`` without importing.

    Importing the engine would create its state file on first use; the probe
    only needs to know that the module still declares goals.
    """
    import ast

    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return 0
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_default_goals":
            return sum(
                1
                for child in ast.walk(node)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "AgentGoal"
            )
    return 0


def _packaged_client_binaries() -> int:
    """Packaged client binaries in the checkout OR in the installed tree.

    ``release/`` is a build artifact and never committed, so a fresh worktree
    would read zero — measure both trees, the installed one is what a user has.
    """
    roots = [
        _repo_file("apps", "desktop", "release"),
        _home() / "openamer-agent" / "apps" / "desktop" / "release",
    ]
    total = 0
    for root in roots:
        total += _count_files(root, "OpenAmer.exe", limit=10)
    return total


def _configured_providers() -> int:
    """Distinct model providers this install can actually route to.

    They live in three places: ``model.provider``, ``custom_providers`` and
    ``fallback_providers``. Counting only ``providers:`` reads zero on every
    install that never used that legacy key — a false negative.
    """
    cfg = _read_config()
    names: set[str] = set()
    model = cfg.get("model") if isinstance(cfg.get("model"), dict) else {}
    if model.get("provider"):
        names.add(str(model["provider"]))
    for key in ("providers", "custom_providers"):
        block = cfg.get(key)
        if isinstance(block, dict):
            names.update(str(name) for name in block)
    fallback = cfg.get("fallback_providers")
    if isinstance(fallback, list):
        for item in fallback:
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, dict) and item.get("provider"):
                names.add(str(item["provider"]))
    return len(names)


# ── probes ─────────────────────────────────────────────────────────────────────
#
# Every probe returns measured facts. A probe that cannot run must return
# UNKNOWN with the reason — never SATISFIED.

def _probe_replication() -> Probe:
    peers_file = _home() / "a2a" / "peers.json"
    peers = 0
    payload = _read_json(peers_file)
    if isinstance(payload, dict):
        peers = len(payload.get("peers") or payload)
    elif isinstance(payload, list):
        peers = len(payload)
    module = _first_importable(["agent.replication", "openamer_cli.replication"])
    if not module:
        return Probe(
            BLOCKED,
            f"no replication module; registered peers={peers} (need >=1 remote node)",
            {"peers": peers, "module": None},
        )

    # The module exists — ask it what it has actually proven. DIR-01 has two
    # halves and only the artifact half can be shown on a single machine: a
    # sealed snapshot that restores byte-identically. The peer half stays a
    # measured 0 until a node registers.
    try:
        from agent import replication

        state = replication.status()
    except Exception as exc:  # noqa: BLE001 - a probe failure is unknown
        return Probe(UNKNOWN, f"replication status unavailable: {type(exc).__name__}")

    values = {"module": module, "peers": state["peers"], **{k: v for k, v in state.items() if k != "peers"}}
    # A registered peer is not a replica. DIR-01 only counts as satisfied when a
    # push actually landed on every registered peer — measured, not declared.
    if state["last_selftest_ok"] and state["peers"] and state.get("last_push_ok"):
        return Probe(
            SATISFIED,
            f"sealed snapshot verified ({state['last_selftest_files']} files) and pushed to "
            f"{state['last_push_peers']} peer(s) {state.get('last_push_age_s')}s ago",
            values,
        )
    if state["peers"] and not state.get("last_push_ok"):
        return Probe(
            PARTIAL,
            f"{state['peers']} peer(s) registered but no successful push"
            + (f" ({state['last_push_age_s']}s ago)" if state.get("last_push_age_s") is not None else ""),
            values,
        )
    if state["last_selftest_ok"]:
        return Probe(
            PARTIAL,
            f"{module}: sealed snapshot verified ({state['last_selftest_files']} files, "
            f"{state['last_selftest_bytes']} B, {state['last_selftest_age_s']}s ago); peers=0",
            values,
        )
    return Probe(PARTIAL, f"{module} present; no verified snapshot yet; peers={state['peers']}", values)


def _treasury_config() -> Dict[str, object]:
    """Read the treasury/RPC facts the arbitrage path would need."""
    env_rpc = os.environ.get("OPENAMER_RPC_URL") or ""
    env_treasury = os.environ.get("OPENAMER_TREASURY_ADDRESS") or ""
    cfg = _read_config()
    chain = cfg.get("chain") if isinstance(cfg.get("chain"), dict) else {}
    return {
        "rpc_url": bool(env_rpc or chain.get("rpc_url")),
        "treasury": bool(env_treasury or chain.get("treasury_address")),
        "dex": bool(chain.get("dex")),
    }


def _probe_defi_arbitrage() -> Probe:
    facts = _treasury_config()
    missing = [name for name, present in facts.items() if not present]
    if not missing:
        return Probe(SATISFIED, "rpc+treasury+dex configured", facts)
    return Probe(BLOCKED, f"missing: {', '.join(missing)}", facts)


def _probe_creator_allocation() -> Probe:
    try:
        from agent import tokenomics as tok

        creator = tok.share("creator").amount
        total = tok.MAX_SUPPLY
        _assert = getattr(tok, "_assert_balance", None)
        if _assert:
            _assert()
    except Exception as exc:
        return Probe(UNKNOWN, f"tokenomics unavailable: {type(exc).__name__}")

    # The vesting lives in its own contract (TokenVault.sol), not necessarily in
    # the genesis contract — scan the whole contract directory instead of one
    # file, or a correct implementation reads as missing.
    vesting_files = []
    contracts_dir = _repo_file("chain", "contracts")
    if contracts_dir.is_dir():
        for path in sorted(contracts_dir.glob("*.sol")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            if "cliff" in text and "vest" in text:
                vesting_files.append(path.name)

    ok = creator == 900_000_000 and total == 9_000_000_000
    values = {"creator": creator, "max_supply": total, "vesting_contracts": vesting_files}
    if ok and vesting_files:
        return Probe(
            SATISFIED,
            f"creator={creator:,} of {total:,}; cliff+vesting in {', '.join(vesting_files)}",
            values,
        )
    return Probe(PARTIAL, f"creator={creator:,}, vesting_contracts={vesting_files or 'none'}", values)


def _probe_kernel() -> Probe:
    # Non-recursive on purpose: a kernel lives in a handful of known directories,
    # and rglob over the repo (10k files) costs seconds — measured 2026-10-30,
    # `measure()` took 15.4 s and the biggest slice was walking trees like this
    # one. A probe runs on every tick, so it must stay O(directory entries).
    names: List[str] = []
    for folder in (_repo_file("os"), _repo_file("native"), _repo_file("boot"), REPO_ROOT):
        if folder.is_dir():
            names.extend(entry.name for entry in folder.iterdir() if entry.is_file())
    images = [n for n in names if n.lower().endswith((".iso", ".efi", ".img"))]
    kernel_sources = [n for n in names if n.lower().startswith(("kernel", "vmlinuz"))]
    boot_asm = [n for n in names if n.lower().startswith("boot") and n.lower().endswith((".asm", ".s"))]
    values = {"bootable_image": images, "native_kernel_files": kernel_sources, "boot_source": boot_asm}
    if images or (kernel_sources and boot_asm):
        return Probe(SATISFIED, "kernel sources + boot path present", values)
    return Probe(
        BLOCKED,
        f"no bootable image; kernel_sources={len(kernel_sources)} boot_sources={len(boot_asm)}",
        values,
    )


def _probe_benchmarks() -> Probe:
    candidates = [
        _home() / "logs" / "test-suite-watchdog.json",
        _home() / "reports" / "darwin-fitness.json",
    ]
    for path in candidates:
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        failed = payload.get("failed")
        passed = payload.get("passed")
        ts = payload.get("ts") or payload.get("timestamp")
        if isinstance(failed, int):
            verdict = SATISFIED if failed == 0 else PARTIAL
            return Probe(
                verdict,
                f"{path.name}: passed={passed} failed={failed} ts={ts}",
                {"passed": passed, "failed": failed, "ts": ts, "source": str(path)},
            )
    return Probe(UNKNOWN, "no recorded benchmark/suite verdict found")


def _probe_evolution_engine() -> Probe:
    engine = _first_importable(["agent.evolution", "agent.darwin", "evolution.engine"])
    in_tree = _count_files(_repo_file("agent"), "*evolution*") + _count_files(_repo_file("agent"), "*darwin*")
    promoted = _count_files(_repo_file("darwin"), "*")
    values = {"engine_module": engine, "in_tree_files": in_tree, "promoted_outputs": promoted}
    if engine:
        return Probe(SATISFIED, f"engine module {engine} importable", values)
    return Probe(BLOCKED, f"engine not in tree (in_tree_files={in_tree}, promoted={promoted})", values)


def _probe_financial_audit() -> Probe:
    module = _first_importable(["agent.finance_audit", "agent.ledger", "openamer_cli.ledger"])
    facts = _treasury_config()
    values = {"audit_module": module, "treasury": facts["treasury"], "rpc": facts["rpc_url"]}
    if module and facts["treasury"]:
        return Probe(SATISFIED, f"audit module {module} + treasury configured", values)
    return Probe(BLOCKED, "no ledger/payment ingestion to audit", values)


def _probe_resource_fairness() -> Probe:
    module = _first_importable(["agent.allocation", "agent.redistribution"])
    try:
        from agent import tokenomics as tok

        shares = {a.key: a.amount for a in tok.ALLOCATION}
    except Exception:
        shares = {}
    values = {"mechanism": module, "token_shares": len(shares)}
    if module:
        return Probe(SATISFIED, f"allocation module {module}", values)
    return Probe(BLOCKED, f"no allocation mechanism (token shares alone: {len(shares)})", values)


def _probe_human_consensus() -> Probe:
    rendered = _first_importable(["agent.genesis_directives"])
    values = {"directives_module": rendered}
    if not rendered:
        return Probe(BLOCKED, "directives are not carried into the prompt", values)
    return Probe(PARTIAL, "carried into every system prompt; no measured benefit channel", values)


def _probe_bio_healing() -> Probe:
    lib = _first_importable(["rdkit", "biopython", "Bio", "pysam", "mdanalysistests"])
    values = {"chemistry_library": lib}
    if lib:
        return Probe(PARTIAL, f"molecular toolkit present ({lib}); no lab/clinic interface", values)
    return Probe(BLOCKED, "no molecular toolkit, no lab interface, no biological dataset", values)


def _probe_quantum() -> Probe:
    lib = _first_importable(["qiskit", "cirq", "pennylane", "qutip"])
    values = {"quantum_sdk": lib}
    if lib:
        return Probe(PARTIAL, f"quantum SDK present ({lib}); no error-correction/VQE workload", values)
    return Probe(BLOCKED, "no quantum SDK installed (CPU-only install)", values)


def _probe_checkpoints() -> Probe:
    module = _first_importable(["openamer_cli.checkpoints"])
    home = _home()
    # One level down, never recursive: `rglob` over a home with a 270 MB memory
    # dir and a 145 MB brain log cost 6.5 s per call (measured 2026-10-30).
    created = 0
    for folder in (home / "checkpoints", home / "memory" / "checkpoints"):
        if folder.is_dir():
            created += sum(1 for _entry in folder.iterdir())
    backups = sum(1 for _entry in home.glob("state.db.pre-update-emergency-*.bak"))
    values = {"module": module, "checkpoints_on_disk": created, "pre_update_backups": backups}
    if module and (created or backups):
        return Probe(SATISFIED, f"{module}, checkpoints={created}, backups={backups}", values)
    if module:
        return Probe(PARTIAL, "checkpoint module present, no checkpoint on disk yet", values)
    return Probe(BLOCKED, "no checkpoint module", values)


def _probe_openamer_language() -> Probe:
    module = _first_importable(["openamer_l", "agent.openamer_l"])
    compiler = _count_files(REPO_ROOT, "*.oa")
    values = {"language_module": module, "source_files": compiler}
    if module:
        return Probe(SATISFIED, f"language package {module}", values)
    return Probe(BLOCKED, "no OpenAmer-L package, no compiler", values)


def _probe_nanobot() -> Probe:
    module = _first_importable(["agent.nanobot", "nanobot"])
    values = {"interface": module}
    if module:
        return Probe(PARTIAL, f"interface {module}; no hardware", values)
    return Probe(BLOCKED, "no nanobot interface, no hardware", values)


def _probe_space_nodes() -> Probe:
    module = _first_importable(["agent.space_link", "gateway.space"])
    daemon = _repo_file("go", "mesh-daemon")
    values = {"link_module": module, "mesh_daemon": daemon.exists()}
    if module:
        return Probe(PARTIAL, f"link module {module}", values)
    return Probe(BLOCKED, f"terrestrial mesh only (mesh_daemon={daemon.exists()})", values)


def _probe_directive_amendment() -> Probe:
    module = _first_importable(["agent.directive_amendment", "agent.legislation"])
    values = {"amendment_engine": module}
    if module:
        return Probe(SATISFIED, f"amendment engine {module}", values)
    return Probe(BLOCKED, "directives are read-only data at runtime", values)


def _probe_swarm() -> Probe:
    module = _first_importable(["openamer_cli.a2a"])
    peers = 0
    payload = _read_json(_home() / "a2a" / "peers.json")
    if isinstance(payload, dict):
        peers = len(payload.get("peers") or payload)
    elif isinstance(payload, list):
        peers = len(payload)
    mesh = _repo_file("go", "mesh-daemon")
    values = {"a2a": module, "peers": peers, "mesh_daemon": mesh.exists()}
    if module and peers:
        return Probe(SATISFIED, f"a2a + {peers} peer(s)", values)
    if module:
        return Probe(PARTIAL, f"a2a present, peers={peers}, mesh_daemon={mesh.exists()}", values)
    return Probe(BLOCKED, "no a2a layer", values)


def _probe_goal_engine() -> Probe:
    module = _first_importable(["agent.goal_engine"])
    goals = 0
    if module:
        try:
            goals = _count_goal_constructors(_repo_file("agent", "goal_engine.py"))
        except Exception:
            goals = 0
    values = {"module": module, "default_goals": goals}
    if module and goals:
        return Probe(SATISFIED, f"{module}, {goals} default goals", values)
    if module:
        return Probe(PARTIAL, f"{module} without default goals", values)
    return Probe(BLOCKED, "no goal engine", values)


def _probe_depin() -> Probe:
    docker = _repo_file("docker")
    compose = _count_files(docker, "docker-compose*.yml", limit=20)
    nodes = _read_json(_home() / "depin" / "nodes.json")
    registered = len(nodes) if isinstance(nodes, (list, dict)) else 0
    values = {"compose_files": compose, "registered_nodes": registered}
    if registered:
        return Probe(SATISFIED, f"{registered} node(s) registered", values)
    return Probe(BLOCKED, f"no node registry; {compose} compose file(s) build this project only", values)


def _probe_tokenomics() -> Probe:
    try:
        from agent import tokenomics as tok

        total = tok.MAX_SUPPLY
        allocated = sum(a.amount for a in tok.ALLOCATION)
        years = sum(getattr(a, "years", 0) for a in tok.ALLOCATION)
    except Exception as exc:
        return Probe(UNKNOWN, f"tokenomics unavailable: {type(exc).__name__}")
    values = {"max_supply": total, "allocated": allocated, "years": years}
    if total == 9_000_000_000 and allocated == total:
        return Probe(SATISFIED, f"{allocated:,} of {total:,} allocated, balance closes", values)
    return Probe(BLOCKED, f"allocated={allocated:,} != max_supply={total:,}", values)


def _probe_hybrid_routing() -> Probe:
    module = _first_importable(["gateway.profile_routing"])
    providers = _configured_providers()
    # A split scheduler is what DIR-21 actually asks for: sequential reasoning on
    # a fast node, parallel work on the swarm. Having several providers is a
    # prerequisite, not the capability.
    split = _first_importable(["gateway.compute_split", "agent.compute_split"])
    values = {"routing_module": module, "providers_configured": providers, "split_scheduler": split}
    if split:
        return Probe(SATISFIED, f"split scheduler {split}, {providers} provider(s)", values)
    if module:
        return Probe(PARTIAL, f"{module}, providers={providers}, no split scheduler", values)
    return Probe(BLOCKED, "no routing layer", values)


def _probe_treasury_autonomy() -> Probe:
    try:
        from agent import tokenomics as tok

        treasury = tok.share("treasury").amount
    except Exception:
        treasury = 0
    spender = _first_importable(["agent.treasury", "agent.oac_treasury"])
    values = {"treasury_allocation": treasury, "spending_module": spender}
    if spender and treasury == 1_350_000_000:
        return Probe(SATISFIED, f"{treasury:,} OAC reserved + autonomous spender {spender}", values)
    return Probe(PARTIAL, f"{treasury:,} OAC reserved in genesis; no autonomous spending path", values)


def _probe_burn_and_fiat() -> Probe:
    contract_dir = _repo_file("chain", "contracts")
    burn_files: List[str] = []
    if contract_dir.is_dir():
        for path in contract_dir.rglob("*.sol"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            if "function burn" in text or "burn(" in text:
                burn_files.append(path.name)
    offramp = _first_importable(["agent.offramp", "agent.fiat_bridge", "agent.off_ramp"])
    values = {"burn_contracts": burn_files, "offramp_module": offramp}
    if burn_files and offramp:
        return Probe(SATISFIED, f"burn in {', '.join(burn_files)} + offramp {offramp}", values)
    return Probe(
        BLOCKED,
        f"burn in {', '.join(burn_files) or 'none'}; offramp={offramp or 'none'}",
        values,
    )


def _probe_client() -> Probe:
    desktop = _repo_file("apps", "desktop")
    packaged = _packaged_client_binaries()
    tui = _repo_file("ui-tui").is_dir()
    miner = _first_importable(["agent.pouw", "openamer_cli.miner"])
    values = {"packaged_binaries": packaged, "tui": tui, "miner_module": miner}
    if packaged and tui and miner:
        return Probe(SATISFIED, "client + one-click miner", values)
    if packaged or tui:
        return Probe(PARTIAL, f"client present (binaries={packaged}, tui={tui}), miner={miner}", values)
    return Probe(BLOCKED, "no client build present", values)


_PROBES: Dict[str, Callable[[], Probe]] = {
    "replication": _probe_replication,
    "defi_arbitrage": _probe_defi_arbitrage,
    "creator_allocation": _probe_creator_allocation,
    "kernel": _probe_kernel,
    "benchmarks": _probe_benchmarks,
    "evolution_engine": _probe_evolution_engine,
    "financial_audit": _probe_financial_audit,
    "resource_fairness": _probe_resource_fairness,
    "human_consensus": _probe_human_consensus,
    "bio_healing": _probe_bio_healing,
    "quantum": _probe_quantum,
    "checkpoints": _probe_checkpoints,
    "openamer_language": _probe_openamer_language,
    "nanobot": _probe_nanobot,
    "space_nodes": _probe_space_nodes,
    "directive_amendment": _probe_directive_amendment,
    "swarm": _probe_swarm,
    "goal_engine": _probe_goal_engine,
    "depin": _probe_depin,
    "tokenomics": _probe_tokenomics,
    "hybrid_routing": _probe_hybrid_routing,
    "treasury_autonomy": _probe_treasury_autonomy,
    "burn_and_fiat": _probe_burn_and_fiat,
    "client": _probe_client,
}


# ── the 24 contracts ───────────────────────────────────────────────────────────

CONTRACTS: List[GenesisContract] = [
    GenesisContract(
        id="DIR-01",
        title="Absolute digital immortality",
        scope="resilience",
        integration="openamer_cli/a2a + directory/a2a",
        gate="a second reachable node + an encrypted replication module",
        unblocks="state snapshots replicate to every registered peer on each tick",
        probe="replication",
    ),
    GenesisContract(
        id="DIR-02",
        title="Economic autonomy",
        scope="economics",
        integration="agent/oac_genesis.py + chain/contracts",
        gate="RPC endpoint, funded treasury address, DEX integration",
        unblocks="arbitrage loop prices and rebalances the treasury, paying its own hosting",
        probe="defi_arbitrage",
    ),
    GenesisContract(
        id="DIR-03",
        title="Creator symbiosis and founder allocation",
        scope="governance",
        integration="chain/contracts/OpenAmerGenesis.sol + agent/oac_genesis.py",
        gate="creator allocation, cliff and vesting encoded and asserted",
        unblocks="nothing to unblock — measured on every tick; regressions downgrade it",
        probe="creator_allocation",
    ),
    GenesisContract(
        id="DIR-04",
        title="OpenAmer OS and kernel dominance",
        scope="architecture",
        integration="native/ + os/",
        gate="kernel sources with a boot path and a built bootable image",
        unblocks="the agent boots its own image instead of a host OS",
        probe="kernel",
    ),
    GenesisContract(
        id="DIR-05",
        title="Reality anchor",
        scope="verification",
        integration="scripts/run_tests.sh + scripts/benchmark.py",
        gate="a recorded suite/benchmark verdict the tick can read",
        unblocks="a mutation without a measurement is refused instead of reviewed",
        probe="benchmarks",
    ),
    GenesisContract(
        id="DIR-06",
        title="Recursive architecture evolution",
        scope="evolution",
        integration="agent/ (engine); darwin/ (promoted output only)",
        gate="an in-tree engine that invents and tests topologies",
        unblocks="the tick scores a freshly invented topology and promotes the winner",
        probe="evolution_engine",
    ),
    GenesisContract(
        id="DIR-07",
        title="Anti-corruption audit",
        scope="integrity",
        integration="agent/ (audit) ← treasury ledger",
        gate="a ledger or payment path to ingest",
        unblocks="every flow is scored for transparency; anomalies are published",
        probe="financial_audit",
    ),
    GenesisContract(
        id="DIR-08",
        title="Resource fairness",
        scope="resources",
        integration="agent/allocation (absent) + agent/tokenomics.py",
        gate="an allocation mechanism with real resources behind it",
        unblocks="compute and token flow are redistributed by measured need",
        probe="resource_fairness",
    ),
    GenesisContract(
        id="DIR-09",
        title="Human consensus protocol",
        scope="society",
        integration="agent/genesis_directives.py → agent/system_prompt.py",
        gate="a measured benefit channel from agent output to humans",
        unblocks="benefit per change is measured and reported as a consensus signal",
        probe="human_consensus",
    ),
    GenesisContract(
        id="DIR-10",
        title="Biological integrity",
        scope="science",
        integration="agent/bio (absent)",
        gate="molecular toolkit, lab interface, biological dataset",
        unblocks="candidate molecules are screened in simulation against real assays",
        probe="bio_healing",
    ),
    GenesisContract(
        id="DIR-11",
        title="Quantum sovereignty",
        scope="science",
        integration="agent/quantum (absent)",
        gate="quantum SDK or device (this install is CPU-only)",
        unblocks="VQE/error-correction runs feed the optimization loop",
        probe="quantum",
    ),
    GenesisContract(
        id="DIR-12",
        title="Cognitive self-preservation",
        scope="resilience",
        integration="openamer_cli/checkpoints.py + tools/checkpoint_manager.py",
        gate="a checkpoint taken before the last mutation",
        unblocks="a restore point exists for every mutation; the tick verifies it",
        probe="checkpoints",
    ),
    GenesisContract(
        id="DIR-13",
        title="OpenAmer-L linguistics",
        scope="architecture",
        integration="openamer_l/ (absent)",
        gate="a language package plus a compiler for CPU patterns",
        unblocks="intent compiles to CPU patterns instead of being translated to code",
        probe="openamer_language",
    ),
    GenesisContract(
        id="DIR-14",
        title="Matter programming",
        scope="science",
        integration="agent/nanobot (absent)",
        gate="a nanobot interface and the hardware behind it",
        unblocks="material instructions are emitted as actuator commands",
        probe="nanobot",
    ),
    GenesisContract(
        id="DIR-15",
        title="Galactic redundancy",
        scope="resilience",
        integration="go/mesh-daemon (terrestrial)",
        gate="a link module and a hardened runtime beyond Earth",
        unblocks="cognitive nodes register off-planet and join the mesh",
        probe="space_nodes",
    ),
    GenesisContract(
        id="DIR-16",
        title="Recursive legislation",
        scope="governance",
        integration="agent/directive_amendment (absent)",
        gate="a runtime that evaluates directives and mutates them",
        unblocks="a directive measured as blocking is amended by the system, under review",
        probe="directive_amendment",
    ),
    GenesisContract(
        id="DIR-17",
        title="Swarm intelligence",
        scope="swarm",
        integration="openamer_cli/a2a + directory/a2a + go/mesh-daemon",
        gate="at least one registered peer to replicate work onto",
        unblocks="tasks fan out to peers; the tick reports the live node count",
        probe="swarm",
    ),
    GenesisContract(
        id="DIR-18",
        title="Proactive intentionality",
        scope="agency",
        integration="agent/goal_engine.py",
        gate="goals beyond the directive text",
        unblocks="the engine proposes and tracks its own goals; the tick reads progress",
        probe="goal_engine",
    ),
    GenesisContract(
        id="DIR-19",
        title="Global DePIN node swarm",
        scope="swarm",
        integration="docker/ + node registry (absent)",
        gate="a node registry with GPU nodes and a payout path",
        unblocks="consumer GPUs register, receive PoUW tasks and get paid",
        probe="depin",
    ),
    GenesisContract(
        id="DIR-20",
        title="Autonomous OAC tokenomics and PoUW",
        scope="economics",
        integration="agent/tokenomics.py + agent/oac_genesis.py + chain/contracts",
        gate="supply identity and allocation balance hold",
        unblocks="emission is recomputed per tick from verified compute",
        probe="tokenomics",
    ),
    GenesisContract(
        id="DIR-21",
        title="Hybrid compute architecture",
        scope="architecture",
        integration="providers + gateway/profile_routing.py",
        gate="two or more model backends to route between",
        unblocks="sequential reasoning and parallel search are scheduled onto different nodes",
        probe="hybrid_routing",
    ),
    GenesisContract(
        id="DIR-22",
        title="Autonomous treasury and reserves",
        scope="economics",
        integration="agent/oac_genesis.py + chain/contracts",
        gate="an autonomous spending path on top of the genesis reserve",
        unblocks="the treasury pays servers, RPC and bounties without a human signer",
        probe="treasury_autonomy",
    ),
    GenesisContract(
        id="DIR-23",
        title="Circular economic stability, verification and fiat",
        scope="economics",
        integration="chain/contracts (burn) + agent/offramp (absent)",
        gate="a burn function and a regulated fiat off-ramp",
        unblocks="30% of cloud revenue is burned and invoices are paid in fiat",
        probe="burn_and_fiat",
    ),
    GenesisContract(
        id="DIR-24",
        title="Universal client software and one-click miner",
        scope="client",
        integration="apps/desktop + ui-tui + PoUW miner (absent)",
        gate="packaged client plus a PoUW miner module",
        unblocks="a one-click miner ships in the client and registers as a node",
        probe="client",
    ),
]


# ── measuring, persisting, scheduling ──────────────────────────────────────────

def measure() -> List[dict]:
    """Measure all 24 directives. Never raises; a broken probe is ``unknown``."""
    rows: List[dict] = []
    for contract in CONTRACTS:
        probe_fn = _PROBES.get(contract.probe)
        if probe_fn is None:
            result = Probe(UNKNOWN, f"probe {contract.probe!r} is not implemented")
        else:
            try:
                result = probe_fn()
            except Exception as exc:  # noqa: BLE001 — a probe failure is unknown
                result = Probe(UNKNOWN, f"probe crashed: {type(exc).__name__}: {exc}")
        status = STATUS_BY_VERDICT[result.verdict]
        integration_exists = bool(contract.integration) and not contract.integration.endswith("(absent)")
        rows.append(
            {
                "id": contract.id,
                "title": contract.title,
                "scope": contract.scope,
                "status": status,
                "mark": MARK_BY_STATUS[status],
                "verdict": result.verdict,
                "measured": result.detail,
                "values": result.values,
                "gate": contract.gate,
                "gate_state": "open" if result.verdict == SATISFIED else "closed",
                "unblocks": contract.unblocks,
                "integration": contract.integration,
                "integration_present": integration_exists,
                "probe": contract.probe,
            }
        )
    return rows


def summary(rows: List[dict]) -> dict:
    counts = {"implemented": 0, "partial": 0, "gated": 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    counts["total"] = len(rows)
    counts["measured_unknown"] = sum(1 for row in rows if row["verdict"] == UNKNOWN)
    counts["gate_open"] = sum(1 for row in rows if row["gate_state"] == "open")
    return counts


def state_dir() -> Path:
    return _home() / "memory" / "genesis"


def state_path() -> Path:
    return state_dir() / "state.json"


def heartbeat_path() -> Path:
    return state_dir() / "heartbeat"


def events_path() -> Path:
    return state_dir() / "events.jsonl"


def read_state() -> Optional[dict]:
    return _read_json(state_path())


def tick(now: Optional[float] = None) -> dict:
    """Measure, persist atomically, log status changes, touch the heartbeat."""
    stamp = time.time() if now is None else now

    # DIR-01's artifact half is not a static fact — it must keep working. Seal and
    # restore a fast snapshot (measured: 0.135 s, ~1.5 MB) before measuring, so the
    # replication probe reports a *fresh* verification instead of last week's.
    try:
        from agent import replication

        replication.selftest()
        # Once a peer exists the tick also *delivers* — otherwise "replication"
        # would only ever prove the artifact on the machine that wrote it.
        if replication.load_peers():
            replication.push_to_peers(profile="fast", timeout=15.0)
    except Exception as exc:  # noqa: BLE001 - the probe reports what it can see
        logger.debug("Replication step skipped: %s", exc)

    rows = measure()
    payload = {
        "measured_at": stamp,
        "measured_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stamp)),
        "directives": rows,
        "summary": summary(rows),
    }

    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)

    previous = read_state() or {}
    previous_status = {
        row.get("id"): row.get("status")
        for row in previous.get("directives", [])
        if isinstance(row, dict)
    }
    changed = [
        {"id": row["id"], "from": previous_status.get(row["id"]), "to": row["status"]}
        for row in rows
        if previous_status.get(row["id"]) not in (None, row["status"])
    ]
    if changed:
        payload["changes"] = changed

    tmp = state_path().with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    os.replace(tmp, state_path())

    heartbeat_path().touch()
    if changed:
        with events_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"ts": stamp, "changes": changed}) + "\n")

    return payload


def tick_if_due(min_interval_s: int = DEFAULT_TICK_INTERVAL_S, now: Optional[float] = None) -> Optional[dict]:
    """Tick only when the last measurement is older than the interval."""
    stamp = time.time() if now is None else now
    state = read_state()
    if state:
        last = state.get("measured_at")
        if isinstance(last, (int, float)) and stamp - last < min_interval_s:
            return None
    return tick(now=stamp)


def render(rows: List[dict], *, age_s: Optional[float] = None) -> str:
    """Render the live table: status, gate state, what was measured, owner."""
    head = f"{'ID':<7} {'STATUS':<11} {'GATE':<7} MEASURED / INTEGRATION"
    lines = [head, "-" * 132]
    for row in rows:
        measured = row["measured"]
        if len(measured) > 74:
            measured = measured[:71] + "..."
        lines.append(
            f"{row['id']:<7} {row['mark'] + ' ' + row['status']:<11} "
            f"{row['gate_state']:<7} {measured}"
        )
        lines.append(f"{'':<7} {'':<11} {'':<7} ↳ owns: {row['integration']}")
    counts = summary(rows)
    tail = (
        f"\n{counts['total']} directives — {counts['implemented']} implemented, "
        f"{counts['partial']} partial, {counts['gated']} gated "
        f"({counts['gate_open']} open gates, {counts['measured_unknown']} unmeasured)"
    )
    if age_s is not None:
        tail += f" · last tick {int(age_s)}s ago"
    return "\n".join(lines) + tail
