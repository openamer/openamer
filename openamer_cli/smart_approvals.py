#!/usr/bin/env python3
"""Smart Approvals (Human-in-the-Loop) for OpenAmer Agent.

Provides risk-aware approval gates that pause agent execution before certain
action types and ask the user for explicit approval or denial.  Integrates
with the existing HITL config (``hitl.enabled`` in config.yaml) and adds a
risk-tiered CLI interface for managing pending approvals.

Risk levels:
    HIGH    — File deletion, system modification, code execution
    MEDIUM  — File write access, network call
    LOW     — File reading, web search

CLI commands::

    openamer approvals list           Show pending approvals
    openamer approvals approve <id>   Approve a request
    openamer approvals reject <id>    Reject a request
    openamer approvals config         Show current HITL configuration
    openamer approvals settings       Configure risk levels interactively
"""

from __future__ import annotations

import argparse
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk Levels
# ---------------------------------------------------------------------------


class RiskLevel(Enum):
    """Risk classification for agent actions requiring approval."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        labels = {
            "low": "🟢 Low",
            "medium": "🟡 Medium",
            "high": "🔴 High",
        }
        return labels.get(self.value, self.value)

    @property
    def timeout_default(self) -> int:
        """Default auto-deny timeout per risk level (seconds)."""
        return {"low": 60, "medium": 30, "high": 15}.get(self.value, 30)


# ---------------------------------------------------------------------------
# Risk Assessment
# ---------------------------------------------------------------------------

# Action-type → risk-level mapping (used for automatic risk classification)
ACTION_RISK_MAP: Dict[str, RiskLevel] = {
    # HIGH — destructive / dangerous
    "file_delete": RiskLevel.HIGH,
    "system_modification": RiskLevel.HIGH,
    "code_execution": RiskLevel.HIGH,
    "terminal_command": RiskLevel.HIGH,
    "plugin_install": RiskLevel.HIGH,
    "install_package": RiskLevel.HIGH,
    # MEDIUM — side effects but recoverable
    "file_write": RiskLevel.MEDIUM,
    "network_request": RiskLevel.MEDIUM,
    "patch": RiskLevel.MEDIUM,
    "git_push": RiskLevel.MEDIUM,
    "env_modification": RiskLevel.MEDIUM,
    # LOW — read-only or safe
    "file_read": RiskLevel.LOW,
    "web_search": RiskLevel.LOW,
    "web_get": RiskLevel.LOW,
    "list_directory": RiskLevel.LOW,
}

# High-risk action types (auto-derived from ACTION_RISK_MAP)
HIGH_RISK_ACTIONS = {
    a for a, r in ACTION_RISK_MAP.items() if r == RiskLevel.HIGH
}
MEDIUM_RISK_ACTIONS = {
    a for a, r in ACTION_RISK_MAP.items() if r == RiskLevel.MEDIUM
}
LOW_RISK_ACTIONS = {
    a for a, r in ACTION_RISK_MAP.items() if r == RiskLevel.LOW
}


def classify_risk(action_type: str, details: Optional[str] = None) -> RiskLevel:
    """Determine the risk level for a given action type.

    Falls back to MEDIUM for unknown action types.
    """
    _ = details  # reserved for future content-based classification
    return ACTION_RISK_MAP.get(action_type, RiskLevel.MEDIUM)


# ---------------------------------------------------------------------------
# Approval Request Data
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRequest:
    """A single pending approval request."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    action: str = ""
    details: str = ""
    risk_level: RiskLevel = RiskLevel.MEDIUM
    created_at: float = field(default_factory=time.monotonic)
    expires_at: float = 0.0
    status: str = "pending"  # pending | approved | rejected | timed_out

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.expires_at <= 0:
            return False
        if now is None:
            now = time.monotonic()
        return now > self.expires_at

    @property
    def summary(self) -> str:
        return (
            f"[{self.risk_level.label}] #{self.id}: {self.action}"
            + (f" — {self.details}" if self.details else "")
        )


# ---------------------------------------------------------------------------
# Approval Manager
# ---------------------------------------------------------------------------


