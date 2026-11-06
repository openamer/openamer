#!/usr/bin/env python3
"""Bridge desktop-only tools to OpenAmer-desktop renderer events.

The preview pane, pane focus, and friends live in the desktop renderer, so
desktop-gated tools reach them through an emitter the desktop ``tui_gateway``
installs at session start via :func:`set_emitter`. Everywhere else it stays
``None`` and the tools report "desktop only". Routing keys off
``OPENAMER_UI_SESSION_ID`` so the event lands on the window that owns the turn
(``_emit``/``write_json`` is ``_stdout_lock``-guarded, so emitting from the
tool's thread is safe).

Some renderer affordances answer back (the preview pane's element inventory and
readback), so the gateway also installs a *blocking* requester via
:func:`set_requester`. It rides the same ``OPENAMER_UI_SESSION_ID`` routing: a
request reaches one window, that window answers with a ``*.respond`` RPC, and
any other window's answer is rejected as cross-session.

The blocking requester shape is derived from NousResearch/hermes-agent
(``tools/desktop_ui.py``, MIT, pinned at bfa652fae87fd7c5c01161188f97a8ed68b5a762);
see ``NOTICE``.
"""

import json
from typing import Callable, Optional

from gateway.session_context import get_session_env

# (sid, event, payload) sink, installed by the desktop gateway.
_emit: Optional[Callable[[str, str, dict], None]] = None

# (sid, event, payload, timeout) -> answer, installed by the desktop gateway.
_ask: Optional[Callable[[str, str, dict, float], str]] = None


def set_emitter(fn: Optional[Callable[[str, str, dict], None]]) -> None:
    """Install (or clear) the renderer-event sink. Called by the desktop gateway."""
    global _emit
    _emit = fn


def set_requester(fn: Optional[Callable[[str, str, dict, float], str]]) -> None:
    """Install (or clear) the blocking renderer-request sink."""
    global _ask
    _ask = fn


def request(event: str, payload: dict, timeout: float = 45.0) -> str:
    """Ask the window that owns the current turn and wait for its answer.

    Returns the renderer's answer (a JSON string), or ``""`` when no requester
    is wired (not the desktop app) or the renderer did not answer in time. The
    request is addressed to ONE window — the one that owns the turn — so a
    second window can neither see it nor answer it.
    """
    fn = _ask
    if fn is None:
        return ""
    return fn(get_session_env("OPENAMER_UI_SESSION_ID", ""), event, payload, timeout) or ""


def passthrough_json(raw) -> str:
    """Desktop answers with a JSON object; pass it through, else wrap the raw text."""
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps({"text": str(raw)}, ensure_ascii=False)



def available() -> bool:
    """True when running under the desktop app (an emitter is wired)."""
    return _emit is not None


def emit(event: str, payload: dict) -> bool:
    """Route ``event`` to the window that owns the current turn.

    Returns ``False`` when no emitter is wired (i.e. not the desktop app)."""
    fn = _emit
    if fn is None:
        return False
    fn(get_session_env("OPENAMER_UI_SESSION_ID", ""), event, payload)
    return True
