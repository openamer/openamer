#!/usr/bin/env python3
"""Human-in-the-Loop (HITL) approval system for OpenAmer Agent.

This module implements an optional approval gate that pauses agent execution
before certain action types and asks the user for explicit approval or denial.

Per AGENTS.md: new capability should arrive as:
  1. CLI command + config option first
  2. Service-gated tool (check_fn) second

This module is the **utility layer** — it provides:
  - HITLConfig dataclass for reading config.yaml values
  - should_pause() — checks if an action type triggers HITL
  - await_approval() — prompts the user (CLI) or auto-denies (gateway)
  - hitl_check() — returns a check_fn wrapper that gates tool handler invocation

Wiring: tools call hitl_check('file_write')(handler) to wrap their handler, or
the check_fn field of registry.register() gets hitl_check() as a wrapper.
"""

from __future__ import annotations

import functools
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default action types that trigger HITL approval
# ---------------------------------------------------------------------------

APPROVAL_REQUIRED_ACTIONS: List[str] = [
    "file_write",
    "terminal_command",
    "network_request",
    "code_execution",
    "plugin_install",
]

# ---------------------------------------------------------------------------
# HITL Config
# ---------------------------------------------------------------------------


@dataclass
class HITLConfig:
    """Parsed HITL settings from config.yaml.

    The ``actions`` list is a subset of APPROVAL_REQUIRED_ACTIONS that the
    user has opted into; only action types present in both lists trigger a
    pause.
    """

    enabled: bool = False
    timeout: int = 30
    actions: List[str] = field(default_factory=lambda: list(APPROVAL_REQUIRED_ACTIONS))

    @classmethod
    def from_config(cls, cfg: Optional[Dict[str, Any]] = None) -> "HITLConfig":
        """Build HITLConfig from the OpenAmer config dict.

        Reads ``cfg[\"hitl\"]`` and falls back to defaults for any missing key.
        ``cfg`` can be ``None`` (no config loaded yet) — returns defaults.
        """
        if cfg is None:
            return cls()
        hitl_section = cfg.get("hitl", {})
        if not isinstance(hitl_section, dict):
            return cls()
        enabled = bool(hitl_section.get("enabled", False))
        timeout = int(hitl_section.get("timeout", 30))
        raw_actions = hitl_section.get("actions", None)
        actions: List[str] = []
        if raw_actions is None:
            # No actions key at all — use the full default list when enabled
            actions = list(APPROVAL_REQUIRED_ACTIONS) if enabled else []
        elif isinstance(raw_actions, list):
            for act in raw_actions:
                if isinstance(act, str) and act in APPROVAL_REQUIRED_ACTIONS:
                    actions.append(act)
        # If raw_actions is present but not a list (e.g. a string), or the
        # filtered list is empty, HITL is effectively off even when enabled.
        return cls(enabled=enabled, timeout=timeout, actions=actions)


# ---------------------------------------------------------------------------
# Module-level cached config (refreshed on every call to avoid stale imports)
# ---------------------------------------------------------------------------

_HITL_CONFIG_CACHE: Optional[HITLConfig] = None
_HITL_CONFIG_LOCK = threading.Lock()


def _get_hitl_config() -> HITLConfig:
    """Return the current HITL config, freshly read from settings.

    Uses ``read_raw_config()`` to avoid the overhead of the full config
    loading pipeline, and caches within the current call chain (rebuilt
    on next invocation).
    """
    global _HITL_CONFIG_CACHE
    try:
        from openamer_cli.config import read_raw_config

        raw = read_raw_config()
    except Exception:
        raw = {}
    cfg = HITLConfig.from_config(raw)
    return cfg


# ---------------------------------------------------------------------------
# Interactive-context detection
# ---------------------------------------------------------------------------

# Thread-local flag: set per-turn by the CLI/TUI loop so that concurrent
# gateway threads don't see each other's interactive mode.
_interactive_ctx = threading.local()


def _is_interactive() -> bool:
    """Return True when the current thread is in an interactive CLI/TUI loop.

    Resolution order:
      1. Thread-local flag (set by the CLI/TUI before agent.run)
      2. OPENAMER_INTERACTIVE env var (legacy CLI single-threaded)
      3. Not a gateway session (no OPENAMER_GATEWAY_SESSION nor platform)
    """
    val = getattr(_interactive_ctx, "value", None)
    if val is not None:
        return bool(val)

    env_val = os.getenv("OPENAMER_INTERACTIVE", "")
    if env_val:
        return env_val.strip().lower() in ("1", "true", "yes")

    # Non-interactive by default (gateway/background/cron)
    return False


def set_interactive_context(interactive: bool) -> None:
    """Bind the interactive flag for the current thread.

    Call this before agent.run() from a CLI/TUI entry point.
    """
    _interactive_ctx.value = interactive


# ---------------------------------------------------------------------------
# Approval check
# ---------------------------------------------------------------------------


