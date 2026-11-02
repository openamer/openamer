"""Cost CLI must report canonical usage, not an unwritten shadow database."""

import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from agent.insights import InsightsEngine
from openamer_cli import cost_dashboard as dashboard
from openamer_state import SessionDB


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    monkeypatch.delenv("OPENAMER_COST_DB", raising=False)
    monkeypatch.setattr(dashboard, "_default_tracker", None)
    # Tests are deterministic and must not require models.dev or credentials.
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    from agent.usage_pricing import _ollama_cloud_catalog
    _ollama_cloud_catalog.cache_clear()
    state = SessionDB(db_path=tmp_path / "state.db")
    yield state
    state.close()


def record(db, sid="cloud", **kwargs):
    db.create_session(session_id=sid, source="cli", model="deepseek-v4.1-flash")
    args = dict(model="deepseek-v4.1-flash", billing_provider="ollama-cloud",
                input_tokens=1_000_000, output_tokens=1_000_000,
                estimated_cost_usd=0, cost_status="unknown", api_call_count=2)
    args.update(kwargs)
    db.update_token_counts(sid, **args)


def test_unknown_stored_zero_is_repriced_in_insights(db):
    record(db)
    report = InsightsEngine(db).generate(days=30)
    assert report["overview"]["estimated_cost"] == pytest.approx(1.5)
    assert report["models"][0]["cost_status"] == "estimated"


def test_cost_cli_uses_session_database_without_writing_it(db, tmp_path):
    record(db)
    before = db._conn.total_changes
    stats = dashboard.get_cost_stats(days=30)
    assert Decimal(stats["total_cost"]) == Decimal("1.50")
    assert stats["total_calls"] == 2
    assert stats["total_tokens"] == 2_000_000
    assert stats["by_provider"][0]["key"] == "ollama-cloud"
    assert Decimal(stats["by_provider"][0]["cost"]) == Decimal("1.50")
    assert stats["data_source"] == "session_db"
    assert db._conn.total_changes == before
    assert not (tmp_path / "cost_dashboard.db").exists()
    assert db._conn.execute("SELECT cost_status FROM sessions").fetchone()[0] == "unknown"


def test_existing_estimate_and_subscription_zero_are_preserved(db):
    record(db, sid="paid", estimated_cost_usd=0.25, cost_status="estimated")
    record(db, sid="included", model="gpt-6.1-sol", billing_provider="openai-codex",
           cost_status="included")
    stats = dashboard.get_cost_stats()
    assert Decimal(stats["total_cost"]) == Decimal("0.25")
    assert stats["included_calls"] == 2
    assert stats["unknown_cost_records"] == 0


def test_unknown_price_is_visible_not_silently_free(db, capsys):
    record(db, model="unpublished-model", billing_provider="unknown")
    stats = dashboard.get_cost_stats()
    assert stats["unknown_cost_records"] == 1
    assert stats["unknown_cost_calls"] == 2
    dashboard.print_cost_report()
    out = capsys.readouterr().out
    assert "unknown" in out.lower()
    assert "estimate" in out.lower()
    assert "invoice" in out.lower()


def test_auxiliary_calls_and_legacy_residual_are_not_lost_or_counted_twice(db):
    record(db, input_tokens=100, output_tokens=0, estimated_cost_usd=1,
           cost_status="estimated", api_call_count=1)
    # Gateway absolute summary exceeds the per-route rows.
    db.update_token_counts("cloud", input_tokens=1000, output_tokens=0,
                           estimated_cost_usd=3, cost_status="estimated",
                           api_call_count=3, absolute=True)
    # Aux tokens are absent from sessions summary, and cannot offset its residual.
    db.record_auxiliary_usage("cloud", "vision", model="aux-model",
                              billing_provider="aux-provider", input_tokens=500,
                              estimated_cost_usd=2)
    stats = dashboard.get_cost_stats()
    assert Decimal(stats["total_cost"]) == Decimal("5")
    assert stats["total_tokens"] == 1500
    assert stats["total_calls"] == 4
    assert dict((x["key"], Decimal(x["cost"])) for x in stats["by_provider"]) == {
        "ollama-cloud": Decimal("3"), "aux-provider": Decimal("2")}
    insights = InsightsEngine(db).generate()
    assert insights["overview"]["estimated_cost"] == pytest.approx(5)
    assert insights["overview"]["total_tokens"] == 1500


