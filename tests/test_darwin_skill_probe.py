"""Tests for the Darwin skill probe (scripts/darwin_skill_probe.py).

The probe is the outcome half of Darwin's fitness, so its scoring has to be
pinned to contracts rather than to whatever the current population happens to
score: a skill that references nothing must not be punished, and a skill whose
reference does not resolve must be.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _probe_module():
    spec = importlib.util.spec_from_file_location(
        "darwin_skill_probe", REPO / "scripts" / "darwin_skill_probe.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def probe():
    return _probe_module()


def _write_skill(tmp_path: Path, body: str) -> Path:
    skill_dir = tmp_path / "sample-skill"
    skill_dir.mkdir()
    md = skill_dir / "SKILL.md"
    md.write_text(body, encoding="utf-8")
    return md


def test_a_real_reference_scores_fully(probe, tmp_path, monkeypatch):
    """A path that exists under one of the candidate roots resolves."""
    real = tmp_path / "helper.py"
    real.write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(probe, "candidate_roots", lambda: [tmp_path])

    md = _write_skill(tmp_path, "Run `helper.py` to do the thing.\n")
    result = probe.probe_skill(md)

    assert result["refs"] == 1
    assert result["score"] == 1.0
    assert result["missing"] == []


def test_a_dangling_reference_is_penalised(probe, tmp_path, monkeypatch):
    """The whole point: a skill naming a file that is gone is unfit."""
    monkeypatch.setattr(probe, "candidate_roots", lambda: [tmp_path])

    md = _write_skill(tmp_path, "Run `ghost.py` to do the thing.\n")
    result = probe.probe_skill(md)

    assert result["refs"] == 1
    assert result["score"] == 0.0
    assert result["missing"] == ["ghost.py"]


def test_a_skill_without_references_is_not_punished(probe, tmp_path, monkeypatch):
    """Prose-only skills cannot be judged, so they score 1.0 — an unmeasurable
    skill must not lose fitness just for being unmeasurable."""
    monkeypatch.setattr(probe, "candidate_roots", lambda: [tmp_path])

    md = _write_skill(tmp_path, "# A skill\n\nThink carefully, then act.\n")
    result = probe.probe_skill(md)

    assert result["refs"] == 0
    assert result["score"] == 1.0


def test_urls_and_home_paths_are_not_filesystem_claims(probe, tmp_path, monkeypatch):
    """`https://...` and `~/...` never resolve locally; counting them as broken
    would punish skills for documenting where a tool lives."""
    monkeypatch.setattr(probe, "candidate_roots", lambda: [tmp_path])

    assert probe.resolve("https://example.com/x.py") is True
    assert probe.resolve("~/scripts/x.py") is True


def test_the_score_is_the_ratio_of_resolved_references(probe, tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "candidate_roots", lambda: [tmp_path])
    (tmp_path / "here.py").write_text("ok\n", encoding="utf-8")

    md = _write_skill(
        tmp_path,
        "First `here.py`, then `gone.py`, and also `nowhere.py`.\n",
    )
    result = probe.probe_skill(md)

    assert result["refs"] == 3
    assert result["ok"] == 1
    assert result["score"] == pytest.approx(0.333, abs=0.001)


def test_a_variant_that_adds_a_dead_reference_scores_lower(probe, tmp_path, monkeypatch):
    """The A/B Darwin now runs must be able to see *something*.

    Measured against the live population every mutation delta is currently 0.00,
    because mutations vary trigger prose while the probe measures referenced
    artifacts — the two do not intersect. What the probe can still catch is
    damage: a variant that names an artifact which does not exist must score
    below its parent, otherwise the whole A/B is decoration.
    """
    monkeypatch.setattr(probe, "candidate_roots", lambda: [tmp_path])
    (tmp_path / "real.py").write_text("ok\n", encoding="utf-8")

    parent = probe.score_text("Run `real.py` to check the thing.\n")
    variant = probe.score_text("Run `real.py`, then `ghost.py` to check.\n")

    assert parent["score"] == 1.0
    assert variant["score"] < parent["score"]
    assert variant["missing"] == ["ghost.py"]
