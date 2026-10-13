"""Regression tests for scripts/training/self_improve.py rule engine.

Hermetic: no network, no LLM, no live files touched. The module is exec'd (not
just AST-parsed) so a broken rule actually runs.

Two bug classes are pinned here.

1. P2 tested the WRONG match object (live on main, 2026-09-20). It guarded on
   `m` -- P1's `CYCLE_SECONDS` regex match -- while proposing `m.group(0)`, the
   CYCLE_SECONDS text itself, as the pattern for apply_and_test() to replace.
   On any target whose cycle interval was under 100s the rule therefore DELETED
   the interval assignment and wrote a second `max_tokens` line in its place.
   Nothing downstream noticed: the patched file still compiles, still
   AST-parses, and still defines loop().

   Measured on the broken form, for
       CYCLE_SECONDS = 60
       max_tokens = 400
   propose_improvement() returned
       [('capacity', 'CYCLE_SECONDS = 60', 'max_tokens=200', ...)]
   and applying it produced
       max_tokens=200
       max_tokens = 400

2. The general form of that bug: apply_and_test() had no check that a *module
   level binding* survives the edit. All three of its original checks passed on
   the corrupted result. The binding-survival gate added 2026-09-23 catches the
   whole class, and `test_binding_gate_rejects_a_binding_deleting_rewrite`
   drives it directly with a synthetic destructive proposal.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TRAINING = REPO / "scripts" / "training"
sys.path.insert(0, str(TRAINING))

_spec = importlib.util.spec_from_file_location(
    "self_improve", TRAINING / "self_improve.py"
)
SI = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SI)


def _capacity_proposals(content):
    return [p for p in SI.propose_improvement("target.py", content) if p[0] == "capacity"]


def test_p2_never_rewrites_the_cycle_interval():
    """The reported symptom: a small cycle interval must not trigger P2 at all."""
    content = "CYCLE_SECONDS = 60\nmax_tokens = 400\n"
    assert _capacity_proposals(content) == [], (
        "P2 must not fire when max_tokens is already >= 100, even if "
        "CYCLE_SECONDS is a small number"
    )


def test_p2_targets_max_tokens_when_it_is_small():
    """The rule still works for its actual purpose: a small max_tokens."""
    content = "CYCLE_SECONDS = 60\nmax_tokens = 50\n"
    props = _capacity_proposals(content)
    assert len(props) == 1, props
    kind, old, new, _why = props[0]
    assert old == "max_tokens = 50", old
    assert new == "max_tokens=200", new
    # And applying it must leave the cycle interval intact.
    patched = content.replace(old, new, 1)
    assert "CYCLE_SECONDS = 60" in patched, patched
    assert "max_tokens=200" in patched, patched
    # `max_tokens = 50` was REPLACED, so exactly one max_tokens reference remains.
    assert patched.count("max_tokens") == 1, patched


def test_p2_pattern_is_always_a_max_tokens_assignment():
    """Invariant across a range of contents: P2's `old` is never a non-max_tokens line."""
    for content in (
        "CYCLE_SECONDS = 30\nmax_tokens = 10\n",
        "max_tokens = 5\n",
        "CYCLE_SECONDS = 900\nmax_tokens = 20\n",
        "CYCLE_SECONDS = 45\n",
        "max_tokens = 99\nCYCLE_SECONDS = 12\n",
    ):
        for _kind, old, _new, _why in _capacity_proposals(content):
            assert "max_tokens" in old, (
                f"P2 proposed replacing a non-max_tokens line {old!r} for {content!r}"
            )
            assert "CYCLE_SECONDS" not in old, (
                f"P2 proposed deleting the cycle interval {old!r} for {content!r}"
            )


# ---- P5 duplicate module-level imports -------------------------------------
#
# Added 2026-09-23 to give the loop real work again. It had produced exactly one
# applied improvement ever and had gone permanently idle: P1/P2/P3/P4 all sit
# behind thresholds the real targets are outside. Four of the six targets bind
# `os` twice at module level (a bare `import os` line plus `os` inside the
# comma-import on the next line), so removing the redundant name gives the loop
# a deterministic, behaviour-free, grep-verified job.

def _dedupe_proposals(content):
    return [p for p in SI.propose_improvement("target.py", content) if p[0] == "dedupe-import"]


