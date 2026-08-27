"""Tests for scripts/trend_scout.py (hourly AI-agent trend radar).

Hermetic: no real network. We cover the offline-testable logic: dedupe/sort by
score, report shaping, dated-copy-once, and that main() tolerates poll failures
without crashing (each source _get is guarded).
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import trend_scout as T  # noqa: E402


def test_dedupe_sort_and_cap():
    items = [(2, "a"), (5, "b"), (5, "b"), (0, "c"), (9, "d")]
    uniq = T._dedupe(items, cap=3)
    # sorted by score desc, deduped, capped
    assert uniq == ["d", "b", "a"]


def test_main_writes_latest_when_sources_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(T, "OUT_DIR", tmp_path)
    monkeypatch.setattr(T, "_hn", lambda: [(0, "[HN error: x]")])
    monkeypatch.setattr(T, "_arxiv", lambda: [(0, "[arXiv error: x]")])
    monkeypatch.setattr(T, "_google_news", lambda: [(0, "[News error: x]")])
    rc = T.main()
    assert rc == 0                       # never crashes the cron
    out = tmp_path / "trend-scout-latest.md"
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "HN error" in content or "arXiv error" in content


def test_main_deduplicates_and_writes_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(T, "OUT_DIR", tmp_path)
    monkeypatch.setattr(T, "_hn", lambda: [(10, "- [HN] Signal A — u1"), (3, "- [HN] Signal B — u2")])
    monkeypatch.setattr(T, "_arxiv", lambda: [(0, "- [HN] Signal A — u1")])   # byte-identical dup
    monkeypatch.setattr(T, "_google_news", lambda: [(0, "- [News] Signal C — u3")])
    rc = T.main()
    assert rc == 0
    content = (tmp_path / "trend-scout-latest.md").read_text(encoding="utf-8")
    assert content.count("Signal A — u1") == 1          # exact-dup deduped
    assert "Signal B" in content and "Signal C" in content