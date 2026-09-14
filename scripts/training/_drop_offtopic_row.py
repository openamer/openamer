"""One-off: drop an off-topic row from the learning buffer (backup kept).

Learned 2026-09-14: cycle_g_security accepted "The ACL Anthology is a curated,
open-access repository of 131,040 papers ..." as a security insight — a
deep-read extraction artifact that only passed the gate because it contains
numbers. Off-topic chrome in the LoRA buffer is worse than a miss, so it is
removed here. Re-runnable: filters every row whose text matches the marker.
"""
import json
import os
import shutil
import time

BUF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "online_buffer.jsonl")
MARKER = "ACL Anthology is a curated"

with open(BUF, encoding="utf-8") as f:
    rows = [l for l in f if l.strip()]

kept = []
dropped = 0
for line in rows:
    try:
        rec = json.loads(line)
    except Exception:
        kept.append(line)
        continue
    if MARKER in rec.get("a", ""):
        dropped += 1
        continue
    kept.append(line)

if dropped:
    shutil.copyfile(BUF, f"{BUF}.bak.{int(time.time())}")
    with open(BUF, "w", encoding="utf-8") as f:
        f.writelines(kept)
print(f"rows={len(rows)} dropped={dropped} kept={len(kept)}")
