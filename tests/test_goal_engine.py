"""Tests for agent.goal_engine."""

import json
import tempfile
from pathlib import Path

from agent.goal_engine import AgentGoal, GoalEngine


def test_default_goals_load(tmp_path):
    engine = GoalEngine(openamer_home=str(tmp_path))
    assert len(engine.goals) >= 4
    ids = {g.id for g in engine.goals}
    assert "autonomy" in ids
    assert "live_verification" in ids


def test_goals_ranked_by_score(tmp_path):
    engine = GoalEngine(openamer_home=str(tmp_path))
    scores = [g.score for g in engine.goals]
    assert scores == sorted(scores, reverse=True)


def test_inactive_goal_hidden(tmp_path):
    engine = GoalEngine(openamer_home=str(tmp_path))
    engine._goals[0].active = False
    active_ids = {g.id for g in engine.goals}
    assert engine._goals[0].id not in active_ids


def test_record_and_read_outcomes(tmp_path):
    engine = GoalEngine(openamer_home=str(tmp_path))
    engine.record_outcome("autonomy", True, "did it")
    engine.record_outcome("autonomy", False, "blocked")
    recs = engine.recent_outcomes("autonomy", n=10)
    assert len(recs) == 2
    assert recs[0]["success"] is False
    assert recs[1]["success"] is True


def test_context_block_includes_active_goals(tmp_path):
    engine = GoalEngine(openamer_home=str(tmp_path))
    block = engine.build_context_block()
    assert "OpenAmer-Agent" in block
    assert "Live-Verifikation" in block
    assert "Autonom durchführen" in block


def test_json_fallback_when_no_yaml(tmp_path):
    goals_path = tmp_path / "openamer_goals.json"
    goals_path.write_text(json.dumps({"goals": [{"id": "x", "name": "Y", "description": "z"}]}))
    engine = GoalEngine(openamer_home=str(tmp_path))
    assert engine.goals[0].id == "x"
