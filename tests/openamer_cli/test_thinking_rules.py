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
    tr.add("lo", proof="p")
    tr.add("hi", proof="p")
    # promote both (proof + bump a hit each) so they're active and loadable
    for r in tr._load():
        tr.bump(r["id"])
    tr.promote()
    hi = next(r for r in tr._load() if r["rule"] == "hi")
    for _ in range(2):
        tr.bump(hi["id"])  # hi ends with more hits than lo
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


def test_consolidate_dedupes_and_merges_hits(store):
    # `add` already dedupes, so inject duplicates directly via _save.
    tr.add("same", proof="p1")
    base = tr._load()[0]
    dup = dict(base, id="zz", hits=3, proof="p2")
    tr._save([base, dup])
    assert len(tr._load()) == 2
    removed = tr.consolidate()
    assert removed == 1
    rules = tr._load()
    assert len(rules) == 1
    assert rules[0]["hits"] == base["hits"] + 3  # merged


def test_prune_trims_to_max_by_hits(store):
    # add 5 rules, bump different counts
    for i in range(5):
        tr.add(f"rule{i}", proof=f"p{i}")
    rules = tr._load()
    # bump only rule0 and rule1 -> they should survive a prune to 2
    tr.bump(rules[0]["id"]); tr.bump(rules[1]["id"])
    removed = tr.prune(max_rules=2)
    assert removed == 3
    remaining = {r["rule"] for r in tr._load()}
    assert remaining == {"rule0", "rule1"}


def test_prune_noop_under_limit(store):
    tr.add("only")
    assert tr.prune(max_rules=5) == 0
    assert len(tr._load()) == 1


def test_dual_buffer_promotion_requires_proof_and_hit(store):
    # New rules are pending (hot buffer). Promotion needs proof AND a hit.
    tr.add("ruleX", proof="real proof")
    tr.add("ruleY")  # no proof
    x = next(r for r in tr._load() if r["rule"] == "ruleX")
    y = next(r for r in tr._load() if r["rule"] == "ruleY")
    # y gets a hit but no proof; x has proof but no hit yet.
    tr.bump(y["id"])
    assert tr.promote() == 0  # neither qualifies
    tr.bump(x["id"])  # now x has proof + hit
    assert tr.promote() == 1
    after = {r["rule"]: r.get("status") for r in tr._load()}
    assert after["ruleX"] == "active"
    assert after["ruleY"] == "pending"


def test_dual_buffer_context_excludes_pending(store):
    tr.add("activeR", proof="p")
    ar = next(r for r in tr._load() if r["rule"] == "activeR")
    tr.bump(ar["id"])
    tr.promote()  # activeR -> active
    tr.add("pendingR")  # stays pending
    ctx = tr.context()
    assert "activeR" in ctx
    assert "pendingR" not in ctx  # hot-buffer rules don't steer tasks yet