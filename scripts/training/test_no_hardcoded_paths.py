#!/usr/bin/env python3
"""Guard: no hardcoded user paths may enter the repo's training scripts.

The repo uses the OPENAMER_HOME convention (portable). The AppData copy uses
hardcoded C:/Users/damir/... paths. A blind `cp` from AppData -> repo silently
reintroduces hardcoded paths and breaks portability — this happened twice.

This test fails if any hardcoded absolute user path leaks into the repo's
scripts/training/*.py, so the mistake is caught at commit time instead of
after the fact.

Run:  python test_no_hardcoded_paths.py
"""
import os, sys, re

REPO_TRAINING = os.path.dirname(os.path.abspath(__file__))

# Patterns that must NOT appear in repo training scripts
HARDCODED = re.compile(
    r"C:/Users/|C:\\Users/|/c/Users/|/home/[a-z]+/|/Users/[a-z]+/"
)


def _py_files():
    out = []
    for root, _, files in os.walk(REPO_TRAINING):
        for f in files:
            if f.endswith(".py") and not f.startswith("test_"):
                out.append(os.path.join(root, f))
    return out


def test_no_hardcoded_paths():
    offenders = []
    for path in _py_files():
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            if HARDCODED.search(line):
                # allow the OPENAMER_HOME fallback default (it's a portable
                # default, not a hardcoded machine path)
                if "OPENAMER_HOME" in line or "pathlib.Path.home()" in line:
                    continue
                offenders.append(f"{os.path.basename(path)}:{i}: {line.strip()[:80]}")
    assert not offenders, (
        "hardcoded user paths leaked into repo training scripts:\n"
        + "\n".join(offenders)
    )


if __name__ == "__main__":
    try:
        test_no_hardcoded_paths()
        print("  [PASS] no hardcoded paths in repo training scripts")
        sys.exit(0)
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        sys.exit(1)
