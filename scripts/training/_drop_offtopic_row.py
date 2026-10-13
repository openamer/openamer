"""Drop off-topic / chrome rows from the learning buffer (backup kept).

Learned 2026-09-14: cycle_g_security accepted "The ACL Anthology is a curated,
open-access repository of 131,040 papers ..." as a security insight — a
deep-read extraction artifact that only passed the gate because it contains
numbers. Off-topic chrome in the LoRA buffer is worse than a miss, so it is
removed here.

Usage:
    python3 _drop_offtopic_row.py                       # default marker (ACL row)
    python3 _drop_offtopic_row.py "CIOs are paying" "ACL Anthology"

Every argument is a case-sensitive substring of the row's answer text; rows
matching ANY marker are dropped. Re-runnable: the buffer is backed up to
online_buffer.jsonl.bak.<ts> before any write, and each dropped row is appended
to buffer_junk.jsonl with reason "offtopic-drop" for the audit trail.
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BUF = os.path.join(HERE, "online_buffer.jsonl")
JUNK = os.path.join(HERE, "buffer_junk.jsonl")
DEFAULT_MARKERS = ["ACL Anthology is a curated"]

markers = sys.argv[1:] or DEFAULT_MARKERS

with open(BUF, encoding="utf-8", newline="") as f:
    rows = [l for l in f if l.strip()]

kept = []
dropped_rows = []
for line in rows:
    try:
        rec = json.loads(line)
    except Exception:
        kept.append(line)
        continue
    text = rec.get("a", "")
    if any(m in text for m in markers):
        dropped_rows.append(line)
        continue
    kept.append(line)

if dropped_rows:
    shutil.copyfile(BUF, f"{BUF}.bak.{int(time.time())}")
    with open(BUF, "w", encoding="utf-8", newline="") as f:
        f.writelines(kept)
    with open(JUNK, "a", encoding="utf-8", newline="") as f:
        for line in dropped_rows:
            try:
                u = json.loads(line).get("u", "")
            except Exception:
                u = ""
            f.write(json.dumps({"reason": "offtopic-drop", "u": u, "a": line.strip()[:300]},
                               ensure_ascii=False) + "\n")

print(f"rows={len(rows)} dropped={len(dropped_rows)} kept={len(kept)} markers={markers}")
