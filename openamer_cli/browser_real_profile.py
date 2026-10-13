#!/usr/bin/env python3
"""Use the user's REAL browser profile for a browser session — on a copy.

WHY A COPY, AND WHY THAT MATTERS
    Logged-in browsing needs the user's cookies. Pointing the agent at the live
    profile directory is not an option: a second browser on the same
    ``--user-data-dir`` collides with the running one (and Chrome refuses), and
    anything the agent changes would land in the profile the user actually uses.
    So the profile is SNAPSHOTTED into an OpenAmer-owned directory and the real
    browser binary is launched on the copy. The user's own browser is untouched.

THE CONSENT BOUNDARY
    This reaches the user's cookies, so it is off by default and gated on
    EXPLICIT config. Two switches, both required for different reasons:

    - ``browser.use_real_profile``           — the master consent flag.
    - ``browser.real_profile_acknowledged``  — a separate acknowledgement of what
      it does. A single flag that both enables and acknowledges would let one
      accidental edit hand the agent the user's session cookies.

    With either missing, :func:`real_profile_status` reports why and nothing is
    copied or launched. There is no auto-enable, ever.

WHAT THIS MODULE DOES NOT DO
    It does not launch a browser by itself, and it does not touch the live
    profile. It resolves, verifies, copies and reports. The launch belongs to the
    browser tool path, which already knows how to attach over CDP — that path
    gets ``launch_args`` from here and adds its own plumbing.

FAIL-CLOSED ON AN UNRESOLVED BROWSER
    If the default browser cannot be resolved to a supported Chromium family,
    the answer is a refusal with the reason, not a guess. Picking a different
    browser than the user's default would drive a DIFFERENT profile and account
    — the wrong-principal bug.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openamer_constants import get_openamer_home

logger = logging.getLogger(__name__)

CONFIG_FLAG_ENABLED = "browser.use_real_profile"
CONFIG_FLAG_ACK = "browser.real_profile_acknowledged"

# Files and directories a Chromium profile needs to carry a logged-in session.
# Everything else (caches, GPU data, code caches) is skipped: it is large, it is
# regenerated, and copying it slows the snapshot down for no benefit.
_PROFILE_FILES = (
    "Cookies", "Cookies-journal", "Login Data", "Login Data-journal",
    "Web Data", "Web Data-journal", "Preferences", "Secure Preferences",
    "Local State", "Local Storage", "Session Storage", "IndexedDB",
)
_PROFILE_DIRS = ("Local Storage", "Session Storage", "IndexedDB")

# Never copy these, even if they match above: they are device-scoped or huge.
_PROFILE_SKIP = ("Cache", "Code Cache", "GPUCache", "Service Worker", "Crashpad", "ShaderCache")

# Launch flags. Not cosmetic: without --no-first-run and
# --no-default-browser-check a first launch opens dialogs that block headless use;
# --disable-sync keeps the copy from pushing state back to the user's account.
REAL_PROFILE_LAUNCH_FLAGS = (
    "--remote-debugging-port=0",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-popup-blocking",
    "--disable-sync",
    "--disable-features=Translate",
    "--no-startup-window",
)

_PROFILE_LOCKED_MARKERS = ("SingletonLock", "SingletonCookie", "lockfile")


class RealProfileError(RuntimeError):
    """A real-profile failure whose message is safe to show the user."""


@dataclass
class RealProfileStatus:
    enabled: bool
    acknowledged: bool
    browser: Optional[str] = None
    binary: Optional[str] = None
    profile_dir: Optional[str] = None
    reason: str = ""
    copy_dir: Optional[str] = None

    @property
    def usable(self) -> bool:
        return bool(self.enabled and self.acknowledged and self.binary and self.profile_dir)

    def to_dict(self) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "acknowledged": self.acknowledged,
            "usable": self.usable,
            "browser": self.browser,
            "binary": self.binary,
            "profile_dir": self.profile_dir,
            "copy_dir": self.copy_dir,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def read_flags() -> Tuple[bool, bool]:
    """``(enabled, acknowledged)`` from config.yaml. Both default to False."""
    enabled = acknowledged = False
    try:
        from openamer_cli.config import load_config
        cfg = load_config() or {}
        browser = cfg.get("browser") or {}
        enabled = bool(browser.get("use_real_profile", False))
        acknowledged = bool(browser.get("real_profile_acknowledged", False))
    except Exception as exc:
        logger.debug("real-profile: config unreadable (%s)", exc)
    return enabled, acknowledged


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _platform_system() -> str:
    """``"Windows" | "Darwin" | "Linux"`` — the vocabulary the resolver expects.

    ``get_chrome_debug_candidates`` compares against ``"Windows"`` / ``"Darwin"``
    (the values ``platform.system()`` returns). ``sys.platform`` returns
    ``"win32"`` / ``"darwin"`` instead, so passing it falls through to the Linux
    branch and finds nothing on a Windows host — verified: 0 candidates for an
    installed Chrome. Normalise here rather than change the shared resolver's
    contract, which its own callers and tests already rely on.
    """
    import platform as _platform

    if sys.platform.startswith("win"):
        return "Windows"
    if sys.platform == "darwin":
        return "Darwin"
    return _platform.system() or "Linux"


def resolve_default_browser() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve the user's default browser to ``(family, binary, profile_dir)``.

    Returns ``(None, None, None)`` when nothing usable is found; the caller
    reports the reason (see :func:`real_profile_status`) instead of guessing.

    A pre-release channel (Beta/Dev/Canary) is refused rather than normalised to
    its stable sibling, because that sibling drives a different profile.
    """
    from openamer_cli.browser_connect import get_chrome_debug_candidates

    candidates = get_chrome_debug_candidates(_platform_system())

    # Family detection from the binary path: the install path IS the identity.
    def family_of(path: str) -> Optional[str]:
        low = path.lower()
        if "brave" in low:
            return "brave"
        if "msedge" in low or "edge" in low:
            return "edge"
        if "chromium" in low:
            return "chromium"
        if "chrome" in low:
            return "chrome"
        return None

    # Windows: the per-user install under LOCALAPPDATA comes first, and the
    # profile lives beside the vendor name in the same LOCALAPPDATA tree.
    home = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    profile_roots = {
        "chrome": home / "Google" / "Chrome" / "User Data",
        "chromium": home / "Chromium" / "User Data",
        "brave": home / "BraveSoftware" / "Brave-Browser" / "User Data",
        "edge": home / "Microsoft" / "Edge" / "User Data",
    }

    for candidate in candidates:
        if not candidate:
            continue
        path = str(candidate)
        if not Path(path).exists():
            continue
        low = path.lower()
        if any(channel in low for channel in ("canary", "beta", "dev-channel", "sxs")):
            continue  # pre-release channel: refuse rather than drive a different profile
        family = family_of(path)
        if family is None:
            continue
        profile = profile_roots.get(family)
        if profile is not None and profile.is_dir():
            return family, path, str(profile)

    return None, None, None


