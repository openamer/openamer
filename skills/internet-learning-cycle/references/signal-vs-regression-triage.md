# Triage: when a SIGNAL says "something is wrong" but nothing is

Two measured cases (21.09.26, cron `cycle_h_efficiency`) where the honest conclusion —
recorded after real tool output — was *nothing is broken*. Both are signal-reading errors,
not regressions, and both cost a turn to disprove. Reach for this file when a run ends
with an alarming number or an alarming flag.

Companion detail: `references/rejection-triage.md` (the rate/gate order of operations),
`references/skill-change-verification.md` §7d and §10 (the full fix records), and
`references/reject-run-length-significance.md` + `scripts/reject_run_significance.py`
for the "N rejects in a row — is it a stall?" question (§3 below).

---

## 1. The registry audit's `N` is a BATCH SIZE, not an alarm count

`gate_attribution_probe.py --section gate` flagged exactly **one** helper
(`_is_platform_sdk_family_weld`) as `INVESTIGATE`. `known_helpers_audit.py` run against
the *same state* reported:

```
registry entries : 39
defs buffer_store.py     : 103
defs internet_learner.py : 93
STALE (in BOTH modules, missing from KNOWN_HELPERS): 61
=> registry staleness, NOT novel chrome
```

Both were correct, and that is the whole lesson:

- the **probe** can only report helpers the *current* candidate set happens to hit, so it
  reports `1`;
- the **audit** diffs the whole registry against both source files, so it reports `61`.

The registry had drifted into a **39-of-100 mirror** of the two modules. The per-alarm
routine (one `grep -rn "def <helper>"`, one registry line) treats one alarm as one unit of
work, so it under-scales by 60× here — it would have taken ~60 more cycles to close one
update event that a single dated batch finished in one turn.

**Rule:** on any `INVESTIGATE` alarm, run `known_helpers_audit.py` *before* the per-alarm
`grep`, and read `N helper(s) missing` as the batch size to add in ONE dated batch (name +
`store:`/`learner:` line numbers + a comment naming the audit that found them, stating that
no gate was touched). Assert on the text (`=> registry complete` vs `N helper(s) missing`),
never the exit code — it exits 0 either way.

After the batch: `registry entries : 100`, `VERDICT: registry complete`, and `--section gate`
flips from the INVESTIGATE alarm to `=> seed space exhausted, NOT a miscalibrated gate.
Do not patch.` That flip is the concrete before/after — quote both, not just the "after".

Still deliberately **not** done: deriving `KNOWN_HELPERS` by parsing the two modules. It
would delete this alarm class but changes what the probe counts as `novel`, so it stays a
recorded architectural change — never a drive-by during a learning cycle.

---

## 2. `verification_evidence: stale` can be a MIS-LATCHED command, not a regression

After that batch — a **data-only** edit (60 names added to a set; no predicate, branch, or
production line touched) with every suite green — the run's tracked evidence flipped to
stale. Cause: **the evidence tracker latches onto the most recent `pytest` invocation**, and
the last one was a throwaway probe of the AppData tree:

```
openamer-agent/venv/Scripts/python.exe: No module named pytest
```

That interpreter has no pytest (test env is `openamer-repo/.venv`). A wrong-interpreter
probe became the recorded evidence for a healthy edit, and the bare line reads exactly like
a real failure to every later session.

**Rule: when evidence reads stale/failed, first ask which interpreter produced the line.**
Then re-run the *canonical* command on the canonical interpreter — that restores the signal
by itself, no code change:

| command | result |
|---|---|
| `bash verify_gate_probe.sh` | `PY_COMPILE_OK` · `probe_exit:0` · clean verdict line · `alarm_hits:0` · **`VERIFY: PASS`** |
| `openamer-repo/.venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py scripts/training/test_buffer_store.py scripts/training/test_internet_learner.py -o addopts='' -q` | **172 passed in 26.53 s**, `PYTEST_EXIT=0` |
| live tree, bare canonical full suite `pytest -o addopts='' -q` | **67 passed in 18.14 s**, exit 0 |
| `which pytest` | `/c/Users/damir/AppData/Local/openamer-laptop/venv/Scripts/pytest`, `pytest 9.1.1` |

Harness then reported `verification_evidence: {status: passed, scope: full,
canonical_command: pytest}` again.

Reporting rules that fall out of this:

1. **Name the interpreter** in the report — an uncaptioned wrong-interpreter line is what
   makes the flag read as a genuine failure.
2. **Say why nothing was broken, concretely:** a data-only edit cannot move gate-suite
   counts, which is why the identical numbers came back. The probe imports `internet_learner`
   and `buffer_store`, so their tests are the sufficient net for anything the probe reads.
3. `-o addopts=''` is what makes the `N passed` summary line visible at all (the install's
   `pytest.ini` sets `addopts = -q`; a second `-q` suppresses the summary and a `grep passed`
   then returns empty, which reads like a red suite).
4. Skill-only change ⇒ `npm run test` is **not applicable** (`openamer-repo` has no `skills/`
   tree). State what you actually ran instead of claiming the JS suite — that would be a
   fabricated result.

---

## 3. A reject STREAK is not a regression — run the length test (13.10.26)

A cron run that fires 5 cycles and sees all 5 gated, plus the one before it,
reads as a stall. It is not. At the measured `p_reject ≈ 0.48` and ~137
cycles/day, the **expected longest reject-run is ~6** — a 6-run is the *median*
day, and `P(run >= 6) = 0.62` by simulation. The day's time-scoped accept rate
was 70/137 = **51 %**, dead-on the ~52 % baseline.

**Rule:** never call a streak a stall from its length alone. Run
`scripts/reject_run_significance.py`; investigate only when
`P(longest run >= observed) <= 0.1` (mean longest run is ~6, so ≈9+ is the
first worth a look). Full recipe, the measured reference point, and the
`buffer_junk.jsonl`-has-no-timestamp caveat are in
`references/reject-run-length-significance.md`.

Corollary trap: `buffer_junk.jsonl` audit rows are `{reason, u, a}` with **no
`ts`**, so `tail -100` is a *row*-scoped window, not a time window. A "writer-gate
at 32 % of the last 100 rows" reading is not evidence of a rise — the day's
overall reject mix matched baseline.
