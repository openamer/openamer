"""DIR-10 — molecular procedure definitions, gated on laboratory hardware.

Precision molecular work needs instruments. This module holds the *protocol*:
named steps, each requiring a capability, with parameters that can be validated
without a lab. On a host without the instruments, ``execute`` refuses and names
what is missing — it never pretends to have run.

That split is the whole point. A protocol definition is data a chemist can
review and a machine can check for internal consistency (unknown instrument,
missing parameter, step that consumes what no earlier step produced). The
execution is hardware. Shipping only the second half would leave nothing to run
when the hardware arrives.

This is a scaffold, not a medical claim: no dosage, no compound and no procedure
here has been validated for use on a living organism, and the module has no
authority to treat anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence

from agent.substrate import Requirement, Substrate, SubstrateUnavailable, check, require

#: Instruments a protocol can name. Adding one here is the only way to make it
#: referenceable — an unknown name is a definition error, not a runtime surprise.
INSTRUMENTS: Dict[str, Requirement] = {
    "liquid_handler": Requirement("liquid_handler", "programmable pipetting robot"),
    "spectrometer": Requirement("spectrometer", "NMR or mass spectrometer for verification"),
    "thermal_cycler": Requirement("thermal_cycler", "precise temperature cycling"),
    "chromatograph": Requirement("chromatograph", "separation + purity assay"),
    "biosafety_cabinet": Requirement("biosafety_cabinet", "containment for live samples"),
}


@dataclass(frozen=True)
class Step:
    name: str
    instrument: str
    parameters: Dict[str, float] = field(default_factory=dict)
    produces: Sequence[str] = ()

    def __post_init__(self) -> None:
        if self.instrument not in INSTRUMENTS:
            raise ValueError(f"unknown instrument {self.instrument!r}; known: {sorted(INSTRUMENTS)}")
        if not self.name.strip():
            raise ValueError("step name must be non-empty")
        if self.instrument != "spectrometer" and not self.parameters:
            raise ValueError(f"step {self.name!r} needs at least one parameter")


@dataclass(frozen=True)
class Protocol:
    name: str
    steps: Sequence[Step]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("protocol name must be non-empty")
        if not self.steps:
            raise ValueError("a protocol needs at least one step")

    @property
    def requirements(self) -> List[Requirement]:
        seen: List[Requirement] = []
        for step in self.steps:
            req = INSTRUMENTS[step.instrument]
            if req not in seen:
                seen.append(req)
        return seen

    def validate(self) -> List[str]:
        """Definition errors, independent of hardware. Empty means consistent."""
        problems: List[str] = []
        produced: set[str] = set()
        for idx, step in enumerate(self.steps):
            for key, value in step.parameters.items():
                if value < 0:
                    problems.append(f"step {idx} ({step.name}): negative parameter {key}={value}")
            if step.instrument == "chromatograph" and not produced:
                problems.append(f"step {idx} ({step.name}): assay before anything is produced")
            produced.update(step.produces)
        return problems

    def plan(self, substrate: Substrate) -> dict:
        """What would run, and what blocks it. Pure — safe without hardware."""
        readiness = check(substrate, self.requirements)
        return {
            "protocol": self.name,
            "steps": [
                {"index": i, "name": s.name, "instrument": s.instrument, "params": dict(s.parameters)}
                for i, s in enumerate(self.steps)
            ],
            "ready": readiness.ready,
            "missing": [r.id for r in readiness.missing],
            "definition_problems": self.validate(),
        }

    def execute(self, substrate: Substrate) -> dict:
        """Refuse without hardware; otherwise return the executed trace.

        Deliberately returns a *trace*, not an outcome: this module cannot verify
        a molecular result, so it reports what was commanded.
        """
        problems = self.validate()
        if problems:
            raise ValueError("protocol has definition problems: " + "; ".join(problems))
        require(f"protocol {self.name!r}", substrate, self.requirements)
        return {
            "protocol": self.name,
            "executed": [step.name for step in self.steps],
            "instruments": [step.instrument for step in self.steps],
            "verified": False,
            "note": "trace of commands; no result was measured or verified",
        }


def readiness_for(protocols: Iterable[Protocol], substrate: Substrate) -> Dict[str, str]:
    return {p.name: check(substrate, p.requirements).describe() for p in protocols}
