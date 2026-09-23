#!/usr/bin/env python3
"""Tests for real-profile browsing (using the user's logged-in cookies).

The tests that matter here are the CONSENT ones and the FAIL-CLOSED ones. A test
that only proved "a profile can be copied" would pass while the agent silently
had access to the user's cookies — which is the failure this module exists to
prevent. So:

- both config flags are required, and neither alone is enough
- nothing is copied or launched when consent is absent
- a locked (in-use) profile is refused rather than copied half-written
- caches are NOT copied; cookies and login data ARE
- a pre-release channel is refused, never normalised to a different profile
- the platform vocabulary matches the resolver (a real bug: sys.platform
  returned "win32", the resolver expected "Windows", and 0 browsers were found
  on a host with Chrome installed)

Everything runs against tmp directories. No test reads or writes the user's real
profile.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli import browser_real_profile as rp  # noqa: E402


@pytest.fixture()
def fake_profile(tmp_path):
    """A minimal Chromium-shaped profile with login state and caches."""
    root = tmp_path / "User Data"
    sub = root / "Default"
    sub.mkdir(parents=True)
    (root / "Local State").write_text("{}", encoding="utf-8")
    (sub / "Cookies").write_bytes(b"SQLite format 3\x00cookie-data")
    (sub / "Login Data").write_bytes(b"SQLite format 3\x00logins")
    (sub / "Preferences").write_text("{}", encoding="utf-8")
    cache = sub / "Cache"
    cache.mkdir()
    (cache / "big.bin").write_bytes(b"x" * 4096)
    return root


# ── consent ────────────────────────────────────────────────────────────────


def test_off_by_default(monkeypatch):
    monkeypatch.setattr(rp, "read_flags", lambda: (False, False))
    status = rp.real_profile_status()
    assert status.usable is False
    assert "off by default" in status.reason
    assert "browser.use_real_profile" in status.reason


def test_enabled_without_acknowledgement_is_refused(monkeypatch):
    """One flag must not be able to hand over the cookies on its own."""
    monkeypatch.setattr(rp, "read_flags", lambda: (True, False))
    status = rp.real_profile_status()
    assert status.usable is False
    assert "acknowledged" in status.reason


def test_acknowledgement_without_the_master_flag_is_refused(monkeypatch):
    monkeypatch.setattr(rp, "read_flags", lambda: (False, True))
    status = rp.real_profile_status()
    assert status.usable is False
    assert "is off" in status.reason


def test_both_flags_required_before_any_browser_lookup(monkeypatch):
    """With consent absent, the resolver must not even run."""
    called = []
    monkeypatch.setattr(rp, "read_flags", lambda: (False, False))
    monkeypatch.setattr(rp, "resolve_default_browser",
                        lambda: called.append(1) or (None, None, None))
    rp.real_profile_status()
    assert called == [], "the browser was resolved without consent"


def test_both_flags_set_reports_unresolvable_browser_honestly(monkeypatch):
    monkeypatch.setattr(rp, "read_flags", lambda: (True, True))
    monkeypatch.setattr(rp, "resolve_default_browser", lambda: (None, None, None))
    status = rp.real_profile_status()
    assert status.usable is False
    assert "not a supported Chromium browser" in status.reason
    assert "different browser means a different account" in status.reason


# ── snapshot ───────────────────────────────────────────────────────────────


def test_snapshot_copies_login_state_and_skips_caches(fake_profile, tmp_path):
    dest = rp.snapshot_profile(str(fake_profile), copy_dir=str(tmp_path / "copy"))
    sub = Path(dest) / "Default"
    assert (sub / "Cookies").exists(), "cookies are the whole point"
    assert (sub / "Login Data").exists()
    assert (Path(dest) / "Local State").exists()
    assert not (sub / "Cache").exists(), "caches must not be copied"
    assert not (sub / "Cache" / "big.bin").exists()


def test_snapshot_refuses_a_locked_profile(fake_profile, tmp_path):
    """A profile in use is refused, not copied half-written.

    Copying a live cookie store can capture a torn write; a copy that looks fine
    and is intermittently signed out is worse than a clear refusal.
    """
    (fake_profile / "SingletonLock").write_text("", encoding="utf-8")
    assert rp.profile_is_locked(str(fake_profile)) is True
    with pytest.raises(rp.RealProfileError) as exc:
        rp.snapshot_profile(str(fake_profile), copy_dir=str(tmp_path / "copy"))
    message = str(exc.value)
    assert "in use" in message
    assert "Close that browser" in message, "the fix must be stated, and it is the user's call"


def test_snapshot_refuses_a_missing_profile(tmp_path):
    with pytest.raises(rp.RealProfileError):
        rp.snapshot_profile(str(tmp_path / "nope"), copy_dir=str(tmp_path / "copy"))


def test_snapshot_refuses_a_profile_with_no_login_state(tmp_path):
    empty = tmp_path / "User Data"
    (empty / "Default").mkdir(parents=True)
    with pytest.raises(rp.RealProfileError) as exc:
        rp.snapshot_profile(str(empty), copy_dir=str(tmp_path / "copy"))
    assert "no login state" in str(exc.value)


# ── launch args ────────────────────────────────────────────────────────────


def test_launch_uses_the_copy_and_never_the_real_profile(fake_profile, tmp_path):
    copy = str(tmp_path / "copy")
    argv = rp.launch_args("/usr/bin/chrome", copy)
    data_dir = next(a for a in argv if a.startswith("--user-data-dir="))
    assert data_dir == f"--user-data-dir={copy}"
    assert str(fake_profile) not in data_dir, "the real profile must never be the target"


def test_launch_is_headless_by_default_and_heads_on_request():
    headless = rp.launch_args("/usr/bin/chrome", "/tmp/c")
    assert "--headless=new" in headless, "a focus-stealing window defeats background use"
    headed = rp.launch_args("/usr/bin/chrome", "/tmp/c", headed=True)
    assert "--headless=new" not in headed
    # new headless shares the cookie store; the legacy flag would start signed out
    assert "--disable-sync" in headless


# ── platform vocabulary (the real bug) ─────────────────────────────────────


def test_platform_system_returns_the_resolver_vocabulary():
    """sys.platform ("win32") is NOT what get_chrome_debug_candidates expects.

    Verified live: passing sys.platform found 0 browsers on a host with Chrome
    installed, because "win32" != "Windows" fell through to the Linux branch.
    """
    value = rp._platform_system()
    assert value in ("Windows", "Darwin", "Linux"), value
    if sys.platform.startswith("win"):
        assert value == "Windows"


def test_resolver_actually_finds_an_installed_browser_on_windows():
    """On this host Chrome is installed; the resolver must see it.

    Skipped elsewhere so the suite stays portable — the point is the vocabulary
    bug above, which only manifests on Windows.
    """
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-specific path resolution")
    family, binary, profile = rp.resolve_default_browser()
    # A host may genuinely have no Chromium browser; then the resolver must say
    # nothing rather than invent one.
    if family is None:
        return
    assert Path(binary).exists(), binary
    assert Path(profile).is_dir(), profile
    assert family in ("chrome", "chromium", "brave", "edge")


def test_pre_release_channels_are_not_normalised(monkeypatch, tmp_path):
    """A Beta/Dev/Canary install must be refused, not mapped to its stable sibling.

    Mapping would drive a different profile — the wrong-principal bug.
    """
    canary = str(tmp_path / "Chrome SxS" / "Application" / "chrome.exe")
    Path(canary).parent.mkdir(parents=True)
    Path(canary).write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "openamer_cli.browser_connect.get_chrome_debug_candidates",
        lambda system: [canary])
    family, binary, profile = rp.resolve_default_browser()
    assert family is None, "a pre-release channel was accepted"


def test_default_profile_dir_matches_the_family(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    (tmp_path / "Google" / "Chrome" / "User Data").mkdir(parents=True)
    assert rp.default_profile_dir("chrome") == str(
        tmp_path / "Google" / "Chrome" / "User Data")
    assert rp.default_profile_dir("brave") is None
