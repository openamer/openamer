#!/usr/bin/env python3
"""Read-only diagnostic for auto_skill_creation.py reporting "0 new skills".

Replays the REAL module predicates (load_registry, slugify, clean_text,
is_usable_text, dedupe_check) over the same tail windows the script scans, and
prints a per-line reject reason. Answers "is the 0 genuine exhaustion, a benign
race, or a filter stall?" without guessing.

Writes nothing. Creates no skill dirs. Safe against the live stores.

Usage:
    python replay_auto_skill_filters.py
    python replay_auto_skill_filters.py --kta 20 --buf 40
"""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

# Same resolution as every scripts/training/*.py — env first, then the profile dir.
HOME = os.environ.get(
    "OPENAMER_HOME",
    str(Path.home() / "AppData" / "Local" / "openamer-laptop"),
)
TRAINING = Path(HOME) / "scripts" / "training"
MODULE = TRAINING / "auto_skill_creation.py"

BUFFER_KEYWORDS = ["trending", "best practice", "research", "competitor", "breakthrough"]


def load_module():
    if not MODULE.is_file():
        sys.exit(f"ABORT: module not found: {MODULE}\n"
                 f"       (is OPENAMER_HOME correct? current: {HOME})")
    spec = importlib.util.spec_from_file_location("auto_skill_creation", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replay(mod, path, n, key_q, key_a, min_len, kw=None, gap_key=None):
    """Replay one source pass. Returns counts + list of unconverted candidates."""
    counts = {"lines": 0, "badjson": 0, "no_question": 0, "filtered": 0,
              "too_short": 0, "unreadable": 0, "duplicate": 0, "candidate": 0}
    unconverted = []
    if not path.is_file():
        print(f"  {path.name}: MISSING")
        return counts, unconverted

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(True)[-n:]
    counts["lines"] = len(lines)
    registry = mod.load_registry()

    for line in lines:
        try:
            d = json.loads(line)
        except Exception:
            counts["badjson"] += 1
            continue
        q, a = d.get(key_q, ""), d.get(key_a, "")
        if not q:
            counts["no_question"] += 1
            continue
        if kw and not any(k in q.lower() for k in kw):
            counts["filtered"] += 1
            continue
        if gap_key and d.get(gap_key):
            a = f"{a} GAP: {d[gap_key]}"
        if len(a) <= min_len:
            counts["too_short"] += 1
            continue
        cleaned = mod.clean_text(a)
        if not mod.is_usable_text(cleaned):
            counts["unreadable"] += 1
            print(f"  unreadable (would print 'skipped unreadable insight'): {q[:60]}")
            continue
        name = "auto-" + mod.slugify(q)
        if mod.dedupe_check(name, cleaned[:150].strip(), registry):
            counts["duplicate"] += 1
            continue
        counts["candidate"] += 1
        unconverted.append(name)
        print(f"  SURVIVES ALL PREDICATES BUT WAS NOT CREATED -> {name}")
        print(f"      desc[:50]: {cleaned[:50]!r}")
    return counts, unconverted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kta", type=int, default=10,
                    help="kta_log.jsonl tail size (script default: 10)")
    ap.add_argument("--buf", type=int, default=30,
                    help="online_buffer.jsonl tail size (script default: 30)")
    args = ap.parse_args()

    mod = load_module()
    registry = mod.load_registry()
    names = {c.get("name") for c in registry.get("created", []) if isinstance(c, dict)}
    print(f"OPENAMER_HOME : {HOME}")
    print(f"registry      : {registry.get('count')} count / {len(names)} unique names")
    print(f"skills dir    : {mod.AUTO_SKILLS}")
    if os.path.isdir(mod.AUTO_SKILLS):
        print(f"on-disk dirs  : {len(os.listdir(mod.AUTO_SKILLS))}")
    else:
        print("on-disk dirs  : <missing>")
    print("  (count > unique names means the description guard historically let "
          "duplicates through — a rising gap is a regression signal)")

    print(f"\n--- kta_log.jsonl (last {args.kta}, keys insight_question/insight_answer) ---")
    kta_counts, kta_unc = replay(
        mod, Path(mod.KTA_LOG), args.kta,
        "insight_question", "insight_answer", 40, gap_key="identified_gap",
    )
    print(f"  {kta_counts}")

    print(f"\n--- online_buffer.jsonl (last {args.buf}, keys u/a, "
          f"keyword-gated on {BUFFER_KEYWORDS}) ---")
    buf_counts, buf_unc = replay(
        mod, Path(mod.BUFFER), args.buf, "u", "a", 80, kw=BUFFER_KEYWORDS,
    )
    print(f"  {buf_counts}")

    total = kta_counts["candidate"] + buf_counts["candidate"]
    print("\n=== VERDICT ===")
    if total:
        print(f"{total} insight(s) pass every filter but produced no skill.")
        print("Re-run auto_skill_creation.py once: a late insight appended after the "
              "cron read its tail (internet_learner and auto-skill both fire at :30) "
              "is picked up immediately. If they are STILL not created, the replay's "
              "predicates diverge from the module — re-read create_skill_from_insight().")
    elif kta_counts["duplicate"] or buf_counts["duplicate"]:
        print("0 candidates: all insights already have skills (duplicate slugs). "
              "Genuine exhaustion — this is the benign 0. Nothing to fix.")
    elif buf_counts["filtered"]:
        print("0 candidates. Note the buffer pass rejected "
              f"{buf_counts['filtered']}/{buf_counts['lines']} lines on the keyword gate "
              "(source `u` lacks trending/best practice/research/competitor/"
              "breakthrough). Those insights still convert via the kta pass — this is "
              "by design, not a stall.")
    else:
        print("0 candidates and no duplicates — inspect the per-line output above: "
              "captures may be too short or unreadable. Fix the upstream learner's "
              "capture quality, not this script.")


if __name__ == "__main__":
    main()
