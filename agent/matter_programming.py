"""DIR-14 — matter-programming job definitions, gated on a fabricator.

Matter programming needs hardware with a working resolution finer than the
structure being built. The integrable half is the *job*: a target pattern, a
required resolution, a material, and a check that the requested structure is
representable at all. The non-integrable half is the fabricator.

So this module plans and refuses. It cannot assemble anything, and it says so in
the return value of every call — a trace of intended placements, never a claim
that matter was rearranged.

The representability rules are the interesting part, because they are what a
future fabricator driver would have to satisfy anyway:

* resolution must be finer than the smallest feature (half the pitch, at least);
* a pattern must be a rectangular bitmask of consistent row length;
* the requested material must be one the fabricator declares it can deposit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

from agent.substrate import Requirement, Substrate, check, require

FABRICATOR = Requirement("nanofabricator", "assembly hardware with sub-micron resolution")


@dataclass(frozen=True)
class AssemblySpec:
    name: str
    pattern: Sequence[str]
    """Row strings of '0'/'1'; '1' is a placement."""
    resolution_nm: float
    """Smallest feature this spec asks for."""
    material: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("spec name must be non-empty")
        if not self.pattern:
            raise ValueError("pattern must have at least one row")
        widths = {len(row) for row in self.pattern}
        if len(widths) != 1:
            raise ValueError(f"all rows must be the same length, got {sorted(widths)}")
        if any(ch not in "01" for row in self.pattern for ch in row):
            raise ValueError("pattern may only contain '0' and '1'")
        if self.resolution_nm <= 0:
            raise ValueError("resolution_nm must be > 0")
        if not self.material.strip():
            raise ValueError("material must be non-empty")

    @property
    def placements(self) -> int:
        return sum(row.count("1") for row in self.pattern)

    @property
    def footprint_nm(self) -> tuple[float, float]:
        rows, cols = len(self.pattern), len(self.pattern[0])
        return (cols * self.resolution_nm, rows * self.resolution_nm)


@dataclass
class Fabricator:
    """A machine that claims a resolution and a material set."""

    label: str
    min_resolution_nm: float
    materials: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.min_resolution_nm <= 0:
            raise ValueError("min_resolution_nm must be > 0")


def feasibility(spec: AssemblySpec, fabricator: Fabricator | None) -> dict:
    """Can this machine build this spec? Never raises — it reports."""
    if fabricator is None:
        return {"feasible": False, "blockers": ["no nanofabricator available"]}
    blockers: List[str] = []
    if fabricator.min_resolution_nm > spec.resolution_nm:
        blockers.append(
            f"resolution: spec needs {spec.resolution_nm} nm, machine reaches "
            f"{fabricator.min_resolution_nm} nm"
        )
    if fabricator.materials and spec.material not in fabricator.materials:
        blockers.append(f"material {spec.material!r} not in {list(fabricator.materials)}")
    return {"feasible": not blockers, "blockers": blockers}


def plan(spec: AssemblySpec, substrate: Substrate, fabricator: Fabricator | None = None) -> dict:
    """Placement trace for a build that has not happened."""
    readiness = check(substrate, [FABRICATOR])
    verdict = feasibility(spec, fabricator)
    return {
        "spec": spec.name,
        "placements": spec.placements,
        "footprint_nm": spec.footprint_nm,
        "substrate_ready": readiness.ready,
        "feasible": verdict["feasible"],
        "blockers": verdict["blockers"] + ([] if readiness.ready else [readiness.describe()]),
        "executed": False,
    }


def build(spec: AssemblySpec, substrate: Substrate, fabricator: Fabricator | None = None) -> dict:
    """Refuse unless the hardware and the spec both allow it."""
    require(f"assembly {spec.name!r}", substrate, [FABRICATOR])
    verdict = feasibility(spec, fabricator)
    if not verdict["feasible"]:
        raise ValueError("infeasible assembly: " + "; ".join(verdict["blockers"]))
    return {
        "spec": spec.name,
        "placements": spec.placements,
        "executed": False,
        "note": "command trace only — no matter was moved and no result was verified",
    }
