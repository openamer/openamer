"""Tests for openamer_cli/a2a/ard.py (Agentic Resource Discovery entry).

Hermeisch: no network. We verify the ARD entry shape against the spec
requirements the module implements: domain-anchored URN identifier, @context,
discovery signals (representativeQueries, capabilities), determinism of URN.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli.a2a import ard  # noqa: E402


def test_arn_is_domain_anchored_and_slugs():
    urn = ard.arn_for("aabb1234", publisher="openamer.github.io",
                      namespace="mesh", name="OpenAmer Agent")
    assert urn.startswith("urn:air:")
    parts = urn.split(":")
    assert parts[2] == "openamer.github.io"
    assert parts[3] == "mesh"
    # name slugged (lowercase, spaces->-)
    assert parts[4] == "openamer-agent"


def test_arn_deterministic():
    assert ard.arn_for("fp1") == ard.arn_for("fp1")


def test_build_entry_carries_discovery_signals():
    e = ard.build_entry("fp1234", capabilities=["a2a.task.ask", "agent-card"],
                        queries=["delegate a task"])
    assert e["@context"] == ard.DEFAULT_CONTEXT
    assert e["identifier"] == ard.arn_for("fp1234")
    assert e["representativeQueries"] == ["delegate a task"]
    assert "a2a.task.ask" in e["capabilities"]
    assert e["nodeFingerprint"] == "fp1234"


def test_defaults_present_and_json_roundtrip():
    e = ard.build_entry("fp")
    # spec: default capability surface + searchable queries
    assert any("ask" in c for c in e["capabilities"])
    assert len(e["representativeQueries"]) >= 2
    # JSON-LD is parseable and stable
    obj = json.loads(ard.to_json(e))
    assert obj["identifier"] == e["identifier"]


def test_write_entry_creates_discoverable_file(tmp_path):
    e = ard.build_entry("fp")
    out = tmp_path / "a2a"
    p = ard.write_entry(e, out)
    assert Path(p).exists()
    obj = json.loads(Path(p).read_text(encoding="utf-8"))
    assert obj["@type"] == "Agent"