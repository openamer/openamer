"""The three watchdog decisions, tested where the test runner can reach them.

These lived in install-local cron scripts (`$OPENAMER_HOME/scripts/cron-*.py`),
which put the behaviour outside the suite — the "unverified" flag for those paths
came back twice, and it was right. The decisions now live in
`scripts/instrument_crons.py`; the runtime files are six-line shims.

What is pinned here: silence is the default, speech is triggered by a CHANGE, and
a measurement never becomes a ranking claim.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


@pytest.fixture(scope="module")
def ic():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("instrument_crons", SCRIPTS / "instrument_crons.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["instrument_crons"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _goal(goal_id: str, verdicts: list[str], **over) -> dict:
    row = {"id": goal_id, "progress": 0.2, "reverted": 3, "milestones": 5,
           "verdicts": verdicts, "kill_suggestion": ""}
    row.update(over)
    return row


def _goal_report(rows: list[dict], without: int = 0) -> dict:
    return {"ts": "2026-11-18T21:00:00", "goals": len(rows),
            "without_kill_criterion": without, "rows": rows}


# ── goal audit ─────────────────────────────────────────────────────────────

def test_goal_digest_is_silent_when_nothing_changed(ic):
    report = _goal_report([_goal("supremacy", ["TREADMILL"])])
    lines, state = ic.goal_digest(report, {"hard": {"supremacy": ["TREADMILL"]}, "no_kill": 0})
    assert lines == [] and state == {"hard": {"supremacy": ["TREADMILL"]}, "no_kill": 0}


def test_goal_digest_speaks_for_a_new_hard_finding(ic):
    report = _goal_report([_goal("monetization", ["TREADMILL"], kill_suggestion="kill_if: x")])
    lines, state = ic.goal_digest(report, {})
    assert any("monetization" in l for l in lines)
    assert any("kill_if: x" in l for l in lines)
    assert state["hard"] == {"monetization": ["TREADMILL"]}


def test_goal_digest_reports_the_structural_gap(ic):
    report = _goal_report([_goal("energy", ["NO_KILL"])], without=5)
    lines, _ = ic.goal_digest(report, {})
    assert any("5/1 goals still declare no kill criterion" in l for l in lines)


def test_goal_digest_announces_a_cleared_goal(ic):
    report = _goal_report([_goal("energy", ["ON_TRACK"])])
    lines, state = ic.goal_digest(report, {"hard": {"energy": ["TREADMILL"]}, "no_kill": 0})
    assert any("cleared energy" in l for l in lines) and state["hard"] == {}


# ── incident classes ───────────────────────────────────────────────────────

def _incident(counts: dict, failures: int = 10, samples: dict | None = None) -> dict:
    return {"ts": "t", "failures": failures,
            "classes": {k: {"count": v, "rule": f"rule-{k}",
                            "sample": (samples or {}).get(k, "")} for k, v in counts.items()}}


def test_incident_digest_is_silent_on_steady_state(ic):
    report = _incident({"measurement_lie": 4})
    lines, state = ic.incident_digest(report, {"counts": {"measurement_lie": 4}})
    assert lines == [] and state == {"counts": {"measurement_lie": 4}}


def test_incident_digest_speaks_for_a_new_class_with_its_rule(ic):
    lines, _ = ic.incident_digest(_incident({"stale_process": 2}), {})
    assert any("new class: stale_process" in l for l in lines)
    assert any("rule: rule-stale_process" in l for l in lines)


def test_incident_digest_flags_a_taxonomy_hole(ic):
    report = _incident({"unknown": 3}, samples={"unknown": "weird text"})
    lines, _ = ic.incident_digest(report, {"unknown": 3})
    assert any("fell through to 'unknown'" in l and "weird text" in l for l in lines)


def test_incident_digest_flags_a_doubling(ic):
    lines, _ = ic.incident_digest(_incident({"quota_network": 8}), {"counts": {"quota_network": 2}})
    assert any("jump: quota_network: 2 -> 8" in l for l in lines)


# ── fresh bench ────────────────────────────────────────────────────────────

def _bench(results: list[dict], ranking: str = "") -> dict:
    return {"ts": "2026-11-18T20:46:01", "items": 3, "seed": "42",
            "results": results, "ranking": ranking}


def _row(name: str, resolved: int, n: int, lo: float, hi: float, error: str = "") -> dict:
    return {"subject": name, "resolved": resolved, "n": n, "share": resolved / n,
            "ci95": [lo, hi], "model_error": bool(error), "model_error_reason": error}


def test_bench_report_prints_every_subject_with_its_interval(ic):
    lines = ic.bench_report(_bench([_row("Mini-OpenAmer", 1, 3, 0.06, 0.79),
                                   _row("reference", 3, 3, 0.44, 1.0)]))
    assert lines[0].startswith("fresh bench 2026-11-18")
    assert any("Mini-OpenAmer" in l and "1/3" in l and "[6.0, 79.0]" in l for l in lines)
    assert any("reference" in l and "3/3" in l for l in lines)


def test_a_model_error_is_not_printed_as_a_score(ic):
    lines = ic.bench_report(_bench([_row("GPU worker", 0, 3, 0.0, 0.56, "URLError: timed out")]))
    joined = "\n".join(lines)
    assert "MODEL ERROR — not a score" in joined
    assert "0/3" not in joined and "unreachable" in joined


def test_the_ranking_warning_is_carried_through(ic):
    lines = ic.bench_report(_bench([_row("a", 1, 3, 0.06, 0.79)],
                                   ranking="ranking NOT established by this run (intervals overlap)"))
    assert any("NOT established" in l for l in lines)
