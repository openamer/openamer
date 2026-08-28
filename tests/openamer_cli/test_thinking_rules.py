"""Tests for scripts/thinking_rules.py (persistent reasoning-rule store).

Hermetic: the store is redirected to a temp dir via a monkeypatched
``rules_path`` (or a module-import override), so no real home is touched.
Pure-function, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import thinking_rules as tr  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point thinking_rules at a temp JSON file, isolated per test."""
    target = tmp_path / "thinking_rules.json"
    monkeypatch.setattr(tr, "rules_path", lambda: target)
    return target


def test_add_dedupes_and_adds(store):
    assert tr.add("Rule A", trigger="when x", proof="seen y") == 0
    assert tr.add("Rule A", trigger="when x", proof="seen y") == 1  # dup
    assert tr.add("Rule B") == 0  # rule without proof is allowed
    rules = tr._load()
    assert len(rules) == 2
    # the rule that had proof keeps it; avoiding another assertion on the
    # proof-less one (a rule may legitimately lack proof).
    a = next(r for r in rules if r["rule"] == "Rule A")
    assert a.get("proof") == "seen y"


def test_bump_increments_and_persists(store):
    tr.add("r", proof="p")
    rid = tr._load()[0]["id"]
    tr.bump(rid)
    tr.bump(rid)
    assert tr._load()[0]["hits"] == 2
    # unknown id is non-fatal
    tr.bump("nope")


def test_purge(store):
    tr.add("a"); tr.add("b")
    a = tr._load()[0]["id"]
    tr._save([r for r in tr._load() if r["id"] != a])
    assert [r["rule"] for r in tr._load()] == ["b"]


def test_context_orders_by_hits(store):
    tr.add("lo")
    tr.add("hi", proof="p")
    high = max(tr._load(), key=lambda r: r["hits"])  # both 0; sort stable
    # bump "hi" so it sorts first
    hi = next(r for r in tr._load() if r["rule"] == "hi")
    tr.bump(hi["id"])
    ctx = tr.context()
    assert ctx.startswith("THINKING RULES")
    assert ctx.index("hi") < ctx.index("lo")
    assert "hi" in ctx and "lo" in ctx


def test_context_empty(store):
    assert "(no thinking rules yet" in tr.context()


def test_file_is_valid_json_and_utf8(store):
    tr.add("ünïcode — Regel")  # ensure_ascii=False round-trips
    raw = store.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data[0]["rule"] == "ünïcode — Regel"