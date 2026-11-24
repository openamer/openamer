# Running one `--once` cycle: triage recipe, rotation, and record locations

Measured 2026-10-12 during an unattended cron run. Complements the stall
calibration already in SKILL.md — this is the **run mechanics and reading**
half, no new gate class.

## 0. Triage order (cheapest first)

1. `curl -s -m 8 http://localhost:8081/health` → expect
   `{"status": "alive", "tools": N, "swaps": M}`. Empty = tool server down →
   restart with the **training venv** interpreter (`venv/Scripts/python.exe
   scripts/training/tool_server.py`, hidden window), wait ~60 s for the CPU
   model load, re-check `/health` until alive.
2. Run ONE cycle: `venv/Scripts/python.exe scripts/training/internet_learner.py --once`.
3. If it reports `rejected, not trained (shallow + deep read both gated)` →
   **re-run `--once` once**. Do not start diagnosing gates.
4. Only if the whole log window is rejects → this becomes a stall investigation.

## 1. One gated line is not a stall (re-measured)

`internet_learn_log.jsonl`, last 28 rows on 2026-10-12:

```
13 x "rejected, not trained (shallow + deep read both gated)"
15 x real learns (learned / doc-learn / paper-learn / github-learn /
     competitor-learn / domain-learn / security-learn / efficiency-learn)
```

~46% reject with accepts interleaved all day (17:08 efficiency, 17:03 security,
16:54 competitor, 16:16 domain, 16:15 docs, 16:01 + 16:33 technews). This is the
same picture as the 23.09.26 measurement in SKILL.md (65/152 = 43%). The stall
condition is "all rows rejected over a window", never a single row.

Dump with **whole** rows, not a key allow-list:

```bash
cd C:/Users/damir/AppData/Local/openamer-laptop
tail -30 scripts/training/internet_learn_log.jsonl | \
  venv/Scripts/python.exe -c "
import sys,json
for l in sys.stdin:
    l=l.strip()
    if not l: continue
    d=json.loads(l)
    print(d.get('ts','')[:19],'|',d.get('source',''),'|',str(d.get('result'))[:150])
"
```

Pitfall: a key allow-list that omits `result` makes the log look like it only
carries `ts`+`source` and hides the accept/reject signal entirely.

## 2. Escape a gated cycle by running `--once` again

`internet_learner.py` ~L6985-6996:

```python
CYCLES = [cycle_a_technews, cycle_b_papers, cycle_c_github, cycle_d_docs,
          cycle_e_competitors, cycle_f_multi_domain, cycle_g_security,
          cycle_h_efficiency]

def next_cycle():
    n = int(open(ROT).read().strip() or 0)
    c = CYCLES[n % len(CYCLES)]
    open(ROT, "w").write(str(n + 1))
    return c
```

Every `--once` takes the **next** source in order — not random, not "the last
one". A gated source is therefore neither sticky nor that source's fault.
Measured: run 1 → `cycle_c_github` rejected (55.5 s); run 2 → `cycle_d_docs`
learned (77.7 s). One retry was the entire fix.

## 3. `--help` runs ALL 8 sources (there is no argparse)

```python
mode = sys.argv[1].lstrip("-") if len(sys.argv) > 1 else ""
if mode == "loop":   run_loop(int(sys.argv[2]) if len(sys.argv) > 2 else 600)
elif mode == "once": run_one()
else:                # ANY other argv, including --help and a typo
    print("=== RUNNING ALL 5 SOURCES ONCE (test) ===")
    for c in CYCLES:
        print(f"  {c.__name__}: {c()}")
```

A typo'd flag or no argument at all also lands in `else`. The full sweep is
synchronous and ~1 min per source, so it presents as a silent hang that trips a
60 s terminal timeout with no output. Never invoke `--help` here.

## 4. Where the real record of a learn lives

| Path | Holds |
|---|---|
| `scripts/training/internet_learn_log.jsonl` | one row per run: `ts`, `source`, `result`, `elapsed_s`; **`result` truncated ~100 chars** |
| `scripts/training/online_buffer.jsonl` | the stored training pair, keys `u` (framing) + `a` (distilled insight); same-second append as the log row → read the tail for full text |
| `scripts/training/buffer_junk.jsonl` | audit of every gate rejection |

**Stale-file trap:** `scripts/training/last_internet_learn.txt` looks like the
authoritative "last learn" record, but its content is from 2026-09-11 and is
**UTF-16** (reads back as interleaved NULs). The current code path does not
write it. Never cite it as the source of truth.

## 5. Distill drift ≠ gate failure

A stored `a` can be noticeably generic relative to its `u` — e.g.
`u` = "vLLM optimization best practices limitations and failure modes" →
`a` = a paragraph about "pre-processing and data augmentation to improve the
quality of the training data". The row is still written and the cycle still
reports success. Don't report that as a failed cycle; if it recurs it belongs to
the distill-prompt / language classes (SKILL.md class 164 territory), not the gate.
