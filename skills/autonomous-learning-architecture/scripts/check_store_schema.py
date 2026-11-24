#!/usr/bin/env python3
"""Audit a shared JSONL store for foreign-schema / partial records.

Live 12.09.26: longterm_episodes.jsonl carried one Discord-blocker record
({timestamp, type, summary, action_needed} — no `text`/`embedding`) and
crashed longterm_memory.py's index_brain() with KeyError: 'text'.

Read-only. Prints the keyset histogram, the "bad" records, and a JSON summary.
Never edits the store — repair is a separate, deliberate step (quarantine +
backup), see references/longterm-store-foreign-record-repair.md.

Usage:
  python check_store_schema.py                          # defaults to the episode store
  python check_store_schema.py <path.jsonl> [--expect text,embedding]
"""
import collections
import json
import os
import sys

DEFAULT_STORE = os.path.join(
    os.environ.get("OPENAMER_HOME", r"C:/Users/damir/AppData/Local/openamer-laptop"),
    "memory", "longterm_episodes.jsonl")


def audit(path, expect=("text", "embedding")):
    n = malformed = 0
    keysets = collections.Counter()
    bad = []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                d = json.loads(line)
            except Exception as exc:                      # malformed JSON
                malformed += 1
                bad.append({"line": i, "reason": "json", "detail": str(exc)[:120]})
                continue
            if not isinstance(d, dict):
                bad.append({"line": i, "reason": "not-a-dict", "detail": repr(d)[:80]})
                continue
            keysets[tuple(sorted(d.keys()))] += 1
            missing = [k for k in expect if k not in d]
            if missing:
                bad.append({"line": i, "reason": "missing " + ",".join(missing),
                            "detail": json.dumps(d, ensure_ascii=False)[:200]})
    return {"path": path, "total_lines": n, "malformed": malformed,
            "expect": list(expect), "foreign_or_partial": len(bad),
            "keysets": {" | ".join(k): v for k, v in keysets.most_common()},
            "bad_samples": bad[:10]}


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    expect = ("text", "embedding")
    for a in sys.argv[1:]:
        if a.startswith("--expect"):
            expect = tuple(x.strip() for x in a.split("=", 1)[1].split(","))
    path = argv[0] if argv else DEFAULT_STORE
    if not os.path.exists(path):
        print(json.dumps({"error": "not found", "path": path}, indent=1))
        sys.exit(2)
    print(json.dumps(audit(path, expect), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