def test_calendar_month_budget_excludes_previous_month(db):
    record(db, sid="now", estimated_cost_usd=2, cost_status="estimated")
    record(db, sid="previous", estimated_cost_usd=99, cost_status="estimated")
    first = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    db._conn.execute("UPDATE sessions SET started_at=? WHERE id='previous'",
                     ((first - timedelta(seconds=1)).timestamp(),))
    db._conn.commit()
    budget = dashboard.get_budget_status()
    assert Decimal(budget["spent_this_month"]) == Decimal("2")


def test_profile_home_is_resolved_per_call_not_global(db, tmp_path, monkeypatch):
    record(db)
    assert Decimal(dashboard.get_cost_stats()["total_cost"]) > 0
    other = tmp_path / "other-profile"
    monkeypatch.setenv("OPENAMER_HOME", str(other))
    stats = dashboard.get_cost_stats()
    assert Decimal(stats["total_cost"]) == 0
    assert not other.exists(), "Read-only cost queries must not initialize a new profile"


def test_real_cli_subprocess_reads_canonical_database(db):
    record(db, estimated_cost_usd=2.5, cost_status="estimated")
    env = dict(os.environ, PYTHONUTF8="1")
    import sys
    result = subprocess.run(
        [sys.executable, "-m", "openamer_cli.main", "cost", "stats", "--pretty"],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert result.returncode == 0, result.stderr
    stats = json.loads(result.stdout)
    assert Decimal(stats["total_cost"]) == Decimal("2.5")
    assert stats["total_calls"] == 2


def test_explicit_legacy_store_remains_supported(db, tmp_path, monkeypatch):
    path = tmp_path / "explicit.db"
    monkeypatch.setenv("OPENAMER_COST_DB", str(path))
    tracker = dashboard._get_tracker()
    tracker.record("legacy", "legacy", 10, 5, "0.75", "legacy-session")
    assert Decimal(dashboard.get_cost_stats()["total_cost"]) == Decimal("0.75")


def test_missing_route_table_uses_session_aggregate(db):
    record(db, estimated_cost_usd=0.5, cost_status="estimated")
    db._conn.execute("DROP TABLE session_model_usage")
    db._conn.commit()
    stats = dashboard.get_cost_stats()
    assert Decimal(stats["total_cost"]) == Decimal("0.5")
    assert stats["total_calls"] == 2


def test_cost_read_surfaces_broken_database_not_fake_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    monkeypatch.delenv("OPENAMER_COST_DB", raising=False)
    (tmp_path / "state.db").write_bytes(b"not sqlite")
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        dashboard.get_cost_stats()


def test_invalid_route_schema_is_not_silently_ignored(db):
    record(db)
    db._conn.execute("ALTER TABLE session_model_usage RENAME COLUMN billing_provider TO broken_provider")
    db._conn.commit()
    import sqlite3
    with pytest.raises(sqlite3.OperationalError):
        dashboard.get_cost_stats()


def test_new_session_between_insights_queries_does_not_crash(db, monkeypatch):
    record(db)
    engine = InsightsEngine(db)
    sessions = engine._get_sessions(0)
    # Another writer creates a session after the cohort query was read.
    record(db, sid="arrived-later")
    rows = engine.get_cost_usage(0, sessions=sessions)
    assert {r["session_id"] for r in rows} == {"cloud"}


def test_repricing_does_not_double_count_existing_session_estimate(db):
    record(db)
    # Legacy route row has unknown zero, but gateway absolute summary already
    # carries a positive historical estimate for these same tokens.
    db.update_token_counts("cloud", input_tokens=1_000_000, output_tokens=1_000_000,
                           estimated_cost_usd=3, cost_status="estimated",
                           api_call_count=2, absolute=True)
    assert Decimal(dashboard.get_cost_stats()["total_cost"]) == Decimal("3")


def test_pre_aux_task_schema_keeps_route_attribution(db):
    record(db, estimated_cost_usd=2, cost_status="estimated")
    # Old session_model_usage schema has route attribution, but no task column.
    columns = [r[1] for r in db._conn.execute("PRAGMA table_info(session_model_usage)")
               if r[1] != "task"]
    db._conn.execute("CREATE TABLE old_usage AS SELECT " + ",".join(columns)
                     + " FROM session_model_usage")
    db._conn.execute("DROP TABLE session_model_usage")
    db._conn.execute("ALTER TABLE old_usage RENAME TO session_model_usage")
    # Session's current model differs; report must retain the real usage route.
    db.update_session_model("cloud", "current-model")
    db._conn.commit()
    stats = dashboard.get_cost_stats()
    assert stats["by_model"][0]["key"] == "deepseek-v4.1-flash"
    assert Decimal(stats["total_cost"]) == Decimal("2")
