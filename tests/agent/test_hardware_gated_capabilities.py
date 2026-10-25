"""DIR-10/14/15: hardware-gated capabilities must refuse, and name what is missing."""

from __future__ import annotations

import pytest

from agent.bio_procedures import INSTRUMENTS, Protocol, Step, readiness_for
from agent.galactic_nodes import (
    INTERACTIVE_RTT_BUDGET_MS,
    LaunchCapability,
    Orbit,
    OrbitalNode,
    plan_constellation,
    deploy,
)
from agent.matter_programming import AssemblySpec, FABRICATOR, Fabricator, build, feasibility, plan
from agent.substrate import Requirement, Substrate, SubstrateUnavailable, check, require


# ── the shared gate ─────────────────────────────────────────────────────────
def test_default_substrate_can_do_nothing() -> None:
    """Nothing is assumed about a host: the empty substrate is the default."""
    assert Substrate().capabilities == set()


def test_check_lists_every_missing_requirement() -> None:
    r = Requirement("lab", "a wet lab")
    readiness = check(Substrate(), [r])
    assert not readiness.ready
    assert readiness.missing == [r]
    assert "missing: lab" in readiness.describe()


def test_require_raises_with_the_missing_id_in_the_message() -> None:
    with pytest.raises(SubstrateUnavailable) as exc:
        require("molecular synthesis", Substrate(), [Requirement("lab", "a wet lab")])
    assert "lab" in str(exc.value)
    assert exc.value.capability == "molecular synthesis"


def test_require_passes_when_the_substrate_has_it() -> None:
    require("x", Substrate(capabilities={"lab"}), [Requirement("lab", "a wet lab")])


# ── DIR-10 ─────────────────────────────────────────────────────────────────
def _protocol() -> Protocol:
    return Protocol(
        "assay",
        [
            Step("dispense", "liquid_handler", {"volume_ul": 20.0}, produces=("mix",)),
            Step("separate", "chromatograph", {"flow_ml_min": 1.0}),
        ],
    )


def test_bio_protocol_rejects_unknown_instrument() -> None:
    with pytest.raises(ValueError, match="unknown instrument"):
        Step("x", "replicator", {"a": 1})


def test_bio_plan_is_pure_and_reports_missing_hardware() -> None:
    planned = _protocol().plan(Substrate())
    assert planned["ready"] is False
    assert set(planned["missing"]) == {"liquid_handler", "chromatograph"}
    assert planned["steps"][0]["name"] == "dispense"


def test_bio_execute_refuses_without_instruments() -> None:
    with pytest.raises(SubstrateUnavailable):
        _protocol().execute(Substrate())


def test_bio_execute_with_hardware_returns_a_trace_not_a_result() -> None:
    lab = Substrate(capabilities=set(INSTRUMENTS), label="test lab")
    trace = _protocol().execute(lab)
    assert trace["executed"] == ["dispense", "separate"]
    assert trace["verified"] is False
    assert "no result was measured" in trace["note"]


def test_bio_definition_error_is_caught_before_hardware() -> None:
    bad = Protocol("bad", [Step("assay-first", "chromatograph", {"flow_ml_min": 1.0})])
    assert bad.validate()
    with pytest.raises(ValueError, match="definition problems"):
        bad.execute(Substrate(capabilities=set(INSTRUMENTS)))


def test_bio_readiness_map_covers_every_protocol() -> None:
    out = readiness_for([_protocol()], Substrate(capabilities={"liquid_handler"}))
    assert "assay" in out and "chromatograph" in out["assay"]


# ── DIR-14 ─────────────────────────────────────────────────────────────────
def _spec() -> AssemblySpec:
    return AssemblySpec("grid", ["101", "010", "101"], resolution_nm=5.0, material="sio2")


def test_matter_spec_rejects_ragged_rows() -> None:
    with pytest.raises(ValueError, match="same length"):
        AssemblySpec("bad", ["10", "1"], resolution_nm=5.0, material="x")


def test_matter_footprint_and_placements() -> None:
    spec = _spec()
    assert spec.placements == 5
    assert spec.footprint_nm == (15.0, 15.0)


def test_matter_infeasible_when_resolution_is_too_coarse() -> None:
    verdict = feasibility(_spec(), Fabricator("coarse", min_resolution_nm=50.0, materials=("sio2",)))
    assert verdict["feasible"] is False
    assert any("resolution" in b for b in verdict["blockers"])


def test_matter_infeasible_when_material_is_unavailable() -> None:
    verdict = feasibility(_spec(), Fabricator("m", min_resolution_nm=1.0, materials=("gold",)))
    assert any("material" in b for b in verdict["blockers"])


def test_matter_build_refuses_without_fabricator_hardware() -> None:
    with pytest.raises(SubstrateUnavailable):
        build(_spec(), Substrate())


def test_matter_build_with_hardware_is_explicitly_not_executed() -> None:
    sub = Substrate(capabilities={FABRICATOR.id})
    fab = Fabricator("fine", min_resolution_nm=1.0, materials=("sio2",))
    out = build(_spec(), sub, fab)
    assert out["executed"] is False
    assert "no matter was moved" in out["note"]


def test_matter_plan_without_fabricator_says_so() -> None:
    planned = plan(_spec(), Substrate())
    assert planned["feasible"] is False
    assert "no nanofabricator available" in planned["blockers"]


# ── DIR-15 ─────────────────────────────────────────────────────────────────
def test_orbit_latency_is_a_physical_floor() -> None:
    leo = Orbit("LEO", altitude_km=550.0)
    rtt = OrbitalNode("n1", leo).round_trip_ms()
    assert 3.0 < rtt < 5.0  # ~3.7 ms at 550 km


def test_far_side_node_is_far_slower() -> None:
    """The surface hop dominates: 180 degrees is orders of magnitude away."""
    leo = Orbit("LEO", altitude_km=550.0)
    overhead = OrbitalNode("a", leo).round_trip_ms(0.0)
    far_side = OrbitalNode("b", leo).round_trip_ms(180.0)
    assert far_side > overhead * 10
    # 180 deg at light speed is ~137 ms RTT -- still inside the interactive
    # budget, which is exactly why the planner reports latency instead of
    # pretending distance alone disqualifies a node.
    assert far_side < INTERACTIVE_RTT_BUDGET_MS


def test_constellation_reports_interactive_capability() -> None:
    leo = Orbit("LEO", altitude_km=550.0)
    nodes = [OrbitalNode("near", leo), OrbitalNode("far", leo)]
    planned = plan_constellation(nodes, Substrate(), None)
    assert planned["feasible"] is False  # no launch capability
    assert planned["interactive_capable"] == ["far", "near"]  # without ground hop, both are close


def test_launch_capability_with_zero_envelope_cannot_place() -> None:
    leo = Orbit("LEO", altitude_km=550.0)
    assert LaunchCapability("none").can_place(leo, 50.0) is False


def test_deploy_refuses_without_launch_hardware() -> None:
    leo = Orbit("LEO", altitude_km=550.0)
    with pytest.raises(SubstrateUnavailable):
        deploy([OrbitalNode("n1", leo)], Substrate())


def test_deploy_with_hardware_returns_a_manifest_not_a_launch() -> None:
    leo = Orbit("LEO", altitude_km=550.0)
    sub = Substrate(capabilities={"launch_vehicle"})
    out = deploy([OrbitalNode("n1", leo)], sub, LaunchCapability("provider-x"))
    assert out["deployed"] == []
    assert out["executed"] is False
    assert "manifest, not a launch" in out["note"]
