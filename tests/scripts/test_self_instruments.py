"""Tests for the six self-instruments (2026-11-18).

Each script here answers one gap the agent named itself: a fresh benchmark, an
automatic recall, a goal audit with kill criteria, cause classes instead of
error counts, and a pixel check for the deployed UI. The tests pin the decisions,
not the cosmetics — a harness that silently scores 0, a recall that returns noise,
an audit that cannot see a treadmill, a classifier that says "unknown".
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _load(name: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bench():
    return _load("fresh_bench")


@pytest.fixture(scope="module")
def recall():
    return _load("episode_recall")


@pytest.fixture(scope="module")
def goals():
    return _load("goal_audit")


@pytest.fixture(scope="module")
def incidents():
    return _load("incident_classes")


@pytest.fixture(scope="module")
def pixels():
    return _load("deploy_pixel_check")


# ── fresh_bench: the tasks must be solvable and never repeated ─────────────

def test_every_generated_task_is_solvable_by_its_own_reference(bench):
    import random
    tasks, _ = bench.make_tasks(6, random.Random("test-seed"))
    bench.verify_tasks(tasks)          # raises if a reference fails its own cases
    assert len(tasks) == 6


def test_signatures_are_unique_across_generators(bench):
    import random
    tasks, _ = bench.make_tasks(6, random.Random("another-seed"))
    sigs = {t["signature"] for t in tasks}
    assert len(sigs) == 6


def test_execution_scoring_separates_right_from_wrong(bench):
    cases = [((), 42)]
    assert bench.run_code("def solve():\n    return 42\n", cases)[0]
    ok, why = bench.run_code("def solve():\n    return 7\n", cases)
    assert not ok and why


def test_a_crashing_solution_is_a_failure_not_a_crash(bench):
    ok, why = bench.run_code("def solve():\n    raise ValueError('boom')\n", [((), 1)])
    assert not ok and "boom" in why


def test_extract_code_prefers_the_fenced_block(bench):
    text = "Here is the code:\n```python\ndef solve():\n    return 1\n```\nThat is all."
    assert bench.extract_code(text).startswith("def solve")


def test_wilson_interval_is_bounded_and_widens_with_few_items(bench):
    lo0, hi0 = bench.wilson(0, 0)
    assert (lo0, hi0) == (0.0, 0.0)
    lo3, hi3 = bench.wilson(3, 3)
    lo20, hi20 = bench.wilson(20, 20)
    assert hi3 <= 1.0 and lo3 >= 0.0
    assert lo20 > lo3          # more items, tighter interval


# ── episode_recall: the German/English bridge and the contradiction flag ───

def test_tokens_bridges_german_diagnosis_vocabulary(recall):
    assert "false positive" .split()[0] in " ".join(recall.tokens("falsch positiv"))
    assert recall.tokens("Platzhalter") & recall.tokens("placeholder")


def test_polarity_reads_both_languages(recall):
    assert recall.polarity("the verifier failed and was wrong") == -1
    assert recall.polarity("behoben und grün, es funktioniert") == 1
    assert recall.polarity("die Katze sitzt auf der Matte") == 0


def test_contradictions_flag_the_older_episode(recall):
    hits = [
        {"ts": "2026-11-18T10:00", "text": "the locale gate failed, false result",
         "topic": ["locale", "gate"]},
        {"ts": "2026-11-18T12:00", "text": "the locale gate is fixed, it works now",
         "topic": ["locale", "gate"]},
    ]
    found = recall.contradictions(hits)
    assert found and found[0]["superseded"].startswith("2026-11-18T10:00")


def test_contradictions_ignore_unrelated_pairs(recall):
    hits = [{"ts": "1", "text": "chrome failed", "topic": ["chrome"]},
            {"ts": "2", "text": "python works", "topic": ["python"]}]
    assert recall.contradictions(hits) == []


# ── goal_audit: it must SEE a treadmill and demand a kill criterion ────────

def _goal(ms, **over):
    base = {"id": "demo", "status": "active", "progress": 0.2,
            "created": "2026-11-01T00:00:00", "target_date": "2027-11-01T00:00:00",
            "milestones": ms}
    base.update(over)
    return base


def test_a_promoted_then_reverted_milestone_is_a_treadmill(goals):
    row = goals.audit_goal(_goal([
        {"id": "m0", "text": "x", "verified": False,
         "promoted_by": "v", "reverted_at": "2026-11-02T00:00:00",
         "verify_ts": "2026-11-18T06:00:00"}] + [
        {"id": f"m{i}", "text": "y", "verified": False, "verify_ts": "2026-11-18T06:00:00"}
        for i in range(1, 4)]), 14)
    assert "TREADMILL" in row["verdicts"] and "NO_KILL" in row["verdicts"]


def test_a_goal_with_a_kill_criterion_loses_the_no_kill_verdict(goals):
    row = goals.audit_goal(_goal(
        [{"id": "m0", "text": "x", "verified": True, "verify_ts": "2026-11-18T06:00:00"}],
        kill_if={"text": "no promotion in 30 days"}), 14)
    assert "NO_KILL" not in row["verdicts"]


def test_staleness_is_measured_from_the_newest_verify_stamp(goals):
    row = goals.audit_goal(_goal(
        [{"id": "m0", "text": "x", "verified": True, "verify_ts": "2020-01-01T00:00:00"}],
        kill_if={"text": "k"}), 14)
    assert "STALLED" in row["verdicts"] and row["staleness_days"] > 1000


# ── incident_classes: today's three incidents and the unknown outcome ──────

def test_the_three_measured_incidents_classify(incidents):
    for expected, text in incidents.FIXTURES:
        assert incidents.classify(text) == expected


def test_an_owner_death_is_unknown_outcome_not_failure(incidents):
    text = ("Scheduler restarted after this execution's owner exited before a durable "
            "terminal state; whether side effects ran is unknown.")
    assert incidents.classify(text) == "unknown_outcome"


def test_a_quota_error_is_not_a_capability_result(incidents):
    assert incidents.classify("HTTP 429 rate limit from provider") == "quota_network"


# ── deploy_pixel_check: the PNG header is read without an image library ────

def test_png_size_reads_width_and_height(pixels, tmp_path):
    png = tmp_path / "x.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + (1920).to_bytes(4, "big")
                    + (1080).to_bytes(4, "big") + b"\x00" * 16)
    assert pixels.png_size(png) == (1920, 1080)


def test_png_size_of_a_non_png_is_zero(pixels, tmp_path):
    junk = tmp_path / "x.bin"
    junk.write_bytes(b"not a png at all")
    assert pixels.png_size(junk) == (0, 0)