def default_profile_dir(family: str) -> Optional[str]:
    """The profile directory for a browser family, or None when absent."""
    home = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    roots = {
        "chrome": home / "Google" / "Chrome" / "User Data",
        "chromium": home / "Chromium" / "User Data",
        "brave": home / "BraveSoftware" / "Brave-Browser" / "User Data",
        "edge": home / "Microsoft" / "Edge" / "User Data",
    }
    root = roots.get(family)
    return str(root) if root is not None and root.is_dir() else None


def profile_is_locked(profile_dir: str) -> bool:
    """True when a running browser holds this profile.

    Chromium writes Singleton* files into a profile in use. That matters because
    the browser must be CLOSED before its cookies can be snapshotted coherently —
    and closing it is the user's decision, not ours.
    """
    if not profile_dir:
        return False
    for marker in _PROFILE_LOCKED_MARKERS:
        if (Path(profile_dir) / marker).exists():
            return True
    return False


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def copy_dir_for() -> str:
    return str(get_openamer_home() / "browser-real-profile")


def snapshot_profile(profile_dir: str, copy_dir: Optional[str] = None,
                     *, default_profile: str = "Default") -> str:
    """Copy the login-bearing parts of ``profile_dir`` into ``copy_dir``.

    Only the files that carry a session are copied (cookies, login data, local
    storage). Caches are skipped: they dominate the size and are regenerated.

    Refuses when the profile is locked, because snapshotting a live profile can
    capture a half-written cookie store — a copy that looks fine and is
    intermittently signed out is worse than a clear refusal.
    """
    if not profile_dir or not Path(profile_dir).is_dir():
        raise RealProfileError("the browser profile directory does not exist")
    if profile_is_locked(profile_dir):
        raise RealProfileError(
            "the browser profile is in use by a running browser. Close that browser "
            "(it quits your session and loses unsaved tabs) and retry — a copy taken "
            "while it runs can capture a half-written cookie store.")

    target = Path(copy_dir or copy_dir_for())
    target.mkdir(parents=True, exist_ok=True)
    src = Path(profile_dir)
    copied = 0

    # Root-level profile files (Local State, Preferences at the root).
    for name in ("Local State", "Preferences", "Secure Preferences"):
        candidate = src / name
        if candidate.is_file():
            shutil.copy2(candidate, target / name)
            copied += 1

    # The active profile subdirectory holds the actual login state.
    sub = src / default_profile
    if not sub.is_dir():
        # Some installs keep the profile flat at the root.
        sub = src
    dest_sub = target / default_profile
    dest_sub.mkdir(parents=True, exist_ok=True)

    for name in _PROFILE_FILES:
        candidate = sub / name
        if candidate.is_file():
            shutil.copy2(candidate, dest_sub / name)
            copied += 1
    for name in _PROFILE_DIRS:
        candidate = sub / name
        if candidate.is_dir():
            shutil.copytree(candidate, dest_sub / name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(*_PROFILE_SKIP))
            copied += 1

    if copied == 0:
        raise RealProfileError(
            "no login state was found in that profile directory — is it the right one?")
    return str(target)


