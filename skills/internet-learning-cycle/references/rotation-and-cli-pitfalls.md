# Rotation advance + CLI pitfalls (measured 12.10.26)

## The remedy for one rejected cycle is one more `--once` — not a fix

`--once` runs `run_one()` -> `next_cycle()`. `next_cycle()` reads an integer
rotation counter from `scripts/training/.il_rotation` (`ROT`), writes it back
**+1**, and executes `CYCLES[n % len(CYCLES)]`.

`CYCLES` has **8** entries, in order:

1. `cycle_a_technews`
2. `cycle_b_papers`
3. `cycle_c_github`
4. `cycle_d_docs`
5. `cycle_e_competitors`
6. `cycle_f_multi_domain`
7. `cycle_g_security`
8. `cycle_h_efficiency`

The cron prompt's "learns from one of 5 sources" is **stale** — it is 8.

So a single `rejected, not trained (shallow + deep read both gated)` is not a
stall: re-running `--once` advances the pointer to the NEXT source and usually
lands an accept.

**Verified example.** 12.10.26: run #1 hit `cycle_e_competitors` -> rejected
(97.3 s). `cat scripts/training/.il_rotation` showed `3149`; `3149 % 8 = 5` ->
next pick `cycle_f_multi_domain`. Run #2 stored a new row: "NASA, IBM Research
Release New AI Model for Weather, Climate" (40.4 s).

`cycle_e_competitors` in particular gates intermittently — as of 12.10.26 the
log held **1029** `both gated` lines, with e-rejections clustered at
02:02/06:07/10:01/11:18/11:42 alternating with accepts at
02:01/08:30/10:41/11:26. Roughly a coin flip on that source; expected, not a bug.

## Verify the accept by the buffer, not stdout

`run_one()` prints the result line, but the durable proof is a new last row in
`scripts/training/online_buffer.jsonl`. Its `u` field begins with the source
label, e.g. `Multi-domain learning (NASA, IBM Research ...)`. Confirm a row
whose timestamp matches your run before reporting "learned".

Report a gated rejection honestly in the same breath — it is normal noise, and
saying so is worth more than a confident "learned X" that didn't store.

## Pitfall — `--help` does NOT print help; it hangs

There is no `argparse`. `__main__` does:

```python
mode = sys.argv[1].lstrip("-") if len(sys.argv) > 1 else ""
if mode == "loop":   run_loop(int(sys.argv[2]) if len(sys.argv) > 2 else 600)
elif mode == "once": run_one()
else:
    print("=== RUNNING ALL 5 SOURCES ONCE (test) ===")
    for c in CYCLES: ...   # runs EVERY cycle
```

So `python internet_learner.py --help` -> mode `"help"` -> the **else** branch,
which runs all 8 cycles live and looks like a >120 s hang.

Do not invoke `--help`. To learn the flags, grep the file for `__main__` /
`add_argument` / `sys.argv`; otherwise just call `--once`.

## Tool server gate (unchanged)

Check `curl -s -m 8 http://localhost:8081/health` first. `{"status": "alive",
"tools": N, "swaps": 0}` means it is up — do not restart. Restart only on empty
output, using the training venv interpreter (plain `python` has no torch) per
the main SKILL.md.