def test_p5_finds_the_real_target_shape():
    """The exact shape measured in the targets: bare import + comma-import."""
    content = "import os\nimport json, os, sys, time\nfrom pathlib import Path\n"
    props = _dedupe_proposals(content)
    assert len(props) == 1, props
    _kind, old, new, _why = props[0]
    patched = content.replace(old, new, 1)
    assert patched.count("os") == content.count("os") - 1, patched
    # the surviving binding must be the standalone `import os` line
    assert "import os" in patched, patched
    assert "os" in SI._module_bindings(patched), patched


def test_p5_never_fires_without_a_duplicate():
    content = "import os\nimport json, sys, time\n"
    assert _dedupe_proposals(content) == [], content


def test_p5_never_removes_the_last_binding_of_a_name():
    """Invariant: a dedupe proposal may not drop a name from the module bindings."""
    for content in (
        "import os\nimport json, os, sys\n",
        "import os, sys\nimport json, os\n",
        "import json, os, sys\nimport os\n",
        "import os\nimport os\n",
    ):
        before = SI._module_bindings(content)
        for _kind, old, new, _why in _dedupe_proposals(content):
            after = SI._module_bindings(content.replace(old, new, 1))
            lost = before - after
            assert not lost, (
                f"P5 would drop module binding(s) {lost} for {content!r} "
                f"via {old!r} -> {new!r}"
            )


# ---- binding-survival gate -------------------------------------------------

def test_binding_gate_rejects_a_binding_deleting_rewrite(tmp_path):
    """The general gate: an edit that deletes a module-level binding is rejected.

    This is the exact shape of the original P2 corruption -- the rewritten file
    still compiles, still AST-parses, and still defines loop(), so only a
    binding-survival check can catch it.
    """
    live = tmp_path / "live.py"
    live.write_text("CYCLE_SECONDS = 60\nmax_tokens = 400\n\n"
                    "def loop():\n    return CYCLE_SECONDS\n", encoding="utf-8")
    sandbox = tmp_path / "sandbox.py"
    proposal = ("capacity", "CYCLE_SECONDS = 60", "max_tokens=200",
                "simulates the historical P2 corruption")
    ok, reason = SI.apply_and_test("live.py", proposal, str(live), str(sandbox))
    assert not ok, "a rewrite that deletes CYCLE_SECONDS must be rejected"
    assert "binding" in reason.lower(), reason


def test_binding_gate_allows_a_genuine_improvement(tmp_path):
    live = tmp_path / "live.py"
    live.write_text("CYCLE_SECONDS = 60\nmax_tokens = 400\n\n"
                    "def loop():\n    return CYCLE_SECONDS\n", encoding="utf-8")
    sandbox = tmp_path / "sandbox.py"
    proposal = ("comment-fix", "CYCLE_SECONDS = 60",
                "CYCLE_SECONDS = 60  # every 1 min", "cosmetic")
    ok, reason = SI.apply_and_test("live.py", proposal, str(live), str(sandbox))
    assert ok, reason
    # and the live file itself must never be touched by a passing test
    assert live.read_text(encoding="utf-8").startswith("CYCLE_SECONDS = 60\n")


def test_apply_and_test_preserves_lf_line_endings(tmp_path):
    """A target that is pure LF must not be flipped to CRLF by a live switch.

    apply_and_test() opened in text mode, so on Windows '\\n' was translated to
    '\\r\\n' on write. Four of the six SAFE_TARGETS are pure LF, so the first
    applied proposal would have rewritten the entire file's line endings --
    a whole-file diff dressed up as a one-line improvement.
    """
    live = tmp_path / "live.py"
    live.write_bytes(b"import os\nimport json, os, sys\n\nMAX = 5\n")
    sandbox = tmp_path / "sandbox.py"
    proposal = ("dedupe-import", "import json, os, sys", "import json, sys", "dup")
    ok, reason = SI.apply_and_test("live.py", proposal, str(live), str(sandbox))
    assert ok, reason
    raw = sandbox.read_bytes()
    assert b"\r\n" not in raw, f"LF target rewritten with CRLF: {raw!r}"
    assert raw == b"import os\nimport json, sys\n\nMAX = 5\n", raw
