"""CI-discoverable mirror: the KTA competitor-gap INCIDENT class (23.09.26).

`scripts/training/test_competitor_gap.py` carries the full standalone suite, but
`scripts/run_tests.sh` only discovers `tests/`, so nothing under
`scripts/training/` gates a merge. This file pins the part of the contract that
changed on 23.09.26 in the root CI actually runs.

The case: the `*/30` knowledge-to-action cron selected
`experiment_competitor_gap` and the latest competitor-buffer row was

    "PocketOS was left scrambling after a rogue AI agent deleted swaths of code
     underpinning its business"

reported as a *lexicon gap* ("lexicon has no token for this signal"). Measured
over the 37 competitor rows that function reads (scoring `a` only, which is all
`signal` ever is): `rogue` 1/37, `deleted` 1/37, `delete` 1/37, `scrambling`
1/37 -- every one a word FROM the report, so growing the lexicon for it would
map an incident onto a capability. `guardrail` 1/36 is a DIFFERENT row
(VoltAgent) and does not stand for this signal; `recovery` / `backup` /
`permission` / `containment` / `rollback` / `destructive` / `audit` / `approval`
/ `action gate` / `human-in-the-loop` / `confirmation` / `deletion` are all
0/37 (the corpus does not support them).

So there was no gap to fill: an incident report is not a capability
description. The honest report names the class and points at the extraction
side. The predicate is the measured one -- an outcome word (rogue / runaway /
destructive) followed by a destructive verb -- 1/37, this row, 0 mis-maps.

Ordering: the lexicon is checked FIRST, so a capability sentence that merely
mentions a deletion still maps. The second test is the whole point of that
bound -- its row was measured to trip the predicate AND carry a lexicon token.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TRAINING = REPO / "scripts" / "training"
sys.path.insert(0, str(TRAINING))

_spec = importlib.util.spec_from_file_location(
    "kta", TRAINING / "knowledge_to_action.py"
)
kta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kta)

FAKE_TOOL_SERVER = "def t_web_search(params):\n    pass\n"

# The 23.09.26 row verbatim (an incident report: damage, no feature).
INCIDENT_Q = ("Competitor intelligence: Claude-powered AI coding agent deletes "
              "company database in 9 seconds")
INCIDENT_A = ("PocketOS was left scrambling after a rogue AI agent deleted "
              "swaths of code underpinning its business")

# A genuine capability sentence that ALSO trips the incident predicate
# (rogue + deletes) and carries a lexicon token (`sandbox`) -> must map.
ORDERING_A = ("Sandboxed execution stops a rogue script before it deletes "
              "production data.")


def _run(entries, tool_server_src=FAKE_TOOL_SERVER):
    """Run the experiment against a TEMP buffer -- the real one is never read."""
    d = tempfile.mkdtemp(prefix="kta_incident_ci_")
    with open(Path(d) / "online_buffer.jsonl", "w", encoding="utf-8") as f:
        for u, a in entries:
            f.write(json.dumps({"u": u, "a": a}) + "\n")
    if tool_server_src is not None:
        with open(Path(d) / "tool_server.py", "w", encoding="utf-8") as f:
            f.write(tool_server_src)
    old = kta.T
    try:
        kta.T = d
        return kta.experiment_competitor_gap()
    finally:
        kta.T = old


def test_incident_report_is_named_an_incident_not_a_lexicon_gap():
    r = _run([(INCIDENT_Q, INCIDENT_A)])
    assert r["measurable"] is True, r
    # the real cause is named on our side, in the extraction, not as a gap
    assert "incident" in r["identified_gap"], r["identified_gap"]
    # and the lexicon-gap reading is explicitly DENIED, not asserted
    assert "not a lexicon gap" in r["result"], r["result"]
    assert "extraction-side gap" in r["result"], r["result"]
    assert "grow the capability lexicon" not in r["proposed_fix"], r["proposed_fix"]
    # the signal is still quoted verbatim -- never silently dropped
    assert "PocketOS" in r["insight_analyzed"], r["insight_analyzed"]
    assert r["signal_candidates"] == 1, r


def test_capability_row_that_trips_the_incident_predicate_still_maps():
    """Bound the ordering: the lexicon runs BEFORE the incident predicate.

    This is the test that fails if the predicate is checked first: the row was
    measured to trip `_INCIDENT` (rogue + deletes) and to carry a lexicon token
    (`sandbox`), so a wrong ordering swallows it.
    """
    r = _run([("Competitor intelligence: agent reliability during incidents",
               ORDERING_A)])
    assert r["measurable"] is True, r
    assert "incident" not in r["identified_gap"], r["identified_gap"]
    assert "NOT mappable" not in r["result"], r["result"]
    # the row maps via the lexicon; identified_gap carries the token LABEL
    assert "sandboxed execution" in r["identified_gap"], r["identified_gap"]


def test_headline_and_cost_classes_still_win_their_own_rows():
    """The neighbouring classes must keep working after this change."""
    r = _run([(("Competitor intelligence: An AI agent coding skeptic tries AI "
                "agent coding"),
               "Feb 2026 An AI agent coding skeptic tries AI agent coding, in "
               "excessive detail minimaxir.")])
    assert "article headline" in r["identified_gap"], r["identified_gap"]

    r = _run([(("Competitor intelligence: multi-agent workflow costs"),
               "The monthly bills developers share are staggering -- $1,600, "
               "$2,500, even $5,000+ for teams running multi-agent workflows.")])
    assert "cost/price" in r["identified_gap"], r["identified_gap"]
