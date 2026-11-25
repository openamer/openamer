"""The Genesis constitution as a versioned, hash-chained artifact.

Why this exists
---------------
``agent/genesis_directives.py`` carries the 24 rules as Python source in the
tracked tree. That is right for *distribution* — every install gets them on
``git pull`` — and wrong for *governance*: a constitutional amendment made at
runtime has no record, no parent, and no way back. DIR-16 asks the system to
evaluate its own directives and mutate them when blocked; a mutation without a
ledger is indistinguishable from corruption.

This module is that ledger. Every change is a new numbered version, chained by
hash to its parent:

    v0001.json  ← genesis, hash h1
    v0002.json  ← parent h1, hash h2, action REPAIR, proposal P-...
    ...

Nothing is ever rewritten in place. A rollback is *also* a new version whose
content equals an older one, so the chain stays append-only and the history
remains readable in one direction. ``verify_chain()`` recomputes every hash.

Invariants are the safety boundary
----------------------------------
An autonomous system that can amend its own constitution must not be able to
amend away the parts that protect anyone. ``INVARIANTS`` runs on every
candidate before it becomes a version, and a failing candidate never touches
disk. The protected set is deliberately small and explicit:

* ``PROTECTED_IDS`` — creator allocation (DIR-03), the tokenomics identity
  (DIR-20), the treasury (DIR-22), and DIR-16 itself (a rule that can delete
  the amendment mechanism is the last rule it ever executes).
* ``PROTECTED_FACTS`` — the load-bearing numbers behind those four, checked as
  substrings so a translation or a rewording passes and a changed number does
  not.
* ``HOLLOW_FLOOR`` — a directive may be rewritten, never emptied: the rule text
  keeps at least this share of its original length.

The invariants are data, not policy prose. ``apply_change`` returns the list of
violations by name; a caller that ignores them still cannot write a file.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from agent.genesis_directives import GENESIS_DIRECTIVES

#: Never removable, never retirable. DIR-16 is here on purpose: the mechanism
#: that amends the constitution is the one rule it may not amend away.
PROTECTED_IDS = ("DIR-03", "DIR-16", "DIR-20", "DIR-22")

#: Numbers a protected directive must keep, as substrings of the rendered rule.
PROTECTED_FACTS: Dict[str, tuple] = {
    "DIR-03": ("900,000,000", "10%", "cliff", "creator"),
    "DIR-16": ("evaluates the efficiency", "mutates"),
    "DIR-20": ("9,000,000,000", "75%", "15%", "10%", "32 years", "halving"),
    "DIR-22": ("1,350,000,000", "15%", "Treasury"),
}

#: A rule may be reworded; it may not be hollowed out to a slogan.
HOLLOW_FLOOR = 0.6

GENESIS = "GENESIS"
REPAIR = "REPAIR"
RETIRE = "RETIRE"
ROLLBACK = "ROLLBACK"
ACTIONS = (GENESIS, REPAIR, RETIRE, ROLLBACK)

_ID_FMT = "DIR-{:02d}"


# --------------------------------------------------------------------------- #
# storage location
# --------------------------------------------------------------------------- #
def home_root() -> Path:
    """The install home that actually holds ``memory/``.

    ``$OPENAMER_HOME`` may point at the tracked tree (``.../openamer-agent``)
    while the runtime state and the version store live one level up in
    ``.../openamer-laptop``. Reading the env var alone therefore produced two
    different answers for "where is the constitution?" depending on how the
    process was started — the same split that let the two Genesis ledgers
    disagree. Prefer the candidate that already has a ``memory/genesis`` tree,
    then any ``memory`` tree, and only then the env var.
    """
    env = os.environ.get("OPENAMER_HOME", "").strip()
    candidates: List[Path] = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path.home() / "AppData" / "Local" / "openamer-laptop")
    candidates.append(Path(__file__).resolve().parents[1])
    for candidate in candidates:
        if (candidate / "memory" / "genesis").is_dir():
            return candidate
    for candidate in candidates:
        if (candidate / "memory").is_dir():
            return candidate
    return candidates[0] if candidates else Path.cwd()


def constitution_dir() -> Path:
    """Where versions live: ``<home>/memory/genesis/constitution``.

    Falls back to the standard install path when no candidate is detectable, so
    a bare checkout and an installed tree agree instead of each inventing a
    location.
    """
    return home_root() / "memory" / "genesis" / "constitution"


def _version_path(directory: Path, version: int) -> Path:
    return directory / f"v{version:04d}.json"


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DirectiveText:
    id: str
    title: str
    rule: str
    scope: str

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "rule": self.rule, "scope": self.scope}


@dataclass
class ChangeResult:
    """Outcome of an attempted amendment."""

    ok: bool
    version: int = 0
    revision_hash: str = ""
    problems: List[str] = field(default_factory=list)

    def why(self) -> str:
        return "; ".join(self.problems) if self.problems else "accepted"


def genesis_directives() -> List[DirectiveText]:
    """The shipped constitution, as the seed for version 1."""
    return [
        DirectiveText(d.id, d.title, d.rule, d.scope) for d in GENESIS_DIRECTIVES
    ]


def canonical_payload(directives: Sequence[DirectiveText]) -> List[dict]:
    return [d.as_dict() for d in directives]


def canonical_hash(directives: Sequence[DirectiveText]) -> str:
    """Stable hash over the directive content only — no timestamps, no paths."""
    blob = json.dumps(
        canonical_payload(directives),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# invariants — the safety boundary
# --------------------------------------------------------------------------- #
def _inv_ids(candidate: Sequence[DirectiveText]) -> List[str]:
    expected = [_ID_FMT.format(i) for i in range(1, 25)]
    got = [d.id for d in candidate]
    if got != expected:
        return [f"ids differ from DIR-01..DIR-24: {got if len(got) < 8 else str(len(got)) + ' rows'}"]
    return []


def _inv_fields(candidate: Sequence[DirectiveText]) -> List[str]:
    problems = []
    for d in candidate:
        if not d.title.strip():
            problems.append(f"{d.id}: empty title")
        if not d.scope.strip():
            problems.append(f"{d.id}: empty scope")
        if len(d.rule.strip()) < 20:
            problems.append(f"{d.id}: rule shorter than 20 chars")
    return problems


def _inv_protected_present(candidate: Sequence[DirectiveText]) -> List[str]:
    present = {d.id for d in candidate}
    return [f"{pid}: protected directive removed" for pid in PROTECTED_IDS if pid not in present]


def _inv_protected_facts(candidate: Sequence[DirectiveText]) -> List[str]:
    problems = []
    for d in candidate:
        needles = PROTECTED_FACTS.get(d.id)
        if not needles:
            continue
        missing = [n for n in needles if n not in d.rule]
        if missing:
            problems.append(f"{d.id}: protected facts lost {missing}")
    return problems


def _inv_not_hollowed(candidate: Sequence[DirectiveText]) -> List[str]:
    """Compare against what *this* constitution was seeded with."""
    original = {d.id: len(d.rule) for d in genesis_directives()}
    problems = []
    for d in candidate:
        floor = original.get(d.id, 0) * HOLLOW_FLOOR
        if len(d.rule) < floor:
            problems.append(
                f"{d.id}: rule shrunk to {len(d.rule)} chars, below "
                f"{int(floor)} ({int(HOLLOW_FLOOR * 100)}% of the original)"
            )
    return problems


INVARIANTS = (
    ("ids", _inv_ids),
    ("fields", _inv_fields),
    ("protected-present", _inv_protected_present),
    ("protected-facts", _inv_protected_facts),
    ("not-hollowed", _inv_not_hollowed),
)


def check_invariants(candidate: Sequence[DirectiveText]) -> List[str]:
    """Every violation, by invariant name. Empty list means the candidate may ship."""
    problems: List[str] = []
    for name, rule in INVARIANTS:
        for problem in rule(candidate):
            problems.append(f"{name}: {problem}")
    return problems


# --------------------------------------------------------------------------- #
# the version store
# --------------------------------------------------------------------------- #
def _read_version(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def versions(directory: Optional[Path] = None) -> List[dict]:
    """All versions, oldest first. An absent directory is an empty history."""
    directory = directory or constitution_dir()
    if not directory.is_dir():
        return []
    out = []
    for path in sorted(directory.glob("v[0-9][0-9][0-9][0-9].json")):
        out.append(_read_version(path))
    return out


def _directives_from(record: dict) -> List[DirectiveText]:
    return [
        DirectiveText(d["id"], d["title"], d["rule"], d["scope"])
        for d in record.get("directives", [])
    ]


def load_current(directory: Optional[Path] = None) -> List[DirectiveText]:
    """The active constitution — the last version, or the shipped text if none."""
    directory = directory or constitution_dir()
    existing = versions(directory)
    if not existing:
        return genesis_directives()
    return _directives_from(existing[-1])


def current_version(directory: Optional[Path] = None) -> int:
    existing = versions(directory or constitution_dir())
    return int(existing[-1]["version"]) if existing else 0


def _write_atomic(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _append_chain(directory: Path, record: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / "chain.jsonl", "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(
            {
                "version": record["version"],
                "hash": record["hash"],
                "parent_hash": record["parent_hash"],
                "action": record["action"],
                "proposal_id": record.get("proposal_id"),
                "reason": record["reason"],
                "created_at": record["created_at"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _new_record(
    version: int,
    directives: Sequence[DirectiveText],
    action: str,
    reason: str,
    parent_hash: Optional[str],
    proposal_id: Optional[str],
) -> dict:
    return {
        "version": version,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "parent_hash": parent_hash,
        "hash": canonical_hash(directives),
        "action": action,
        "proposal_id": proposal_id,
        "reason": reason,
        "directives": canonical_payload(directives),
    }


def ensure_genesis(directory: Optional[Path] = None) -> int:
    """Create version 1 from the shipped text if the store is empty."""
    directory = directory or constitution_dir()
    if versions(directory):
        return current_version(directory)
    record = _new_record(
        1, genesis_directives(), GENESIS,
        "seeded from agent/genesis_directives.py", None, None,
    )
    directory.mkdir(parents=True, exist_ok=True)
    _write_atomic(_version_path(directory, 1), record)
    _append_chain(directory, record)
    return 1


def apply_change(
    action: str,
    directives: Sequence[DirectiveText],
    reason: str,
    proposal_id: Optional[str] = None,
    directory: Optional[Path] = None,
) -> ChangeResult:
    """Validate, then write exactly one new version. Never rewrites history.

    The invariant check runs *before* anything touches disk, so a rejected
    candidate cannot leave a partial version behind.
    """
    if action not in ACTIONS:
        return ChangeResult(False, problems=[f"unknown action {action!r}"])
    directory = directory or constitution_dir()
    ensure_genesis(directory)

    problems = check_invariants(directives)
    if problems:
        return ChangeResult(False, problems=problems)

    existing = versions(directory)
    parent = existing[-1]
    if canonical_hash(directives) == parent["hash"]:
        return ChangeResult(
            False, int(parent["version"]), parent["hash"],
            ["candidate is identical to the current version — no version written"],
        )

    record = _new_record(
        int(parent["version"]) + 1, directives, action, reason,
        parent["hash"], proposal_id,
    )
    _write_atomic(_version_path(directory, record["version"]), record)
    _append_chain(directory, record)
    return ChangeResult(True, record["version"], record["hash"], [])


def rollback(steps: int = 1, reason: str = "manual rollback", directory: Optional[Path] = None) -> ChangeResult:
    """Restore an earlier version *as a new version*.

    Append-only on purpose: a rollback that rewrote the chain would erase the
    evidence of what was rolled back and why.
    """
    directory = directory or constitution_dir()
    existing = versions(directory)
    if not existing:
        return ChangeResult(False, problems=["no versions to roll back from"])
    if steps < 1:
        return ChangeResult(False, problems=["steps must be >= 1"])
    target_index = len(existing) - 1 - steps
    if target_index < 0:
        return ChangeResult(
            False, int(existing[-1]["version"]), existing[-1]["hash"],
            [f"cannot roll back {steps}: only {len(existing)} version(s) exist"],
        )
    target = existing[target_index]
    return apply_change(
        ROLLBACK, _directives_from(target),
        f"{reason}: restore v{int(target['version']):04d}",
        None, directory,
    )


def verify_chain(directory: Optional[Path] = None) -> List[str]:
    """Recompute every hash and every parent link. Empty list means intact."""
    directory = directory or constitution_dir()
    problems: List[str] = []
    previous_hash: Optional[str] = None
    for index, record in enumerate(versions(directory)):
        expected_version = index + 1
        if int(record.get("version", -1)) != expected_version:
            problems.append(
                f"v{expected_version:04d}: file says version {record.get('version')}"
            )
        actual = canonical_hash(_directives_from(record))
        if actual != record.get("hash"):
            problems.append(
                f"v{expected_version:04d}: content hash {actual[:12]} != recorded "
                f"{str(record.get('hash'))[:12]}"
            )
        if record.get("parent_hash") != previous_hash:
            problems.append(
                f"v{expected_version:04d}: parent {str(record.get('parent_hash'))[:12]} "
                f"!= previous {str(previous_hash)[:12]}"
            )
        previous_hash = record.get("hash")
    return problems


def history(directory: Optional[Path] = None) -> List[dict]:
    """Compact view of the chain for CLI output: no directive bodies."""
    return [
        {
            "version": int(r["version"]),
            "action": r["action"],
            "hash": str(r["hash"])[:12],
            "parent_hash": (str(r["parent_hash"])[:12] if r.get("parent_hash") else "-"),
            "reason": r.get("reason", ""),
            "proposal_id": r.get("proposal_id"),
            "created_at": r.get("created_at", ""),
        }
        for r in versions(directory or constitution_dir())
    ]
