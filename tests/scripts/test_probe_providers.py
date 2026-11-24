"""Tests for scripts/bench/probe_providers.py.

Regression for a measured false finding (2026-11-24): the probe wrote a report
claiming 96 of 100 providers were ``DEAD_DNS``. Twelve hours later 56 of the 93
distinct hosts resolved from the same machine, and almost all of the remaining
rows simply had no API key configured. The report told the operator "these
providers do not exist" when the truth was "you have no keys" plus a resolver
outage.

Two defects are pinned here:

1. ``NO_KEY`` was unreachable -- ``not dns`` was checked first, so every
   key-less provider was classified as a DNS failure.
2. A *global* resolver outage was reported as N individual provider deaths. The
   ``resolver_canary`` exists to distinguish "provider gone" from "my instrument
   is broken", and ``RESOLVER_DOWN`` is the verdict when the instrument fails.

A lying measurement instrument is worse than no instrument, because it is
believed and every downstream decision inherits it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE = REPO_ROOT / "scripts" / "bench" / "probe_providers.py"


@pytest.fixture(scope="module")
def probe():
    """Load probe_providers.py as a module (scripts/ is not an importable package)."""
    pytest.importorskip("yaml")
    spec = importlib.util.spec_from_file_location("probe_providers", PROBE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _spec(base_url: str = "https://api.example.com/v1") -> dict:
    return {"name": "Example", "base_url": base_url}


# --- defect 1: NO_KEY must not be reported as DEAD_DNS -----------------------


def test_missing_key_is_not_reported_as_dead_dns(probe):
    """An unset API key is not evidence that the provider's host vanished."""
    verdict = probe.verdict_for(
        _spec(), key_src="env-missing:EXAMPLE_API_KEY", dns=False, probe={"http": None}
    )
    assert verdict == "NO_KEY"


def test_absent_key_source_is_not_reported_as_dead_dns(probe):
    verdict = probe.verdict_for(_spec(), key_src="none", dns=False, probe={"http": None})
    assert verdict == "NO_KEY"


def test_keyless_provider_with_dead_host_is_dead_dns(probe):
    """A keyless provider needs no key, so a missing host IS the blocker."""
    verdict = probe.verdict_for(
        _spec(), key_src="none", dns=False, probe={"http": None}, keyless=True
    )
    assert verdict == "DEAD_DNS"


# --- defect 2: a broken instrument must not blame the subjects --------------


def test_resolver_outage_is_not_reported_as_provider_death(probe):
    """96 provider deaths were really one resolver outage."""
    verdict = probe.verdict_for(
        _spec(),
        key_src="env:EXAMPLE_API_KEY",
        dns=False,
        probe={"http": None},
        keyless=False,
        resolver_ok=False,
    )
    assert verdict == "RESOLVER_DOWN"
    assert verdict != "DEAD_DNS"


def test_dead_host_with_healthy_resolver_is_dead_dns(probe):
    verdict = probe.verdict_for(
        _spec(),
        key_src="env:EXAMPLE_API_KEY",
        dns=False,
        probe={"http": None},
        keyless=False,
        resolver_ok=True,
    )
    assert verdict == "DEAD_DNS"


# --- behaviour that must not regress ---------------------------------------


def test_live_remote_provider(probe):
    verdict = probe.verdict_for(
        _spec(), key_src="env:K", dns=True, probe={"http": 200}, resolver_ok=True
    )
    assert verdict == "LIVE"


def test_unauthorized_is_distinct_from_no_key(probe):
    """A rejected key and a missing key need different operator actions."""
    assert (
        probe.verdict_for(_spec(), key_src="env:K", dns=True, probe={"http": 401})
        == "UNAUTHORIZED"
    )


def test_local_host_is_never_classified_as_dns_failure(probe):
    """Local endpoints have no DNS and must not be judged by it."""
    spec = _spec("http://127.0.0.1:8099/v1")
    assert (
        probe.verdict_for(spec, key_src="none", dns=False, probe={"http": 200})
        == "LIVE_LOCAL"
    )
    assert (
        probe.verdict_for(spec, key_src="none", dns=False, probe={"http": None})
        == "LOCAL_DOWN"
    )


# --- the canary itself ------------------------------------------------------


def test_resolver_canary_reports_ok_when_all_hosts_resolve(probe, monkeypatch):
    monkeypatch.setattr(probe, "dns_ok", lambda host: True)
    canary = probe.resolver_canary()
    assert canary["ok"] is True
    assert set(canary["resolved"]) == set(probe.CANARY_HOSTS)


def test_resolver_canary_reports_not_ok_when_nothing_resolves(probe, monkeypatch):
    """This is the state the 2026-11-24 report was written in."""
    monkeypatch.setattr(probe, "dns_ok", lambda host: False)
    canary = probe.resolver_canary()
    assert canary["ok"] is False
    assert canary["resolved"] == []


def test_resolver_canary_requires_all_canaries(probe, monkeypatch):
    """One resolving host is not enough: a partial resolver is still untrustworthy."""
    monkeypatch.setattr(probe, "dns_ok", lambda host: host == probe.CANARY_HOSTS[0])
    canary = probe.resolver_canary()
    assert canary["ok"] is False
    assert canary["resolved"] == [probe.CANARY_HOSTS[0]]
