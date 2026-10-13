#!/usr/bin/env python3
"""Memory entry scoring: importance x recency x references (auto-dream index idea).

MEMORY.md entries are separated by a lone "§" line. auto-dream scores memory
by importance x recency x references and decays/archives -- never deletes.
We adapt the *idea* to MEMORY.md scale: no archive yet, just a ranked view so
pruning/consolidation decisions stop being gut feel.

Scoring
  importance : keyword weight (VOLLMACHT/vision/cost/bug/security > neutral)
  recency    : entries that mention a date/version decay with age
  references : how many *other* files in the workspace mention the entry's
               distinctive tokens (a fact cited elsewhere is load-bearing)

Usage: memory_score.py [--top N] [--json]
Exit 0 always. Read-only.
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

OA_HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
MEM = OA_HOME / "memories" / "MEMORY.md"

# importance keywords -> weight
IMPORTANT = {
    "vollmacht": 3.0, "vision": 2.5, "monetaris": 2.5, "cost": 2.0, "kosten": 2.0,
    "bug": 1.8, "fix": 1.6, "security": 2.2, "default": 1.8, "single-source": 2.2,
    "falle": 2.0, "pitfall": 2.0, "nie ": 2.0, "no-": 1.4, "werkzeug": 1.2,
}
EVERGREEN = ("vision", "vollmacht", "single-source", "regel", "rule", "prinzip")


def parse_entries(text):
    """Split MEMORY.md on lone § lines, return list of (index, entry)."""
    parts = re.split(r"^\s*§\s*$", text, flags=re.M)
    out = []
    for i, p in enumerate(parts):
        e = p.strip()
        if e:
            out.append((i, e))
    return out


def corpus(ref_dir):
    """Concatenate small-ish text files for reference counting."""
    blob = []
    for pat in ("skills/**/*.md", "reports/*.md", "memory/self_model/*.md"):
        for f in OA_HOME.glob(pat):
            try:
                if f.stat().st_size < 400_000:
                    blob.append(f.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
    return "\n".join(blob).lower()


def tokens(entry, k=6):
    words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{4,}", entry)
    # distinctive = longest / least common-ish; keep insertion order unique
    seen, out = set(), []
    for w in sorted(words, key=len, reverse=True):
        lw = w.lower()
        if lw not in seen:
            seen.add(lw)
            out.append(lw)
        if len(out) >= k:
            break
    return out


def score(entry, blob):
    low = entry.lower()
    imp = 1.0
    for kw, w in IMPORTANT.items():
        if kw in low:
            imp = max(imp, w)
    if any(e in low for e in EVERGREEN):
        imp += 0.5

    # recency: penalty only if the entry carries a date and looks time-bound
    rec = 1.0
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{2,4})", entry)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            y = y + 2000 if y < 100 else y
            age_days = (datetime.now() - datetime(y, mo, d)).days
            if age_days > 30 and not any(e in low for e in EVERGREEN):
                rec = max(0.4, 1.0 - age_days / 365.0)
        except Exception:
            pass

    toks = tokens(entry)
    refs = sum(1 for t in toks if t in blob)
    ref_score = 1.0 + min(refs, 6) * 0.25

    total = imp * rec * ref_score
    return {
        "importance": round(imp, 2), "recency": round(rec, 2),
        "refs": refs, "ref_score": round(ref_score, 2), "total": round(total, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not MEM.exists():
        print(f"MEMORY.md not found at {MEM}")
        return 0
    text = MEM.read_text(encoding="utf-8", errors="ignore")
    entries = parse_entries(text)
    blob = corpus(OA_HOME)

    rows = []
    for i, e in entries:
        s = score(e, blob)
        rows.append({"i": i, "head": e.splitlines()[0][:70], "chars": len(e), **s})

    rows.sort(key=lambda r: r["total"])
    if a.json:
        print(json.dumps({"count": len(rows), "mean_total": round(
            sum(r["total"] for r in rows) / max(1, len(rows)), 2), "rows": rows},
            indent=2, ensure_ascii=False))
        return 0

    print(f"MEMORY SCORE (importance x recency x references)  entries={len(rows)}")
    print("=" * 92)
    print(f"{'total':>6} {'imp':>5} {'rec':>5} {'refs':>5} {'chars':>6}  entry")
    print("-" * 92)
    show = rows[: a.top] if a.top else rows
    for r in show:
        print(f"{r['total']:>6} {r['importance']:>5} {r['recency']:>5} {r['refs']:>5} "
              f"{r['chars']:>6}  {r['head']}")
    print("=" * 92)
    weak = [r for r in rows if r["total"] < 2.0]
    print(f"low-value candidates (<2.0): {len(weak)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
