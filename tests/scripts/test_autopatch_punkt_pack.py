"""Tests for scripts/punkt_morning.py, darwin_skill_autopatch.py, build_pro_pack.py.

Focus: pure logic (parsing/scoring), no network, no real skills dir.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod




# ── punkt_morning ────────────────────────────────────────────────────────

def test_cron_health_reports_errors(tmp_path):
    pm = _load("punkt_morning")
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps([
        {"name": "ok-job", "enabled": True, "last_status": "ok"},
        {"name": "bad-job", "enabled": True, "last_status": "error"},
        {"name": "paused-err", "enabled": False, "last_status": "error"},
    ]), encoding="utf-8")
    pm.CRON_JOBS = jobs_file
    out = pm.cron_health()
    assert "3 Jobs" in out
    assert "1 mit Fehler" in out
    assert "bad-job" in out
    assert "paused-err" not in out  # disabled jobs ignored


def test_git_activity_parses_commits(tmp_path):
    pm = _load("punkt_morning")
    pm._git = lambda args: "abc1 feat: x\nabc2 fix: y"
    pm.REPO = tmp_path
    out = pm.git_activity()
    assert "2 Commits" in out
    assert "feat: x" in out


def test_trends_missing_file_is_safe(tmp_path):
    pm = _load("punkt_morning")
    pm.TREND_LATEST = tmp_path / "nope.md"
    assert "keine Datei" in pm.trends()


def test_main_writes_report(tmp_path, capsys):
    pm = _load("punkt_morning")
    pm.TREND_LATEST = tmp_path / "nope.md"
    pm.OUT = tmp_path / "briefing.md"
    pm._git = lambda args: ""
    rc = pm.main()
    assert rc == 0
    text = pm.OUT.read_text(encoding="utf-8")
    assert "PUNKT" in text


# ── darwin_skill_autopatch ──────────────────────────────────────────────

def test_skills_from_report_sorted_worst_first():
    ap = _load("darwin_skill_autopatch")
    report = {"skill_results": [{"name": "a", "score": 50}, {"name": "b", "score": 10}]}
    names = [s["name"] for s in ap.skills_from_report(report)]
    assert names == ["b", "a"]


def test_git_revert_restores_from_bak(tmp_path):
    ap = _load("darwin_skill_autopatch")
    f = tmp_path / "SKILL.md"
    f.write_text("patched", encoding="utf-8")
    bak = f.with_suffix(".md.bak")
    bak.write_text("original", encoding="utf-8")
    assert ap.git_revert(f) is True
    assert f.read_text(encoding="utf-8") == "original"
    assert not bak.exists()
    assert ap.git_revert(f) is False  # no bak left


def test_weak_selection_below_threshold():
    ap = _load("darwin_skill_autopatch")
    report = {"skill_results": [
        {"name": "weak", "score": 30}, {"name": "strong", "score": 80},
        {"name": "edge", "score": 40},
    ]}
    weak = [s for s in ap.skills_from_report(report) if s["score"] < 40][:5]
    assert [s["name"] for s in weak] == ["weak"]  # threshold is exclusive


# ── build_pro_pack ──────────────────────────────────────────────────────

def test_hardcoded_path_detection():
    bp = _load("build_pro_pack")
    d = tmp = Path(pytest.tmp_path) if False else None  # noqa: F841
    skill = Path(__file__).parent / "_packtmp" / "skill-x"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text("use C:\\Users\\damir\\x", encoding="utf-8")
    ok, why = bp.skill_ok(skill)
    assert not ok and "hardcoded" in why
    (skill / "SKILL.md").write_text("clean", encoding="utf-8")
    ok, why = bp.skill_ok(skill)
    assert ok


def test_manifest_shape_after_selection():
    bp = _load("build_pro_pack")
    scores = {"good1": 75, "good2": 71, "low": 40, "darwin-harvested-x": 90}
    cands = sorted(((n, s) for n, s in scores.items()
                    if s >= bp.MIN_SCORE and not n.startswith(bp.EXCLUDE_PREFIXES)),
                   key=lambda kv: -kv[1])
    assert [n for n, _ in cands] == ["good1", "good2"]
