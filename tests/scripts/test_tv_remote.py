"""Hermetic tests for ``scripts/tv_remote.py`` (Philips JointSpace remote).

No network, no TV. The transport function ``_request`` is replaced by a fake
device that models the behaviour measured on a 58PUS6203/12:

* ``POST /6/audio/volume {"volume": N}`` answers 200 and **does not** change
  the level -- that is why ``cmd_volume`` must not use it.
* Keys do change the level, but only when the device decides to apply them;
  an unapplied key still answers 200. Hence ``cmd_volume`` has to read the
  value back and report ``MISMATCH`` instead of trusting the status code.

``time.sleep`` is patched out so the polling loop costs nothing.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "openamer_cli" / "tv.py"


def _load():
    spec = importlib.util.spec_from_file_location("tv_remote_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def tv(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "_STATE", tmp_path / "tv.json")
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr(mod, "resolve_host", lambda host=None: "10.0.0.9")
    return mod


class FakeDevice:
    """Minimal JointSpace stand-in. ``keys_work=False`` models a dropped press."""

    def __init__(self, level: int = 10, keys_work: bool = True):
        self.level = level
        self.keys_work = keys_work
        self.calls: list[tuple[str, dict | None]] = []
        self.status_override: dict[str, int] = {}
        self.screenstate = "On"
        self.screen_writes_land = True

    def __call__(self, host, path, payload=None, timeout=6.0):
        self.calls.append((path, payload))
        if path in self.status_override:
            return self.status_override[path], "override"
        if path == "/6/audio/volume" and payload is None:
            return 200, {"current": self.level, "min": 0, "max": 60, "muted": False}
        if path == "/6/audio/volume":
            return 200, "Ok"  # acknowledged and ignored, exactly like the TV
        if path == "/6/input/key":
            if self.keys_work:
                self.level += {"VolumeUp": 1, "VolumeDown": -1}.get(payload["key"], 0)
            return 200, "Ok"
        if path == "/6/screenstate":
            if payload is None:
                return 200, {"screenstate": self.screenstate}
            # models the real device: acknowledges, may or may not apply
            if self.screen_writes_land:
                self.screenstate = payload["screenstate"]
            return 200, "Ok"
        if path == "/6/system/softwareversion":
            return 200, {"softwareversion": "mt5886:TPM186E_018.005.058.001"}
        return 200, "Ok"


def test_volume_never_uses_the_ignored_json_write(tv, capsys):
    dev = FakeDevice(level=10)
    tv._request = dev
    assert tv.main(["volume", "13"]) == 0
    out = capsys.readouterr().out
    assert "volume 10 -> 13" in out and "OK" in out
    writes = [p for p, body in dev.calls if p == "/6/audio/volume" and body is not None]
    assert writes == [], "cmd_volume must not rely on the write the TV ignores"


def test_volume_reports_mismatch_when_the_key_is_dropped(tv, capsys):
    dev = FakeDevice(level=10, keys_work=False)
    tv._request = dev
    assert tv.main(["volume", "12"]) == 1
    out = capsys.readouterr().out
    assert "MISMATCH" in out and "10 -> 10" in out


def test_volume_clamps_to_device_range(tv):
    dev = FakeDevice(level=58)
    tv._request = dev
    assert tv.main(["volume", "99"]) == 0
    assert dev.level == 60, "target above max must clamp to max, not overshoot"


def test_volume_read_does_not_send_keys(tv):
    dev = FakeDevice(level=42)
    tv._request = dev
    assert tv.main(["volume"]) == 0
    assert [p for p, _ in dev.calls] == ["/6/audio/volume"]


def test_key_alias_and_raw_name_both_reach_the_api(tv):
    dev = FakeDevice()
    tv._request = dev
    tv.main(["key", "volup"])
    tv.main(["key", "Home"])
    assert [body["key"] for path, body in dev.calls if path == "/6/input/key"] == [
        "VolumeUp",
        "Home",
    ]


def test_power_maps_state_to_philips_key_name(tv):
    dev = FakeDevice()
    tv._request = dev
    tv.main(["power", "off"])
    assert dev.calls[-1] == ("/6/input/key", {"key": "Standby"})


def test_unreachable_device_fails_loudly(tv, capsys):
    tv._request = lambda *a, **k: (0, "unreachable: timed out")
    assert tv.main(["info"]) == 1
    assert "unreachable" in capsys.readouterr().out


def test_cached_host_is_used_without_rediscovery(monkeypatch, tmp_path):
    # Fresh module: the ``tv`` fixture stubs resolve_host for the cmd_* tests.
    mod = _load()
    cache = tmp_path / "tv.json"
    cache.write_text('[{"host": "10.0.0.9"}]', encoding="utf-8")
    monkeypatch.setattr(mod, "_STATE", cache)
    monkeypatch.setattr(mod, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(mod, "discover", lambda *a, **k: pytest.fail("must not rescan"))
    assert mod.resolve_host() == "10.0.0.9"


def test_stale_cache_falls_back_to_discovery(monkeypatch, tmp_path):
    mod = _load()
    cache = tmp_path / "tv.json"
    cache.write_text('[{"host": "10.0.0.9"}]', encoding="utf-8")
    monkeypatch.setattr(mod, "_STATE", cache)
    monkeypatch.setattr(mod, "_port_open", lambda *a, **k: False)
    monkeypatch.setattr(mod, "discover", lambda *a, **k: [{"host": "10.0.0.77"}])
    assert mod.resolve_host() == "10.0.0.77"


def test_open_posts_to_the_activity_route_not_launch(tv, capsys):
    """Measured: /6/activities/launch answers 405; only /6/activities/<name> works."""
    dev = FakeDevice()
    tv._request = dev
    assert tv.main(["open", "https://example.com"]) == 0
    path, body = dev.calls[-1]
    assert path == "/6/activities/browser"
    assert body == {"url": "https://example.com"}


def test_open_uses_the_flat_url_body_that_actually_navigates(tv, capsys):
    """Measured on 58PUS6203/12: the Intent body answers 200 and does nothing.

    Only ``{"url": ...}`` moves the browser, so it must be the first (and on a
    working TV the only) call. The Intent form is a fallback, not the default.
    """
    dev = FakeDevice()
    tv._request = dev
    assert tv.main(["open", "https://example.com"]) == 0
    bodies = [body for path, body in dev.calls if path == "/6/activities/browser"]
    assert bodies == [{"url": "https://example.com"}], \
        "the Intent form returns 200 without navigating and must not be sent first"


def test_open_falls_back_to_the_intent_body_when_url_is_rejected(tv, capsys):
    """Firmware that rejects the flat body gets the documented Intent form."""
    real = FakeDevice()

    def request(host, path, payload=None, timeout=6.0):
        if path == "/6/activities/browser" and payload is not None and "url" in payload:
            real.calls.append((path, payload))
            return 405, "Method not allowed"
        return real(host, path, payload, timeout)

    tv._request = request
    # the fallback succeeds, so the command reports success - but only after
    # the flat body was tried and rejected
    assert tv.main(["open", "https://example.com"]) == 0
    bodies = [body for path, body in real.calls if path == "/6/activities/browser"]
    assert bodies[0] == {"url": "https://example.com"}
    assert bodies[-1]["intent"]["uri"] == "https://example.com"


def test_activity_reports_405_as_failure(tv, capsys):
    """The TV answers 405 for any activity it does not advertise."""
    dev = FakeDevice()
    dev.status_override = {"/6/activities/tv": 405}
    tv._request = dev
    assert tv.main(["activity", "tv"]) == 1
    assert "405" in capsys.readouterr().out


def test_info_reports_the_installed_firmware(tv, capsys):
    """The TV answers /6/system/softwareversion; info must surface it."""
    dev = FakeDevice()
    tv._request = dev
    # /6/system must answer a dict, otherwise cmd_info bails out early
    base = dev.__call__

    def with_system(host, path, payload=None, timeout=6.0):
        if path == "/6/system":
            return 200, {"name": "58PUS6203/12", "nettvversion": "4.6.0.1",
                         "featuring": {"systemfeatures": {"pairing_type": "none"}}}
        return base(host, path, payload, timeout)

    tv._request = with_system
    assert tv.main(["info"]) == 0
    out = capsys.readouterr().out
    assert "firmware  mt5886:TPM186E_018.005.058.001" in out


def test_app_reports_started_vs_not_installed(tv, capsys, monkeypatch):
    """DIAL answers 201 for installed apps and 404 for everything else."""
    monkeypatch.setattr(tv, "_dial_launch",
                        lambda h, a: (201, 56789) if a == "YouTube" else (404, None))
    assert tv.main(["app", "YouTube"]) == 0
    assert "gestartet" in capsys.readouterr().out
    assert tv.main(["app", "Spotify"]) == 1
    assert "nicht installiert" in capsys.readouterr().out


def test_apps_lists_only_the_installed_ones(tv, capsys, monkeypatch):
    installed = {"Netflix", "YouTube"}
    monkeypatch.setattr(tv, "_dial_launch",
                        lambda h, a: (201, 56789) if a in installed else (404, None))
    assert tv.main(["apps"]) == 0
    out = capsys.readouterr().out
    assert "Netflix" in out and "YouTube" in out
    assert "Spotify" not in out


def test_browse_wraps_the_target_in_the_browser_app(tv):
    """'browse <host>' must hand the URL to the shell as an encoded ?u= value."""
    dev = FakeDevice()
    tv._request = dev
    assert tv.main(["browse", "github.com"]) == 0
    path, body = dev.calls[-1]
    assert path == "/6/activities/browser"
    uri = body["url"]
    assert uri.startswith(tv.BROWSER_APP + "?u=")
    assert "https%3A%2F%2Fgithub.com" in uri, uri


def test_browse_without_url_opens_the_shell_only(tv):
    dev = FakeDevice()
    tv._request = dev
    assert tv.main(["browse"]) == 0
    assert dev.calls[-1][1]["url"] == tv.BROWSER_APP


def test_browse_keeps_an_explicit_scheme(tv):
    dev = FakeDevice()
    tv._request = dev
    tv.main(["browse", "http://example.com/x"])
    uri = dev.calls[-1][1]["url"]
    assert "http%3A%2F%2Fexample.com%2Fx" in uri, uri


def test_parser_exposes_every_documented_subcommand(tv):
    for name in ("discover", "info", "key", "volume", "mute", "open", "browse",
                 "activity", "app", "apps", "power", "screen", "context"):
        assert name in tv.build_parser()._subparsers._group_actions[0].choices


def test_screen_status_reads_the_panel_state(tv, capsys):
    dev = FakeDevice()
    dev.screenstate = "Off"
    tv._request = dev
    assert tv.main(["screen"]) == 0
    assert '"screenstate": "Off"' in capsys.readouterr().out


def test_screen_off_writes_and_verifies(tv, capsys):
    dev = FakeDevice()
    tv._request = dev
    assert tv.main(["screen", "off"]) == 0
    out = capsys.readouterr().out
    assert "screenstate=Off" in out and "OK" in out
    assert dev.screenstate == "Off"


def test_screen_reports_mismatch_when_the_write_is_ignored(tv, capsys):
    """A 200 is not proof: this API acknowledges writes it never applies."""
    dev = FakeDevice()
    dev.screen_writes_land = False
    tv._request = dev
    assert tv.main(["screen", "off"]) == 1
    out = capsys.readouterr().out
    assert "MISMATCH" in out and "screenstate=On" in out


def test_context_flags_the_missing_screen_readback(tv, capsys):
    """Measured: every field is NA on this model, so it is not a UI readback."""
    dev = FakeDevice()

    def request(host, path, payload=None, timeout=6.0):
        if path == "/6/context":
            return 200, {"level1": "NA", "level2": "NA", "level3": "NA",
                         "data": "NA", "Recording": "Off"}
        return dev(host, path, payload, timeout)

    tv._request = request
    assert tv.main(["context"]) == 0
    assert "does not report the screen" in capsys.readouterr().out


def test_script_is_a_shim_over_the_shared_command_surface(tv):
    """``openamer tv`` attaches the same sub-actions to a plain ``tv`` parser.

    This is what ``openamer_cli/subcommands/tv.py`` does, so the test pins the
    wiring without importing the (heavy) ``openamer_cli`` package.
    """
    import argparse

    root = argparse.ArgumentParser()
    subs = root.add_subparsers(dest="command")
    tv_parser = subs.add_parser("tv")
    tv_parser.add_argument("--host", default=None)
    tv.add_tv_subcommands(tv_parser)

    args = root.parse_args(["tv", "info"])
    assert args.command == "tv" and args.cmd == "info"
    assert callable(args.func)

    args = root.parse_args(["tv", "--host", "10.0.0.5", "key", "home"])
    assert args.host == "10.0.0.5" and args.key == "home"
