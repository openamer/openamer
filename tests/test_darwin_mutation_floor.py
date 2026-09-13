"""The mutation floor must exclude, not label.

Darwin now measures a variant against its parent with the outcome probe and
refuses to enter a damaging variant as a candidate. That refusal is only real if
something downstream honours it: tournament() trials offspring whose status is
exactly "candidate" (darwin_engine.py:640), so a "rejected" status keeps the
variant out of trials entirely.

Pinned here because the live population currently produces delta 0.00 for every
mutation — the floor is silent in production, which is precisely when a
regression in it would go unnoticed.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture()
def engine(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "darwin_engine", REPO / "scripts" / "darwin_engine.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    skills = tmp_path / "skills"
    skill_dir = skills / "sample-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "Run `python real.py` to verify the thing.\n", encoding="utf-8"
    )
    (tmp_path / "real.py").write_text("ok\n", encoding="utf-8")

    monkeypatch.setattr(mod, "SKILLS_DIR", skills)
    monkeypatch.setattr(mod, "DARWIN_DIR", tmp_path / "darwin")
    monkeypatch.setattr(mod, "record_lineage", lambda *a, **k: None)
    # The probe resolves references against the real roots; point them at tmp so
    # the fixture decides what exists.
    monkeypatch.setattr(mod, "_probe_text", _probe_with_roots(tmp_path))
    return mod


def _probe_with_roots(root: Path):
    """A probe scorer that only trusts *root*."""
    from importlib import util as _util

    spec = _util.spec_from_file_location(
        "probe_for_floor", REPO / "scripts" / "darwin_skill_probe.py"
    )
    probe = _util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    def score(text: str) -> dict:
        refs = [m.group(1) or m.group(2) for m in probe.REF_RE.finditer(text)]
        refs = [r for r in dict.fromkeys(refs) if r]
        missing = [r for r in refs if not (root / r).exists() and not r.startswith(("http", "~"))]
        total = len(refs)
        ok = total - len(missing)
        return {"refs": total, "ok": ok, "score": ok / total if total else 1.0, "missing": missing}

    return score


def _run(engine, monkeypatch, variant_text: str) -> dict:
    monkeypatch.setattr(engine, "_mutate_skill_md", lambda text, op: variant_text)
    fitness = {"sample-skill": {"fitness": 10.0, "usage": 0}}
    offspring = engine.mutate(fitness, top_n=1, apply=True)
    assert offspring, "mutate produced nothing — fixture is wrong, not the floor"
    return offspring[0]


def test_a_variant_that_breaks_a_reference_is_rejected(engine, monkeypatch):
    result = _run(engine, monkeypatch, "Run `python ghost.py` to verify the thing.\n")

    assert result["delta"] < 0
    assert result["status"] == "rejected"

    saved = json.loads(
        (engine.DARWIN_DIR / "offspring" / f"{result['child']}.json").read_text(encoding="utf-8")
    )
    assert saved["status"] == "rejected", "the saved record is what tournament() reads"


def test_a_harmless_variant_stays_a_candidate(engine, monkeypatch):
    """Positive control: equal or better must not be filtered out."""
    result = _run(engine, monkeypatch, "Run `python real.py` to verify the thing.\n")

    assert result["delta"] == 0.0
    assert result["status"] == "candidate"
