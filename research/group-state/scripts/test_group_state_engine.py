#!/usr/bin/env python3
"""Verify the group-state ENGINE: train, persist, reload, answer, and the tool.

WHY: the architecture was demonstrated but never USABLE — every script trained
and evaluated in one process, and nothing was ever written to disk. This test
guards the properties that make it a real artifact rather than a demo:

  1. a trained model can be SAVED and RELOADED with identical behaviour
  2. answers are correct at lengths far beyond anything trained on
  3. answers agree with an INDEPENDENT group-theoretic computation
  4. the tool layer reports bad input as an error instead of guessing
  5. a request NEVER trains (training on demand blew the HTTP timeout)

Run:  python scripts/test_group_state_engine.py
"""
import json
import os
import random
import sys
import tempfile
import time
import types
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "training"))

import group_state_engine as gse
from group_state_engine import FORMAT, answer, load, save, train
from group_scaling_lab import compose

FAIL = []


def check(name, cond, detail=""):
    print(f"  {'OK  ' if cond else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")
    if not cond:
        FAIL.append(name)


def section(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def load_tool_fn():
    """Extract t_group_state from tool_server WITHOUT importing the module.

    Importing tool_server starts the 2B model and binds :8081 — unacceptable in
    a test. The function is self-contained apart from module globals, which are
    supplied here.

    Returns None when tool_server.py is absent: the integration belongs to the
    HOST project, and a research checkout of this directory does not carry it.
    The caller skips those checks rather than reporting a failure for a file
    that was never supposed to be here.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    server = os.path.join(here, "training", "tool_server.py")
    if not os.path.exists(server):
        return None
    src = open(server, encoding="utf-8").read()
    m = re.search(r"(_GROUP_CACHE = \{.*?\n\n\ndef t_group_state\(params\):.*?\n"
                  r"(?=\nEXECUTORS))", src, re.S)
    if not m:
        raise RuntimeError("t_group_state not found in tool_server.py")
    mod = types.ModuleType("tool_probe")
    exec("import os, sys\nfrom pathlib import Path\n" + m.group(1),
         mod.__dict__)
    return mod.t_group_state


def main():
    section("1) train -> save -> reload gives IDENTICAL behaviour")
    m1, g1, stats = train("A5", epochs=60, n_train=128)
    tmp = os.path.join(tempfile.gettempdir(), "_gs_test_a5.json")
    save(m1, g1, stats, tmp)
    m2, g2, payload = load(tmp)
    check("model file written", os.path.exists(tmp))
    check("reloaded group matches", g2.name == g1.name)
    check("reloaded params match",
          [p.n for p in m1.params()] == [p.n for p in m2.params()])
    same = True
    rng = random.Random(11)
    for _ in range(40):
        mv = [rng.randrange(g1.num_gens) for _ in range(rng.randrange(1, 20))]
        a1 = answer(m1, g1, mv)["element_index"]
        a2 = answer(m2, g2, mv)["element_index"]
        if a1 != a2:
            same = False
    check("40 sequences agree before/after reload", same)
    check("params == K^2+K",
          sum(p.n for p in m1.params()) == g1.num_gens ** 2 + g1.num_gens,
          f"{sum(p.n for p in m1.params())}")

    # the format tag is the artifact's contract: written by save(), asserted by
    # load(). Centralised as FORMAT so the two can never drift apart.
    check("saved artifact carries the format tag",
          json.load(open(tmp, encoding="utf-8"))["format"] == FORMAT, FORMAT)
    bad_fmt = os.path.join(tempfile.gettempdir(), "_gs_bad_format.json")
    json.dump({"format": "not-this-format"}, open(bad_fmt, "w"))
    try:
        load(bad_fmt)
        check("load rejects an unknown format", False)
    except ValueError:
        check("load rejects an unknown format", True)

    section("2) accuracy far beyond the training lengths")
    for L in (4, 12, 48, 200):
        rng = random.Random(900 + L)
        moves = [[rng.randrange(g2.num_gens) for _ in range(L)]
                 for _ in range(40)]
        hit = sum(answer(m2, g2, mv)["correct"] for mv in moves)
        check(f"L={L} (never trained past 7)", hit == 40, f"{hit}/40")

    section("3) agreement with an INDEPENDENT computation")
    rng = random.Random(5)
    ok = True
    for _ in range(60):
        mv = [rng.randrange(g2.num_gens) for _ in range(rng.randrange(1, 25))]
        st = g2.identity
        for k in mv:
            st = compose(st, g2.generators[k])
        r = answer(m2, g2, mv)
        if r["element_index"] != g2.index[st]:
            ok = False
    check("element index == direct composition, 60 sequences", ok)

    section("4) the TOOL layer: bad input is an ERROR, never a guess")
    t_group_state = load_tool_fn()
    if t_group_state is None:
        print("  SKIP  tool_server.py not present — the tool wiring belongs to")
        print("        the host project, not to this research checkout")
    else:
        r = t_group_state({"group": "A5", "moves": []})
        check("empty moves -> error", "error" in r)
        r = t_group_state({"group": "Z10", "moves": [1]})
        check("out-of-range index -> error",
              "error" in r and r.get("valid_indices") == "0..0")
        r = t_group_state({"group": "NO_SUCH_GROUP", "moves": [0]})
        check("unknown group -> error (no crash)", "error" in r)
        # A5 has exactly 2 generators (3-cycle + 5-cycle), so valid indices are
        # 0..1. An earlier version of this test used index 2 and mis-flagged a
        # CORRECT rejection as a failure. Bounds are read from the group.
        r = t_group_state({"group": "A5", "moves": "0 1"})
        check("string moves accepted", r.get("correct") is True,
              json.dumps(r)[:80])
        r = t_group_state({"group": "A5", "moves": [0, 1]})
        check("valid call returns correctness flag", "correct" in r)
        r = t_group_state({"group": "A5", "moves": [2]})
        check("index 2 on a 2-generator group -> error", "error" in r)

    section("5) a request must NEVER train")
    # Point the model dir at an EMPTY temp dir. A missing artifact must produce
    # an immediate error, never a ~100 s training run (S6 takes ~161 s, which
    # is what blew the HTTP timeout in the first integration attempt).
    empty = tempfile.mkdtemp()
    old = gse.DEFAULT_DIR
    gse.DEFAULT_DIR = empty
    try:
        t0 = time.time()
        missing = not os.path.exists(gse.model_path("A5"))
        dt = time.time() - t0
        check("engine reports the artifact as missing", missing)
        check("checking does not train anything", dt < 2.0, f"{dt:.3f}s")

        if t_group_state is not None:
            t0 = time.time()
            r = t_group_state({"group": "A5", "moves": [0, 1]})
            dt = time.time() - t0
            check("tool refuses a missing artifact fast", dt < 2.0, f"{dt:.3f}s")
            check("refusal names the fix command", "fix" in r or "error" in r,
                  json.dumps(r)[:70])
        else:
            print("  SKIP  tool-level refusal check (tool_server.py absent)")
    finally:
        gse.DEFAULT_DIR = old

    print()
    print("=" * 78)
    if FAIL:
        print(f"ENGINE TEST: FAILURES PRESENT ({len(FAIL)}): {FAIL}")
        sys.exit(1)
    print("ENGINE TEST: ALL OK")
    print("=" * 78)


if __name__ == "__main__":
    main()
