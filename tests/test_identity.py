"""Behaviour contracts for OpenAmer's identity core.

These test *relationships that must hold*, not frozen values: the identity is
measured, so its numbers move. What must not move is the contract -- a
rendered identity is always consistent with a fresh measurement, a wrong claim
is always caught, and a missing source is reported as unmeasured rather than
silently zeroed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openamer_cli import identity


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated OPENAMER_HOME so these never touch the real install."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    return tmp_path


def _seed_sources(home: Path) -> None:
    """Create the artifacts the identity measures, with known content."""
    self_model = home / "memory" / "self_model"
    self_model.mkdir(parents=True, exist_ok=True)
    (self_model / "current_state.json").write_text(
        json.dumps(
            {
                "age_days": 3,
                "memory_episodes": 10,
                "evolution_events": 20,
                "world_model_edges": 30,
                "learning_buffer": 40,
                "knowledge_to_action": 50,
                "meta_lessons": 2,
                "tools": 9,
                "identity": "test core",
            }
        ),
        encoding="utf-8",
    )
    memory = home / "memory"
    (memory / "longterm_episodes.jsonl").write_text("a\nb\nc\n", encoding="utf-8")
    (memory / "world_model.jsonl").write_text("x\ny\n", encoding="utf-8")
    cron = home / "cron"
    cron.mkdir(exist_ok=True)
    (cron / "jobs.json").write_text(
        json.dumps({"jobs": [{"enabled": True}, {"enabled": False}]}), encoding="utf-8"
    )
    skill_dir = home / "skills" / "demo"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")


def test_genesis_is_written_once_and_never_clobbered(home: Path) -> None:
    """Genesis is immutable: a second call must not rewrite an existing file."""
    first = identity.ensure_genesis()
    assert first["belongs_to"] == "Damir"
    path = identity.genesis_path()

    # Simulate a hand-corrected genesis; ensure_genesis must respect it.
    edited = dict(first)
    edited["belongs_to"] = "someone-else"
    path.write_text(json.dumps(edited), encoding="utf-8")

    assert identity.ensure_genesis()["belongs_to"] == "someone-else"


def test_corrupt_genesis_falls_back_to_the_code_of_record(home: Path) -> None:
    """A corrupt genesis is rewritten from GENESIS, never trusted or crashed on."""
    identity.ensure_genesis()
    identity.genesis_path().write_text("{not json", encoding="utf-8")
    assert identity.ensure_genesis()["belongs_to"] == identity.GENESIS["belongs_to"]


def test_refresh_then_verify_is_consistent(home: Path) -> None:
    """The central contract: what refresh writes, verify must accept."""
    _seed_sources(home)
    identity.refresh_identity()
    result = identity.verify_identity()
    assert result["ok"], result["drift"]


def test_verify_catches_a_stale_claim(home: Path) -> None:
    """A number that reality no longer supports must be reported as drift."""
    _seed_sources(home)
    identity.refresh_identity()

    # Inflate a measured count the way a hand-written, self-flattering
    # narrative would.
    path = identity.narrative_path()
    text = path.read_text(encoding="utf-8")
    real = identity.measure_facts()["facts"]["memory_episodes"]["value"]
    path.write_text(
        text.replace(f"| Episodes (core's own count) | {real} |", 
                     f"| Episodes (core's own count) | {real + 1000} |"),
        encoding="utf-8",
    )

    result = identity.verify_identity()
    assert not result["ok"]
    assert any("memory_episodes" in item for item in result["drift"])


def test_missing_sources_are_unmeasured_not_zero(home: Path) -> None:
    """A missing artifact is an honest gap, never a zero."""
    measured = identity.measure_facts()
    # Entries carry the path in the message, so match on the fact name.
    assert any("skills" in item for item in measured["unmeasured"])
    assert any("episodic_ledger_lines" in item for item in measured["unmeasured"])
    # The key contract: nothing was invented for the absent sources.
    assert "skills" not in measured["facts"]
    assert "episodic_ledger_lines" not in measured["facts"]


def test_identity_may_disclaim_a_borrowed_glyph(home: Path) -> None:
    """Naming a foreign glyph to disclaim it is not drift -- claiming it is."""
    _seed_sources(home)
    identity.refresh_identity()
    assert identity.verify_identity()["ok"]

    path = identity.narrative_path()
    text = path.read_text(encoding="utf-8")

    # A negation-aware check: the disclaimer passes ...
    negated = text + "\nMy mark is my own, not the caduceus.\n"
    path.write_text(negated, encoding="utf-8")
    assert identity.verify_identity()["ok"], "a disclaimer must not be flagged"

    # ... but a positive claim does not.
    claimed = text + "\nMy mark is the caduceus.\n"
    path.write_text(claimed, encoding="utf-8")
    assert not identity.verify_identity()["ok"]


def test_history_appends_one_record_per_refresh(home: Path) -> None:
    """The measured self is a timeline, not a single overwritten snapshot."""
    _seed_sources(home)
    identity.refresh_identity()
    identity.refresh_identity()
    lines = identity.history_path().read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        assert "facts" in json.loads(line)


def test_rendered_identity_cites_its_sources(home: Path) -> None:
    """Every rendered number must carry the file it came from."""
    _seed_sources(home)
    measured = identity.measure_facts()
    rendered = identity.render_identity(measured)
    for entry in measured["facts"].values():
        assert str(entry["value"]) in rendered
        assert entry["source"] in rendered


# --- silicon is measured, never asserted (added 2026-11-19) ------------------
# The identity used to state "I am a CPU-only install here: no GPU acceleration
# is available locally." On this machine that was measurably false (Radeon 860M
# iGPU + XDNA "NPU Compute Accelerator Device"), which is exactly the failure
# this module is supposed to prevent: a self-description that asserts hardware
# instead of probing it. These tests pin the replacement contract.

_PROBE = {
    "cpu": "AMD Ryzen AI 7 350 w/ Radeon 860M",
    "gpus": ["AMD Radeon(TM) 860M Graphics"],
    "npus": ["NPU Compute Accelerator Device"],
}


def test_accelerators_are_probed_and_rendered(home: Path, monkeypatch) -> None:
    """A detected NPU/GPU must appear in the identity, with its probe source."""
    _seed_sources(home)
    monkeypatch.setattr(identity, "measure_accelerators", lambda: _PROBE)
    measured = identity.measure_facts()
    assert "accelerators" in measured["facts"]
    value = measured["facts"]["accelerators"]["value"]
    assert "NPU Compute Accelerator Device" in value
    assert "Radeon" in value

    rendered = identity.render_identity(measured)
    assert "NPU Compute Accelerator Device" in rendered
    assert "CPU-only" not in rendered


def test_retired_cpu_only_claim_is_not_rendered(home: Path, monkeypatch) -> None:
    """A stored genesis record with the old fixed claim must not be repeated."""
    _seed_sources(home)
    identity.ensure_genesis()
    path = identity.genesis_path()
    record = json.loads(path.read_text(encoding="utf-8"))
    record["boundaries"].append(
        "I am a CPU-only install here: no GPU acceleration is available locally."
    )
    path.write_text(json.dumps(record), encoding="utf-8")

    monkeypatch.setattr(identity, "measure_accelerators", lambda: _PROBE)
    rendered = identity.render_identity(identity.measure_facts())
    assert "CPU-only" not in rendered
    assert "no GPU acceleration" not in rendered
    assert "measured, not assumed" in rendered


def test_verify_flags_cpu_only_drift_against_a_live_probe(home: Path, monkeypatch) -> None:
    """Claiming CPU-only while the probe sees silicon is drift, not a boundary."""
    _seed_sources(home)
    monkeypatch.setattr(identity, "measure_accelerators", lambda: _PROBE)
    identity.refresh_identity()
    assert identity.verify_identity()["ok"]

    path = identity.narrative_path()
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n- I am a CPU-only install: no GPU acceleration is available locally.\n",
        encoding="utf-8",
    )
    result = identity.verify_identity()
    assert not result["ok"]
    assert any("CPU-only" in item for item in result["drift"])


def test_unmeasurable_accelerators_are_reported_unmeasured(home: Path, monkeypatch) -> None:
    """No probe -> an honest gap, not an invented hardware claim."""
    _seed_sources(home)
    monkeypatch.setattr(identity, "measure_accelerators", lambda: None)
    measured = identity.measure_facts()
    assert "accelerators" not in measured["facts"]
    assert any("accelerators" in item for item in measured["unmeasured"])
    rendered = identity.render_identity(measured)
    assert "unmeasured on this platform" in rendered
