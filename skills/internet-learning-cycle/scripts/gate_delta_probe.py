#!/usr/bin/env python
"""Delta-probe a candidate junk-gate pattern over the LIVE learning buffer.

WHY: the skill's core rule is "prove a gate change with an old-vs-new delta over
the live buffer, never with 'the tests pass'". That probe was hand-written four
times in one session and each rewrite re-introduced a different footgun
(module-name collision in sys.modules, comparing _clean_insight output instead of
the raw text, hand-shortened fixtures under 90 chars). This script is the recipe,
encoded once.

USAGE
    # 1. pure measurement, no source edit — is my candidate narrow enough?
    $OPENAMER_HOME/venv/Scripts/python.exe _gate_delta.py --candidate-file cand.py

    # 2. verify an ALREADY-APPLIED pattern (no candidate file) end to end
    $OPENAMER_HOME/venv/Scripts/python.exe _gate_delta.py --applied

cand.py must define, at module level:
    CAND      -- a compiled re.Pattern (the narrowest possible junk signature)
    COUNTER   -- list of >=90-char counter-case strings that MUST stay learnable
    LEAK      -- the VERBATIM row taken from the log (never a paraphrase)
Optional: STRIPPING = True if the candidate is a STRIP (not a reject) class.

READ THE OUTPUT THIS WAY
    regressions == 0                ... hard requirement, non-negotiable
    newly_rejected                   ... every one must be provably junk
    leak caught True / counters False ... the actual acceptance criterion
A non-zero `regressions` means you widened the gate too far. A `False` on the
leak means you keyed on the wrong thing. Neither is fixed by editing the test.

PITFALLS THIS SCRIPT ALREADY AVOIDS
  * loads each module under a UNIQUE name with importlib -> no sys.modules
    collision (that collision once faked a "writer-gate leak")
  * asserts m.__file__ / w.__file__ point at the real training dir before
    trusting any verdict
  * reports the module path it actually tested, so you can prove you measured
    the LIVE HOME copy and not the repo copy
"""
import argparse
import importlib.util
import io
import json
import os
import sys

HOME = os.environ.get(
    "OPENAMER_TRAINING_DIR",
    r"C:\Users\damir\AppData\Local\openamer-laptop\scripts\training",
)
IL_PATH = os.path.join(HOME, "internet_learner.py")
BS_PATH = os.path.join(HOME, "buffer_store.py")
BUF = os.path.join(HOME, "online_buffer.jsonl")


def load(path, name):
    """Load a module under a unique name. Never reuse a name (sys.modules collision)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def read_buffer(path):
    rows = []
    for line in io.open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-file", help="module defining CAND/COUNTER/LEAK")
    ap.add_argument("--applied", action="store_true",
                    help="no candidate; verify the pattern already in _JUNK_RE")
    args = ap.parse_args()

    if not (args.candidate_file or args.applied):
        ap.error("pass --candidate-file <cand.py> or --applied")

    IL = load(IL_PATH, "il_delta")
    BS = load(BS_PATH, "bs_delta")

    # Prove we measured the LIVE copy, not some other checkout.
    assert os.path.normcase(IL.__file__) == os.path.normcase(IL_PATH), IL.__file__
    assert os.path.normcase(BS.__file__) == os.path.normcase(BS_PATH), BS.__file__
    print("IL:", IL.__file__)
    print("BS:", BS.__file__)

    # Guard against the self-destructing alternation (empty alternative).
    print("gate self-broken '||':", "||" in IL._JUNK_RE.pattern, "(must be False)")

    if args.applied:
        CAND = IL._JUNK_RE
        COUNTER, LEAK = [], None
    else:
        C = load(os.path.abspath(args.candidate_file), "cand_delta")
        CAND = C.CAND
        COUNTER = getattr(C, "COUNTER", [])
        LEAK = getattr(C, "LEAK", None)
        print("candidate pattern:", CAND.pattern[:160])

    rows = read_buffer(BUF)
    print("buffer rows:", len(rows))

    cand_hits = [r.get("a", "") for r in rows if CAND.search(r.get("a") or "")]
    print("candidate hits in buffer:", len(cand_hits))
    for h in cand_hits:
        print("   HIT:", h[:200])

    if LEAK:
        print("leak caught by candidate:", bool(CAND.search(LEAK)))
        print("leak judged junk  (L/W):", IL._is_junk(LEAK), BS._is_nav_chrome(LEAK))

    for c in COUNTER:
        # A counter-case under 90 chars tests the SHORT-CANDIDATE rule, not yours.
        flag = "" if len(c) >= 90 else "   <-- WARNING: <90 chars, tests a DIFFERENT gate"
        print("counter L/W: %-5s %-5s <- %s%s" % (
            IL._is_junk(c), BS._is_nav_chrome(c), c[:70], flag))

    junk_rows = [r.get("a", "") for r in rows if IL._is_junk(r.get("a") or "")]
    print("junk-flagged rows now:", len(junk_rows))
    for h in junk_rows:
        print("   JUNK:", h[:200])
    print("\nDone. regressions must be 0; leak True; every counter False.")


if __name__ == "__main__":
    main()
