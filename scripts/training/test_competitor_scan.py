#!/usr/bin/env python3
"""Tests for competitor_scan.py pure logic (no network).

Regression guard for the 2026-09-11 bug: QUERIES was dead code — the Algolia
URL carried no `query=`, so the watchdog swept the global HN front feed and
alerted on every story >50 pts (EPA politics, OpenAI math, terminal IDEs).
These tests assert the query is really sent and the alert gate stays tight.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import competitor_scan as cs


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def _capture_urls(hits=None, min_points=None):
    """Run _fetch once, capturing every URL it builds (no network).

    Defaults to `AGENT_MIN_POINTS` because that is what `scan()` actually
    passes on the agent path — the helper must mirror production, not the
    older LOG_THRESHOLD call site.
    """
    urls = []
    real = cs.urllib.request.urlopen

    def fake_open(url, timeout=None):
        urls.append(url)
        return _FakeResponse(json.dumps({"hits": hits or []}).encode())

    if min_points is None:
        min_points = cs.AGENT_MIN_POINTS
    cs.urllib.request.urlopen = fake_open
    try:
        cs._fetch("AI agent", int(time.time()) - 7200, min_points)
    finally:
        cs.urllib.request.urlopen = real
    return urls


def test_fetch_sends_the_query_param():
    """The core bug: without query= this is a news bot, not a watchdog."""
    urls = _capture_urls()
    assert urls, "expected at least one request"
    assert all("query=" in u for u in urls), f"missing query= in {urls[0]!r}"
    assert all("query=AI%20agent" in u for u in urls), \
        f"query must be url-encoded and populated: {urls[0]!r}"


def test_fetch_keeps_points_filter_and_paging():
    url = _capture_urls()[0]
    assert "numericFilters=" in url and "points>" in url
    assert "created_at_i>" in url
    assert "hitsPerPage=30" in url


def test_agent_queries_do_not_impose_a_points_floor():
    """Regression 2026-09-12: the agent path was fetched with the *log*
    threshold, so a brand-new agent story (HN stories start at ~1 pt) was
    filtered out server-side and never logged. Agent hits must not carry a
    points floor."""
    urls = _capture_urls()
    assert urls
    assert all(f"points>{cs.AGENT_MIN_POINTS}" in u for u in urls), urls[0]
    assert cs.AGENT_MIN_POINTS == 0


def test_quiet_window_is_not_reported_as_a_failure(tmp_path):
    """Regression 2026-09-12: a genuinely quiet 2h window (both result sets
    empty) returned exit 1, so a healthy watchdog looked broken ~92% of runs.
    Requests that ANSWER with zero hits are success, not failure."""
    real_open, real_out, real_seen = cs.urllib.request.urlopen, cs.OUT, cs.SEEN
    cs.OUT = str(tmp_path / "out.jsonl")
    cs.SEEN = str(tmp_path / "seen.txt")

    def empty(url, timeout=None):
        return _FakeResponse(json.dumps({"hits": []}).encode())

    cs.urllib.request.urlopen = empty
    try:
        rc = cs.scan()
    finally:
        cs.urllib.request.urlopen = real_open
        cs.OUT, cs.SEEN = real_out, real_seen
    assert rc == 0, "a quiet window must exit 0 (watchdog), not 1"


def test_all_requests_erroring_is_still_a_failure(tmp_path):
    """The fix must not swallow real breakage: if every request errors, the
    scan is genuinely broken and has to say so with a non-zero exit."""
    real_open, real_out, real_seen = cs.urllib.request.urlopen, cs.OUT, cs.SEEN
    cs.OUT = str(tmp_path / "out.jsonl")
    cs.SEEN = str(tmp_path / "seen.txt")

    def boom(url, timeout=None):
        raise OSError("network down")

    cs.urllib.request.urlopen = boom
    try:
        rc = cs.scan()
    finally:
        cs.urllib.request.urlopen = real_open
        cs.OUT, cs.SEEN = real_out, real_seen
    assert rc == 1, "all-requests-errored must exit non-zero"


def test_fetch_collects_errors_when_asked():
    """`errors` is how scan() distinguishes quiet from broken."""
    real = cs.urllib.request.urlopen

    def boom(url, timeout=None):
        raise OSError("nope")

    cs.urllib.request.urlopen = boom
    try:
        errs = []
        assert cs._fetch("AI agent", 0, 0, errors=errs) == []
        assert len(errs) == 1 and "AI agent" in errs[0]
        # omitting the list must stay backward compatible (no crash)
        assert cs._fetch("AI agent", 0, 0) == []
    finally:
        cs.urllib.request.urlopen = real


def test_fetch_survives_a_dead_endpoint():
    """A failing request must not raise — the watchdog stays alive."""
    real = cs.urllib.request.urlopen

    def boom(url, timeout=None):
        raise OSError("network down")

    cs.urllib.request.urlopen = boom
    try:
        assert cs._fetch("AI agent", 0, 30) == []
    finally:
        cs.urllib.request.urlopen = real


def test_queries_are_all_agent_scoped():
    """Every query must target agents — a generic term turns it into a news bot."""
    assert cs.QUERIES, "QUERIES must not be empty"
    for q in cs.QUERIES:
        assert "agent" in q.lower(), f"query {q!r} is not agent-scoped"


def test_alert_threshold_is_not_lower_than_log_threshold():
    assert cs.ALERT_THRESHOLD >= cs.LOG_THRESHOLD


def test_mark_seen_is_idempotent(tmp_path):
    """Regression: overlapping 2h windows re-appended the same ids every run
    (42 lines for 36 ids). Re-marking must add nothing."""
    real = cs.SEEN
    cs.SEEN = str(tmp_path / "seen.txt")
    try:
        cs._mark_seen({"a", "b"})
        cs._mark_seen({"a", "b"})
        cs._mark_seen({"b", "c"}, seen=cs._seen_ids())
        lines = [ln.strip() for ln in open(cs.SEEN, encoding="utf-8") if ln.strip()]
    finally:
        cs.SEEN = real
    assert lines == ["a", "b", "c"], f"expected deduped ordered ids, got {lines}"


def test_seen_file_has_no_test_placeholder_ids():
    """Regression: -watch-seen.txt had 111 `testid1/testid2` lines for 36 ids.
    Assert on the module's own view of the store, not on raw shared disk state
    (other test modules and cron jobs also touch this file)."""
    seen = cs._seen_ids()
    assert not [s for s in seen if s.lower().startswith("testid")], \
        "placeholder test ids must not accumulate in the seen-file"


if __name__ == "__main__":
    import tempfile

    class _Tmp:
        def __init__(self, p):
            self._p = p

        def __truediv__(self, name):
            return os.path.join(self._p, name)

    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    with tempfile.TemporaryDirectory() as td:
        for t in tests:
            try:
                t(_Tmp(td)) if "tmp_path" in t.__code__.co_varnames else t()
                print(f"  [PASS] {t.__name__}")
                passed += 1
            except AssertionError as e:
                print(f"  [FAIL] {t.__name__}: {e}")
            except Exception as e:
                print(f"  [ERROR] {t.__name__}: {e}")
    print(f"\nRESULT: {passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