def launch_args(binary: str, copy_dir: str, *, headed: bool = False) -> List[str]:
    """The argv for launching the real browser on the COPY.

    Headless by default: a window that steals focus defeats a background
    capability. ``--headless=new`` is used rather than the legacy flag because
    only the new headless shares the profile's cookie store — the old one starts
    signed out, which would make this whole feature pointless.
    """
    argv = [binary, f"--user-data-dir={copy_dir}", *REAL_PROFILE_LAUNCH_FLAGS]
    if not headed:
        argv.append("--headless=new")
    return argv


def real_profile_status(*, verify_browser: bool = True) -> RealProfileStatus:
    """Whether real-profile browsing may run, and why not when it may not.

    ``verify_browser=False`` skips the binary/profile resolution — used by status
    commands that only want to report the flags.
    """
    enabled, acknowledged = read_flags()
    status = RealProfileStatus(enabled=enabled, acknowledged=acknowledged)

    if not enabled and not acknowledged:
        status.reason = (f"off by default. Enable {CONFIG_FLAG_ENABLED} to let the agent "
                         f"browse with your logged-in cookies (it copies your profile and "
                         f"launches the real browser on the copy; your own browser and "
                         f"profile are never modified). It also needs "
                         f"{CONFIG_FLAG_ACK} set to true.")
        return status
    if not enabled:
        status.reason = f"{CONFIG_FLAG_ACK} is set but {CONFIG_FLAG_ENABLED} is off."
        return status
    if not acknowledged:
        status.reason = (f"{CONFIG_FLAG_ENABLED} is on but {CONFIG_FLAG_ACK} is not set. "
                         "Both are required: one flag that enables and acknowledges at once "
                         "would let a single accidental edit hand over your cookies.")
        return status
    if not verify_browser:
        return status

    family, binary, profile = resolve_default_browser()
    status.browser, status.binary, status.profile_dir = family, binary, profile
    status.copy_dir = copy_dir_for()
    if binary is None or profile is None:
        status.reason = ("your default browser is not a supported Chromium browser "
                         "(Chrome, Edge, Brave, Chromium), or its profile directory was "
                         "not found. Real-profile browsing needs one of those; there is no "
                         "fallback, because a different browser means a different account.")
        return status
    return status
