#!/usr/bin/env python3
"""Prompt channel for credential entry.

A credential must be typed by the USER, on their own surface, through a masked
field — never as a tool argument and never into the conversation. That means the
vault tools cannot ask for one themselves: they need the hosting surface (the
desktop app, the CLI, a TUI) to supply a prompt callback.

This module is that channel, and nothing more:

- A surface calls :func:`set_prompt_callback` once at startup.
- The vault tools call :func:`can_prompt` before asking and
  :func:`get_save_login_prompt` to obtain the callback.
- With no callback registered — a cron job, a gateway request, an API session —
  ``can_prompt()`` is False and the caller returns a typed refusal. There is no
  stdin fallback on purpose: a non-interactive session waiting on stdin would
  hang, and ``prompt_toolkit``/``input()`` cannot guarantee masked echo across
  the surfaces this agent runs on.

Same shape as :mod:`tools.clarify_tool`, which already delegates its UI to a
platform-provided ``callback(question, choices)``.

The callback contract:

    callback(origin: str, site_label: str) -> dict

It must return ``{"identifier": str, "password": str}``, or an empty dict if the
user declined. It MUST mask the password on screen and MUST NOT log, print, or
otherwise persist what the user typed. Returning the values is the entire point
— they travel from the user's keyboard to this process and straight into the
page, and are never re-exported.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

# The one callback slot. A process has a single hosting surface.
_prompt_lock = threading.Lock()
_save_login_callback: Optional[Callable[[str, str], Dict[str, Any]]] = None


def set_prompt_callback(callback: Optional[Callable[[str, str], Dict[str, Any]]]) -> None:
    """Register (or clear, with ``None``) the surface's masked credential prompt.

    Called once by the hosting surface at startup. The callback receives
    ``(origin, site_label)`` and returns ``{"identifier", "password"}`` or ``{}``.
    """
    global _save_login_callback
    with _prompt_lock:
        _save_login_callback = callback


def get_save_login_prompt() -> Optional[Callable[[str, str], Dict[str, Any]]]:
    """The registered masked prompt, or None when this session cannot ask."""
    with _prompt_lock:
        return _save_login_callback


def can_prompt() -> bool:
    """Whether this session can ask the user for a credential.

    False for cron, gateway and API sessions — they have no interactive surface,
    and a refusal there is correct behaviour, not a missing feature.
    """
    return get_save_login_prompt() is not None


def clear_prompt_callback() -> None:
    """Drop the callback (test/teardown helper)."""
    set_prompt_callback(None)
