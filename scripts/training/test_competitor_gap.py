#!/usr/bin/env python3
"""Tests for knowledge_to_action.experiment_competitor_gap — the KTA gap analysis.

Run:  python test_competitor_gap.py

Regression guard for the bug found 12.09: `experiment_competitor_gap` returned a
HARDCODED dict. Live evidence from kta_log.jsonl (559 runs): 96 competitor-gap
runs produced exactly ONE distinct `identified_gap` string while the buffer's
competitor signal changed — an "experiment" that inspected nothing, recited a
canned line, and always reported `measurable: False`.

The contract these tests pin:
  1. the gap is derived from the REAL latest buffer signal (two different signals
     => two different gaps; never a constant);
  2. the entry carries a real MEASUREMENT of our own tool surface;
  3. an unmappable / non-answer signal is reported honestly as such (which is
     the useful finding) instead of being papered over with an invented gap;
  4. no competitor signal at all => explicit "no competitor data yet".

All tests work against a TEMP dir (kta.T is monkeypatched) — the real
online_buffer.jsonl / tool_server.py are never read or written.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import knowledge_to_action as kta


def _tmp_env(entries, tool_server_src=None):
    """Build a temp training dir holding a buffer + optional tool_server.py."""
    d = tempfile.mkdtemp(prefix="ktagap_test_")
    buf = os.path.join(d, "online_buffer.jsonl")
    with open(buf, "w", encoding="utf-8") as f:
        for u, a in entries:
            f.write(json.dumps({"u": u, "a": a}) + "\n")
    if tool_server_src is not None:
        with open(os.path.join(d, "tool_server.py"), "w", encoding="utf-8") as f:
            f.write(tool_server_src)
    return d


FAKE_TOOL_SERVER = "\n".join([
    "def t_web_search(params):",
    "    pass",
    "",
    "def t_run_python(params):",
    "    pass",
    "",
    "def t_see(params):",
    "    pass",
]) + "\n"


def test_no_competitor_data_is_explicit():
    old = kta.T
    try:
        kta.T = _tmp_env([("What is LoRA?", "LoRA is low-rank adaptation of weights.")])
        r = kta.experiment_competitor_gap()
        assert r["result"] == "no competitor data yet", r
        assert "identified_gap" not in r, r
    finally:
        kta.T = old


def test_gap_is_derived_not_hardcoded():
    """THE regression: two different signals must yield two different gaps."""
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("Competitor intelligence: OpenHands architecture",
             "OpenHands ships a modular SDK with a plugin system for tools."),
        ], tool_server_src=FAKE_TOOL_SERVER)
        a = kta.experiment_competitor_gap()

        kta.T = _tmp_env([
            ("Competitor intelligence: Devin sandbox",
             "Devin runs each task in a sandbox with persistent memory."),
        ], tool_server_src=FAKE_TOOL_SERVER)
        b = kta.experiment_competitor_gap()

        assert a["identified_gap"] != b["identified_gap"], (a, b)
        # lexicon is ordered — 'modular' wins over the later 'sdk' token
        assert "modular tool packaging" in a["identified_gap"], a["identified_gap"]
        assert "sandbox" in b["identified_gap"].lower(), b["identified_gap"]
        # the canned string from the buggy version must be gone
        assert "modular SDK design — our tool_server.py is monolithic" not in a["identified_gap"]
    finally:
        kta.T = old


def test_entry_carries_a_real_measurement():
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("Competitor intelligence: OpenHands",
             "OpenHands has a modular SDK design."),
        ], tool_server_src=FAKE_TOOL_SERVER)
        r = kta.experiment_competitor_gap()
        assert r["measurable"] is True, r
        stats = r["measured_tool_surface"]
        assert stats["tool_funcs"] == 3, stats       # counted from the fake source
        assert stats["lines"] >= 3, stats
        assert "3 tool funcs" in r["result"], r["result"]
        assert r["signal_source_question"], r
        assert r["insight_analyzed"], r
    finally:
        kta.T = old


def test_unmappable_signal_reported_honestly():
    """A snippet with no known capability token must NOT be turned into an
    invented gap, and must NOT be blamed on upstream ("junk") either.

    Live 12.09.26: the real non-answer snippet ("Foray into the Web, Windows 95,
    ...") hit this branch, but so did a GENUINE capability description (the Kiro
    one) that the lexicon simply had no token for. The honest report names the
    actual cause on our side — a lexicon gap — instead of asserting a defect in
    someone else's pipeline we never inspected.
    """
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("Competitor intelligence: OpenHands agent architecture updates",
             "Foray into the Web, Windows 95, Windows XP, and Xbox 1."),
        ], tool_server_src=FAKE_TOOL_SERVER)
        r = kta.experiment_competitor_gap()
        assert r["measurable"] is True, r
        assert "NOT mappable" in r["result"], r["result"]
        assert "no mappable capability" in r["identified_gap"], r["identified_gap"]
        # the fix must point at OUR lexicon, not at "upstream is broken"
        assert "lexicon" in r["proposed_fix"], r["proposed_fix"]
        assert "upstream" not in r["result"].lower() or "not proof" in r["result"].lower(), r["result"]
    finally:
        kta.T = old


def test_real_capability_snippet_maps_instead_of_being_called_junk():
    """Regression (live 12.09.26): a genuine capability description must map.

    This is the exact signal that produced the false "upstream competitor
    pipeline produces junk" claim — it is a real product description, so the
    lexicon must resolve it to a capability and report measurable: True.
    """
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("What new agent architectures are trending on GitHub?",
             "Kiro helps developers and teams do their best work: turn prompts "
             "into executable specs, validate code correctness to find bugs unit "
             "tests miss, and build across large codebases with parallel agents."),
        ], tool_server_src=FAKE_TOOL_SERVER)
        r = kta.experiment_competitor_gap()
        assert r["measurable"] is True, r
        assert "NOT mappable" not in r["result"], r["result"]
        assert "parallel multi-agent execution" in r["identified_gap"], r["identified_gap"]
    finally:
        kta.T = old


def test_missing_tool_server_does_not_crash():
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("Competitor intelligence: OpenHands",
             "OpenHands ships a modular SDK."),
        ])  # no tool_server.py written
        r = kta.experiment_competitor_gap()
        assert r["measurable"] is True, r
        assert r["measured_tool_surface"]["tool_funcs"] == 0, r
        assert "0 tool funcs" in r["result"], r["result"]
    finally:
        kta.T = old


def test_latest_signal_wins_and_junk_lines_tolerated():
    old = kta.T
    try:
        d = _tmp_env([
            ("Competitor intelligence: Devin",
             "Devin adds a sandbox for every task."),
            ("Competitor intelligence: OpenHands",
             "OpenHands has a modular SDK."),
        ], tool_server_src=FAKE_TOOL_SERVER)
        # a malformed line and a blank line must not break the scan
        with open(os.path.join(d, "online_buffer.jsonl"), "a", encoding="utf-8") as f:
            f.write("{not json\n\n")
        kta.T = d
        r = kta.experiment_competitor_gap()
        assert r["signal_candidates"] == 2, r
        assert "modular" in r["insight_analyzed"].lower(), r["insight_analyzed"]
    finally:
        kta.T = old


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001 — standalone runner
                fails += 1
                print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"\n{'OK' if not fails else 'FAILED'}: {fails} failure(s)")
    sys.exit(1 if fails else 0)
