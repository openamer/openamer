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

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tv_remote.py"


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

    def __call__(self, host, path, payload=None, timeout=6.0):
        self.calls.append((path, payload))
        if path == "/6/audio/volume" and payload is None:
            return 200, {"current": self.level, "min": 0, "max": 60, "muted": False}
        if path == "/6/audio/volume":
            return 200, "Ok"  # acknowledged and ignored, exactly like the TV
        if path == "/6/input/key":
            if self.keys_work:
                self.level += {"VolumeUp": 1, "VolumeDown": -1}.get(payload["key"], 0)
            return 200, "Ok"
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


def test_parser_exposes_every_documented_subcommand(tv):
    for name in ("discover", "info", "key", "volume", "mute", "open", "app", "power"):
        assert name in tv.build_parser()._subparsers._group_actions[0].choices
