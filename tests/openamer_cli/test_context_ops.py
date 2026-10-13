"""Tests for deterministic context/tool-result helpers (context_ops.py)."""

from __future__ import annotations

import openamer_cli.context_ops as co


def test_estimate_tokens_empty_is_zero():
    assert co.estimate_tokens("") == 0


def test_estimate_tokens_is_deterministic():
    assert co.estimate_tokens("hello world") == co.estimate_tokens("hello world")


def test_estimate_tokens_scales_with_length():
    assert co.estimate_tokens("x" * 4000) >= co.estimate_tokens("x" * 4)


def test_prune_keeps_small_input_unchanged():
    s = "short output"
    assert co.prune_tool_result(s, budget_tokens=100) == s


def test_prune_tail_keeps_end_signal():
    big = "START\n" + "A" * 2000 + "\nSTATUS: exit 0\n"
    out = co.prune_tool_result(big, budget_tokens=20)
    assert co.estimate_tokens(out) <= 20
    assert "exit 0" in out  # tail signal preserved
    assert "truncated" in out


def test_prune_head_keeps_start():
    big = "HEADER LINE\n" + "B" * 2000 + "\nfooter"
    out = co.prune_tool_result(big, budget_tokens=20, prefer="head")
    assert co.estimate_tokens(out) <= 20
    assert "HEADER LINE" in out
    assert "footer" not in out


def test_prune_head_tail_keeps_both_ends():
    big = "AAA" + "C" * 2000 + "ZZZ"
    out = co.prune_tool_result(big, budget_tokens=40, prefer="head+tail")
    assert co.estimate_tokens(out) <= 40
    assert out.startswith("AAA")
    assert out.endswith("ZZZ")
    assert "truncated" in out


def test_prune_respects_max_chars():
    big = "D" * 5000
    out = co.prune_tool_result(big, budget_tokens=1000, max_chars=200)
    assert len(out) <= 200 + 40  # marker overhead


def test_compact_messages_within_budget_unchanged():
    msgs = [{"role": "user", "content": "hi"}]
    assert co.compact_messages(msgs, budget_tokens=1000) == msgs


def test_compact_messages_prunes_oversize_tool():
    msgs = [{"role": "tool", "content": "E" * 4000}]
    out = co.compact_messages(msgs, budget_tokens=100)
    total = sum(co.estimate_tokens(m["content"]) for m in out)
    assert total <= 100
    assert "truncated" in out[0]["content"]


def test_compact_messages_does_not_mutate_input():
    msgs = [{"role": "tool", "content": "F" * 4000, "extra": 1}]
    orig = [dict(m) for m in msgs]
    co.compact_messages(msgs, budget_tokens=100)
    assert msgs == orig  # untouched


def test_compact_messages_preserves_newest_user():
    msgs = [
        {"role": "assistant", "content": "A" * 500},
        {"role": "user", "content": "G" * 500},
    ]
    out = co.compact_messages(msgs, budget_tokens=50)
    # Newest user content survives (not replaced by placeholder).
    assert out[-1]["content"].startswith("G")
    # At least one older message was collapsed.
    collapsed = [m for m in out if "compacted" in (m.get("content") or "")]
    assert collapsed


def test_compact_preserves_extra_keys():
    msgs = [{"role": "tool", "content": "H" * 4000, "tool_name": "ls"}]
    out = co.compact_messages(msgs, budget_tokens=50)
    assert out[0]["tool_name"] == "ls"  # unknown key preserved


def test_compact_empty_and_nonstr_handled():
    assert co.compact_messages([], budget_tokens=100) == []
    msgs = [{"role": "tool", "content": None}]
    out = co.compact_messages(msgs, budget_tokens=100)
    assert out == msgs  # non-str content left as-is, no crash
