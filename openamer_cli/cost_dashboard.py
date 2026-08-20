"""
Cost Dashboard — track, report, and budget LLM inference costs.

Provides the :class:`CostTracker` class (in-memory and optionally
persisted via the :class:`CostStore` SQLite backend) and a set of
reporting functions for the ``openamer cost`` CLI.

Design principles:

* Costs are stored as :class:`decimal.Decimal` strings to avoid float
  accumulation errors.
* Each :class:`CostRecord` is immutable after creation.
* The tracker accumulates per-session, per-model, and per-provider
  totals without external dependencies beyond the Python stdlib.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

# =============================================================================
# Data model
# =============================================================================


@dataclass(frozen=True)
class CostRecord:
    """An immutable record of a single LLM inference call.

    Attributes:
        timestamp: ISO-8601 datetime string (UTC).
        model: Model name (e.g. ``\"gpt-4o\"``).
        provider: Provider name (e.g. ``\"openai\"``, ``\"openrouter\"``).
        tokens_in: Number of input/prompt tokens.
        tokens_out: Number of output/completion tokens.
        cost: Total cost in USD (as a decimal string for precision).
        session_id: OpenAmer session identifier.
    """

    timestamp: str
    model: str
    provider: str
    tokens_in: int
    tokens_out: int
    cost: Decimal | str
    session_id: str

    def __post_init__(self) -> None:
        """Normalise cost to Decimal."""
        if isinstance(self.cost, str):
            object.__setattr__(self, "cost", Decimal(self.cost))

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.tokens_in + self.tokens_out

    @property
    def cost_usd(self) -> Decimal:
        """Cost as a Decimal, always."""
        return Decimal(self.cost) if isinstance(self.cost, str) else self.cost

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly dict."""
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "provider": self.provider,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost": str(self.cost_usd),
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CostRecord:
        """Deserialise from a dict (e.g. loaded from JSON or DB)."""
        return cls(
            timestamp=d["timestamp"],
            model=d["model"],
            provider=d["provider"],
            tokens_in=int(d["tokens_in"]),
            tokens_out=int(d["tokens_out"]),
            cost=Decimal(str(d["cost"])),
            session_id=d["session_id"],
        )


# =============================================================================
# SQLite-backed store
# =============================================================================

_DEFAULT_DB = str(
    Path.home()
    / ".openamer"
    / "cost_dashboard.db"
)


class CostStore:
    """SQLite persistence for :class:`CostRecord` entries.

    Thread-safe for single-writer access. Creates the DB and table on
    first use.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._path = db_path or os.environ.get(
            "OPENAMER_COST_DB", _DEFAULT_DB
        )
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cost_records (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    model       TEXT NOT NULL,
                    provider    TEXT NOT NULL,
                    tokens_in   INTEGER NOT NULL,
                    tokens_out  INTEGER NOT NULL,
                    cost        TEXT NOT NULL,
                    session_id  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cost_ts ON cost_records(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cost_session ON cost_records(session_id)"
            )

    def insert(self, record: CostRecord) -> int:
        """Insert a record and return its row id."""
        with sqlite3.connect(self._path) as conn:
            cur = conn.execute(
                """
                INSERT INTO cost_records
                    (timestamp, model, provider, tokens_in, tokens_out, cost, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.timestamp,
                    record.model,
                    record.provider,
                    record.tokens_in,
                    record.tokens_out,
                    str(record.cost_usd),
                    record.session_id,
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def query(
        self,
        days: int = 30,
        session_id: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> list[CostRecord]:
        """Query records matching optional filters.

        Args:
            days: Only records within this many days from now.
            session_id: Optional session ID filter.
            model: Optional model name filter.
            provider: Optional provider name filter.

        Returns:
            List of matching :class:`CostRecord` instances.
        """
        threshold = datetime.now(timezone.utc).isoformat()
        # Simple time-window filter: records whose timestamp falls within
        # the last N days.
        import datetime as dt_module

        cutoff = (
            datetime.now(timezone.utc) - dt_module.timedelta(days=days)
        ).isoformat()

        clauses: list[str] = ["timestamp >= ?"]
        params: list[Any] = [cutoff]

        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if model:
            clauses.append("model = ?")
            params.append(model)
        if provider:
            clauses.append("provider = ?")
            params.append(provider)

        sql = (
            "SELECT timestamp, model, provider, tokens_in, tokens_out, "
            "cost, session_id FROM cost_records WHERE "
            + " AND ".join(clauses)
            + " ORDER BY timestamp DESC"
        )

        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            CostRecord(
                timestamp=row[0],
                model=row[1],
                provider=row[2],
                tokens_in=row[3],
                tokens_out=row[4],
                cost=Decimal(row[5]),
                session_id=row[6],
            )
            for row in rows
        ]

    def total_cost(
        self,
        days: int = 30,
        session_id: str | None = None,
    ) -> Decimal:
        """Compute total cost over matching records."""
        records = self.query(days=days, session_id=session_id)
        return sum((r.cost_usd for r in records), Decimal("0"))

    def delete_older_than(self, days: int) -> int:
        """Delete records older than *days*. Returns count of deleted rows."""
        cutoff = (
            datetime.now(timezone.utc) - datetime.timedelta(days=days)
        ).isoformat()
        with sqlite3.connect(self._path) as conn:
            cur = conn.execute(
                "DELETE FROM cost_records WHERE timestamp < ?", (cutoff,)
            )
            return cur.rowcount


# =============================================================================
# In-memory tracker
# =============================================================================


class CostTracker:
    """In-memory cost tracker with optional SQLite persistence.

    Accumulates :class:`CostRecord` entries and provides summary views
    by session, model, and provider.

    Usage::

        tracker = CostTracker()
        tracker.record("gpt-4o", "openai", 100, 50, Decimal("0.003"))
        report = tracker.get_cost_stats(days=30)
    """

    def __init__(self, store: CostStore | None = None) -> None:
        self._store = store or CostStore()
        self._records: list[CostRecord] = []

    def record(
        self,
        model: str,
        provider: str,
        tokens_in: int,
        tokens_out: int,
        cost: Decimal | str,
        session_id: str = "unknown",
    ) -> CostRecord:
        """Record a new inference call and persist it.

        Args:
            model: Model name.
            provider: Provider name.
            tokens_in: Input tokens.
            tokens_out: Output tokens.
            cost: Cost in USD.
            session_id: Session identifier (default ``\"unknown\"``).

        Returns:
            The created :class:`CostRecord`.
        """
        record = CostRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            provider=provider,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            session_id=session_id,
        )
        self._records.append(record)
        self._store.insert(record)
        return record

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_cost_stats(self, days: int = 30) -> dict[str, Any]:
        """Compute cost breakdowns for the last *days*.

        Returns a dict with:
            ``total_cost``: Total USD spent.
            ``total_tokens``: Total tokens consumed.
            ``total_calls``: Total API calls.
            ``by_model``: Dict ``{model: cost}`` sorted descending.
            ``by_provider``: Dict ``{provider: cost}`` sorted descending.
            ``by_session``: Dict ``{session_id: cost}`` sorted descending.
            ``avg_cost_per_call``: Average cost per API call.
            ``cost_per_token``: Average cost per token.
            ``period_days``: The requested period.
        """
        records = self._store.query(days=days)

        total_cost = sum((r.cost_usd for r in records), Decimal("0"))
        total_tokens = sum(r.total_tokens for r in records)
        total_calls = len(records)

        by_model: dict[str, Decimal] = defaultdict(Decimal)
        by_provider: dict[str, Decimal] = defaultdict(Decimal)
        by_session: dict[str, Decimal] = defaultdict(Decimal)

        for r in records:
            by_model[r.model] += r.cost_usd
            by_provider[r.provider] += r.cost_usd
            by_session[r.session_id] += r.cost_usd

        def _sorted(d: dict[str, Decimal]) -> list[dict[str, str]]:
            return [
                {"key": k, "cost": str(v)}
                for k, v in sorted(d.items(), key=lambda x: x[1], reverse=True)
            ]

        return {
            "total_cost": str(total_cost),
            "total_tokens": total_tokens,
            "total_calls": total_calls,
            "by_model": _sorted(by_model),
            "by_provider": _sorted(by_provider),
            "by_session": _sorted(by_session),
            "avg_cost_per_call": (
                str(total_cost / Decimal(str(total_calls)))
                if total_calls
                else "0"
            ),
            "cost_per_token": (
                str(total_cost / Decimal(str(total_tokens)))
                if total_tokens
                else "0"
            ),
            "period_days": days,
        }

    def get_budget_status(self) -> dict[str, Any]:
        """Return budget vs. spent figures.

        Reads optional config from ``OPENAMER_MONTHLY_BUDGET`` (default
        ``\"100\"`` USD) and computes spent for the current calendar month.

        Returns:
            Dict with ``monthly_budget``, ``spent_this_month``,
            ``remaining``, ``percent_used``.
        """
        budget_str = os.environ.get("OPENAMER_MONTHLY_BUDGET", "100")
        try:
            monthly_budget = Decimal(budget_str)
        except Exception:
            monthly_budget = Decimal("100")

        # Calculate spend for current calendar month
        now = datetime.now(timezone.utc)
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Approximate by using a day-count-based query
        days_into_month = now.day
        spent = self._store.total_cost(days=days_into_month)

        remaining = monthly_budget - spent
        if monthly_budget > 0:
            percent_used = float((spent / monthly_budget) * 100)
        else:
            percent_used = 0.0

        return {
            "monthly_budget": str(monthly_budget),
            "spent_this_month": str(spent),
            "remaining": str(remaining),
            "percent_used": round(percent_used, 1),
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def print_cost_report(self, days: int = 30) -> None:
        """Pretty-print a cost report to stdout.

        Uses basic string formatting — no external dependencies.
        """
        stats = self.get_cost_stats(days=days)
        budget = self.get_budget_status()

        print("=" * 60)
        print(f"  OpenAmer Cost Report (last {days} days)")
        print("=" * 60)
        print()
        print(f"  Total cost:        ${stats['total_cost']}")
        print(f"  Total tokens:      {stats['total_tokens']:,}")
        print(f"  Total API calls:   {stats['total_calls']}")
        print(f"  Avg cost/call:     ${stats['avg_cost_per_call']}")
        print(f"  Cost per token:    ${stats['cost_per_token']}")
        print()
        print("  --- Budget ---")
        print(f"  Monthly budget:    ${budget['monthly_budget']}")
        print(f"  Spent this month:  ${budget['spent_this_month']}")
        print(f"  Remaining:         ${budget['remaining']}")
        print(f"  Percent used:      {budget['percent_used']}%")
        print()
        print("  --- By Model ---")
        for entry in stats["by_model"][:10]:
            print(f"    {entry['key']:30s}  ${entry['cost']}")
        print()
        print("  --- By Provider ---")
        for entry in stats["by_provider"]:
            print(f"    {entry['key']:30s}  ${entry['cost']}")
        print()
        print("  --- Top Sessions ---")
        for entry in stats["by_session"][:10]:
            print(f"    {entry['key']:30s}  ${entry['cost']}")
        print()
        print("=" * 60)


# =============================================================================
# Module-level convenience
# =============================================================================

_default_tracker: CostTracker | None = None


def _get_tracker() -> CostTracker:
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = CostTracker()
    return _default_tracker


def get_cost_stats(days: int = 30) -> dict[str, Any]:
    """Module-level convenience — see :meth:`CostTracker.get_cost_stats`."""
    return _get_tracker().get_cost_stats(days=days)


def get_budget_status() -> dict[str, Any]:
    """Module-level convenience — see :meth:`CostTracker.get_budget_status`."""
    return _get_tracker().get_budget_status()


def print_cost_report(days: int = 30) -> None:
    """Module-level convenience — see :meth:`CostTracker.print_cost_report`."""
    _get_tracker().print_cost_report(days=days)


# =============================================================================
# CLI entry point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OpenAmer Cost Dashboard")
    subparsers = parser.add_subparsers(dest="command")

    report_parser = subparsers.add_parser("report", help="Print cost report")
    report_parser.add_argument(
        "--days", type=int, default=30, help="Number of days to report"
    )

    stats_parser = subparsers.add_parser("stats", help="Show cost statistics as JSON")
    stats_parser.add_argument(
        "--days", type=int, default=30, help="Number of days"
    )
    stats_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )

    budget_parser = subparsers.add_parser(
        "budget", help="Show budget status"
    )

    args = parser.parse_args()

    tracker = _get_tracker()

    if args.command == "report":
        tracker.print_cost_report(days=args.days)
    elif args.command == "stats":
        stats = tracker.get_cost_stats(days=args.days)
        indent = 2 if getattr(args, "pretty", False) else None
        print(json.dumps(stats, indent=indent))
    elif args.command == "budget":
        budget = tracker.get_budget_status()
        indent = 2 if getattr(args, "pretty", False) else None
        print(json.dumps(budget, indent=indent))
    else:
        parser.print_help()