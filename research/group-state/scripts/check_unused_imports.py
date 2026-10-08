#!/usr/bin/env python3
"""Find unused imports / obvious dead locals in the research scripts.

Cheap AST check, no linter dependency: a name imported but never referenced
elsewhere in the module is either dead weight or a sign the module was edited
without cleaning up.
"""
import ast
import os
import sys

SCRIPTS = [
    "state_tracking_lab.py", "diagnose_rotor_drift.py", "cyclic_state_lab.py",
    "rotor_snap_lab.py", "rotor_snap_warmup.py", "validate_rotor_snap.py",
    "final_comparison.py", "gradcheck_cyclic_state.py",
    "gradcheck_eps_sweep.py", "research_arxiv_probe.py",
]
BASE = "scripts"

problems = 0
for name in SCRIPTS:
    path = os.path.join(BASE, name)
    if not os.path.isfile(path):
        print(f"  MISSING {path}")
        continue
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported[(a.asname or a.name).split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    imported[a.asname or a.name] = node.lineno
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            pass
    # also count names appearing inside attribute chains / strings-free
    raw = src
    dead = []
    for n, ln in imported.items():
        # count textual occurrences beyond the import line
        occurrences = sum(1 for line in raw.splitlines()
                          if n in line)
        if occurrences <= 1 and n not in used:
            dead.append((n, ln))
    if dead:
        problems += len(dead)
        print(f"  {name}:")
        for n, ln in dead:
            print(f"      unused import '{n}' (line {ln})")
    else:
        print(f"  OK   {name}")

print()
print(f"unused imports found: {problems}")
sys.exit(1 if problems else 0)
