#!/usr/bin/env python3
"""One-time cleanup: strip junk + exact duplicates from the online buffer.

The buffer feeds both the rolling CPU LoRA and (via replay) the nightly
training data, so junk rows must be removed from the STORE, not only blocked
at the writer — online_learning's replay branch re-injects old rows.

Archives every removed row to `buffer_junk_archive.jsonl` (never silent, never
destructive) and rewrites the buffer with the survivors. Refuses to write an
empty result (an empty read is a bug, not an intent).
"""
import json
import sys
from pathlib import Path

T = Path(__file__).parent
sys.path.insert(0, str(T))
import buffer_store as bs

BUF = T / "online_buffer.jsonl"
ARCHIVE = T / "buffer_junk_archive.jsonl"


def main():
    rows = [json.loads(l) for l in open(BUF, encoding="utf-8") if l.strip()]
    keep, drop = [], []
    seen = set()
    for r in rows:
        a = r.get("a", "")
        if bs.is_junk(a):
            drop.append((r, "junk"))
            continue
        # An empty/whitespace completion is not "junk" by contract (a caller may
        # legitimately record a placeholder) — but it teaches a LoRA nothing, so
        # the STORE cleanup drops it. is_junk stays unchanged to honour that.
        if not (a or "").strip():
            drop.append((r, "empty"))
            continue
        key = json.dumps(r, ensure_ascii=False, sort_keys=True)
        if key in seen:
            drop.append((r, "duplicate"))
            continue
        seen.add(key)
        keep.append(r)

    if not keep:
        print(json.dumps({"error": "refused: result would be empty",
                          "total": len(rows)}))
        return 1

    with open(ARCHIVE, "a", encoding="utf-8") as f:
        for r, reason in drop:
            f.write(json.dumps({"reason": reason, **r}, ensure_ascii=False) + "\n")

    tmp = BUF.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(BUF)

    from collections import Counter
    reasons = Counter(x[1] for x in drop)
    print(json.dumps({
        "ok": True, "before": len(rows), "after": len(keep),
        "removed": len(drop), "reasons": dict(reasons),
        "archive": ARCHIVE.name,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
