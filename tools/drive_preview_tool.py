#!/usr/bin/env python3
"""Interact with the page already open in the OpenAmer desktop preview pane.

The page lives in the renderer's ``<webview>``, so this tool is schema plus a
thin dispatcher over the gateway's blocking renderer bridge: it emits
``preview.act.request`` to the ONE window that owns the current turn and waits
for that window's ``preview.act.respond``. Element inventory, ref resolution and
the actual DOM work happen in the renderer; nothing here evaluates code in the
page by itself.

Bounded port of NousResearch/hermes-agent ``tools/drive_preview_tool.py`` (MIT,
pinned at bfa652fae87fd7c5c01161188f97a8ed68b5a762) — the ref/inventory idea and
the "re-inventory after acting" shape are theirs; the verb set, the delta
protocol, the pointer/strobe/overlay layers and the browser-bar plumbing are NOT
ported (see ``NOTICE``).
"""

from typing import Callable, Optional

from tools import desktop_ui
from tools.desktop_ui import passthrough_json
from tools.registry import registry, tool_error
from utils import env_var_enabled

ACTIONS = ("elements", "click", "type", "read")

# Verbs that need an element to act on — a ref from the last inventory.
NEEDS_REF = ("click", "type")

# The renderer answers this request; see tui_gateway's ``preview.act.respond``.
ACT_EVENT = "preview.act.request"

# One round trip; the renderer answers immediately (it never waits on the page
# for longer than a short settle), so this only expires when the window is gone.
ACT_TIMEOUT_S = 45.0


def _bridge(payload: dict) -> str:
    """Blocking round trip to the window that owns this turn."""
    return desktop_ui.request(ACT_EVENT, payload, timeout=ACT_TIMEOUT_S)


def drive_preview_tool(
    action: str = "",
    ref: Optional[str] = None,
    text: Optional[str] = None,
    submit: Optional[bool] = None,
    limit: Optional[int] = None,
    callback: Optional[Callable] = None,
) -> str:
    """Dispatch one interaction to the desktop preview pane and return its outcome."""
    if callback is None:
        if not desktop_ui.available():
            return tool_error("drive_preview is only available in the OpenAmer desktop app.")
        callback = _bridge
    verb = (action or "").strip().lower()
    if verb not in ACTIONS:
        return tool_error(f"action must be one of: {', '.join(ACTIONS)}.")
    if verb in NEEDS_REF and not (ref or "").strip():
        return tool_error(
            f"{verb} needs a ref from action='elements' (e.g. 'btn-sign-in'). "
            "Call elements first, and call it again whenever a ref is reported stale."
        )
    if verb == "type" and text is None:
        return tool_error("type needs the text to enter.")

    try:
        payload = {
            name: val
            for name, val in (
                ("action", verb),
                ("ref", (ref or "").strip() or None),
                ("text", text),
                ("submit", submit),
                ("max", None if limit is None else int(limit)),
            )
            if val is not None
        }
    except (TypeError, ValueError):
        return tool_error("max must be an integer.")

    try:
        raw = callback(payload)
    except Exception as exc:
        return tool_error(f"Failed to act on the preview pane: {exc}")
    if not raw:
        return tool_error(
            "No preview window answered: either no page is open in the preview pane, "
            "or this session's preview is not the one on screen. Open a page with "
            "open_preview first. If the pane IS open, the desktop app may be older "
            "than this backend — its bridge-unavailable error names that case."
        )
    return passthrough_json(raw)


def check_drive_preview_requirements() -> bool:
    """Desktop GUI only — OPENAMER_DESKTOP is set on the gateway the app spawns."""
    return env_var_enabled("OPENAMER_DESKTOP")


DRIVE_PREVIEW_SCHEMA = {
    "name": "drive_preview",
    "description": (
        "Use the page already open in the desktop preview pane: fill forms, click "
        "through a flow, read the result back. It drives the SAME preview the user "
        "is looking at, for this session only — it never opens, redirects or "
        "retargets the pane, and it refuses when another session's page is on "
        "screen. ALWAYS start with action='elements': it inventories clickable and "
        "typable elements as refs ('btn-sign-in') with role/label/value. Act by "
        "ref — never by guessed coordinates. Refs belong to the page they were read "
        "from: after the page navigates they are stale and the call fails instead of "
        "hitting the wrong element, so call elements again. Every action answers "
        "with a refreshed inventory (bounded by 'max'), so a click → inspect loop "
        "does not need a second call. action='read' returns the visible text (and, "
        "with a ref, that element's value). Type text only into fields the user "
        "asked you to fill; never type credentials, card numbers or tokens. This is "
        "not a general browser: there is no navigation, no download and no "
        "arbitrary script evaluation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": list(ACTIONS),
                "description": "Start with 'elements'.",
            },
            "ref": {
                "type": "string",
                "description": "Element ref from an elements call. Required for click/type.",
            },
            "text": {"type": "string", "description": "type: the text to enter."},
            "submit": {
                "type": "boolean",
                "description": "type: submit the field's form after entering the text.",
            },
            "max": {
                "type": "integer",
                "description": "elements: cap the inventory (default 60, max 200).",
            },
        },
        "required": ["action"],
    },
}


registry.register(
    name="drive_preview",
    toolset="terminal",
    schema=DRIVE_PREVIEW_SCHEMA,
    handler=lambda args, **kw: drive_preview_tool(
        action=args.get("action", ""),
        ref=args.get("ref"),
        text=args.get("text"),
        submit=args.get("submit"),
        limit=args.get("max"),
        callback=kw.get("callback"),
    ),
    check_fn=check_drive_preview_requirements,
    emoji="🖱️",
)
