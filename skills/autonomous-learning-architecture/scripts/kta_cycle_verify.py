#!/usr/bin/env python3
"""Run one KTA cycle AND prove it was recorded.

Calls knowledge_to_action.kta_cycle() in-process and counts kta_log.jsonl lines
before/after, so the result is evidence (APPENDED=True) rather than stdout only.

Usage:
    python kta_cycle_verify.py            # defaults to the live install
    python kta_cycle_verify.py <training_dir>

Windows note: run this from a short path (e.g. %TEMP%) if the shell stalls on
long paths; module resolution is done via an explicit sys.path insert.
"""
import json
import os
import runpy
import sys

TF = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.expanduser("~"), "AppData", "Local", "openamer-laptop", "scripts", "training"
)
sys.path.insert(0, TF)

KTA = os.path.join(TF, "knowledge_to_action.py")
LOG = os.path.join(TF, "kta_log.jsonl")
ROT = os.path.join(TF, ".kta_rotation")


def count(path):
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


if not os.path.exists(KTA):
    print("ERROR: knowledge_to_action.py not found at %s" % KTA)
    raise SystemExit(2)

before = count(LOG)
mod = runpy.run_path(KTA)
entry = mod["kta_cycle"]()
after = count(LOG)

print("LOG_LINES_BEFORE=%d AFTER=%d APPENDED=%s" % (before, after, after > before))
if not after > before:
    print("WARN: no log line appended -> no cycle recorded "
          "(see references/kta-cycle-verification.md pitfalls)")
print("ENTRY=" + json.dumps(
    {k: v for k, v in (entry or {}).items()
     if k in ("ts", "experiment", "action", "result", "predicted_from",
              "identified_gap", "lesson", "next")},
    ensure_ascii=False))
rot = open(ROT, encoding="utf-8").read().strip() if os.path.exists(ROT) else "none"
print("ROTATION=" + rot)
