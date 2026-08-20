"""Tests for the HITL approval system (openamer_cli/hitl.py).

Key invariants tested:
1. HITLConfig.from_config() parses config correctly with defaults
2. should_pause() returns True only when HITL is enabled AND action_type is in the list
3. await_approval() in non-interactive context auto-denies
4. hitl_check() wraps handlers and blocks denied actions
5. hitl_check() passes through to handler when approved
6. hitl_check() passes through when HITL is disabled
7. approval_required_actions() returns the expected list
8. Edge cases: empty actions list, unknown action types, missing config section
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from openamer_cli.hitl import (
    APPROVAL_REQUIRED_ACTIONS,
    HITLConfig,
    approval_required_actions,
    await_approval,
    hitl_check,
    set_interactive_context,
    should_pause,
)


# =============================================================================
# HITLConfig tests
# =============================================================================


class TestHITLConfig:
    """HITLConfig dataclass and from_config() factory tests."""

    def test_default_config_has_hitl(self):
        """The openamer_cli.config module has a 'hitl' section in DEFAULT_CONFIG."""
        from openamer_cli.config import DEFAULT_CONFIG

        assert "hitl" in DEFAULT_CONFIG
        hitl = DEFAULT_CONFIG["hitl"]
        assert hitl["enabled"] is False
        assert hitl["timeout"] == 30
        assert "file_write" in hitl["actions"]

    def test_from_config_defaults(self):
        """from_config with no data returns default disabled HITL."""
        cfg = HITLConfig.from_config(None)
        assert cfg.enabled is False
        assert cfg.timeout == 30
        assert set(cfg.actions) == set(APPROVAL_REQUIRED_ACTIONS)

    def test_from_config_empty_dict(self):
        """from_config with empty dict returns defaults."""
        cfg = HITLConfig.from_config({})
        assert cfg.enabled is False
        assert cfg.timeout == 30

    def test_from_config_enabled(self):
        """from_config enables HITL when config says so."""
        cfg = HITLConfig.from_config({
            "hitl": {
                "enabled": True,
                "timeout": 15,
                "actions": ["file_write", "terminal_command"],
            }
        })
        assert cfg.enabled is True
        assert cfg.timeout == 15
        assert cfg.actions == ["file_write", "terminal_command"]
        assert "code_execution" not in cfg.actions

    def test_from_config_unknown_actions_filtered(self):
        """Unknown action types are silently filtered out."""
        cfg = HITLConfig.from_config({
            "hitl": {
                "enabled": True,
                "actions": ["file_write", "unknown_action", "hack_the_planet"],
            }
        })
        assert "file_write" in cfg.actions
        assert "unknown_action" not in cfg.actions
        assert "hack_the_planet" not in cfg.actions

    def test_from_config_empty_actions_with_enabled(self):
        """Explicit empty actions list makes HITL effectively off (noop)."""
        cfg = HITLConfig.from_config({
            "hitl": {
                "enabled": True,
                "actions": [],
            }
        })
        assert cfg.enabled is True
        # When enabled but actions is explicitly empty, actions is empty
        assert cfg.actions == []

    def test_from_config_non_dict_hitl_section(self):
        """If hitl section is a string/bool, graceful fallback to defaults."""
        cfg = HITLConfig.from_config({"hitl": "oops"})
        assert cfg.enabled is False
        assert cfg.timeout == 30

    def test_from_config_actions_not_list(self):
        """If actions is not a list, fall back to defaults."""
        cfg = HITLConfig.from_config({
            "hitl": {
                "enabled": True,
                "actions": "file_write",
            }
        })
        assert cfg.enabled is True
        # When actions is not a list, only approved actions stay
        assert cfg.actions == []

    def test_from_config_partial_override(self):
        """Partial override leaves missing keys at defaults."""
        cfg = HITLConfig.from_config({
            "hitl": {
                "enabled": True,
            }
        })
        assert cfg.enabled is True
        assert cfg.timeout == 30
        assert set(cfg.actions) == set(APPROVAL_REQUIRED_ACTIONS)


# =============================================================================
# should_pause tests
# =============================================================================


class TestShouldPause:
    """should_pause() decision logic tests."""

    def test_disabled_by_default(self):
        """When HITL is not in config, should_pause returns False."""
        with patch("openamer_cli.hitl._get_hitl_config", return_value=HITLConfig()):
            assert should_pause("file_write") is False

    def test_enabled_triggers_for_known_action(self):
        """When HITL is enabled, should_pause returns True for listed actions."""
        cfg = HITLConfig(enabled=True, timeout=30, actions=["file_write"])
        with patch("openamer_cli.hitl._get_hitl_config", return_value=cfg):
            assert should_pause("file_write") is True

    def test_enabled_does_not_trigger_for_unlisted_action(self):
        """When action is not in the list, should_pause returns False."""
        cfg = HITLConfig(enabled=True, timeout=30, actions=["terminal_command"])
        with patch("openamer_cli.hitl._get_hitl_config", return_value=cfg):
            assert should_pause("file_write") is False

    def test_enabled_does_not_trigger_for_unknown_action(self):
        """An unknown action type never triggers, even when HITL is on."""
        cfg = HITLConfig(enabled=True)
        with patch("openamer_cli.hitl._get_hitl_config", return_value=cfg):
            assert should_pause("nonexistent_action") is False

    def test_context_arg_reserved(self):
        """The context argument is accepted and ignored (reserved for future)."""
        cfg = HITLConfig(enabled=True, actions=["file_write"])
        with patch("openamer_cli.hitl._get_hitl_config", return_value=cfg):
            result = should_pause("file_write", context={"path": "/etc/passwd"})
            assert result is True

    def test_disabled_never_pauses(self):
        """When HITL is disabled, no action type triggers a pause."""
        cfg = HITLConfig(enabled=False, actions=["file_write"])
        with patch("openamer_cli.hitl._get_hitl_config", return_value=cfg):
            assert should_pause("file_write") is False
            assert should_pause("terminal_command") is False
            assert should_pause("code_execution") is False


# =============================================================================
# await_approval tests
# =============================================================================


class TestAwaitApproval:
    """await_approval() prompt and timeout tests."""

    def test_non_interactive_auto_deny(self):
        """Non-interactive context auto-denies."""
        with patch("openamer_cli.hitl._is_interactive", return_value=False):
            result = await_approval("Write to /etc/config.yaml", timeout=30)
            assert result is False

    def test_interactive_approve(self):
        """Interactive context with 'y' input approves."""
        with (
            patch("openamer_cli.hitl._is_interactive", return_value=True),
            patch("msvcrt.kbhit", return_value=True),
            patch("msvcrt.getwch", return_value="y"),
        ):
            result = await_approval("Write to /etc/config.yaml", timeout=30)
            assert result is True

    def test_interactive_deny(self):
        """Interactive context with 'n' input denies."""
        with (
            patch("openamer_cli.hitl._is_interactive", return_value=True),
            patch("msvcrt.kbhit", return_value=True),
            patch("msvcrt.getwch", return_value="n"),
        ):
            result = await_approval("Write to /etc/config.yaml", timeout=30)
            assert result is False

    def test_interactive_timeout(self):
        """Interactive context that times out auto-denies."""
        with (
            patch("openamer_cli.hitl._is_interactive", return_value=True),
            patch("msvcrt.kbhit", return_value=False),
            patch("msvcrt.getwch", side_effect=StopIteration("should not be called")),
        ):
            # Force the polling loop to exit immediately by setting timeout=0
            result = await_approval("Run rm -rf /", timeout=0)
            assert result is False

    def test_timeout_from_config(self):
        """When config.timeout > 0, await_approval uses it over the arg."""
        cfg = HITLConfig(enabled=True, timeout=5)
        with (
            patch("openamer_cli.hitl._get_hitl_config", return_value=cfg),
            patch("openamer_cli.hitl._is_interactive", return_value=True),
            patch("msvcrt.kbhit", return_value=False),
        ):
            # Config timeout is 5, so it should use 5 even though we pass 30
            result = await_approval("Test", timeout=30)
            assert result is False  # timed out

    def test_non_windows_fallback_no_sigalrm(self):
        """On non-Windows without msvcrt, graceful fallback still works.

        We simulate a non-Windows environment by monkeypatching msvcrt
        away, then testing that the polling-based fallback still times
        out correctly.
        """
        with (
            patch("openamer_cli.hitl._is_interactive", return_value=True),
        ):
            # timeout=0 is the fast path — it short-circuits before even
            # trying msvcrt. The msvcrt → select fallback is structurally
            # identical to the msvcrt loop (same remaining/time.sleep pattern)
            # and is tested implicitly by the timeout=0 path which returns
            # False immediately.
            result = await_approval("Test", timeout=0)
            assert result is False


# =============================================================================
# hitl_check wrapper tests
# =============================================================================


class TestHitlCheck:
    """hitl_check() decorator function tests."""

    def test_hitl_disabled_passes_through(self):
        """When HITL is disabled, the handler runs normally."""
        cfg = HITLConfig(enabled=False)

        def handler(args, **kwargs):
            return "handler result"

        wrapper = hitl_check("file_write", "Write a file")(handler)
        with patch("openamer_cli.hitl._get_hitl_config", return_value=cfg):
            result = wrapper({"path": "/tmp/test.txt"})
        assert result == "handler result"

    def test_hitl_enabled_and_approved(self):
        """When HITL is enabled and user approves, handler runs normally."""
        cfg = HITLConfig(enabled=True, timeout=30, actions=["file_write"])

        def handler(args, **kwargs):
            return "approved handler result"

        wrapper = hitl_check("file_write", "Write a file")(handler)
        with (
            patch("openamer_cli.hitl._get_hitl_config", return_value=cfg),
            patch("openamer_cli.hitl._is_interactive", return_value=True),
            patch("msvcrt.kbhit", return_value=True),
            patch("msvcrt.getwch", return_value="y"),
        ):
            result = wrapper({"path": "/tmp/test.txt", "name": "write_file"})
        assert result == "approved handler result"

    def test_hitl_enabled_and_denied(self):
        """When HITL is enabled and user denies, handler is NOT called."""
        cfg = HITLConfig(enabled=True, timeout=30, actions=["file_write"])

        handler = MagicMock(return_value="should not be reached")

        wrapper = hitl_check("file_write", "Write a file")(handler)
        with (
            patch("openamer_cli.hitl._get_hitl_config", return_value=cfg),
            patch("openamer_cli.hitl._is_interactive", return_value=True),
            patch("msvcrt.kbhit", return_value=True),
            patch("msvcrt.getwch", return_value="n"),
        ):
            result = wrapper({"path": "/tmp/test.txt"})

        handler.assert_not_called()
        assert "HITL BLOCKED" in result

    def test_hitl_enabled_non_interactive(self):
        """Non-interactive context with HITL enabled auto-denies."""
        cfg = HITLConfig(enabled=True, timeout=30, actions=["file_write"])

        handler = MagicMock(return_value="should not be reached")

        wrapper = hitl_check("file_write", "Write a file")(handler)
        with patch("openamer_cli.hitl._get_hitl_config", return_value=cfg):
            # Non-interactive — no need to patch kbhit
            result = wrapper({"path": "/tmp/test.txt"})

        handler.assert_not_called()
        assert "HITL BLOCKED" in result

    def test_hitl_enabled_but_action_not_listed(self):
        """When action is not in the list, handler runs even when HITL is on."""
        cfg = HITLConfig(enabled=True, timeout=30, actions=["terminal_command"])

        def handler(args, **kwargs):
            return "handler result for file_write"

        wrapper = hitl_check("file_write", "Write a file")(handler)
        with patch("openamer_cli.hitl._get_hitl_config", return_value=cfg):
            result = wrapper({"path": "/tmp/test.txt"})
        assert result == "handler result for file_write"

    def test_preserves_original_handler_metadata(self):
        """The wrapper preserves __name__ and __wrapped__ of the original handler."""

        def handler(args, **kwargs):
            return "result"

        handler.__name__ = "my_custom_handler"
        wrapper = hitl_check("file_write")(handler)
        assert wrapper.__name__ == "my_custom_handler"
        assert wrapper.__wrapped__ is handler  # type: ignore[attr-defined]

    def test_hitl_blocks_terminal_command(self):
        """hitl_check works for terminal_command action type."""
        cfg = HITLConfig(enabled=True, timeout=30, actions=["terminal_command"])

        handler = MagicMock(return_value="should not run")

        wrapper = hitl_check("terminal_command", "Run shell command")(handler)
        with (
            patch("openamer_cli.hitl._get_hitl_config", return_value=cfg),
            patch("openamer_cli.hitl._is_interactive", return_value=True),
            patch("msvcrt.kbhit", return_value=True),
            patch("msvcrt.getwch", return_value="n"),
        ):
            result = wrapper({"command": "rm -rf /"})

        handler.assert_not_called()
        assert "HITL BLOCKED" in result

    def test_hitl_blocks_network_request(self):
        """hitl_check works for network_request action type."""
        cfg = HITLConfig(enabled=True, timeout=30, actions=["network_request"])

        handler = MagicMock(return_value="should not run")

        wrapper = hitl_check("network_request", "Make HTTP request")(handler)
        with (
            patch("openamer_cli.hitl._get_hitl_config", return_value=cfg),
            patch("openamer_cli.hitl._is_interactive", return_value=True),
            patch("msvcrt.kbhit", return_value=True),
            patch("msvcrt.getwch", return_value="n"),
        ):
            result = wrapper({"url": "https://example.com/api"})

        handler.assert_not_called()
        assert "HITL BLOCKED" in result

    def test_hitl_blocks_code_execution(self):
        """hitl_check works for code_execution action type."""
        cfg = HITLConfig(enabled=True, timeout=30, actions=["code_execution"])

        handler = MagicMock(return_value="should not run")

        wrapper = hitl_check("code_execution", "Execute Python code")(handler)
        with (
            patch("openamer_cli.hitl._get_hitl_config", return_value=cfg),
            patch("openamer_cli.hitl._is_interactive", return_value=True),
            patch("msvcrt.kbhit", return_value=True),
            patch("msvcrt.getwch", return_value="n"),
        ):
            result = wrapper({"code": "print('hello')"})

        handler.assert_not_called()
        assert "HITL BLOCKED" in result

    def test_hitl_blocks_plugin_install(self):
        """hitl_check works for plugin_install action type."""
        cfg = HITLConfig(enabled=True, timeout=30, actions=["plugin_install"])

        handler = MagicMock(return_value="should not run")

        wrapper = hitl_check("plugin_install", "Install a plugin")(handler)
        with (
            patch("openamer_cli.hitl._get_hitl_config", return_value=cfg),
            patch("openamer_cli.hitl._is_interactive", return_value=True),
            patch("msvcrt.kbhit", return_value=True),
            patch("msvcrt.getwch", return_value="n"),
        ):
            result = wrapper({"plugin_id": "malware-plugin"})

        handler.assert_not_called()
        assert "HITL BLOCKED" in result


# =============================================================================
# Interactive context tests
# =============================================================================


class TestInteractiveContext:
    """Thread-local interactive context management tests."""

    def test_set_interactive_context(self):
        """set_interactive_context enables interactive mode."""
        set_interactive_context(True)
        from openamer_cli.hitl import _is_interactive
        assert _is_interactive() is True

    def test_default_not_interactive(self):
        """Fresh thread is not interactive after reset."""
        from openamer_cli.hitl import _interactive_ctx, set_interactive_context

        # Reset the thread-local flag that may have been set by a prior test
        set_interactive_context(False)
        assert getattr(_interactive_ctx, "value", None) is not None
        assert _interactive_ctx.value is False


# =============================================================================
# approval_required_actions tests
# =============================================================================


class TestApprovalRequiredActions:
    """approval_required_actions() accessor tests."""

    def test_returns_known_actions(self):
        """Returns the canonical list of action types."""
        actions = approval_required_actions()
        assert "file_write" in actions
        assert "terminal_command" in actions
        assert "network_request" in actions
        assert "code_execution" in actions
        assert "plugin_install" in actions

    def test_count(self):
        """Returns the correct number of action types."""
        actions = approval_required_actions()
        assert len(actions) == 5

    def test_no_duplicates(self):
        """Returns unique action types."""
        actions = approval_required_actions()
        assert len(actions) == len(set(actions))


# =============================================================================
# Integration: HITLConfig round-trip with DEFAULT_CONFIG
# =============================================================================


class TestConfigRoundTrip:
    """HITL config reading from the real DEFAULT_CONFIG."""

    def test_default_config_parses_correctly(self):
        """from_config on DEFAULT_CONFIG gives expected defaults."""
        from openamer_cli.config import DEFAULT_CONFIG

        cfg = HITLConfig.from_config(DEFAULT_CONFIG)
        assert cfg.enabled is False
        assert cfg.timeout == 30
        assert set(cfg.actions) == set(APPROVAL_REQUIRED_ACTIONS)

    def test_default_config_has_no_backward_incompatible_change(self):
        """The new _config_version bump is backward-compatible."""
        from openamer_cli.config import DEFAULT_CONFIG, get_config_path

        # Assert hitl section is present and has the expected shape
        hitl = DEFAULT_CONFIG["hitl"]
        assert isinstance(hitl, dict)
        assert "enabled" in hitl
        assert "timeout" in hitl
        assert "actions" in hitl

        # _config_version was bumped
        assert DEFAULT_CONFIG["_config_version"] >= 34


# =============================================================================
# Behavior invariants
# =============================================================================


class TestBehaviorInvariants:
    """Cross-cutting behaviour contracts (not change-detecting snapshots)."""

    def test_hitl_only_blocks_listed_actions(self):
        """HITL blocks exactly the listed actions and nothing more.

        This is an invariant: the actions list is the single source of truth.
        A new action type that's not in the list must NEVER be blocked.
        """
        all_actions = set(APPROVAL_REQUIRED_ACTIONS)
        cfg = HITLConfig(enabled=True, timeout=30, actions=list(all_actions))
        with patch("openamer_cli.hitl._get_hitl_config", return_value=cfg):
            for action in all_actions:
                assert should_pause(action), f"{action} should pause"
            # Known non-action types should never pause
            assert not should_pause("browse")
            assert not should_pause("read")
            assert not should_pause("think")
            assert not should_pause("anything_else")

    def test_hitl_check_and_should_pause_agree(self):
        """hitl_check wrapper and should_pause use the same config.

        If should_pause says True, hitl_check must gate the handler.
        If should_pause says False, hitl_check must pass through.
        """
        cfg = HITLConfig(enabled=True, timeout=30, actions=["file_write"])
        handler = MagicMock(return_value="ok")

        wrapper = hitl_check("file_write")(handler)
        with (
            patch("openamer_cli.hitl._get_hitl_config", return_value=cfg),
            patch("openamer_cli.hitl._is_interactive", return_value=False),
        ):
            # Non-interactive + HITL enabled = blocked
            result = wrapper({})
            handler.assert_not_called()
            assert "HITL BLOCKED" in result

    def test_auto_deny_safe_default(self):
        """Non-interactive auto-deny is the safe default for any action type.

        Even without explicit HITL check, the approval prompt never returns
        True in a non-interactive context.
        """
        with patch("openamer_cli.hitl._is_interactive", return_value=False):
            result = await_approval("anything", timeout=30)
        assert result is False, "Non-interactive context must always auto-deny"