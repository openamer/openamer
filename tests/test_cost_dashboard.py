"""Tests for the Cost Dashboard (cost_dashboard.py).

Tests are isolated from real filesystem I/O by using temp files for the
SQLite store and monkeypatching environment variables.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from openamer_cli.cost_dashboard import (
    CostRecord,
    CostStore,
    CostTracker,
    get_budget_status,
    get_cost_stats,
)


# =============================================================================
# CostRecord tests
# =============================================================================


class TestCostRecord:
    """CostRecord dataclass behaviour."""

    def test_frozen(self) -> None:
        r = CostRecord("2026-01-01T00:00:00", "gpt-4o", "openai", 100, 50, "0.01", "sess-1")
        with pytest.raises(Exception):
            r.model = "gpt-3.5"  # type: ignore[misc]

    def test_cost_as_decimal(self) -> None:
        r = CostRecord("2026-01-01T00:00:00", "gpt-4o", "openai", 100, 50, "0.01", "sess-1")
        assert isinstance(r.cost, Decimal)
        assert r.cost == Decimal("0.01")

    def test_total_tokens(self) -> None:
        r = CostRecord("2026-01-01T00:00:00", "gpt-4o", "openai", 100, 50, "0.01", "sess-1")
        assert r.total_tokens == 150

    def test_to_dict(self) -> None:
        r = CostRecord("2026-01-01T00:00:00", "gpt-4o", "openai", 100, 50, "0.01", "sess-1")
        d = r.to_dict()
        assert d["model"] == "gpt-4o"
        assert d["cost"] == "0.01"
        assert d["tokens_in"] == 100

    def test_from_dict_roundtrip(self) -> None:
        d = {
            "timestamp": "2026-06-15T12:00:00",
            "model": "claude-3-opus",
            "provider": "anthropic",
            "tokens_in": 500,
            "tokens_out": 200,
            "cost": "0.015",
            "session_id": "sess-roundtrip",
        }
        r = CostRecord.from_dict(d)
        assert r.model == "claude-3-opus"
        assert r.cost_usd == Decimal("0.015")
        assert r.tokens_in == 500
        assert r.tokens_out == 200


# =============================================================================
# CostStore tests
# =============================================================================


class TestCostStore:
    """SQLite-backed CostStore tests using a temporary database."""

    @pytest.fixture
    def store(self) -> CostStore:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        store = CostStore(db_path=db_path)
        yield store
        # Force-close SQLite connections so Windows can delete the file
        store._path = None  # type: ignore[assignment]
        import gc
        gc.collect()
        try:
            os.unlink(db_path)
        except PermissionError:
            pass  # Windows file lock — acceptable cleanup artifact

    def test_insert_and_query(self, store: CostStore) -> None:
        r = CostRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model="gpt-4o",
            provider="openai",
            tokens_in=100,
            tokens_out=50,
            cost="0.005",
            session_id="sess-test",
        )
        row_id = store.insert(r)
        assert row_id > 0

        results = store.query(days=1)
        assert len(results) == 1
        assert results[0].model == "gpt-4o"
        assert results[0].cost_usd == Decimal("0.005")

    def test_query_with_filters(self, store: CostStore) -> None:
        r1 = CostRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model="gpt-4o", provider="openai",
            tokens_in=100, tokens_out=50, cost="0.005", session_id="sess-a",
        )
        r2 = CostRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model="claude-3-haiku", provider="anthropic",
            tokens_in=200, tokens_out=100, cost="0.002", session_id="sess-b",
        )
        store.insert(r1)
        store.insert(r2)

        filtered = store.query(days=1, model="gpt-4o")
        assert len(filtered) == 1
        assert filtered[0].session_id == "sess-a"

        filtered2 = store.query(days=1, provider="anthropic")
        assert len(filtered2) == 1
        assert filtered2[0].session_id == "sess-b"

    def test_total_cost(self, store: CostStore) -> None:
        store.insert(CostRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model="m1", provider="p1",
            tokens_in=10, tokens_out=5, cost="1.00", session_id="s",
        ))
        store.insert(CostRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model="m2", provider="p2",
            tokens_in=20, tokens_out=10, cost="2.50", session_id="s",
        ))
        total = store.total_cost(days=1)
        assert total == Decimal("3.50")


# =============================================================================
# CostTracker tests
# =============================================================================


class TestCostTracker:
    """CostTracker in-memory tracking and reporting."""

    @pytest.fixture
    def tracker(self) -> CostTracker:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        store = CostStore(db_path=db_path)
        yield CostTracker(store=store)
        import gc
        gc.collect()
        try:
            os.unlink(db_path)
        except PermissionError:
            pass

    def test_record_and_stats(self, tracker: CostTracker) -> None:
        tracker.record("gpt-4o", "openai", 100, 50, "0.01", "sess-1")
        tracker.record("gpt-4o", "openai", 200, 100, "0.02", "sess-1")
        tracker.record("claude-3-haiku", "anthropic", 50, 25, "0.001", "sess-2")

        stats = tracker.get_cost_stats(days=30)
        assert stats["total_calls"] == 3
        assert Decimal(stats["total_cost"]) == Decimal("0.031")  # 0.01 + 0.02 + 0.001
        assert stats["total_tokens"] == 525  # 150 + 300 + 75

    def test_get_cost_stats_breakdowns(self, tracker: CostTracker) -> None:
        tracker.record("gpt-4o", "openai", 100, 50, "0.01", "sess-a")
        tracker.record("claude-3-haiku", "anthropic", 50, 25, "0.005", "sess-b")

        stats = tracker.get_cost_stats(days=30)
        assert len(stats["by_model"]) == 2
        assert len(stats["by_provider"]) == 2
        assert len(stats["by_session"]) == 2

    def test_get_budget_status(self, tracker: CostTracker, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAMER_MONTHLY_BUDGET", "50")
        budget = tracker.get_budget_status()
        assert Decimal(budget["monthly_budget"]) == Decimal("50")
        assert "spent_this_month" in budget
        assert "remaining" in budget
        assert "percent_used" in budget
        assert budget["percent_used"] >= 0

    def test_record_returns_record(self, tracker: CostTracker) -> None:
        r = tracker.record("gpt-4o", "openai", 100, 50, "0.01", "sess-1")
        assert isinstance(r, CostRecord)
        assert r.model == "gpt-4o"


# =============================================================================
# Module-level convenience tests
# =============================================================================


class TestModuleLevel:
    """Module-level convenience functions."""

    def test_get_cost_stats_returns_dict(self) -> None:
        # These should never raise even with empty DB
        stats = get_cost_stats(days=30)
        assert isinstance(stats, dict)
        assert "total_cost" in stats

    def test_get_budget_status_returns_dict(self) -> None:
        status = get_budget_status()
        assert isinstance(status, dict)
        assert "monthly_budget" in status