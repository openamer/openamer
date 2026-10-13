"""Tests for knowledge_to_action's competitor-gap experiment (scripts/training).

CI-discoverable mirror: `scripts/training/test_competitor_gap.py` carries the
full standalone suite, but `scripts/run_tests.sh` only discovers `tests/`, so
nothing under `scripts/training/` gates a merge. This file pins the part of the
contract that changed on 23.09.26 in the root CI actually runs.

The 23.09.26 case: the latest competitor-buffer row was an article HEADLINE

    "Feb 2026 An AI agent coding skeptic tries AI agent coding, in
     excessive detail minimaxir."

and the experiment reported it as a *lexicon gap* ("lexicon has no token for
this signal"). Measured over the 45 competitor rows that function reads (scoring
`a` only, which is all `signal` ever is): `ai agent coding` 2/45 and `coding
skeptic` / `skeptic` / `excessive detail` / `minimaxir` each 1/45 -- every hit
being this headline or its sibling. So there was no gap to fill: a headline is
not a capability description, and inventing a token for it would map a title
onto a capability. The honest report names the class and the extraction side.

Discriminator: a headline is a near-echo of its own source question (significant
words of `u` reappearing in `a`), flagged when echo >= 0.6 and len(a) < 160.
Measured over all 45 rows it trips on exactly 1 (the headline, echo 100%) and
mis-fires on 0 -- hence the sibling-row control below, which is the whole point
of the bound.
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

# The 23.09.26 row verbatim (a headline: date + title + author handle).
HEADLINE_Q = ("Competitor intelligence: An AI agent coding skeptic tries AI "
              "agent coding, in excessive detail")
HEADLINE_A = ("Feb 2026 An AI agent coding skeptic tries AI agent coding, in "
              "excessive detail minimaxir.")

# Same source question, but REAL prose -> must NOT be flagged as a headline.
# This is the control that bounds the discriminator.
SIBLING_A = ("AI agent coding/ vibecoding where the author talks about all the "
             "wonderful things agents can now do supported by vague anecdata, "
             "how agents will lead to the atrophy of programming skills, how "
             "agents impugn the sovereignty of the human soul, etc etc.")

# The 22.09.26 signal the lexicon WAS grown for -> still on the normal path.
CAPABILITY_A = ("Engineers who want an agent to autonomously plan, edit across "
                "files and run tests on complex real-world work, and will pay "
                "for depth Pro $20/mo (annual $17); Max $100-$200/mo 2 OpenAI "
                "Codex 4.")


def _run(entries, tool_server_src=FAKE_TOOL_SERVER):
    """Run the experiment against a TEMP buffer -- the real one is never read."""
    d = tempfile.mkdtemp(prefix="kta_gap_ci_")
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


def test_headline_is_named_a_headline_not_a_lexicon_gap():
    r = _run([(HEADLINE_Q, HEADLINE_A)])
    assert r["measurable"] is True, r
    # the real cause is named on our side, in the extraction, not as a gap
    assert "article headline" in r["identified_gap"], r["identified_gap"]
    assert "extraction" in r["proposed_fix"], r["proposed_fix"]
    # and the lexicon-gap reading is explicitly DENIED, not asserted
    assert "not a lexicon gap" in r["result"], r["result"]
    # the signal is still quoted verbatim -- never silently dropped
    assert "minimaxir" in r["insight_analyzed"], r["insight_analyzed"]
    assert r["signal_candidates"] == 1, r


def test_content_row_sharing_the_headline_question_is_not_flagged():
    """Bound the discriminator: prose under the same question stays normal."""
    r = _run([(HEADLINE_Q, SIBLING_A)])
    assert "article headline" not in r["identified_gap"], r["identified_gap"]
    assert "headline signal" not in r["result"], r["result"]


def test_genuine_capability_row_still_maps():
    """The 22.09.26 fix must survive: a capability row maps, is not a headline."""
    r = _run([(("Competitor intelligence: The secret recipe of powerful AI "
                "coding Agents"), CAPABILITY_A)])
    # the gap reports the mapped LABEL, not the raw token
    assert "multi-file agentic execution" in r["identified_gap"], r["identified_gap"]
    assert "headline" not in r["identified_gap"].lower(), r["identified_gap"]


def test_unmappable_non_headline_prose_still_reports_a_lexicon_gap():
    """A long non-answer that is not a headline keeps the original wording."""
    r = _run([(("Competitor intelligence: OpenHands agent architecture updates"),
               "Foray into the Web, Windows 95, Windows XP, and Xbox 1. " * 4)])
    assert "NOT mappable" in r["result"], r["result"]
    assert "lexicon" in r["proposed_fix"], r["proposed_fix"]
    assert "headline signal" not in r["result"], r["result"]
