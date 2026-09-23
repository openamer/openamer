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
        # token selection became specificity-based on 17.09.26 (longest token
        # wins, e6e94a191), so 'persistent memory' (17 chars) now outranks
        # 'sandbox' (7). The contract this test pins is unchanged: two different
        # signals derive two different, non-hardcoded gaps.
        assert "modular tool packaging" in a["identified_gap"], a["identified_gap"]
        assert "persistent memory" in b["identified_gap"].lower(), b["identified_gap"]
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
        # Measured token ranking for this snippet under the specificity rule
        # (17.09.26, e6e94a191): 'code correctness' 16 > 'executable spec' 15 >
        # 'parallel agent' 14 > 'validate code' 13 > 'unit test' 9. The longest
        # match wins, so this signal maps to the code-conformance capability.
        # The test's contract is that a genuine capability description resolves
        # to *a* capability rather than being called junk; the longest-match
        # rule is what makes that deterministic.
        assert "automated code-conformance check" in r["identified_gap"], r["identified_gap"]
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


def test_headline_signal_is_named_as_headline_not_a_lexicon_gap():
    """Live 23.09.26: the latest competitor row was an article HEADLINE
    ("Feb 2026 An AI agent coding skeptic tries AI agent coding, in excessive
    detail minimaxir.").

    A headline is not a capability description, so the lexicon having no token
    for it is CORRECT -- inventing one (e.g. `minimaxir`) would map a title onto
    a capability. But the report must name the real cause (the extraction side
    shipped a headline with no capability sentence) instead of claiming a
    lexicon gap that does not exist.
    """
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("Competitor intelligence: An AI agent coding skeptic tries AI agent "
             "coding, in excessive detail",
             "Feb 2026 An AI agent coding skeptic tries AI agent coding, in "
             "excessive detail minimaxir."),
        ], tool_server_src=FAKE_TOOL_SERVER)
        r = kta.experiment_competitor_gap()
        assert r["measurable"] is True, r
        assert "article headline" in r["identified_gap"], r["identified_gap"]
        assert "headline signal" in r["result"], r["result"]
        # the fix points at the EXTRACTION side, and is not a lexicon gap
        assert "extraction" in r["proposed_fix"], r["proposed_fix"]
        # the report must DENY the lexicon-gap reading, not assert it
        assert "not a lexicon gap" in r["result"], r["result"]
        # the signal is still quoted verbatim, never silently dropped
        assert "minimaxir" in r["insight_analyzed"], r["insight_analyzed"]
    finally:
        kta.T = old


def test_content_row_sharing_a_headline_question_is_not_flagged():
    """Guard the sibling row: same source question, but REAL prose content.

    Measured 23.09.26 over the 45 competitor rows: exactly ONE row trips the
    headline discriminator (echo>=0.6 AND len(a)<160) and it is the headline.
    This sibling row (echo 0.20, 249 chars) must stay on the normal path --
    that is what proves the discriminator does not swallow content rows.
    """
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("Competitor intelligence: An AI agent coding skeptic tries AI agent "
             "coding, in excessive detail",
             "AI agent coding/ vibecoding where the author talks about all the "
             "wonderful things agents can now do supported by vague anecdata, how "
             "agents will lead to the atrophy of programming skills, how agents "
             "impugn the sovereignty of the human soul, etc etc."),
        ], tool_server_src=FAKE_TOOL_SERVER)
        r = kta.experiment_competitor_gap()
        assert r["measurable"] is True, r
        assert "article headline" not in r["identified_gap"], r["identified_gap"]
        assert "headline signal" not in r["result"], r["result"]
    finally:
        kta.T = old


