"""Rate analysis: per-source and per-hour learned/rejected from internet_learn_log.jsonl."""
import json, collections
from datetime import datetime

rows = [json.loads(l) for l in open(
    "C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/internet_learn_log.jsonl",
    encoding="utf-8") if l.strip()]

print("total logged cycles:", len(rows))


def ok(r):
    return "rejected" not in r["result"] and "no insight" not in r["result"]


print("\n=== per source (all time) ===")
by = collections.defaultdict(lambda: [0, 0])
for r in rows:
    by[r["source"]][0 if ok(r) else 1] += 1
for s in sorted(by):
    g, b = by[s]
    print(f"  {s:26} learned={g:3} rejected={b:3}  rate={g/(g+b)*100:5.1f}%")

print("\n=== overall last N ===")
for n in (10, 20, 40, 60, 100, len(rows)):
    sub = rows[-n:]
    g = sum(1 for r in sub if ok(r))
    print(f"  last {n:4}: {g}/{len(sub)} learned = {g/len(sub)*100:5.1f}%")

print("\n=== per hour (last 12) ===")
byh = collections.defaultdict(lambda: [0, 0])
for r in rows:
    h = r["ts"][:13]
    byh[h][0 if ok(r) else 1] += 1
for h in sorted(byh)[-12:]:
    g, b = byh[h]
    print(f"  {h}  learned={g:3} rejected={b:3}  rate={g/(g+b)*100:5.1f}%")

print("\n=== per source, LAST 30 cycles only ===")
by2 = collections.defaultdict(lambda: [0, 0])
for r in rows[-30:]:
    by2[r["source"]][0 if ok(r) else 1] += 1
for s in sorted(by2):
    g, b = by2[s]
    print(f"  {s:26} learned={g:3} rejected={b:3}  rate={g/(g+b)*100:5.1f}%")

print("\n=== elapsed_s stats ===")
el = [r.get("elapsed_s", 0) for r in rows[-30:]]
print(f"  last30: n={len(el)} mean={sum(el)/len(el):.0f}s max={max(el):.0f}s")
