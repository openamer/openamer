"""Tests for persistent user-message feedback (message_feedback.py)."""

from __future__ import annotations

from openamer_cli import message_feedback as mf


def test_record_returns_dict_with_signal_and_persisted():
    r = mf.record_feedback(signal="helpful", assistant_text="nice", log_path="/nonexistent/dir/x.jsonl")
    assert r["signal"] == "helpful"
    assert r["_persisted"] is False  # unwritable -> graceful degrade


def test_record_never_raises_on_bad_path(tmp_path):
    # log_path pointing at a directory, not a file, must not raise.
    r = mf.record_feedback(signal="x", log_path=tmp_path)
    assert r["_persisted"] is False


def test_round_trip(tmp_path):
    lp = tmp_path / "fb.jsonl"
    mf.record_feedback(signal="helpful", assistant_text="a", session_id="s1", log_path=lp)
    mf.record_feedback(signal="not_helpful", assistant_text="b", session_id="s2", log_path=lp)
    rows = mf.load_feedback(lp)
    assert len(rows) == 2
    # newest first
    assert rows[0]["session_id"] == "s2"
    assert rows[1]["session_id"] == "s1"


def test_load_empty_and_missing(tmp_path):
    assert mf.load_feedback(tmp_path / "nope.jsonl") == []


def test_load_skips_malformed_lines(tmp_path):
    lp = tmp_path / "fb.jsonl"
    lp.write_text("{not json}\n", encoding="utf-8")
    mf.record_feedback(signal="ok", assistant_text="t", log_path=lp)
    rows = mf.load_feedback(lp)
    assert len(rows) == 1
    assert rows[0]["signal"] == "ok"


def test_load_limit(tmp_path):
    lp = tmp_path / "fb.jsonl"
    for i in range(5):
        mf.record_feedback(signal=f"s{i}", assistant_text=str(i), log_path=lp)
    rows = mf.load_feedback(lp, limit=2)
    assert len(rows) == 2
    assert rows[0]["signal"] == "s4"


def test_assistant_text_capped(tmp_path):
    lp = tmp_path / "fb.jsonl"
    r = mf.record_feedback(signal="x", assistant_text="z" * 5000, log_path=lp)
    assert len(r["assistant_text"]) <= 2000


def test_summarize_counts_and_latest(tmp_path):
    lp = tmp_path / "fb.jsonl"
    mf.record_feedback(signal="not_helpful", assistant_text="old bad", log_path=lp)
    mf.record_feedback(signal="helpful", assistant_text="good one", log_path=lp)
    mf.record_feedback(signal="not_helpful", assistant_text="newer bad", log_path=lp)
    rows = mf.load_feedback(lp)
    s = mf.summarize_feedback(rows)
    assert s["counts"] == {"not_helpful": 2, "helpful": 1}
    # latest helpful is the "good one" (only one); latest not-helpful is newest.
    assert s["latest_helpful"] == "good one"
    assert s["latest_not_helpful"] == "newer bad"


def test_summarize_empty():
    assert mf.summarize_feedback([])["counts"] == {}