def test_cost_datapoint_is_named_not_mapped_to_a_capability():
    """Live 23.09.26: the latest competitor row was a PRICE observation.

    "The monthly bills developers share on Reddit and GitHub are staggering --
    $1,600, $2,500, even $5,000+ for teams running multi-agent workflows on
    frontier models."

    It is not a headline (echo 0.10, 161 chars, so the headline discriminator
    leaves it alone) and it is not a capability description. It slipped through
    only because the generic `multi-agent` token was in the lexicon and mapped
    it onto a capability it does not describe. Measured over the 40 competitor
    rows the consumer reads: the cost predicate (>= 2 currency amounts AND a
    money word) trips 2/40, and after the lexicon runs only this row is left.
    """
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("Competitor intelligence: An AI coding agent, used to write code, "
             "needs to reduce your maintenance costs",
             "The monthly bills developers share on Reddit and GitHub are "
             "staggering \u2014 $1,600, $2,500, even $5,000+ for teams running "
             "multi-agent workflows on frontier models."),
        ], tool_server_src=FAKE_TOOL_SERVER)
        r = kta.experiment_competitor_gap()
        assert r["measurable"] is True, r
        assert "cost/price datapoint" in r["identified_gap"], r["identified_gap"]
        assert "cost datapoint" in r["result"], r["result"]
        # the fix points at the PIPELINE (carry a capability sentence), denies
        # the lexicon reading, and the result names the extraction side
        assert "capability sentence" in r["proposed_fix"], r["proposed_fix"]
        assert "grow the capability lexicon" not in r["proposed_fix"], r["proposed_fix"]
        assert "not a lexicon gap" in r["result"], r["result"]
        assert "extraction-side gap" in r["result"], r["result"]
        # the signal is still quoted verbatim, never silently dropped
        assert "$1,600" in r["insight_analyzed"], r["insight_analyzed"]
    finally:
        kta.T = old


def test_cost_row_carrying_a_capability_still_maps():
    """Guard the OTHER cost row: a capability sentence with prices attached.

    The 22.09.26 `edit across files` row carries 4 currency amounts
    ("Pro $20/mo (annual $17); Max $100-$200/mo") AND a capability description.
    It must keep mapping -- which is why the cost predicate is checked AFTER
    the lexicon, never before. A predicate that swallowed it would lose a real
    capability signal.
    """
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("Competitor intelligence: agent pricing tiers",
             "Engineers who want an agent to autonomously plan, edit across "
             "files and run tests on complex real-world work, and will pay for "
             "depth Pro $20/mo (annual $17); Max $100-$200/mo"),
        ], tool_server_src=FAKE_TOOL_SERVER)
        r = kta.experiment_competitor_gap()
        assert r["measurable"] is True, r
        assert "multi-file agentic execution" in r["identified_gap"], r["identified_gap"]
        assert "cost datapoint" not in r["result"], r["result"]
    finally:
        kta.T = old


def test_specific_multi_agent_phrases_map_their_own_rows():
    """The two phrases that replaced the generic `multi-agent` must still map.

    Measured 23.09.26 over the 40 competitor rows: `multi-agent modes` 1/40
    (the ANUS single/multi-agent switching row) and `multi-agent systems` 1/40
    (the AgentTool row), each with 0 mis-maps -- versus the bare token's 5/40
    with 4 mis-maps. Retiring the generic word must not lose these signals.
    """
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("Competitor intelligence: agent orchestration",
             "Context compaction, token counters, and AgentTool for multi-agent "
             "systems Open-Source AI Orchestration for Production-Grade Agents"),
        ], tool_server_src=FAKE_TOOL_SERVER)
        r = kta.experiment_competitor_gap()
        assert r["measurable"] is True, r
        assert "multi-agent orchestration" in r["identified_gap"], r["identified_gap"]
        assert "NOT mappable" not in r["result"], r["result"]
    finally:
        kta.T = old


def test_bare_multi_agent_no_longer_maps_an_unrelated_row():
    """THE regression guard for the retired token -- fails on the OLD lexicon.

    A row that only says "multi-agent" in passing describes no capability the
    phrase names. Under the old lexicon this mapped to "multi-agent
    orchestration" (a label whose own phrase `multi-agent orchestration` occurs
    0/40 in the corpus). The honest report is a lexicon gap.
    """
    old = kta.T
    try:
        kta.T = _tmp_env([
            ("Competitor intelligence: agent news",
             "Teams running multi-agent setups report growing operational "
             "complexity across their toolchains."),
        ], tool_server_src=FAKE_TOOL_SERVER)
        r = kta.experiment_competitor_gap()
        assert r["measurable"] is True, r
        assert "NOT mappable" in r["result"], r["result"]
        assert "no mappable capability" in r["identified_gap"], r["identified_gap"]
        assert "lexicon gap" in r["result"], r["result"]
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
