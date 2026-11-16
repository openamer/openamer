"""Regression tests for the self-hosted health probe's degraded semantics.

Measured 2026-11-16: the 5-minute Self-Hosted Health Check failed 36 of 183
runs in bursts, because a slow ``/api/generate`` call was read as "no provider
at all" even though the Ollama server was still answering. The probe now
separates REACHABILITY (``/api/version``) from GENERATE LATENCY, and retries
liveness once before declaring an outage.

These tests pin both halves of that contract:

* reachable + slow generate  -> available, degraded  (no false outage)
* unreachable                -> unavailable          (a real outage still fails)
* one failed liveness probe  -> retried, then healthy
"""
import importlib.util
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO / "scripts" / "self-hosted.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("openamer_self_hosted", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Resp:
    """Minimal stand-in for the object urlopen() returns."""

    def __init__(self, status=200, payload=None):
        self.status = status
        self._body = json.dumps(payload or {}).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture()
def sh(monkeypatch):
    mod = _load_module()
    # Deterministic: never actually sleep or hit the network in the retry path.
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None, raising=False)
    return mod


def _fake_urlopen(monkeypatch, routes):
    """routes: list of (url_substring, behaviour) consumed in order.

    behaviour is either an exception instance (raised) or a (status, payload).
    """
    calls = []

    def _open(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        calls.append(url)
        for i, (needle, behaviour) in enumerate(routes):
            if needle in url:
                routes.pop(i)
                if isinstance(behaviour, BaseException):
                    raise behaviour
                status, payload = behaviour
                return _Resp(status, payload)
        raise AssertionError(f"unexpected request: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", _open)
    return calls


def test_slow_generate_is_degraded_not_dead(sh, monkeypatch):
    """The measured false-outage shape: generate times out, server is alive."""
    _fake_urlopen(monkeypatch, [
        ("/api/generate", TimeoutError("timed out")),
        ("/api/version", (200, {"version": "0.40.16"})),
    ])
    result = sh.check_local_health({"fallback": {"model": "test-model"}})
    assert result["available"] is True
    assert result["degraded"] is True
    assert result["provider"] == "ollama"
    assert "reachable" in result["note"]


def test_real_outage_still_reads_as_unavailable(sh, monkeypatch):
    """Both doors closed = the probe must NOT claim a provider."""
    _fake_urlopen(monkeypatch, [
        ("/api/generate", TimeoutError("timed out")),
        ("/api/version", ConnectionRefusedError("refused")),
    ])
    result = sh.check_local_health({"fallback": {"model": "test-model"}})
    assert result["available"] is False
    assert not result.get("degraded")


def test_liveness_is_retried_once(sh, monkeypatch):
    """A single hiccup must not be reported as an outage."""
    calls = _fake_urlopen(monkeypatch, [
        ("/api/version", ConnectionRefusedError("hiccup")),
        ("/api/version", (200, {"version": "0.40.16"})),
        ("/api/tags", (200, {"models": [{"name": "qwen3.5:4b-q4_K_M", "size": 3400000000}]})),
    ])
    result = sh.check_ollama()
    assert result["available"] is True
    assert result["version"] == "0.40.16"
    assert sum(1 for u in calls if u.endswith("/api/version")) == 2


def test_two_failed_liveness_probes_stay_unavailable(sh, monkeypatch):
    _fake_urlopen(monkeypatch, [
        ("/api/version", ConnectionRefusedError("down")),
        ("/api/version", ConnectionRefusedError("down")),
    ])
    result = sh.check_ollama()
    assert result["available"] is False
    assert result["error"]
