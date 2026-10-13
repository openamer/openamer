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
