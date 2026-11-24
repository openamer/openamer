#!/usr/bin/env python3
"""AST hygiene probe: find DEAD NAMES and DUPLICATE FUNCTION BODIES.

WHY THIS EXISTS
---------------
A research session built a gate suite for its own scripts and this probe found
three real defects that no compiler catches:

  * dead names   -- gen_index, GEN_NAMES, _hard_perm, forward_exact_state
  * duplicate    -- choice_accuracy was copied verbatim into 3 scripts
                    (consolidated to one canonical definition)
  * wrong-scope  -- an earlier scan over ALL of scripts/ reported ~45 "dead"
                    functions, almost all PRE-EXISTING in other people's files.
                    That noise invites a diff touching foreign code.

USAGE
-----
    python ast-hygiene-probe.py scripts/s5_*.py scripts/perm_state_lab.py
    python ast-hygiene-probe.py scripts/ --dead --dups
    python ast-hygiene-probe.py scripts/*.py --min-body 4 --json

Exit codes: 0 = clean, 1 = findings. Usable as a gate stage.

SCOPE DISCIPLINE (the whole point)
----------------------------------
Pass ONLY the files you are working on. Cross-file resolution is deliberate:
a helper defined in A and imported by B is NOT dead, so B must be in the file
list. Including unrelated files is what produces the ~45-false-positive scan.
"""
import argparse
import ast
import glob
import json
import os
import re
import sys


def expand(patterns):
    """Files or globs or DIRECTORIES -> list of .py files.

    A directory must be expanded, not returned: passing `scripts/` straight
    through makes read() skip it as not-a-file, and the probe would then report
    ZERO findings on ZERO parsed files = a FALSE CLEAN. That is the same
    failure class as a counter that can only move one way.
    """
    out = []
    for p in patterns:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                out.extend(os.path.join(root, f) for f in files
                           if f.endswith(".py"))
            continue
        hits = glob.glob(p)
        if hits:
            out.extend(h for h in hits if h.endswith(".py"))
        elif os.path.isfile(p):
            out.append(p)
    return sorted(set(out))


def read(path):
    try:
        return open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return None


def normalise_constant(node):
    """Mask string/int literals so differing log text does not hide a clone."""
    for n in ast.walk(node):
        if isinstance(n, ast.Constant):
            n.value = "<S>"


def fingerprint(fn):
    body = ast.Module(body=fn.body, type_ignores=[])
    normalise_constant(body)
    dump = ast.dump(body)
    return re.sub(r"\s+", "", dump)


def collect(paths):
    """names = {name: n_definitions}, bodies = {fingerprint: [where]}"""
    names, bodies, sources = {}, {}, {}
    for p in paths:
        src = read(p)
        if src is None:
            continue
        sources[p] = src
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            print(f"  SKIP (syntax error) {p}: {e}")
            continue

        def note(nm, where):
            names.setdefault(nm, []).append(where)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                note(node.name, f"{p}:{node.name}")
                if len(node.body) >= MIN_BODY:
                    bodies.setdefault(fingerprint(node), []).append(
                        f"{p}:{node.name}")
            elif isinstance(node, ast.ClassDef):
                note(node.name, f"{p}:{node.name}")
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        note(m.name, f"{p}:{node.name}.{m.name}")
                        if len(m.body) >= MIN_BODY:
                            bodies.setdefault(fingerprint(m), []).append(
                                f"{p}:{node.name}.{m.name}")
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id.isupper():
                        note(t.id, f"{p}:{t.id}")
    return names, bodies, sources


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="files or globs IN YOUR SCOPE")
    ap.add_argument("--dead", action="store_true", help="report dead names")
    ap.add_argument("--dups", action="store_true", help="report clones")
    ap.add_argument("--all", action="store_true", help="both checks (default)")
    ap.add_argument("--min-body", type=int, default=3,
                    help="ignore bodies shorter than N statements (default 3)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    global MIN_BODY
    MIN_BODY = args.min_body
    do_dead = args.dead or args.all or not (args.dead or args.dups)
    do_dups = args.dups or args.all or not (args.dead or args.dups)

    paths = expand(args.paths)
    if not paths:
        print("no files matched")
        return 2

    names, bodies, sources = collect(paths)
    if not sources:
        # Parsing nothing must NEVER read as a clean result.
        print(f"ERROR: {len(paths)} path(s) matched but 0 files parsed -- "
              f"refusing to report clean")
        return 2
    corpus = "\n".join(sources.values())

    # a name is dead when its ONLY definition-site occurrence is the definition.
    # Dunder names are excluded: __init__/__enter__/__exit__/__iter__ are called by
    # the language's protocols, never by name in the source, so a source-occurrence
    # count can only ever call them dead. Measured 2026-10-11: a class with a
    # context manager reported three dead methods that were all live.
    dead = []
    def is_protocol_name(nm: str) -> bool:
        return nm.startswith('__') and nm.endswith('__')
    for nm, where in names.items():
        if len(re.findall(r"\b" + re.escape(nm) + r"\b", corpus)) <= 1 and not is_protocol_name(nm):
            dead.append({"name": nm, "where": where[0]})

    dups = [{"sites": v} for v in bodies.values() if len(v) > 1]

    if args.json:
        print(json.dumps({"files": len(paths), "dead": dead, "dups": dups},
                         indent=1))
    else:
        print(f"scope: {len(paths)} file(s), min-body={MIN_BODY}")
        if do_dead:
            print(f"\n-- dead names ({len(dead)}) --")
            for d in dead:
                print(f"  {d['where']}")
            if not dead:
                print("  none")
        if do_dups:
            print(f"\n-- duplicate bodies ({len(dups)}) --")
            for d in dups:
                print("  " + "  ==  ".join(d["sites"]))
            if not dups:
                print("  none")
        # Reminder, because over-broad scope is the known failure mode
        print("\nnote: same-named methods of DIFFERENT classes are not clones,")
        print("      and cross-file helpers are not dead -- keep scope tight.")

    return 1 if (dead or dups) else 0


if __name__ == "__main__":
    sys.exit(main())
