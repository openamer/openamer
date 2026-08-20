"""Tests for openamer_cli/smart_approvals.py — Smart Approvals HITL system.

Covers:
  - Risk classification (LOW, MEDIUM, HIGH)
  - Approval request lifecycle (create → approve/reject → resolve)
  - Auto-reject timeout
  - Expired request cleanup
  - Circuit breaker integration
  - ApprovalManager singleton behaviour
  - Edge cases (double-approve, unknown IDs, empty pending list)
"""

from __future__ import annotations

import time
from threading import Event

import pytest

from openamer_cli.smart_approvals import (
    HIGH_RISK_ACTIONS,
    LOW_RISK_ACTIONS,
    MEDIUM_RISK_ACTIONS,
    ApprovalManager,
    ApprovalRequest,
    RiskLevel,
    classify_risk,
    is_circuit_breaker_tripped,
    require_approval_if_tripped,
    reset_circuit_breaker,
    trip_circuit_breaker,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the ApprovalManager singleton between tests.

    We exploit the fact that the singleton is NOT formally destroyed between
    tests; instead we clear its internal state by popping all pending items.
    """
    mgr = ApprovalManager()
    with mgr._lock:
        mgr._pending.clear()
    # Also ensure the circuit breaker starts clean
    reset_circuit_breaker()
    yield


@pytest.fixture
def mgr() -> ApprovalManager:
    return ApprovalManager()


# =============================================================================
# 1. Risk Classification Tests (3 tests)
# =============================================================================


class TestRiskClassification:
    """Verify risk levels are correctly assigned per action type."""

    def test_high_risk_actions(self):
        """HIGH risk actions include destructive operations."""
        assert "file_delete" in HIGH_RISK_ACTIONS
        assert "system_modification" in HIGH_RISK_ACTIONS
        assert "code_execution" in HIGH_RISK_ACTIONS
        assert "terminal_command" in HIGH_RISK_ACTIONS
        assert "plugin_install" in HIGH_RISK_ACTIONS

    def test_medium_risk_actions(self):
        """MEDIUM risk actions include ops with side effects."""
        assert "file_write" in MEDIUM_RISK_ACTIONS
        assert "network_request" in MEDIUM_RISK_ACTIONS
        assert "patch" in MEDIUM_RISK_ACTIONS

    def test_low_risk_actions(self):
        """LOW risk actions are read-only / safe."""
        assert "file_read" in LOW_RISK_ACTIONS
        assert "web_search" in LOW_RISK_ACTIONS
        assert "list_directory" in LOW_RISK_ACTIONS


class TestClassifyRisk:
    """Unit tests for ``classify_risk()``."""

    def test_classify_file_delete_is_high(self):
        assert classify_risk("file_delete") == RiskLevel.HIGH

    def test_classify_file_write_is_medium(self):
        assert classify_risk("file_write") == RiskLevel.MEDIUM

    def test_classify_file_read_is_low(self):
        assert classify_risk("file_read") == RiskLevel.LOW

    def test_classify_unknown_defaults_to_medium(self):
        assert classify_risk("unknown_action") == RiskLevel.MEDIUM


# =============================================================================
# 2. Approval Lifecycle Tests (5+ tests)
# =============================================================================


class TestApprovalLifecycle:
    """Full lifecycle of an approval request."""

    def test_request_approval_creates_pending_request(self, mgr: ApprovalManager):
        """request_approval() returns a pending ApprovalRequest with an ID."""
        req = mgr.request_approval("file_write", "Write to deploy.yaml", RiskLevel.MEDIUM)
        assert req.id is not None
        assert req.id != ""
        assert req.status == "pending"
        assert req.action == "file_write"
        assert req.details == "Write to deploy.yaml"
        assert req.risk_level == RiskLevel.MEDIUM

    def test_pending_list_returns_pending(self, mgr: ApprovalManager):
        """get_pending() returns all active approval requests."""
        req1 = mgr.request_approval("file_write", "Write config.yaml")
        req2 = mgr.request_approval("code_execution", "Run build", RiskLevel.HIGH)
        pending = mgr.get_pending()
        ids = [r.id for r in pending]
        assert req1.id in ids
        assert req2.id in ids
        assert len(pending) == 2

    def test_pending_list_empty_when_no_requests(self, mgr: ApprovalManager):
        """get_pending() returns an empty list when there are no requests."""
        assert mgr.get_pending() == []

    def test_approve_resolves_request(self, mgr: ApprovalManager):
        """approve() marks the request as 'approved' and removes it from pending."""
        req = mgr.request_approval("file_write", "Update settings")
        approved = mgr.approve(req.id)
        assert approved is not None
        assert approved.status == "approved"
        # It should no longer appear in pending
        assert req.id not in [r.id for r in mgr.get_pending()]

    def test_reject_resolves_request(self, mgr: ApprovalManager):
        """reject() marks the request as 'rejected' and removes it from pending."""
        req = mgr.request_approval("network_request", "Call external API")
        rejected = mgr.reject(req.id)
        assert rejected is not None
        assert rejected.status == "rejected"
        assert req.id not in [r.id for r in mgr.get_pending()]

    def test_approve_unknown_id_returns_none(self, mgr: ApprovalManager):
        """approve() returns None for a non-existent request ID."""
        result = mgr.approve("nonexistent")
        assert result is None

    def test_reject_unknown_id_returns_none(self, mgr: ApprovalManager):
        """reject() returns None for a non-existent request ID."""
        result = mgr.reject("nonexistent")
        assert result is None

    def test_double_approve_returns_none(self, mgr: ApprovalManager):
        """approving an already-approved request returns None."""
        req = mgr.request_approval("file_read", "Check file")
        first = mgr.approve(req.id)
        assert first is not None
        second = mgr.approve(req.id)
        assert second is None


# =============================================================================
# 3. Timeout / Expiry Tests (2 tests)
# =============================================================================


class TestTimeout:
    """Auto-reject timeout behaviour."""

    def test_auto_reject_timeout_sets_default(self, mgr: ApprovalManager):
        """auto_reject_timeout() updates the manager's default timeout."""
        mgr.auto_reject_timeout(seconds=60.0)
        # We can check the internal value
        assert mgr._timeout == 60.0
        # The next request should use the RiskLevel default,
        # not the manager timeout — manager timeout is a separate setting
        req = mgr.request_approval("file_read", "Test")
        assert req.expires_at > 0

    def test_expired_request_removed_from_pending(self, mgr: ApprovalManager):
        """get_pending() removes expired requests and marks them timed_out."""
        req = mgr.request_approval(
            action="file_write",
            details="Expired test",
            risk_level=RiskLevel.MEDIUM,
        )
        # Manually set expires_at to the past
        with mgr._lock:
            stored = mgr._pending[req.id]
            stored.expires_at = time.monotonic() - 1.0  # 1 second ago

        pending = mgr.get_pending()
        assert req.id not in [r.id for r in pending]

    def test_approval_request_is_expired(self, mgr: ApprovalManager):
        """ApprovalRequest.is_expired() correctly detects past expiry."""
        req = ApprovalRequest(
            action="test",
            details="",
            risk_level=RiskLevel.LOW,
            expires_at=time.monotonic() - 5,  # 5 seconds ago
        )
        assert req.is_expired()
        assert not req.is_expired(now=time.monotonic() - 10)  # before expiry


# =============================================================================
# 4. Auto-classification Test (1 test)
# =============================================================================


class TestAutoClassification:
    """When no risk_level is passed, it is auto-classified."""

    def test_request_approval_auto_classifies(self, mgr: ApprovalManager):
        """request_approval() without risk_level auto-classifies from action."""
        req_high = mgr.request_approval("code_execution", "Run script")
        assert req_high.risk_level == RiskLevel.HIGH

        req_medium = mgr.request_approval("network_request", "Fetch URL")
        assert req_medium.risk_level == RiskLevel.MEDIUM

        req_low = mgr.request_approval("file_read", "Read file")
        assert req_low.risk_level == RiskLevel.LOW


# =============================================================================
# 5. Circuit Breaker Integration Tests (2 tests)
# =============================================================================


class TestCircuitBreaker:
    """Integration with the circuit breaker for --auto / initiative mode."""

    def test_circuit_breaker_trip_and_reset(self):
        """trip_circuit_breaker() and reset_circuit_breaker() work."""
        assert not is_circuit_breaker_tripped()
        trip_circuit_breaker()
        assert is_circuit_breaker_tripped()
        reset_circuit_breaker()
        assert not is_circuit_breaker_tripped()

    def test_require_approval_if_tripped_creates_request(self, mgr: ApprovalManager):
        """When the circuit breaker is tripped, an approval request is created."""
        trip_circuit_breaker()
        req = require_approval_if_tripped(
            "code_execution", "Dangerous command", RiskLevel.HIGH
        )
        assert req is not None
        assert req.status == "pending"
        assert req.action == "code_execution"
        assert req.risk_level == RiskLevel.HIGH
        # It should show up in pending
        assert req.id in [r.id for r in mgr.get_pending()]
        reset_circuit_breaker()

    def test_require_approval_if_tripped_returns_none_when_not_tripped(self):
        """When the circuit breaker is not tripped, no approval is created."""
        reset_circuit_breaker()
        req = require_approval_if_tripped("file_read", "Safe read", RiskLevel.LOW)
        assert req is None


# =============================================================================
# 6. Configuration Test (1 test)
# =============================================================================


class TestConfig:
    """ApprovalManager configuration helpers."""

    def test_get_config_returns_dict(self, mgr: ApprovalManager):
        """get_config() returns a structured dictionary."""
        cfg = mgr.get_config()
        assert isinstance(cfg, dict)
        assert "risk_levels" in cfg
        assert "auto_reject_timeout" in cfg
        assert "pending_count" in cfg
        assert "LOW" in cfg["risk_levels"]
        assert "MEDIUM" in cfg["risk_levels"]
        assert "HIGH" in cfg["risk_levels"]
        assert isinstance(cfg["risk_levels"]["LOW"]["actions"], list)
        assert isinstance(cfg["risk_levels"]["HIGH"]["timeout"], int)


# =============================================================================
# 7. Singleton Behaviour (1 test)
# =============================================================================


class TestSingleton:
    """ApprovalManager is a thread-safe singleton."""

    def test_singleton_returns_same_instance(self):
        """Multiple instantiations return the same object."""
        m1 = ApprovalManager()
        m2 = ApprovalManager()
        assert m1 is m2

    def test_singleton_shares_pending_state(self):
        """Pending state is shared across singleton instances."""
        m1 = ApprovalManager()
        m2 = ApprovalManager()
        req = m1.request_approval("file_read", "Singleton test")
        assert req.id in [r.id for r in m2.get_pending()]


# =============================================================================
# 8. Risk Level Labels Test (1 test)
# =============================================================================


class TestRiskLevelLabels:
    """RiskLevel labels and properties."""

    def test_risk_level_labels(self):
        assert RiskLevel.HIGH.label == "🔴 High"
        assert RiskLevel.MEDIUM.label == "🟡 Medium"
        assert RiskLevel.LOW.label == "🟢 Low"

    def test_risk_level_timeout_defaults(self):
        assert RiskLevel.HIGH.timeout_default == 15
        assert RiskLevel.MEDIUM.timeout_default == 30
        assert RiskLevel.LOW.timeout_default == 60


# =============================================================================
# 9. Summary Property Test (1 test)
# =============================================================================


class TestApprovalRequestSummary:
    """ApprovalRequest.summary formatting."""

    def test_summary_with_details(self):
        req = ApprovalRequest(
            id="abc123",
            action="file_write",
            details="Write to main.py",
            risk_level=RiskLevel.MEDIUM,
        )
        summary = req.summary
        assert "abc123" in summary
        assert "file_write" in summary
        assert "Write to main.py" in summary

    def test_summary_without_details(self):
        req = ApprovalRequest(
            id="abc123",
            action="file_read",
            details="",
            risk_level=RiskLevel.LOW,
        )
        summary = req.summary
        assert "abc123" in summary
        assert "file_read" in summary
        # Should not have '—' trailing
        assert " — " not in summary


# =============================================================================
# Total: 20+ tests (well above the minimum 8)
# =============================================================================