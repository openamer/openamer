"""Spend budget for a session and for a day.

The turn loop already stops on an *iteration* count
(``agent/iteration_budget.py``), which nobody reasons in.  This adds the
dimension users actually budget in -- money -- and participates in the same
stop condition, so a breach ends the turn the way an exhausted iteration
budget does instead of inventing a second control flow.

Off by default: with ``budget.enabled: false`` every verdict is ``allow`` and
nothing in the loop changes.  Enforcement only exists once the user asks for it.

Why ``reason`` is a string and not a bool: a guard that refuses real work must
be able to say *why* it refused.  A bare ``False`` makes a correct block
indistinguishable from a bug, which is the same rule ``darwin_engine`` follows
for its topic rejections.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Verdict actions, best to worst.
ALLOW = "allow"
WARN = "warn"
BLOCK = "block"

# Named reasons -- never a bare boolean.
REASON_DISABLED = "budget_disabled"
REASON_WITHIN = "within_budget"
REASON_SESSION_CAP = "session_cap_reached"
REASON_DAY_CAP = "day_cap_reached"
REASON_SESSION_WARN = "session_warn_threshold"
REASON_DAY_WARN = "day_warn_threshold"

_STORE_NAME = "spend_day.json"


def default_config() -> dict[str, Any]:
    """The shape ``config.yaml`` carries under ``budget:`` (all off)."""
    return {
        "enabled": False,
        "max_usd_per_session": 0.0,
        "max_usd_per_day": 0.0,
        "warn_at_percent": 80,
        "on_exceed": BLOCK,
    }


def load_config() -> dict[str, Any]:
    """Read ``budget:`` from the live config, falling back to the defaults.

    Lazy import: this module is imported from the agent loop, and the config
    layer imports enough that a module-level import would be circular.
    """
    cfg = default_config()
    try:
        from openamer_cli.config import load_config as _load

        section = (_load() or {}).get("budget")
    except Exception:  # pragma: no cover - config unavailable: stay inert
        return cfg
    if isinstance(section, dict):
        cfg.update({k: v for k, v in section.items() if k in cfg})
    return cfg


def _as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if out >= 0 else fallback


@dataclass(frozen=True)
class BudgetVerdict:
    """One decision about whether spending may continue."""

    action: str
    reason: str
    scope: str = ""
    spent_usd: float = 0.0
    limit_usd: float = 0.0
    percent: float = 0.0

    @property
    def blocks(self) -> bool:
        return self.action == BLOCK

    def describe(self) -> str:
        if self.action == ALLOW and self.reason == REASON_DISABLED:
            return "Spend budget is off (budget.enabled: false)."
        if self.limit_usd <= 0:
            return f"Spent ${self.spent_usd:.4f} ({self.scope or 'no cap set'})."
        return (
            f"Spent ${self.spent_usd:.4f} of ${self.limit_usd:.2f} "
            f"({self.percent:.0f}%) -- {self.reason} [{self.scope}]"
        )


def evaluate(
    session_usd: float,
    day_usd: float,
    cfg: Optional[dict[str, Any]] = None,
) -> BudgetVerdict:
    """Decide from two observed amounts and the configured caps. Pure."""
    cfg = dict(default_config()) if cfg is None else cfg
    session_usd = _as_float(session_usd)
    day_usd = _as_float(day_usd)

    if not cfg.get("enabled"):
        return BudgetVerdict(ALLOW, REASON_DISABLED, "", session_usd)

    on_exceed = str(cfg.get("on_exceed") or BLOCK).strip().lower()
    if on_exceed not in (BLOCK, WARN):
        on_exceed = BLOCK
    warn_at = _as_float(cfg.get("warn_at_percent"), 80.0)

    # Caps first: a breach outranks a threshold, and the day cap is checked
    # after the session cap so the tighter, more local limit wins the label.
    for scope, spent, limit, cap_reason, warn_reason in (
        ("session", session_usd, _as_float(cfg.get("max_usd_per_session")),
         REASON_SESSION_CAP, REASON_SESSION_WARN),
        ("day", day_usd, _as_float(cfg.get("max_usd_per_day")),
         REASON_DAY_CAP, REASON_DAY_WARN),
    ):
        if limit <= 0:
            continue
        percent = (spent / limit) * 100.0
        if spent >= limit:
            return BudgetVerdict(on_exceed, cap_reason, scope, spent, limit, percent)
        if warn_at > 0 and percent >= warn_at:
            return BudgetVerdict(WARN, warn_reason, scope, spent, limit, percent)

    return BudgetVerdict(ALLOW, REASON_WITHIN, "", max(session_usd, day_usd))


# ── the daily store ────────────────────────────────────────────────────────
# A day cap needs a day total, and a session total is only one process.  The
# store is one small JSON document under OPENAMER_HOME, rewritten atomically,
# and reset by date -- never deleted, so the last day's figure survives a read.

def _store_path() -> Path:
    try:
        from openamer_constants import get_openamer_home

        home = Path(get_openamer_home())
    except Exception:  # pragma: no cover
        home = Path(os.getenv("OPENAMER_HOME") or Path.home() / ".openamer")
    return home / "memory" / _STORE_NAME


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_store(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def day_spend(path: Optional[Path] = None) -> float:
    """Today's accrued spend in USD; 0.0 for a fresh or unreadable store."""
    store = _read_store(path or _store_path())
    if str(store.get("date") or "") != _today():
        return 0.0
    return _as_float(store.get("spent_usd"))


def record(amount_usd: float, path: Optional[Path] = None) -> float:
    """Add ``amount_usd`` to today's total and return the new total.

    Written to a sibling temp file and moved into place, so a crash mid-write
    cannot leave a half-written day total behind.
    """
    amount = _as_float(amount_usd)
    if amount <= 0:
        return day_spend(path)
    target = path or _store_path()
    total = day_spend(target) + amount
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".spend_day_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"date": _today(), "spent_usd": round(total, 8)}, fh)
        os.replace(tmp, target)
    except OSError:  # pragma: no cover - a read-only home must not break a turn
        return total
    return total


class SpendBudget:
    """Convenience wrapper the turn loop talks to.

    ``ok_to_continue`` is the only method the loop's while-condition needs, so
    wiring stays a single predicate next to the iteration budget.
    """

    def __init__(self, cfg: Optional[dict[str, Any]] = None) -> None:
        self.cfg = load_config() if cfg is None else cfg

    def verdict(self, session_usd: float, day_usd: Optional[float] = None) -> BudgetVerdict:
        # Off means off: the turn loop asks this on every iteration, so the
        # disabled path must not touch the disk. The day store is read only
        # when a day cap is actually configured.
        if not self.cfg.get("enabled"):
            return BudgetVerdict(ALLOW, REASON_DISABLED, "", _as_float(session_usd))
        if day_usd is None:
            day_usd = day_spend() if _as_float(self.cfg.get("max_usd_per_day")) > 0 else 0.0
        return evaluate(session_usd, day_usd, self.cfg)

    def ok_to_continue(self, session_usd: float, day_usd: Optional[float] = None) -> bool:
        return not self.verdict(session_usd, day_usd).blocks

    def note(self, amount_usd: float) -> float:
        """Record a spend event so the day total keeps up with the session.

        A no-op while the feature is off -- otherwise every user would grow a
        spend file they never asked for.
        """
        if not self.cfg.get("enabled"):
            return 0.0
        return record(amount_usd)
