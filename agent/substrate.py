"""Substrate gating: declare what hardware a capability needs, and refuse.

DIR-10, DIR-14 and DIR-15 describe capabilities this machine does not have — a
wet lab, a nanofabricator, a launch vehicle. The honest way to "integrate" them
is not to fake a result: it is to ship the *interface* plus an explicit
prerequisite, so that when the hardware exists the same code runs, and until
then every attempt fails loudly with the missing piece named.

Design rules, all of them there to stop silent nonsense:

* A requirement has a stable id. "missing" is always a concrete list of ids, so
  a refusal can be printed to a human without interpretation.
* ``require`` raises ``SubstrateUnavailable`` — never returns None and never
  degrades to a no-op. A capability that quietly does nothing is unmeasurable.
* Nothing here reads the environment by guessing a vendor layout: the substrate
  is passed in, so a test can supply one and the caller decides what the host
  has.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Set


@dataclass(frozen=True)
class Requirement:
    id: str
    description: str

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("requirement id must be non-empty")


class SubstrateUnavailable(RuntimeError):
    """Raised when a capability is invoked without its hardware."""

    def __init__(self, capability: str, missing: Iterable[Requirement]):
        self.capability = capability
        self.missing = list(missing)
        names = ", ".join(f"{r.id} ({r.description})" for r in self.missing)
        super().__init__(f"{capability} requires hardware that is not present: {names}")


@dataclass
class Substrate:
    """What a host can actually do. Empty by default — nothing is assumed."""

    capabilities: Set[str] = field(default_factory=set)
    label: str = "unknown host"

    def has(self, requirement: Requirement) -> bool:
        return requirement.id in self.capabilities


@dataclass(frozen=True)
class Readiness:
    ready: bool
    missing: List[Requirement]

    def describe(self) -> str:
        if self.ready:
            return "ready"
        return "missing: " + ", ".join(r.id for r in self.missing)


def check(substrate: Substrate, requirements: Iterable[Requirement]) -> Readiness:
    reqs = list(requirements)
    missing = [r for r in reqs if not substrate.has(r)]
    return Readiness(ready=not missing, missing=missing)


def require(
    capability: str, substrate: Substrate, requirements: Iterable[Requirement]
) -> None:
    """Raise ``SubstrateUnavailable`` unless every requirement is met."""
    readiness = check(substrate, requirements)
    if not readiness.ready:
        raise SubstrateUnavailable(capability, readiness.missing)