def should_pause(action_type: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """Return True when the given action type requires HITL approval.

    An action type requires approval when HITL is enabled AND the action type
    is in the configured actions list.  The optional ``context`` dict is
    reserved for future enrichment (e.g. file paths, command text) and is not
    used in the boolean decision today.

    Args:
        action_type: One of APPROVAL_REQUIRED_ACTIONS.
        context: Optional dict with additional action metadata (unused today).

    Returns:
        True if the agent should pause and ask for approval before proceeding.
    """
    _ = context  # reserved for future use
    cfg = _get_hitl_config()
    if not cfg.enabled:
        return False
    return action_type in cfg.actions


# ---------------------------------------------------------------------------
# Approval prompting
# ---------------------------------------------------------------------------


def await_approval(prompt: str, timeout: int = 30) -> bool:
    """Ask the user to approve or deny an agent action.

    In interactive (CLI/TUI) mode, prints the prompt and waits for keypress.
    In non-interactive mode (gateway/background/cron), auto-denies with a log
    warning after the timeout.

    Args:
        prompt: Human-readable description of what the agent wants to do.
        timeout: Seconds to wait before auto-denying.

    Returns:
        True if the user approved, False if they denied or timed out.
    """
    cfg = _get_hitl_config()

    # If we have an explicit timeout override from config, use it
    effective_timeout = timeout
    if cfg.timeout > 0:
        effective_timeout = cfg.timeout

    if not _is_interactive():
        logger.warning(
            "HITL: auto-deny (non-interactive context) — %s",
            prompt,
        )
        return False

    # Interactive prompt
    print(
        f"\n❓ OpenAmer needs your approval: {prompt}. "
        f"Approve? [y/N] (auto-denies in {effective_timeout}s)"
    )

    # Fast-path: zero timeout → immediate deny
    if effective_timeout <= 0:
        print("  ⏱️  Auto-denied (timeout)")
        return False

    start = time.monotonic()
    remaining = effective_timeout

    try:
        import msvcrt  # Windows-specific — fast key polling

        while remaining > 0:
            if msvcrt.kbhit():  # type: ignore[attr-defined]
                ch = msvcrt.getwch()  # type: ignore[attr-defined]
                if ch.lower() == "y":
                    print("  ✅ Approved")
                    return True
                # Any other key (including Enter/msvcrt specials) is a deny
                print("  ❌ Denied")
                return False
            time.sleep(0.1)
            remaining = effective_timeout - (time.monotonic() - start)
        print("  ⏱️  Auto-denied (timeout)")
        return False
    except ImportError:
        # Fallback for non-Windows: time.sleep polling loop
        # (signal-based alarm would need SIGALRM which isn't on Windows)
        import select
        import sys

        while remaining > 0:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                resp = sys.stdin.readline().strip().lower()
                if resp == "y":
                    print("  ✅ Approved")
                    return True
                print("  ❌ Denied")
                return False
            remaining = effective_timeout - (time.monotonic() - start)
        print("  ⏱️  Auto-denied (timeout)")
        return False


# ---------------------------------------------------------------------------
# check_fn wrapper
# ---------------------------------------------------------------------------


def hitl_check(action_type: str, action_description: str = "") -> Callable[[Callable], Callable]:
    """Return a decorator that wraps a tool handler with HITL approval gating.

    When ``should_pause(action_type)`` returns True, the wrapper pauses
    execution, asks for user approval via ``await_approval()``, and only
    calls the original handler if approved.  If denied, it returns a
    descriptive error message to the agent.

    Usage (at tool registration site)::

        registry.register(
            name="write_file",
            toolset="file",
            schema=...,
            handler=hitl_check("file_write", "Write a file on the host")(_handle_write_file),
            ...
        )

    Or as a wrapper at handler definition::

        @hitl_check("terminal_command", "Execute a shell command")
        def my_handler(args, **kwargs):
            ...

    Args:
        action_type: The action category to check (must be in
            APPROVAL_REQUIRED_ACTIONS).
        action_description: Optional human-readable label used in the
            approval prompt.  If empty, the action_type is used.

    Returns:
        A decorator that wraps the handler function.
    """

    def decorator(handler: Callable) -> Callable:
        @functools.wraps(handler)
        def wrapper(*args: Any, **kwargs: Any) -> str:
            if should_pause(action_type):
                desc = action_description or f"agent action: {action_type}"
                # Extract a bit more context from the first positional arg
                # (the tool args dict) if available
                if args and isinstance(args[0], dict):
                    tool_args = args[0]
                    if "name" in tool_args:
                        desc = f"{desc} ({tool_args['name']})"
                    if "path" in tool_args:
                        desc = f"{desc} on {tool_args['path']}"
                    if "command" in tool_args:
                        cmd = str(tool_args["command"])
                        if len(cmd) > 120:
                            cmd = cmd[:117] + "..."
                        desc = f"{desc}: {cmd}"

                cfg = _get_hitl_config()
                approved = await_approval(desc, cfg.timeout)
                if not approved:
                    return (
                        f"[HITL BLOCKED] The agent was not allowed to perform "
                        f"this action: {desc}.  User denied or timed out."
                    )
                # Approved — fall through to the real handler
            return handler(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Convenience accessor
# ---------------------------------------------------------------------------


def approval_required_actions() -> List[str]:
    """Return the list of action types that trigger HITL approval.

    This is the public API for enumerating which action types are monitored.
    Consumers (CLI help text, TUI panels, docs) should call this function
    rather than importing the constant directly.
    """
    return list(APPROVAL_REQUIRED_ACTIONS)