class ApprovalManager:
    """Manages human-in-the-loop approval requests.

    Thread-safe singleton. Handles request creation, approval, rejection,
    timeout-based auto-rejection, and listing of pending requests.
    """

    _instance: Optional[ApprovalManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> ApprovalManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        with self._lock:
            if getattr(self, "_initialized", False):
                return
            self._pending: Dict[str, ApprovalRequest] = {}
            self._lock = threading.Lock()
            self._auto_reject_timer: Optional[threading.Timer] = None
            self._timeout: float = 30.0
            self._initialized = True

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def request_approval(
        self,
        action: str,
        details: str = "",
        risk_level: Optional[RiskLevel] = None,
    ) -> ApprovalRequest:
        """Create a new approval request and return it.

        Args:
            action: The action type (e.g. ``"file_write"``, ``"code_execution"``).
            details: Human-readable description of what the agent wants to do.
            risk_level: Explicit risk level. If None, auto-classified from action.

        Returns:
            The created ApprovalRequest (status ``"pending"``).
        """
        if risk_level is None:
            risk_level = classify_risk(action, details)

        timeout = risk_level.timeout_default

        req = ApprovalRequest(
            action=action,
            details=details,
            risk_level=risk_level,
            expires_at=time.monotonic() + timeout,
        )

        with self._lock:
            self._pending[req.id] = req

        logger.info(
            "Approval requested: %s (risk=%s, timeout=%ds)",
            req.summary, risk_level.value, timeout,
        )
        return req

    def approve(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Approve a pending request.

        Args:
            approval_id: The request ID to approve.

        Returns:
            The resolved ApprovalRequest, or None if not found / not pending.
        """
        with self._lock:
            req = self._pending.pop(approval_id, None)
        if req is None:
            logger.warning("Approval not found: %s", approval_id)
            return None
        if req.status != "pending":
            # Already resolved — put it back
            with self._lock:
                self._pending[approval_id] = req
            logger.warning("Approval %s already %s", approval_id, req.status)
            return None
        req.status = "approved"
        logger.info("Approval granted: %s", req.summary)
        return req

    def reject(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Reject a pending request.

        Args:
            approval_id: The request ID to reject.

        Returns:
            The resolved ApprovalRequest, or None if not found / not pending.
        """
        with self._lock:
            req = self._pending.pop(approval_id, None)
        if req is None:
            logger.warning("Approval not found: %s", approval_id)
            return None
        if req.status != "pending":
            with self._lock:
                self._pending[approval_id] = req
            logger.warning("Approval %s already %s", approval_id, req.status)
            return None
        req.status = "rejected"
        logger.info("Approval denied: %s", req.summary)
        return req

    def get_pending(self) -> List[ApprovalRequest]:
        """Return all pending approval requests (sorted by creation time).

        Expired requests are auto-rejected on access.
        """
        now = time.monotonic()
        pending: List[ApprovalRequest] = []
        expired_ids: List[str] = []
        with self._lock:
            for rid, req in list(self._pending.items()):
                if req.is_expired(now):
                    req.status = "timed_out"
                    expired_ids.append(rid)
                    logger.info("Approval timed out: %s", req.summary)
                else:
                    pending.append(req)
            for rid in expired_ids:
                self._pending.pop(rid, None)
        pending.sort(key=lambda r: r.created_at)
        return pending

    def auto_reject_timeout(self, seconds: float = 30.0) -> None:
        """Set the default auto-reject timeout for future requests.

        Updates the manager's default timeout. Does *not* retroactively
        change existing requests.
        """
        self._timeout = seconds
        logger.info("Approval auto-reject timeout set to %.0fs", seconds)

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def get_config(self) -> Dict[str, object]:
        """Return current approval manager configuration as a dict."""
        try:
            from openamer_cli.hitl import _get_hitl_config

            hitl_cfg = _get_hitl_config()
        except Exception:
            hitl_cfg = None

        return {
            "auto_reject_timeout": self._timeout,
            "pending_count": len(self._pending),
            "risk_levels": {
                "LOW": {
                    "actions": sorted(LOW_RISK_ACTIONS),
                    "timeout": RiskLevel.LOW.timeout_default,
                },
                "MEDIUM": {
                    "actions": sorted(MEDIUM_RISK_ACTIONS),
                    "timeout": RiskLevel.MEDIUM.timeout_default,
                },
                "HIGH": {
                    "actions": sorted(HIGH_RISK_ACTIONS),
                    "timeout": RiskLevel.HIGH.timeout_default,
                },
            },
            "hitl_enabled": getattr(hitl_cfg, "enabled", False) if hitl_cfg else False,
            "hitl_timeout": getattr(hitl_cfg, "timeout", 30) if hitl_cfg else 30,
            "hitl_actions": getattr(hitl_cfg, "actions", []) if hitl_cfg else [],
        }


# ---------------------------------------------------------------------------
# Circuit Breaker Integration
# ---------------------------------------------------------------------------

_CIRCUIT_BREAKER_TRIPPED = threading.Event()


def trip_circuit_breaker() -> None:
    """Trip the circuit breaker, requiring approval for the next action."""
    _CIRCUIT_BREAKER_TRIPPED.set()


def reset_circuit_breaker() -> None:
    """Reset the circuit breaker after approval or manual override."""
    _CIRCUIT_BREAKER_TRIPPED.clear()


def is_circuit_breaker_tripped() -> bool:
    """Check whether the circuit breaker is tripped."""
    return _CIRCUIT_BREAKER_TRIPPED.is_set()


def require_approval_if_tripped(
    action: str,
    details: str = "",
    risk_level: Optional[RiskLevel] = None,
) -> Optional[ApprovalRequest]:
    """If the circuit breaker is tripped, create an approval request.

    Intended for ``--auto`` / ``initiative`` mode integration: when the
    circuit breaker trips (e.g. repeated failures, suspicious command),
    the agent must pause and get approval before proceeding.

    Returns the ApprovalRequest if one was created, or None if the
    circuit breaker is not tripped.
    """
    if not is_circuit_breaker_tripped():
        return None
    mgr = ApprovalManager()
    req = mgr.request_approval(action, details, risk_level)
    logger.warning(
        "Circuit breaker tripped — approval required: %s", req.summary,
    )
    return req


# ---------------------------------------------------------------------------
# CLI Handlers
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    """Show pending approvals."""
    mgr = ApprovalManager()
    pending = mgr.get_pending()
    if not pending:
        print("✅  No pending approvals.")
        return 0

    print(f"\n{'Pending Approvals':━^60}")
    for i, req in enumerate(pending, 1):
        remaining = max(0, req.expires_at - time.monotonic()) if req.expires_at > 0 else 0
        print(f"  {i}. {req.summary}")
        print(f"     ├─ Action:  {req.action}")
        print(f"     ├─ Timeout: {remaining:.0f}s remaining")
        print(f"     └─ ID:      {req.id}")
    print()
    print("  openamer approvals approve <id>   — approve")
    print("  openamer approvals reject <id>    — reject")
    print("━" * 60)
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    """Approve a pending request by ID."""
    mgr = ApprovalManager()
    req = mgr.approve(args.approval_id)
    if req is None:
        print(f"❌  Approval not found or already resolved: {args.approval_id}")
        return 1
    print(f"✅  Approved: {req.summary}")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    """Reject a pending request by ID."""
    mgr = ApprovalManager()
    req = mgr.reject(args.approval_id)
    if req is None:
        print(f"❌  Approval not found or already resolved: {args.approval_id}")
        return 1
    print(f"❌  Rejected: {req.summary}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Show current HITL configuration and risk level mapping."""
    _ = args
    mgr = ApprovalManager()
    cfg = mgr.get_config()

    print(f"\n{'Smart Approvals Configuration':━^60}")
    print(f"  HITL enabled:      {cfg['hitl_enabled']}")
    print(f"  HITL timeout:      {cfg['hitl_timeout']}s")
    print(f"  HITL actions:      {', '.join(cfg['hitl_actions']) or '(none)'}")
    print(f"  Auto-reject timeout: {cfg['auto_reject_timeout']:.0f}s")
    print(f"  Pending requests:  {cfg['pending_count']}")
    print()

    print(f"{'Risk Level Mapping':━^60}")
    for level_name in ("LOW", "MEDIUM", "HIGH"):
        info = cfg["risk_levels"][level_name]
        print(f"  {level_name:<8}  timeout={info['timeout']}s  "
              f"actions: {', '.join(info['actions']) or '(none)'}")
    print("━" * 60)
    return 0


def cmd_settings(args: argparse.Namespace) -> int:
    """Interactively configure risk levels and approvals.

    Currently displays current settings and suggests config.yaml keys.
    """
    _ = args
    mgr = ApprovalManager()
    cfg = mgr.get_config()

    print(f"\n{'Approval Settings':━^60}")
    print(f"  Current auto-reject timeout: {cfg['auto_reject_timeout']:.0f}s")
    print(f"  HITL enabled:                {cfg['hitl_enabled']}")
    print(f"  HITL timeout:                {cfg['hitl_timeout']}s")
    print(f"  HITL actions:                {', '.join(cfg['hitl_actions']) or '(none)'}")
    print()
    print("To change these settings, edit your config.yaml:")
    print("  ~/.openamer/config.yaml")
    print()
    print("  hitl:")
    print("    enabled: true          # Enable HITL approvals")
    print("    timeout: 30            # Default approval timeout")
    print("    actions:               # Actions requiring approval")
    print("      - file_write")
    print("      - code_execution")
    print("      - terminal_command")
    print("      - network_request")
    print("      - file_delete")
    print("      - plugin_install")
    print()
    print("Or use:  openamer config set hitl.enabled true")
    print("         openamer config set hitl.timeout 60")
    print("━" * 60)
    return 0


# ---------------------------------------------------------------------------
# CLI Registration
# ---------------------------------------------------------------------------


def register_cli(parser: argparse.ArgumentParser) -> None:
    """Wire subcommands onto the ``openamer approvals`` parser."""
    subs = parser.add_subparsers(dest="approvals_command", metavar="COMMAND")

    # Default (no subcommand) → list
    parser.set_defaults(func=cmd_list)

    # List
    p_list = subs.add_parser("list", aliases=["ls"], help="Show pending approvals")
    p_list.set_defaults(func=cmd_list)

    # Approve
    p_approve = subs.add_parser("approve", help="Approve a pending request by ID")
    p_approve.add_argument("approval_id", help="The approval request ID")
    p_approve.set_defaults(func=cmd_approve)

    # Reject
    p_reject = subs.add_parser("reject", help="Reject a pending request by ID")
    p_reject.add_argument("approval_id", help="The approval request ID")
    p_reject.set_defaults(func=cmd_reject)

    # Config
    p_config = subs.add_parser("config", help="Show current HITL configuration")
    p_config.set_defaults(func=cmd_config)

    # Settings
    p_settings = subs.add_parser(
        "settings",
        help="Display approval settings and config.yaml guidance",
    )
    p_settings.set_defaults(func=cmd_settings)