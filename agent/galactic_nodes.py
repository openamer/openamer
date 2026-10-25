"""DIR-15 — off-planet cognitive nodes: constellation planning, launch-gated.

Galactic redundancy needs launch capability. What can be built now is the part
that does not: node placement, the latency a node at a given orbit actually
imposes, and a feasibility verdict against a declared launch envelope. A future
launch provider plugs into ``LaunchCapability``; until one exists, ``deploy``
refuses and names the missing hardware.

The latency model is the reason this is worth having before the hardware: a
"galactic" node that is 400 ms away cannot serve interactive reasoning, and a
planner that ignores that would happily produce a useless constellation. Round
trip is modelled as light-time only (the physical floor); real links add more,
which the module states rather than hides.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Sequence

from agent.substrate import Requirement, Substrate, check, require

LAUNCH = Requirement("launch_vehicle", "capability to place a node in orbit")

#: Vacuum speed of light in km/s.
C_KM_S = 299_792.458

#: Earth radius, used to sanity-bound a low-orbit altitude.
EARTH_RADIUS_KM = 6_371.0


@dataclass(frozen=True)
class Orbit:
    name: str
    altitude_km: float

    def __post_init__(self) -> None:
        if self.altitude_km <= 0:
            raise ValueError("altitude_km must be > 0")

    @property
    def radius_km(self) -> float:
        return EARTH_RADIUS_KM + self.altitude_km

    def one_way_ms(self, ground_latency_deg: float = 0.0) -> float:
        """Physical floor: straight-line light time from ground to node, in ms.

        ``ground_latency_deg`` adds the great-circle hop along the surface, so a
        node on the far side of the planet is not treated as overhead.
        """
        if not 0.0 <= ground_latency_deg <= 180.0:
            raise ValueError("ground_latency_deg must be within [0, 180]")
        surface_km = math.radians(ground_latency_deg) * EARTH_RADIUS_KM
        return ((self.altitude_km + surface_km) / C_KM_S) * 1000.0


@dataclass(frozen=True)
class OrbitalNode:
    node_id: str
    orbit: Orbit
    compute_units: float = 1.0

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("node_id must be non-empty")
        if self.compute_units <= 0:
            raise ValueError("compute_units must be > 0")

    def round_trip_ms(self, ground_latency_deg: float = 0.0) -> float:
        return 2 * self.orbit.one_way_ms(ground_latency_deg)


@dataclass
class LaunchCapability:
    """What a provider can actually lift. Zero means none."""

    provider: str
    max_mass_kg: float = 0.0
    max_nodes_per_launch: int = 0
    reachable_altitudes_km: Sequence[float] = field(default_factory=tuple)

    def can_place(self, orbit: Orbit, node_mass_kg: float) -> bool:
        if self.max_mass_kg <= 0 or self.max_nodes_per_launch <= 0:
            return False
        if node_mass_kg > self.max_mass_kg:
            return False
        if not self.reachable_altitudes_km:
            return False
        return any(abs(orbit.altitude_km - alt) <= 1.0 for alt in self.reachable_altitudes_km)


#: A node able to run interactive latency-sensitive work.
INTERACTIVE_RTT_BUDGET_MS = 250.0


def plan_constellation(
    nodes: Sequence[OrbitalNode],
    substrate: Substrate,
    launch: LaunchCapability | None = None,
    node_mass_kg: float = 50.0,
) -> dict:
    """Feasibility of a constellation, with the latency each node imposes."""
    readiness = check(substrate, [LAUNCH])
    blockers: List[str] = []
    if not readiness.ready:
        blockers.append(readiness.describe())
    if launch is None:
        blockers.append("no launch provider configured")
    else:
        for node in nodes:
            if not launch.can_place(node.orbit, node_mass_kg):
                blockers.append(f"{node.node_id}: {launch.provider} cannot place this orbit/mass")

    latencies = {
        n.node_id: round(n.round_trip_ms(), 2) for n in nodes
    }
    interactive = [nid for nid, rtt in latencies.items() if rtt <= INTERACTIVE_RTT_BUDGET_MS]
    return {
        "nodes": len(nodes),
        "total_compute_units": round(sum(n.compute_units for n in nodes), 3),
        "round_trip_ms": latencies,
        "interactive_capable": sorted(interactive),
        "feasible": not blockers,
        "blockers": blockers,
    }


def deploy(nodes: Sequence[OrbitalNode], substrate: Substrate, launch: LaunchCapability | None = None) -> dict:
    """Refuse without a launch capability."""
    require("orbital deployment", substrate, [LAUNCH])
    if launch is None:
        raise ValueError("no launch provider configured")
    return {
        "deployed": [],
        "requested": [n.node_id for n in nodes],
        "provider": launch.provider,
        "executed": False,
        "note": "no vehicle was commanded; this is a manifest, not a launch",
    }
