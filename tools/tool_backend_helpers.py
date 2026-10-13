"""Shared helpers for tool backend selection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from utils import is_truthy_value


_DEFAULT_BROWSER_PROVIDER = "local"
_DEFAULT_MODAL_MODE = "auto"
_VALID_MODAL_MODES = {"auto", "direct", "managed"}


def managed_openamer_tools_enabled(*, force_fresh: bool = False) -> bool:
    """Return True when the user is entitled to the OpenAmer Tool Gateway.

    Entitlement is paid OpenAmer Portal service access OR a live free tool pool
    (``tool_gateway_entitled``). Per-category coverage (the pool funds image but
    not video, etc.) is narrowed by callers via ``tool_gateway_entitled_for``;
    this coarse gate only answers "is any managed tool usable at all".

    Tool Gateway availability fails closed on unknown/error entitlement.  We
    intentionally catch all exceptions and return False — never block startup.
    ``force_fresh=True`` is for interactive configuration flows that should
    reflect a just-purchased subscription, credits, or pool grant immediately.
    """
    try:
        from openamer_cli.openamer_account import get_openamer_portal_account_info

        if force_fresh:
            account_info = get_openamer_portal_account_info(force_fresh=True)
        else:
            account_info = get_openamer_portal_account_info()
        if not account_info.logged_in:
            return False
        return account_info.tool_gateway_entitled
    except Exception:
        return False


def openamer_tool_gateway_unavailable_message(
    capability: str = "the OpenAmer Tool Gateway",
    *,
    force_fresh: bool = False,
) -> str:
    """Return account-aware guidance for an unavailable OpenAmer Tool Gateway path."""
    try:
        from openamer_cli.openamer_account import (
            format_openamer_portal_entitlement_message,
            get_openamer_portal_account_info,
        )

        account_info = get_openamer_portal_account_info(force_fresh=force_fresh)
        message = format_openamer_portal_entitlement_message(
            account_info,
            capability=capability,
        )
        if message:
            return message
    except Exception:
        pass
    return (
        f"{capability} is unavailable. Run `openamer model` to refresh your "
        "OpenAmer Portal login and billing status."
    )


def normalize_browser_cloud_provider(value: object | None) -> str:
    """Return a normalized browser provider key."""
    provider = str(value or _DEFAULT_BROWSER_PROVIDER).strip().lower()
    return provider or _DEFAULT_BROWSER_PROVIDER


def coerce_modal_mode(value: object | None) -> str:
    """Return the requested modal mode when valid, else the default."""
    mode = str(value or _DEFAULT_MODAL_MODE).strip().lower()
    if mode in _VALID_MODAL_MODES:
        return mode
    return _DEFAULT_MODAL_MODE


def normalize_modal_mode(value: object | None) -> str:
    """Return a normalized modal execution mode."""
    return coerce_modal_mode(value)


def has_direct_modal_credentials() -> bool:
    """Return True when direct Modal credentials/config are available."""
    try:
        modal_file_exists = (Path.home() / ".modal.toml").exists()
    except (PermissionError, OSError):
        modal_file_exists = False
    return bool(
        (os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET"))
        or modal_file_exists
    )


def resolve_modal_backend_state(
    modal_mode: object | None,
    *,
    has_direct: bool,
    managed_ready: bool,
    managed_enabled: bool | None = None,
) -> Dict[str, Any]:
    """Resolve direct vs managed Modal backend selection.

    Semantics:
    - ``direct`` means direct-only
    - ``managed`` means managed-only
    - ``auto`` prefers managed when available, then falls back to direct
    """
    requested_mode = coerce_modal_mode(modal_mode)
    normalized_mode = normalize_modal_mode(modal_mode)
    if managed_enabled is None:
        managed_enabled = managed_openamer_tools_enabled()
    managed_mode_blocked = (
        requested_mode == "managed" and not managed_enabled
    )

    if normalized_mode == "managed":
        selected_backend = "managed" if managed_enabled and managed_ready else None
    elif normalized_mode == "direct":
        selected_backend = "direct" if has_direct else None
    else:
        selected_backend = "managed" if managed_enabled and managed_ready else "direct" if has_direct else None

    return {
        "requested_mode": requested_mode,
        "mode": normalized_mode,
        "has_direct": has_direct,
        "managed_ready": managed_ready,
        "managed_mode_blocked": managed_mode_blocked,
        "selected_backend": selected_backend,
    }


def resolve_openai_audio_api_key() -> str:
    """Prefer the voice-tools key, but fall back to the normal OpenAI key."""
    return (
        os.getenv("VOICE_TOOLS_OPENAI_KEY", "")
        or os.getenv("OPENAI_API_KEY", "")
    ).strip()


def prefers_gateway(config_section: str) -> bool:
    """Return True when the user opted into the Tool Gateway for this tool.

    Reads ``<section>.use_gateway`` from config.yaml.  Never raises.
    """
    try:
        from openamer_cli.config import load_config
        section = (load_config() or {}).get(config_section)
        if isinstance(section, dict):
            return is_truthy_value(section.get("use_gateway"), default=False)
    except Exception:
        pass
    return False


def fal_key_is_configured() -> bool:
    """Return True when FAL_KEY is set to a non-whitespace value.

    Consults both ``os.environ`` and ``~/.openamer/.env`` (via
    ``openamer_cli.config.get_env_value`` when available) so tool-side
    checks and CLI setup-time checks agree.  A whitespace-only value
    is treated as unset everywhere.
    """
    value = os.getenv("FAL_KEY")
    if value is None:
        # Fall back to the .env file for CLI paths that may run before
        # dotenv is loaded into os.environ.
        try:
            from openamer_cli.config import get_env_value

            value = get_env_value("FAL_KEY")
        except Exception:
            value = None
    return bool(value and value.strip())

# ---------------------------------------------------------------------------
# `openamer tools` selection state
#
# THE single runtime read of the persisted per-category backend selection. Kept
# separate from the config schema defaults on purpose: key *presence* in the raw
# config.yaml means the user actually made a choice, which is what distinguishes
# "direct, no credentials yet" from "never configured, autodetect allowed".
# ---------------------------------------------------------------------------

NOUS_MANAGED_PROVIDER = "nous"
# Per-capability keys that also count as "this category has been configured".
_EXTRA_SELECTION_KEYS = {"web": ("search_backend", "extract_backend")}
# Key(s) carrying the category's provider selection. ``browser.backend`` is the DRIVER
# choice (browser-use CLI vs built-in), not the cloud provider — excluded.
_SELECTION_NAME_KEYS = {"browser": ("cloud_provider",), "web": ("backend",)}
_DEFAULT_NAME_KEYS = ("provider", "backend", "cloud_provider")


def _raw_section(section: str) -> Dict[str, Any] | None:
    """The RAW (unmerged) config.yaml mapping for ``section``, or None."""
    try:
        from openamer_cli.config import read_raw_config_readonly
        cfg = read_raw_config_readonly() or {}
        raw = cfg.get(section) if isinstance(cfg, dict) else None
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def read_selection(section: str) -> str | None:
    """The persisted `openamer tools` selection for ``section``.

    Returns ``"nous"`` (managed gateway row), a vendor name (direct, own
    credentials), or ``None`` (never configured -> legacy autodetect allowed).
    Reads the RAW config.yaml so key presence means "actually written", not
    "schema default"; a raw ``local`` is therefore a real user selection.
    Legacy shim: ``use_gateway: true`` was only ever written by the managed row,
    so it maps to ``"nous"`` regardless of the name key. Never raises.
    """
    raw = _raw_section(section)
    if raw is None:
        return None
    if is_truthy_value(raw.get("use_gateway")):
        return NOUS_MANAGED_PROVIDER
    for key in _SELECTION_NAME_KEYS.get(section, _DEFAULT_NAME_KEYS):
        text = str(raw.get(key)).strip().lower() if raw.get(key) is not None else ""
        if text:
            return text
    # use_gateway: false with no name key is not a usable selection shape;
    # per-capability web keys still count as configured via selection_exists().
    return None


def selection_exists(section: str) -> bool:
    """True when `openamer tools` has written ANY selection for ``section``.

    Distinguishes "never configured" (legacy autodetect) from "configured to
    something else", including capability-specific keys that carry the selection
    for composite sections such as ``web``.
    """
    raw = _raw_section(section)
    if raw is None:
        return False
    if read_selection(section) is not None:
        return True
    for key in _EXTRA_SELECTION_KEYS.get(section, ()):
        if raw.get(key) is not None and str(raw.get(key)).strip():
            return True
    # ``use_gateway: false`` alone is a deliberate "direct, no vendor name" state.
    return raw.get("use_gateway") is not None


REMOVED_BACKENDS: Dict[str, Dict[str, str]] = {}


def removed_backend_note(section: str, name: str) -> Optional[str]:
    """Replacement hint when a stored backend was removed from the catalog."""
    return REMOVED_BACKENDS.get(section, {}).get((name or "").strip().lower())


def selection_error(section: str, selection_name: str, failure: str) -> str:
    """Actionable error for a stored selection that cannot run.

    Names the section, the stored selection and the missing prerequisite so the
    user knows which `openamer tools` row to fix — never a silent fallback to a
    different backend.
    """
    hint = removed_backend_note(section, selection_name)
    tail = f" {hint}" if hint else ""
    return (
        f"`{section}` is set to '{selection_name}' but {failure}."
        f" Run `openamer tools` to pick a working {section} backend.{tail}"
    )


# Upstream-compatible spellings. Files ported from the upstream tree import these
# names verbatim; aliasing them here keeps every port compiling without a rebrand
# pass, and both spellings resolve to the same object.
managed_nous_tools_enabled = managed_openamer_tools_enabled
nous_tool_gateway_unavailable_message = openamer_tool_gateway_unavailable_message
