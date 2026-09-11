#!/usr/bin/env python3
"""Tests for buffer_store.py — the single source of truth for buffer writes.

Run:  python test_buffer_store.py

Regression guard for the bug fixed 11.09: the 300-example cap lived only in
online_learning's replay branch, so any cycle with fresh data grew the buffer
without bound (training on unbounded duplicates degrades loss). These tests
prove the cap is enforced on EVERY append. All work on a TEMP buffer — the
real online_buffer.jsonl is never touched.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buffer_store as bs


def _tmp_buf():
    d = tempfile.mkdtemp(prefix="bufstore_test_")
    return os.path.join(d, "buf.jsonl")


def test_append_creates_and_counts():
    buf = _tmp_buf()
    assert bs.count(buf) == 0
    n = bs.append("q1", "a1", buffer=buf)
    assert n == 1, n
    assert bs.count(buf) == 1
    rec = json.loads(open(buf, encoding="utf-8").readline())
    assert rec["u"] == "q1" and rec["a"] == "a1"


def test_cap_enforced_on_every_append():
    """The core regression: 311 writes must leave exactly 300 lines."""
    buf = _tmp_buf()
    for i in range(311):
        bs.append(f"q{i}", f"a{i}", buffer=buf)
    assert bs.count(buf) == 300, bs.count(buf)
    lines = open(buf, encoding="utf-8").readlines()
    # FIFO: oldest evicted, newest kept
    assert json.loads(lines[0])["u"] == "q11"
    assert json.loads(lines[-1])["u"] == "q310"


def test_custom_cap_honoured():
    buf = _tmp_buf()
    for i in range(12):
        bs.append(f"q{i}", f"a{i}", buffer=buf, max_buf=5)
    assert bs.count(buf) == 5
    assert json.loads(open(buf, encoding="utf-8").readline())["u"] == "q7"


def test_enforce_cap_is_idempotent():
    buf = _tmp_buf()
    for i in range(305):
        bs.append(f"q{i}", f"a{i}", buffer=buf)
    assert bs.enforce_cap(buf) == 300
    assert bs.enforce_cap(buf) == 300  # second call is a no-op


def test_enforce_cap_missing_file_is_safe():
    """A trim on a nonexistent buffer must not raise into the caller."""
    assert bs.enforce_cap(_tmp_buf()) == 0


def test_truncation_limits():
    buf = _tmp_buf()
    bs.append("u" * 5000, "a" * 5000, buffer=buf)
    rec = json.loads(open(buf, encoding="utf-8").readline())
    assert len(rec["u"]) == 3000
    assert len(rec["a"]) == 4000


def test_none_values_are_tolerated():
    buf = _tmp_buf()
    bs.append(None, None, buffer=buf)
    rec = json.loads(open(buf, encoding="utf-8").readline())
    assert rec["u"] == "" and rec["a"] == ""


# --- junk gate (regression: 112 of 300 live buffer entries on 11.09.26 were
# reasoning-trace leaks, degenerate "Self Self Self" repetition, or raw
# tool-call JSON — all three would be trained on) ---

def test_junk_classifier_catches_the_three_observed_classes():
    # 1. reasoning-trace leak
    assert bs.is_junk("Self-critique: Here's a thinking process:\n\n1. **Analyze "
                      "User Input:**\n   - User asks a question")
    # 2. degenerate repetition
    assert bs.is_junk("Self\n\nSelf\n\nSelf\n\nSelf\n\nSelf\n\nSelf\n\nSelf")
    # 3. raw tool-call JSON instead of an answer
    assert bs.is_junk('{"tool": "web_search", "params": {"query": "x"}}')


def test_real_answers_are_not_junk():
    for good in (
        "LoRA adapters inject trainable low-rank matrices into each layer.",
        "Sleep consolidation replays the day's episodes and promotes the "
        "high-usefulness ones into permanent memory.",
        "Prompt injection is blocked by a deterministic pre-execution gate "
        "that never calls a model.",
    ):
        assert not bs.is_junk(good), good


def test_append_refuses_junk_and_logs_it():
    """A junk write must not change the buffer, but must be auditable."""
    buf = _tmp_buf()
    junk_log = buf + ".junk.jsonl"
    orig = bs.JUNK_LOG
    bs.JUNK_LOG = junk_log
    try:
        bs.append("q", "a good answer with real content", buffer=buf)
        assert bs.count(buf) == 1
        n = bs.append("q", "Self\n\nSelf\n\nSelf\n\nSelf\n\nSelf\n\nSelf", buffer=buf)
        assert n == 1, "junk must not be appended"
        assert bs.count(buf) == 1
        assert json.loads(open(junk_log, encoding="utf-8").readline())["reason"] == "junk"
    finally:
        bs.JUNK_LOG = orig


def test_empty_completion_still_appends():
    """The historical contract tolerates placeholders; only junk is refused."""
    buf = _tmp_buf()
    assert bs.append("q", "", buffer=buf) == 1


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  [PASS] {name}")
            except Exception as e:
                fails += 1
                print(f"  [FAIL] {name}: {e}")
    print(f"\n{'FAILED' if fails else 'OK'}: {fails} failure(s)")
    sys.exit(1 if fails else 0)
