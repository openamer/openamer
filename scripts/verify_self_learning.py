#!/usr/bin/env python3
"""Verification for scripts/self_learning.py.

Proves the honesty gate FIRES (not just that it is silent on good data) using
crafted data where the answer is knowable a priori, plus the live-DB invariants.

Note: the live window is "newest 80 rows" of state.db, which GROWS as the agent
works — so which features leak is NOT a stable assertion. Only structural facts
(assistant rows carry tool_name=NULL) and the crafted cases are asserted by name.
Exit 0 = all checks passed.
"""
import contextlib
import importlib.util
import io
import random
import sys
from pathlib import Path

SCRIPTS = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\scripts")
TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else SCRIPTS / "self_learning.py"
spec = importlib.util.spec_from_file_location("sl", TARGET)
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)
print(f"# target: {TARGET}")

passed, failed = 0, 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS  {name}" + (f"  [{detail}]" if detail else ""))
    else:
        failed += 1
        print(f"FAIL  {name}" + (f"  [{detail}]" if detail else ""))


def synth(feat_idx, invert, n=60, seed=11):
    """Label == feature[feat_idx] (or its inverse). Answer known a priori."""
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        feats = [rnd.randint(0, 1) for _ in range(7)]
        lab = float(1 - feats[feat_idx] if invert else feats[feat_idx])
        out.append((feats, [lab]))
    return out


# ── 1. gate FIRES on a crafted direct leak (answer known a priori) ─────────
got = [f[0] for f in sl.leak_findings(synth(6, invert=False))]
check("gate fires on crafted direct leak", "tool_name" in got, f"flagged={got}")

# ── 2. gate FIRES on a crafted INVERTED leak ──────────────────────────────
# this is the bug class the first gate version missed (base 0.019 -> 0.981)
res = sl.leak_findings(synth(6, invert=True))
got = [f[0] for f in res]
check("gate fires on crafted inverted leak", "tool_name" in got, f"flagged={got}")
for nm, base, strength in res:
    if nm == "tool_name":
        check("inverted leak reported as strong", strength >= 0.9,
              f"direct={base:.3f} strength={strength:.3f}")

# ── 3. gate stays SILENT on uncorrelated data ─────────────────────────────
rnd = random.Random(7)
clean = [([rnd.randint(0, 1) for _ in range(7)], [float(rnd.randint(0, 1))])
         for _ in range(60)]
check("gate silent on uncorrelated data", sl.leak_findings(clean) == [],
      f"flagged={sl.leak_findings(clean)}")

# ── 4. threshold is a real bound, not decoration ──────────────────────────
# 0.55 correlation must NOT be flagged at the default 0.70 threshold
weak = []
for i in range(100):
    feats = [0] * 7
    feats[6] = 1.0 if i % 2 == 0 else 0.0
    weak.append((feats, [1.0 if (i % 2 == 0) != (i % 100 >= 55) else 0.0]))
check("threshold respected (weak separator not flagged)", sl.leak_findings(weak) == [],
      f"flagged={sl.leak_findings(weak)}")

# ── 5. live DB: determinism + structural leak ─────────────────────────────
a = sl.extract_training_data(limit=80)
b = sl.extract_training_data(limit=80)
check("extraction deterministic (no ORDER BY RANDOM)",
      [x for x, _y in a] == [x for x, _y in b] and len(a) > 4, f"n={len(a)}")
check("live window flags at least one leak", len(sl.leak_findings(a)) > 0,
      f"flagged={[f[0] for f in sl.leak_findings(a)]}")

# ── 6. ablation zeroes the role feature but does NOT silence the gate ─────
abl = sl.extract_training_data(limit=80, drop_role=True)
check("role feature actually zeroed", all(x[5] == 0.0 for x, _y in abl))
check("second leak survives ablation", len(sl.leak_findings(abl)) > 0,
      f"flagged={[f[0] for f in sl.leak_findings(abl)]}"
      " (empty here would mean the ablation was mistaken for a fix)")

# ── 7. end-to-end: the runner tells the truth on real data ───────────────
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    try:
        exec(compile(TARGET.read_text(encoding="utf-8"), "sl", "exec"),
             {"__name__": "__main__", "__file__": str(TARGET)})
    except SystemExit as e:
        check("runner exit code is 0", e.code in (0, None), f"code={e.code}")
out = buf.getvalue()
check("runner warns instead of claiming learning",
      "NICHT gelernt" in out and "✅ Training abgeschlossen" not in out)
check("runner names the leaking feature", "LEAK-WARNUNG" in out)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
