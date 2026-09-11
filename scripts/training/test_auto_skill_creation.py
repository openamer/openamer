#!/usr/bin/env python3
"""Tests for auto_skill_creation.py — dedup guards against re-creating known skills.

Run:  python test_auto_skill_creation.py

Regression guard for the bug fixed 11.09: `dedupe_check()` compared only a
description prefix, but the answer text drifts run-to-run while the question
slug stays constant — so the same skill was re-created (and overwritten) on
every run. Live evidence: the registry held 195 entries across just 33 unique
names, and a run reporting "1 new skill" produced zero net-new directories.

Every test works in a TEMP skills dir + TEMP registry; the real repo
`skills/auto-generated/` and the live `auto_skills.json` are never touched.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_skill_creation as asc


def _sandbox():
    """Point the module at temp skills dir + temp registry, return both paths."""
    d = tempfile.mkdtemp(prefix="autoskill_test_")
    skills = os.path.join(d, "skills")
    os.makedirs(skills, exist_ok=True)
    registry = os.path.join(d, "auto_skills.json")
    asc.AUTO_SKILLS = skills
    asc.REGISTRY = registry
    return skills, registry


def test_name_slug_is_stable_across_drifting_answers():
    """The same question must always slugify to the same skill name."""
    q = "Find the structural connection between energy efficiency and learning process"
    a1 = "KI-Performance-Optimierung: Python-Skript fuer RAM/Disk/Cron-Monitoring"
    a2 = "Performance optimization loop: monitor RAM, disk and cron timings"
    skills, _ = _sandbox()
    first = asc.create_skill_from_insight(q, a1, "test")
    second = asc.create_skill_from_insight(q, a2, "test")
    assert first is not None, "first insight should create a skill"
    assert second is None, "same question with a different answer is a duplicate"
    assert len(os.listdir(skills)) == 1, os.listdir(skills)


def test_existing_directory_blocks_recreation():
    """A pre-existing skill dir is enough to reject, even with an empty registry."""
    q = "How does energy efficiency relate to agent architecture"
    a = "A" * 120
    skills, _ = _sandbox()
    assert asc.create_skill_from_insight(q, a, "test") is not None
    # wipe the registry: the on-disk directory alone must still dedup
    with open(asc.REGISTRY, "w", encoding="utf-8") as f:
        json.dump({"created": [], "count": 0}, f)
    assert asc.create_skill_from_insight(q, a, "test") is None
    assert len(os.listdir(skills)) == 1


def test_identical_description_blocks_even_under_a_new_slug():
    """The original prefix rule still holds: same insight text → duplicate."""
    skills, _ = _sandbox()
    a = "Identical insight answer text that is comfortably longer than fifty chars"
    assert asc.create_skill_from_insight("first phrasing of the question", a, "t") is not None
    assert asc.create_skill_from_insight("second phrasing of the question", a, "t") is None
    assert len(os.listdir(skills)) == 1


def test_distinct_insights_still_create_distinct_skills():
    """The guard must not over-block: genuinely new insights still land."""
    skills, _ = _sandbox()
    a1 = "First distinct answer about quantization and 4-bit inference on CPUs ok"
    a2 = "Second distinct answer about retrieval augmented generation pipelines ok"
    assert asc.create_skill_from_insight("question alpha about quantization", a1, "t") is not None
    assert asc.create_skill_from_insight("question beta about retrieval", a2, "t") is not None
    assert len(os.listdir(skills)) == 2


def test_registry_records_each_created_skill_once():
    """Registry entries must stay unique by name — no duplicate bookkeeping."""
    skills, registry = _sandbox()
    q = "Repeated question about latency budgets in local inference stacks"
    for ans in ("answer one " * 10, "answer two " * 10, "answer three " * 10):
        asc.create_skill_from_insight(q, ans, "t")
    reg = json.load(open(registry, encoding="utf-8"))
    names = [e["name"] for e in reg["created"]]
    assert len(names) == len(set(names)) == 1, names
    assert reg["count"] == 1


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
