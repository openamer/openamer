#!/usr/bin/env python3
"""Scrub rows that the current quality gate rejects from the training buffer.

The gate was tightened today, so rows written BEFORE the fix may still be
pollutants (e.g. the "Download PDF Download PDF Review Article Open access
Publish" line the multi-domain cycle learned off a PDF landing page). This
moves every rejected row into buffer_junk.jsonl (reason 'pre-existing') and
keeps the accepted rows, with a timestamped backup of the original.
"""
import json, shutil, sys, time
from pathlib import Path

T = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\scripts\training")
sys.path.insert(0, str(T))
import internet_learner as il
from buffer_store import JUNK_LOG, count, enforce_cap  # noqa: E402

buf = Path(il.BUFFER)
backup = buf.with_suffix(f".jsonl.bak.{time.strftime('%Y%m%d_%H%M%S')}")
shutil.copy2(buf, backup)

kept, dropped = [], []
for line in buf.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    rec = json.loads(line)
    a = rec.get("a", "")
    if il._is_junk(a) or not il._clean_insight(a):
        dropped.append(rec)
    else:
        kept.append(rec)

if dropped:
    with open(JUNK_LOG, "a", encoding="utf-8") as f:
        for rec in dropped:
            f.write(json.dumps({"reason": "pre-existing", "u": rec.get("u", ""),
                                "a": rec.get("a", "")}, ensure_ascii=False) + "\n")
    buf.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept),
                   encoding="utf-8")
    enforce_cap(buf)

print(f"kept={len(kept)} dropped={len(dropped)} backup={backup.name}")
for r in dropped:
    print("  DROPPED:", r.get("a", "")[:90])
print("buffer count now:", count(buf))
