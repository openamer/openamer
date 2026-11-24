#!/usr/bin/env python3
"""Audit the gate-attribution probe's KNOWN_HELPERS registry against reality.

Why this exists
---------------
`gate_attribution_probe.py --section gate` prints

    N candidate(s) matched an UNKNOWN helper -- likely novel chrome shape

whenever a leaf junk-heuristic it met is missing from its hand-maintained
KNOWN_HELPERS set.  That set is a *mirror* of the helpers defined in
scripts/training/buffer_store.py + internet_learner.py, so it goes stale every time
a new helper lands.  On 21.09.26 it fired four separate times (class 66, a 9-helper
batch, class 90, class 99) and EVERY one resolved to "defined in both modules, just
absent from the set" -- registry staleness, not novel chrome.  Each event cost a
manual two-file `grep -rn "def <helper>"`.

This script does that grep for the WHOLE registry at once.

Output
------
  STALE     defined in BOTH modules, missing from KNOWN_HELPERS -> add them in one
            dated batch (house style), do NOT investigate them as novel chrome.
  ONE-SIDED defined in exactly one module -> informational.
  DEAD      listed in KNOWN_HELPERS but defined in NEITHER module -> typo or the
            helper was deleted; the probe can never hit it.

Read-only, always exits 0: it is a report, not a gate.  Assert on the text
(`=> registry complete` vs `N helper(s) missing`), never on the exit code -- same
rule as the probe itself.

Caveat -- STALE means "not in the registry", not "must be added": KNOWN_HELPERS is a
curated list of *documented* helper shapes, so a helper defined in both modules could
in principle be deliberately undocumented.  Treat a STALE line as a question with the
line numbers already attached, not as an instruction; add the ones that are real
junk-shape guards (that is what every 21.09.26 event turned out to be).

First-run note (authored 21.09.26): the script prints the parse counts and samples it
used on every run, so a bad parse is visible rather than silent.  Sanity-check those
samples against
  grep -rn "def _is_" scripts/training/buffer_store.py | wc -l
before trusting a verdict.  Manual fallback for a single helper:
  grep -rn "def <helper>" scripts/training/buffer_store.py scripts/training/internet_learner.py
"""

import os
import re

HOME = os.environ.get("OPENAMER_HOME") or os.path.join(
    os.path.expanduser("~"), "AppData", "Local", "openamer-laptop")
TRAINING = os.path.join(HOME, "scripts", "training")
PROBE = os.path.join(HOME, "skills", "internet-learning-cycle",
                     "scripts", "gate_attribution_probe.py")
MODULES = [os.path.join(TRAINING, "buffer_store.py"),
           os.path.join(TRAINING, "internet_learner.py")]

NAME = r"(?:is_|_is_)[A-Za-z0-9_]+"
DEF_RE = re.compile(r"^def\s+(" + NAME + r")\s*\(", re.M)
ASSIGN_RE = re.compile(r"^(" + NAME + r")\s*=", re.M)
ENTRY_RE = re.compile(r'"(' + NAME + r')"')


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as exc:
        print(f"  ! cannot read {path}: {exc}")
        return None


def parse_registry(path):
    """Names inside the probe's KNOWN_HELPERS set, or None if unparsable."""
    text = _read(path)
    if text is None:
        return None
    start = text.find("KNOWN_HELPERS = {")
    if start < 0:
        print("  ! 'KNOWN_HELPERS = {' not found -- parse failed")
        return None
    m = re.search(r"^\}", text[start:], re.M)
    if not m:
        print("  ! unterminated KNOWN_HELPERS block -- parse failed")
        return None
    names = set()
    for raw in text[start:start + m.start()].splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue                      # comment lines carry quoted helper names
        line = line.split("#", 1)[0]      # drop the trailing `# store:3348 ...`
        names.update(ENTRY_RE.findall(line))
    return names


def parse_defs(path):
    """Helper names defined in one module, or None if unreadable."""
    text = _read(path)
    if text is None:
        return None
    names = set(DEF_RE.findall(text))
    names.update(ASSIGN_RE.findall(text))
    return names


def line_of(path, name):
    """1-based line of `def <name>(`, for the comment the registry entry needs."""
    pat = re.compile(r"^\s*def\s+" + re.escape(name) + r"\s*\(")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                if pat.match(line):
                    return i
    except OSError:
        pass
    return "?"


def main():
    print("=== known_helpers_audit ===")
    print(f"probe:  {PROBE}")
    for p in MODULES:
        print(f"module: {p}")

    reg = parse_registry(PROBE)
    if reg is None:
        print("VERDICT: cannot audit -- probe registry not parsable")
        return 0

    defs = {}
    for p in MODULES:
        s = parse_defs(p)
        if s is None:
            print(f"VERDICT: cannot audit -- {os.path.basename(p)} not readable")
            return 0
        defs[p] = s

    all_defs = set().union(*defs.values()) if defs else set()
    if not all_defs:
        print("VERDICT: cannot audit -- no helpers parsed from the modules")
        return 0

    print(f"\nregistry entries : {len(reg)}   sample: {sorted(reg)[:3]}")
    for p in MODULES:
        print(f"defs {os.path.basename(p):22s}: {len(defs[p])}   "
              f"sample: {sorted(defs[p])[:3]}")

    both = set.intersection(*defs.values()) if len(defs) > 1 else set(all_defs)
    one_sided = all_defs - both
    stale = both - reg
    dead = reg - all_defs

    if one_sided:
        print(f"\nONE-SIDED (defined in exactly one module, informational): "
              f"{len(one_sided)}")
        for n in sorted(one_sided)[:8]:
            print(f"  {n}")

    if dead:
        print(f"\nDEAD (in KNOWN_HELPERS but defined in NEITHER module): {len(dead)}")
        for n in sorted(dead):
            print(f"  {n}")

    if stale:
        print(f"\nSTALE (defined in BOTH modules, missing from KNOWN_HELPERS): "
              f"{len(stale)}")
        for n in sorted(stale):
            locs = ", ".join(f"{os.path.basename(p)}:{line_of(p, n)}"
                             for p in MODULES)
            print(f"  {n:42s} {locs}")
        print(f"\nN helper(s) missing: {len(stale)}")
        print("  -> registry staleness, NOT novel chrome. Add the real junk-shape")
        print("     guards in ONE batch with a dated comment + line numbers, then")
        print("     re-run verify_gate_probe.sh.")
        print("VERDICT: stale registry -- review the names above")
    else:
        print("\nAll helpers defined in both modules are present in the registry.")
        print("=> registry complete. Any remaining INVESTIGATE alarm is a genuinely")
        print("   novel shape: probe the FULL stored string before touching a rule.")
        print("VERDICT: registry complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
