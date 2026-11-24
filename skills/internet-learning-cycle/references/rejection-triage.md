# Triage: "rejected, not trained (shallow + deep read both gated)"

A rejection line is the NORMAL outcome of an exhausted rotation — **not**
automatically a bug. Do not edit a gate on one rejection. Measure first, in this
order. (SKILL.md is at its size cap; this detail lives here.)

## Worked example — a lone reject that correctly produced NO patch (22.09.26)

Cron delivered a single line: `[internet-learn] cycle_g_security: rejected, not
trained (shallow + deep read both gated) (52.8s)`. Full triage, ~6 min:

| check | result | so |
|---|---|---|
| repo worktree (`git status --porcelain scripts/training tests/scripts`) | clean, only an untracked test file | no inherited uncommitted gatework (Root cause AV) |
| `curl -s localhost:8081/health` | `{"status":"alive","tools":10}` | no restart |
| §1d live probes | both query sources real (5.5 s / 1.0 s) | generator intact |
| §1 buffer fill | **247/300** | below cap -> Root cause B excluded |
| census (§1c) with `keys=['u','a']` | **5** junk-flagged legacy rows, 2 of them class BG | buffer healthy |
| §2 reason split (160-row tail) | **85 junk** / 71 duplicate / 4 no-tech-signal | junk dominates = gate working |
| §4 answer-presence | **64/71** duplicate `a` already stored | repetition is real |
| §1 per-day rate | **38/88 = 43.2 %**, in the 35-50 % band; 36 real learns that day | no step change |

Trend that matters for the write-up: 13.09. -> 22.09. = 100 / 68.5 / 62.3 / 63.7 /
45.2 / 55.2 / 35.4 / 27.8 / 42.1 / 43.2 %. A monotone decay of this shape is
**seed exhaustion widening over days**, not one gate breaking on one day — and
the fix class for it is *more sources / wider novelty*, which is the same
standing as §1b's avoid-window: propose, do not land on a rejection.

**Verdict: no patch.** Loosening the gate on this evidence would trade one honest
rejection for a junk leak. Report the reject line, the band, and the learn count
together — never the reject count alone.

## Run this first — the whole triage in one command

`scripts/gate_attribution_probe.py` (in this skill) does sections 1–4 below and
prints the denominators, so you do not hand-write the probes again:

```bash
python <OPENAMER_HOME>/skills/internet-learning-cycle/scripts/gate_attribution_probe.py
python .../gate_attribution_probe.py --section gate     # just the gate attribution
python .../gate_attribution_probe.py --tail 400         # buffer_junk slice size
```

For the **rate** half of the triage (§1) use the other packaged action instead of
writing a throwaway table — the hand-written version leaves a `tmp_*.py` that must
be deleted and proven deleted (see `skill-change-verification.md` §8):

```bash
python <OPENAMER_HOME>/skills/internet-learning-cycle/scripts/rejection_rate_table.py
python .../rejection_rate_table.py --hours 24 --last 100
```

It prints per-day, per-hour, and per-source rates plus a trailing-cycle rate, and
ends in one of the two verdict SHAPES (stall vs rotation noise) rather than making
you eyeball the numbers. Read-only, so it adds nothing to the changed-path census.

Its section 3 is the piece worth reaching for: for every distinct junk candidate
it reports **extractor-only / writer-only / both / neither**, plus the leaf-helper
histogram with any helper that is NOT in its `KNOWN_HELPERS` set flagged as
`INVESTIGATE`. That separates "seed space exhausted" (writer-only, all known) from
"possible novel chrome shape" (an unknown helper) in one shot.

**But it does not always print a verdict — check, do not infer.** Until 21.09.26 the
guard was `writer_only and not extractor_only`, so a single extractor-only candidate
(a leaf component whose composite gate is the real verdict) suppressed the whole
conclusion: the probe exited 0 having printed *no verdict at all*, which is exactly
how a healthy run gets misread as "something is wrong". Fixed to the honest criterion
`writer_only and not novel`, with the extractor-only count reported parenthetically.
A `--section gate` run must end in **either** `=> seed space exhausted … Do not patch.`
**or** the `N candidate(s) matched an UNKNOWN helper` block. Ending in neither is the
bug, not a clean bill of health — and since the exit code is 0 both ways,
`echo $?`/`exit_code:0` proves nothing about the verdict. Assert on the output text.

**Also: clear `INVESTIGATE` alarms in batches, not one helper at a time.** A single
run on 21.09.26 flagged **9** helpers; one
`grep -rn "def <h>" scripts/training/buffer_store.py scripts/training/internet_learner.py`
showed 2 defs each, i.e. one registry-update event, not nine investigations. Batch
them into `KNOWN_HELPERS` with a dated comment and the line numbers. Full table and
fix record: `references/skill-change-verification.md` §7.

**But the converse holds too: a SINGLE recurring alarm is also registry staleness,
and costs one `grep` — expect it, don't escalate it.** Later the same day the alarm
came back as exactly one helper, `_is_course_cta_opener`. One
`grep -rn "_is_course_cta_opener\|_is_course_cta_chrome" scripts/training/*.py`
returned 2 defs (`buffer_store.py:2826`, `internet_learner.py:2988`) and showed the
sibling `_is_course_cta_chrome` already in the set — same shape, one line added, no
root-cause work, no prose churn. So: read `N` as *batch size*, never as *severity*.
One helper = one grep; nine helpers = one grep too (they share the update event).
Full record incl. the verdict after the fix: `references/skill-change-verification.md` §7b.

**A SECOND batch landed the same day (22.09.26), and that is the expected cadence.**
A later cron turn's `--section gate` run flagged one alarm again
(`_is_affiliation_author_list`); `known_helpers_audit.py` expanded it to **7** STALE
helpers in one update event (`_is_affiliation_author_list`, `_is_aggregator_card_header_weld`,
`_is_arxiv_submitter_run`, `_is_breadcrumb_title_repeat`, `_is_caps_nav_lockup_weld`,
`_is_credit_byline_run`, `_is_date_stamp_listing_strip` — store:3550-4192 /
learner:3768-4007). Added in one dated batch; both probes then read their real verdicts
(`registry complete` / `seed space exhausted … Do not patch.`). Two batches on one day is
**the registry trailing the source**, not a regression: the set mirrors two files that both
grew. Expect one alarm per update event and pay it with one `known_helpers_audit.py` run —
never treat the alarm count as severity, and never patch a gate on it (§4's two-sided
replay is still the only thing that licenses a rule change). Full verification transcript
of that second batch (7 helpers, `VERIFY: PASS`, 162 passed, CRLF check, the single-copy
`find`): `references/skill-change-verification.md` §7f.

**A THIRD batch landed 23.09.26 — same cadence, same shape.** The live `--section gate`
run flagged **two** alarms (`_is_serp_title_snippet_repeat`, `_is_article_byline_chrome`)
and `known_helpers_audit.py` expanded them to **5** STALE helpers in one update event
(`_is_aggregator_card_affordance_rail` store:4309/learner:4048, `_is_article_byline_chrome`
4531/4316, `_is_de_consultation_contact_chrome` 2791/2941, `_is_feed_handle_unit_row`
2729/2879, `_is_serp_title_snippet_repeat` 4484/4269 — 2 defs each, confirmed with one
`grep -n "def <helper>" scripts/training/buffer_store.py scripts/training/internet_learner.py`).
That run also read `ONE-SIDED: 16` (informational, unchanged). Added in one dated batch;
both probes then read their real verdicts — `known_helpers_audit.py` → `VERDICT: registry
complete`, `gate_attribution_probe.py --section gate` → `All junk rejects are WRITER-side
and every leaf hit is pre-existing: => seed space exhausted, NOT a miscalibrated gate. Do
not patch.` CRLF preserved (`crlf 419 / barelf 0 / double-CR 0` via an `rb` read) because the
probe file is CRLF. Three batches in three days is still the registry trailing TWO source
files that both keep growing — one `known_helpers_audit.py` run pays each update event.

**And the "no patch" verdict is not the same as "nothing learned".** Same turn, the §1
escalation (one `--once` at a time, stop at the first `learned:`) went
`b_papers` reject → `c_github` reject → `d_docs` reject → `e_competitors` reject →
**`f_multi_domain` converted** in 17.0 s (`TorchPhysics … open-source PyTorch library that
implements deep learning methods for partial differential equations`), buffer tail
verified with `keys ['u','a']`. Four honest rejects + one real learn is the documented
rotation regime, and the reject count must never be reported alone.

### Editing the packaged probe ITSELF (`skills/internet-learning-cycle/scripts/`)

Four facts that make a `KNOWN_HELPERS` batch edit cheap, measured 23.09.26:

- **There is exactly ONE copy and NO repo twin.** `find <HOME> -name gate_attribution_probe.py`
  → **1** hit (HOME); `ls ~/openamer-repo/skills/internet-learning-cycle*` → *No such file
  or directory* (the repo's `skills/` dir holds a different, unrelated set). So an edit to
  a packaged probe needs **no repo sync and no commit** — the "THREE copies, reconcile and
  commit" rule at the top of SKILL.md governs `scripts/training/`, NOT these probes. Do not
  go looking for a second copy to diff against; there isn't one.
- **These files are CRLF** (405 lines / 405 CRLF before the edit). The `patch` tool
  preserved that; assert it anyway after every edit, because a `write_file` round-trip is
  how a lone-LF or `\r\r\n` corruption gets in and **neither `ast.parse` nor `py_compile`
  can see it**. One-liner (prints `crlf`, `barelf`, `doubleCR` — the last two must be 0):
  `python -c "d=open(P,'rb').read(); print(d.count(b'\r\n'), d.count(b'\n')-d.count(b'\r\n'), d.count(b'\r\r'))"`
- **Membership check that the batch actually landed:** count `"<helper>"` occurrences in the
  probe file → exactly **1** each. A count >1 means a re-run insert script's idempotence
  check missed the comment block and duplicated it (the documented re-run trap).
- **Verification trio, cheapest first, assert on TEXT not exit codes:** `py_compile` (native
  path form) → `bash skills/internet-learning-cycle/scripts/verify_gate_probe.sh` (must print
  `VERIFY: PASS` **and** `alarm_hits:0`; it greps the output because the probe exits 0 either
  way) → the two suites **one file per process**: `tests/scripts/test_internet_learner_gate.py`
  **181 passed** and `scripts/training/test_internet_learner.py` **24 passed** (23.09.26).
  Use `venv/Scripts/python.exe` — bare `python` in this shell is the agent venv with no pytest,
  and passing both paths in one invocation aborts with `import file mismatch` (shared basename).
  Note the asymmetry: pytest's short `-q` line for the first file shows only dots +
  `[100%]`, so grep for `passed` on the **non**-`-q` run to get the number.

**Two tool rules that paid for themselves in the same run:**

- **When `search_files` goes quiet, use a targeted terminal `grep`.** On
  `scripts/training` it returned `IO error 3` and, on a retry, a bare `total_count: 0`
  for a directory that plainly exists — silence, not absence (so the 0 must never be
  reported as "nothing found"). The plain-literal form answers in one call:
  `grep -rn "_is_affiliation_author_list" scripts/training/*.py` → 2 defs. Keep it a
  literal: regex escapes in a search pattern are their own trap (§1b-ter).
- **Never `grep -r` from the install root.** That glob walks `node_modules`/`venv`/cache
  and hits the 60 s clamp, which then looks exactly like a broken tool
  (`[Command timed out after 60s]`, `exit_code: 124`). Scope to
  `scripts/training/*.py` + `skills/<skill>/scripts/*.py`, or `find -name`.
  Detail: `references/cron-cycle-constraints.md` §2b.

Note the file-write rule this runs under: in a cron session `python -c` and
heredocs are BLOCKED — run the probe as a file invocation (it is one), and edit it
via `write_file`/`patch`, never an inline snippet.

### One command instead of one `grep` per alarm: `scripts/known_helpers_audit.py`

Every `INVESTIGATE` alarm on 21.09.26 — four separate events (class 66, a 9-helper
batch, class 90, class 99) — resolved to the **same shape**: a helper defined in
BOTH `buffer_store.py` and `internet_learner.py` that was simply absent from the
probe's hand-maintained `KNOWN_HELPERS`. The set is a *mirror* of two source files,
so it goes stale every time a helper lands. That is a maintenance cost, not a bug
hunt.

The per-alarm routine above (one `grep -rn "def <helper>" …`, then one registry
line) stays the fallback. The packaged action diffs the **whole registry** against
the source in one command:

```bash
python <OPENAMER_HOME>/skills/internet-learning-cycle/scripts/known_helpers_audit.py
```

It prints `STALE` (in both modules, missing from the registry -> add them in a single
dated batch), `ONE-SIDED` (informational) and `DEAD` (registry entries defined
nowhere). Read-only, exits 0 either way — assert on the text
(`=> registry complete` vs `N helper(s) missing`), never on the exit code, exactly as
with the probe itself.

Authored 21.09.26 and self-reporting: it prints its parse counts and samples on every
run, so a bad parse is visible instead of silent. On its first run, sanity-check those
samples against `grep -rn "def _is_" scripts/training/buffer_store.py | wc -l` before
trusting a verdict.

**The durable fix is deliberately NOT done.** `KNOWN_HELPERS` could be *derived* by
parsing those two modules instead of hand-mirroring them, which would delete this
whole alarm class. That changes what the probe counts as `novel`, so it is an
architectural change to record — do not do it autonomously on the strength of an
alarm.

**False-alarm fixed 20.09.26:** the probe's `KNOWN_HELPERS` set was missing
`_is_generated_plan_echo_fragment` (class 66, defined in BOTH
`buffer_store.py:1678` and `internet_learner.py:1928`), so section 3 printed
`NOT a known helper: INVESTIGATE` for 2 candidates that were in fact a
pre-existing shape. Added to the set — if section 3 ever flags an unknown helper
again, first `grep -rn "<helper>" scripts/training/*.py` and check whether it is
simply absent from `KNOWN_HELPERS` before treating it as novel chrome.

## 1. Rate first — with a per-day table

**Before reading any `n/MAX_BUF` fill level, read
`references/cap-counts-lines-not-records.md`.** `count()` and `enforce_cap()`
count PHYSICAL LINES, so blank separator lines inside the store halve the
effective record cap: "300/300 — full" and "152/300 — 51 % full" are the same
file. A `duplicate`-heavy reject tail is then saturation *of a half-sized
buffer*, not seed exhaustion. Measured 21.09.26: 152 records, 164 non-junk rows
lost, `clean_buffer.py` accounts for 0 of them.

`scripts/training/internet_learn_log.jsonl`: one JSON row per cycle
(`ts`, `source`, `result`, `elapsed_s`). Count cycles and how many contain
`rejected`, per day and per source.

```
DAY        cycles reject  rate
2026-09-17    208   113   54.3%
2026-09-18     67    30   44.8%
2026-09-19    113    73   64.6%
2026-09-20     53    35   66.0%
TOTAL        2107   534   25.3%
```

Read it like this:
- **Flat and rotating** (e.g. steady ~30%, different cycles each time) = rotation
  noise. No fix.
- **A step change, or flat ACROSS ALL sources** = investigate. In the run above
  every one of the eight cycles sat in 44.8–69% — that uniformity is the tell that
  it is not one cycle's bug.

### A stall can start AND clear inside one day — go per-HOUR for the live verdict

The per-day table above is too coarse to answer "is it stalling *now*". Bucket the
last ~12 hours of `ts` prefixes (`r["ts"][:13]`); this is the fastest stall/no-stall
call and it settles the question before any root-cause work:

```
hour            n  pass%
2026-09-21T02   10     30%
2026-09-21T03    9     56%
2026-09-21T07   12     17%
2026-09-21T08    8     62%
2026-09-21T11   18     33%
```

Swinging ~17 %→~67 % hour to hour = **rotation noise, no stall**: report the rate
and stop. 21.09.26 live: 38 % over the last 60 cycles against a 71 % long-run rate
(1,593 of 2,245) — inside normal variance, **not** a trigger. Do not open a
root-cause investigation on a mixed-rate same-day window.

The stall signature is different and unmistakable: **0 % for consecutive hours,
uniformly across ALL eight sources**, with the buffer pinned at its cap. That — and
only that — is the trigger for the deep-dive in the `internet-learner-stall-fix`
skill. Two consecutive `--once` runs both rejecting is ordinary and proves nothing.

Quick triage order once a mixed rate is confirmed: per-hour table → reason split by
OWNER (§2) → confirm the mix looks like `junk`+`duplicate` (21.09.26: 219 junk /
174 duplicate over the last 400 audit rows = the gate working as specified) → stop.

## 1b. The novelty ledger `.il_seen_queries` — the cheapest "is it exhausting?" read

Before blaming seeds, look at the **re-issue ledger**: `scripts/training/.il_seen_queries`,
one line per query `_novel_query()` issued, trimmed to the last 800 by `_remember_query()`.
Its **unique:total ratio** is the fastest exhaustion signal available:

```
measured 2026-09-21:  800 lines, only 177 unique   ->  every query re-issued ~13x
```

Read it like this:
- **total ≈ unique** (e.g. 800/780) = the live-headline path is genuinely finding fresh
  headlines; a reject tail is then ordinary rotation noise.
- **total >> unique, one small set repeating N times** = the avoid-list window is too
  small for the re-issue rate. `_novel_query()` calls `_recent_queries(n=60)` — it only
  ever sees the **last 60** queries — while the ledger holds 800. So a query issued 61
  lines ago is invisible again, its live headline is stale, and the cycle burns a full
  `store -> deep_learn(k=2) -> deep_learn(k=6)` excursion only to be refused as
  `duplicate`. That is the mechanism behind a duplicate-heavy reject tail.
- Cadence is what makes the ratio bite: `internet-learner-247` runs **every 5 min**
  (~326 cycles/day). Against 177 live seeds that is ~1.8 re-issues of every seed per day
  (2026-09-21: 226 cycles / 97 stored / 128 rejected = 57 %).

Packaged read (no `python -c`, which is blocked in cron):
`scripts/query_ledger_audit.py` — prints lines, unique, ratio, repeat histogram, verdict.

The one-line fix (raise `_recent_queries(n=60)` toward the ledger's own 800) is **NOT
applied**: it changes which strings reach the gates, so it is an architecture change to
propose, not to land on a rejection — same standing as root cause AG in §5.

### Ad-hoc re-runs inflate the rate — never read a manual streak as a stall

`--once` issued back-to-back in one session rejects **by construction**: each run appends
its query to the same 60-deep avoid window, so run N+1 sees its own predecessors as
"recent" and falls through to the LLM/static-seed path. Measured 21.09.26: **six**
consecutive manual `--once` runs produced six "both gated", while the *scheduled* runs in
the same hour were storing fine (last successful learn 12 min before the streak). The
per-day/per-hour table over `internet_learn_log.jsonl` is the verdict; your own loop is
not. This is the concrete form of §1's "two consecutive `--once` runs prove nothing".

**Re-confirmed 22.09.26, and it costs real wall-clock.** The cron task was a single
`--once`, which returned `cycle_f_multi_domain: rejected, not trained (… both gated)
(66.1s)`. Because a lone reject is not evidence either way (§1), the run was escalated:
**5 further `--once` calls, 47-66 s each (~4.5 min total)**, four of them rejecting
(g, h, a, and the f already seen), and only the sixth converting. So the *first* line a
cron report tends to quote — "rejected" — was the least informative of the six.

The discipline that makes this cheap and honest:

- Escalate **one run at a time**, stopping at the first `learned: …`. A single accept
  is the answer; do not run a fixed batch of six.
- Each run **advances the eight-cycle rotation** (c -> e -> f -> g -> h -> a -> b here),
  so consecutive runs sample *different* sources — that is why one of them converts, not
  luck. A streak of `--once` calls is not a repeat of the same experiment.
- Report the streak shape honestly: `N runs, k learned / N-k rejected`, and never present
  the reject count as the cycle's outcome. Then run the per-source table (§1) — the band
  is what licenses the "no gate change" verdict, not the streak.
- The verdict after 5 rejects was still the documented one: **no novel shapes, no gate
  edit**, source exhaustion. The 5th reject being `cycle_f_multi_domain` — the *same*
  source the cron line showed — is not a per-source bug; f sits at 45.1 % over 5 days.
- Wall-clock budget: ~50-65 s per `--once`. A cron turn with a 5-run escalation needs
  ~5 min; each call must be its own `terminal()` invocation (the 60 s foreground clamp in
  `cron-cycle-constraints.md` §1 is about a *single* call overrunning, not a budget).

### The packaged probes do NOT live in `scripts/training/`

`gate_attribution_probe.py`, `rejection_rate_table.py`, `known_helpers_audit.py` and
`query_ledger_audit.py` are packaged **in this skill**
(`<OPENAMER_HOME>/skills/internet-learning-cycle/scripts/`).

**And they need `OPENAMER_HOME` set explicitly when the ambient value is stale**
(live 23.09.26): a bare run printed
`log not found: C:/Users/damir/_vaultfinal\scripts\training\internet_learn_log.jsonl`
— that reads like a missing log, is a stale-env artifact, and exits 0. Prepend the
real home:
```bash
OPENAMER_HOME=C:/Users/damir/AppData/Local/openamer-laptop \
  python skills/internet-learning-cycle/scripts/rejection_rate_table.py
```
Same family as the `_vaultfinal` stale-`OPENAMER_HOME` trap recorded elsewhere.

Invoking
`scripts/training/gate_attribution_probe.py` fails with
`[Errno 2] No such file or directory` and reads like a missing tool — it is a wrong path.
The **data** files, by contrast, *do* live in `scripts/training/`:
`internet_learn_log.jsonl`, `buffer_junk.jsonl`, `online_buffer.jsonl`, `.il_seen_queries`.

**And a THIRD location, measured 22.09.26: `diagnose_learn_rates.py` is not in this
skill either.** Its real home is
`skills/software-development/training-scripts-hygiene/scripts/diagnose_learn_rates.py`
(as is `which_rule_matches.py`, cited in §3).
`python scripts/training/diagnose_learn_rates.py --days 5` -> `[Errno 2] No such file
or directory`. That wrong path is easy to construct deliberately, because the verdict
text in `internet-learner-stall-fix`'s archive says *"Re-derive this from
`diagnose_learn_rates.py --days 5`"* — **bare script name, no path** — so the reader
glues it onto `scripts/training/`. One `find <HOME> -name diagnose_learn_rates.py`
resolves it; do not retry the same path with a different spelling (§5 of
`cron-cycle-constraints.md`). It is also the rate+per-source reader this triage wants,
so once found, run it rather than hand-writing a table.

Second independent sample of the healthy band (22.09.26, `--days 5`): per-source
**34.8-47.3 %** — a_technews 34.8 / b_papers 44.9 / c_github 40.4 / d_docs 46.0 /
e_competitors 38.0 / f_multi_domain 45.1 / g_security 47.3 / h_efficiency 35.6 — no
outlier, i.e. the same shape as the 36.8-48.9 % band recorded for root cause 128. Per-day
21.09 = 42.1 %, above 20.09's 27.8 %. The trailing day (22.09, cut at 00:25) read 28.6 %
and the script itself flagged it as PARTIAL — never compare that row to a closed day.

## 1b-ter. Two reading traps on the LOG and on your own probes (measured 22.09.26)

**`tail -N internet_learn_log.jsonl` is NOT chronological — never call its last
line "the latest cycle".** Measured: the final three lines carried `ts` of
08:39:56, 09:22:17, then **07:29:11**, while the file's own mtime was 07:29:11.
Append order is real; the `ts` field is not monotone (some cycles stamp ahead of
wall clock, here by ~2 h). Consequences:

- Read trends ONLY from the rates table (§1), never from tail order. In that
  session the last tail line was the *oldest* of the three — quoting it as "the
  newest reject" would have been backwards.
- The partial-day cut is taken at **wall clock**, so future-stamped rows land
  *beyond* it: the per-day table showed a `2026-09-22T09` row while the day was
  still being cut at 07:30. Do not read the extra row as a decline.
- **The partial row moves as the day fills — a third reason never to compare it
  to a closed day.** Same date 22.09.26: `28.6 %` at a 00:25 cut (§1b, earlier
  session) vs `39.6 %` (42 ok / 64 rej) at a 07:30 cut in this one. One date, two
  "rates", both honest, neither a trend.

**Do not put regex escapes in a `search_files` pattern.** Asking for
`shallow \+ deep read both gated` reached ripgrep as `shallow /+ deep read both
gated` → `regex parse error: unclosed group` (it reads `\+` as `/+`). Search for
the plain literal (`both gated`) and let the surrounding lines carry the context.
This is a *pattern-writing* rule, not a broken tool: the plain literal matched
8 site lines in one shot. Separately, `search_files` still returns
`IO error … os error 3` on `AppData/Local` while `ls`/`find`/`grep` in the same
directory succeed — use `grep` there (already noted in SKILL.md).

### Positive control — prove a gate FIRES before hunting a fix

Cheapest way to separate "gate is working as designed" from "gate is broken", and
it needs no corpus work: count the marker in BOTH stores. A marker confined to
junk with **zero** accepted rows is the gate doing its job.

```bash
grep -c 'Self-critique' buffer_junk.jsonl      # -> 1097
grep -c 'Self-critique' online_buffer.jsonl    # -> 0
```

Only after that control do you ask whether the *query* was the problem. Without
it, a recurring gated fragment family looks like a leak that needs a new marker —
and adding a marker for something already caught is pure churn (the quantization /
energy-efficiency family rejects of 22.09.26 were already `duplicate`/`junk` for
the documented reasons; no marker was warranted).

### Rule out the autopilot writer (cause T) with TWO md5 samples

A single hash is not a measurement. Take two samples ~5 s apart before touching
`internet_learner.py`; if hash AND size AND mtime all hold, no Darwin writer is
active and any patch you make will survive:

```bash
md5sum scripts/training/internet_learner.py; stat -c '%y %s' scripts/training/internet_learner.py
sleep 5
md5sum scripts/training/internet_learner.py; stat -c '%y %s' scripts/training/internet_learner.py
```

22.09.26: `e449a7fd…`, 282452 bytes, mtime 06:27 — identical in both samples.

### Confirming sample: below-cap rejection regime, 22.09.26 (~07:30 UTC)

A third independent read of the same healthy band, all consistent with §1b and
root cause 128 — a rejection line with the buffer BELOW cap is regime, not stall:

| probe | value | reading |
|---|---|---|
| buffer fill | **238 / 300** | stall trigger unmet (its conjunction needs cap-pinned) |
| rates, last 40 | ok 11 / rej 29 = 27.5 % | low, but 26-40 % days recur since 13.09 |
| rates, 7d per-source | 40.8-54.6 % across **all 8** cycles | uniform → rotation noise, not one source |
| today vs yesterday | 39.6 % vs 42.1 % | no step change |
| `.il_seen_queries` | 800 lines / **180 distinct** | 128 re-confirmed (177 on 21.09) |
| `git status --porcelain scripts/training tests/scripts` | clean | no inherited gate work (cause AV) |
| tool_server `/health` | `alive, tools:10, swaps:3` | no restart |

Both `--once` runs rejected (`cycle_h_efficiency`, then `cycle_a_technews`). Two
rejects still prove nothing on their own (§1) — what licenses the no-patch
verdict is the **band**, and the write-up must carry band + learn count, never the
reject count alone.

## 1c. The store-KEY trap — a census on the wrong key reports a FALSE zero

Both learning stores are keyed by SHORT names, and reading a plausible-looking
wrong key yields a *perfect* result that is pure artifact. Measured 22.09.26:

| store | record keys | wrong read |
|---|---|---|
| `scripts/training/online_buffer.jsonl` | **`u`, `a`** | `rec["assistant"]` -> `''` on every row |
| `scripts/training/buffer_junk.jsonl` | **`reason`, `u`, `a`** | `rec["insight"]` / `rec["text"]` -> `''` on every row |
| `longterm_episodes` | **`text`** | same shape |

A census written as `rec.get("assistant") or rec.get("a") or ""` reads `''` for
all rows, and `_is_junk("")` is True — so the run reports a **false 5-of-247
junk**, or with the opposite key guess "buffer junk = 0". Both readings are
fiction. **Print `list(rec.keys())` from row 0 before censusing any store**; the
key names differ per store by design and are not discoverable from the docs.

Corollary: an unkey-verified `0 junk` is *unmeasured*, not clean. Say
"unmeasured" rather than reporting the zero. (Same family as the `u`/`a`
`KeyError: 'U'` case trap in `cycle-evidence-reporting.md`.)

### 1c-bis. A KEYED NONZERO census is not a leak either — sweep BOTH gates and name which one fired

The symmetric trap to 1c. Sweep the buffer with **both** gates, never one:

```python
def load(p, n):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); sys.path.insert(0, T); s.loader.exec_module(m); return m
bs = load('buffer_store.py', 'bs'); il = load('internet_learner.py', 'il')
recs = [json.loads(l) for l in open('online_buffer.jsonl', encoding='utf-8', errors='replace') if l.strip()]
print('writer-gate leaks', sum(bs.is_junk(r['a']) for r in recs),
      '| extractor-gate', sum(il._is_junk(r['a']) for r in recs))
```

Measured 12.10.26 on the 300-row buffer: **`buffer_store` 0, `internet_learner` 7**.
The 7 are **pre-gate legacy rows, not a writer leak** — the two gates are not
interchangeable, because the EXTRACTOR carries a rule the writer does not:
`internet_learner._is_junk` (~L4784) refuses `len(t) < 25`, while
`buffer_store.is_junk` has no stub rule at all. Six of the 7 are sub-25-char stubs
(`Energy = power * time.`, `Compute requires energy.`, `Could be philosophical.`,
`Google, Microsoft, Meta.`, `Biological:\n- Sleep`) and the seventh is a
self-instruction echo (`Need maybe categorize: hardware failures, …`) — the agent's
OWN self-dialogue, never internet-learned prose.

- Read a nonzero **extractor** sweep as *"legacy rows the extractor would now
  refuse"*, never as *"the writer is leaking"*.
- Do **not** bolt the `len<25` stub rule onto `buffer_store` to "clean" them: the
  rows turn over with the 300-cap rotation anyway, and a writer-side length rule is
  a brand-new false-positive surface on real short-but-valid insights for zero
  benefit.
- This is the **mirror** of 2b: there the WRITER is stricter (extractor blind,
  71–92 % writer-only). Either direction, the rule is the same — **name which gate
  fired before believing any count**, and never edit a gate on the count alone.

## 1d. Is the LIVE PATH degraded? — probe the two query sources directly

§1b's ledger tells you seeds are re-issued; it does not tell you whether the
freshness machinery still *works*. Probe both sources by name, with a timing
bound, instead of inferring from the reject tail:

```python
il._llm_novel_query("<domain kw>", [])   # LLM-synthesised query path
il._fresh_headline("<domain kw>", [])    # live HN Algolia headline path
```

Measured 22.09.26: both returned real values (`'github trending ai agent
frameworks'` in 5.5 s; `'Serpent.AI – Game Agent Framework in Python'` in 1.0 s)
-> query rotation is intact, so the rejections are NOT a starved generator and
no generator-side patch is warranted. A `""`/exception here is what would
license generator work. Run these BEFORE any root-cause reading: they are ~7 s
and they delete the largest false hypothesis.

**One unconfirmed lead, unmeasured — do not act on it.** A single buffer row
(`D3sign/STOCK PHOTO/Getty Images By Mason Leib April 29, 2026 …`) has a
photo-credit/chrome *shape*. That is a hunch with no control corpus; §3b's
two-sided replay is the gate for turning it into a class. Record, do not patch.

## 2. Reason — split by OWNER, not over the whole file

`scripts/training/buffer_junk.jsonl` is a **shared** audit store: other writers
append to it too. A reason histogram over the whole file has the wrong
denominator. Filter by the `u` question-prefix first and print the denominator:

```python
OWNERS = ["Internet learning (", "Latest research insight:",
          "What new agent architectures", "Best practice from official docs:",
          "Competitor intelligence:", "Multi-domain learning (",
          "Security learning (", "Efficiency learning (",
          "Structural connection between"]
rows = [json.loads(l) for l in open(STORE, encoding="utf-8", errors="replace") if l.strip()]
mine = [r for r in rows if any(r.get("u", "").startswith(p) for p in OWNERS)]
print("owned:", len(mine), "of", len(rows),
      collections.Counter(r.get("reason") for r in mine))
```

Live numbers: 6,813 rows total, but only **~310 of the last 400** were
learner-owned (85 foreign `junk` rows would otherwise have been miscounted).
Reason counts over the owned tail: `duplicate 162 / junk 139 / no-tech-signal 9`.

Rows carry **no timestamp** — "the last N rows" is the only recency window
available, so take a tail slice and say so.

### 2b. A WRITER-GATE-dominant split is a different verdict — and it is still "no patch"

Every split recorded above is junk- or duplicate-dominant. Measured 23.09.26 the
owned tail came back **`duplicate 31 · writer-gate 19 · junk 8 · no-tech-signal 2`**
(last 60 learner-owned rows) — the first sample where **`writer-gate` is the
second-largest reason and `junk` is a minority (13 %)**. Cycle-level rate the same
turn: **16 of the last 30 cycles rejected (53 %)**; hourly buckets 12 h back sat at
25 %–100 % with no zero-hour run.

Read it like this:

- **`writer-gate` firing means the EXTRACTOR gate PASSED the text and
  `buffer_store` refused it.** That is §5's finding BC (six writer-only helpers the
  extractor deliberately lacks), i.e. cost in TIME, never a wrongly-stored row.
  A 31/19 duplicate+writer-gate split is therefore **the gates working
  as specified**, not a calibration failure.
- **Do NOT touch `_is_junk()` / `_JUNK_RE` on this distribution.** `junk` at 8/60
  is a small minority and a junk-led histogram is precisely what a real leak looks
  like; widening or narrowing the extract gate here buys nothing and risks a
  leak (same standing as §3b: no gate edit without the two-sided replay).
- 53 % is above the 35–50 % band recorded 13.09.–22.09. and above the 34.8–47.3 %
  per-source band, but a *single* turn's tail slice is not a trend — report the
  band + the learn count, never the reject count (§1b-ter: `tail -N` is not
  chronological anyway).

**Cheap generator control, same turn:** call the composite
`_novel_query()` four times in one process (not the two leaf sources of §1d) and
check the strings differ. 23.09.26 returned 4/4 distinct, article-grade queries
(`Open-sourced jev architecture…`, `Recursively summarizing enables long-term
dialogue memory in LLMs`, `Hardware Acceleration of LLMs: A comprehensive survey`,
`An embarrassingly simple approach to recover unlearned knowledge for LLMs`) →
the generator is intact, so the rejects are downstream (gates), not starved
seeds. A stuck generator returns the same static seed 4×; that is the only
outcome that licenses generator-side work.

**And the escalation is the whole fix for a lone reject** (§1b re-confirmed
twice): run 1 `cycle_b_papers` rejected in 52.5 s, an immediate run 2 converted —
`cycle_c_github` stored `NVIDIA RTX PRO 5500 Blackwell: What Actually Fits in 84GB
for Local LLMs` in 48.2 s. Escalate one run at a time, stop at the first `learned:`.

**Third sample, and the first with the writer-gate census ATTRIBUTED (23.09.26).**
`cycle_g_security: rejected … (48.4s)`, buffer CAP-PINNED at 300, tail-400 reason mix
`duplicate 212 · writer-gate 101 · junk 80 · no-tech-signal 7`. Beyond the usual §2b
verdict, this turn did what §5's finding BC had only asserted — **name WHICH writer
helper refuses**:

| refusal cause (`buffer_store` side) | rows | of 152 |
|---|---|---|
| `_is_serp_snippet` | 140 | **92 %** |
| `_is_nav_chrome` | 44 | |
| other / marker tuple | 2 | |

**And the decisive number: `internet_learner._is_junk()` returned False on
152/152.** The extractor believes every one is trainable; the writer refuses all of
them. That is finding BC quantified and singly-sourced — 92 % of the extractor/writer
disagreement is ONE helper, the SERP family.

```python
def load(p, n):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
bs = load('buffer_store.py', 'bs_probe'); il = load('internet_learner.py', 'il_probe')
rows = [str(json.loads(l).get('a') or '')
        for l in open('buffer_junk.jsonl', encoding='utf-8', errors='replace')
        if l.strip() and json.loads(l).get('reason') == 'writer-gate'][-300:]
c = collections.Counter()
for a in rows:
    for name in ('_is_serp_snippet', '_is_nav_chrome',
                 '_is_docs_cta_serp_run', '_is_truncated_serp_tail'):
        if getattr(bs, name)(a):
            c[name] += 1
print(c, 'learner blind:', sum(1 for a in rows if not il._is_junk(a)), '/', len(rows))
```

Run it from `scripts/training/` with `OPENAMER_HOME` set (otherwise the leaf modules
resolve to a stale copy — the `_vaultfinal` trap above).

**Still NO patch, on two independent numbers.** Closing the 92 % means folding
`_is_serp_snippet` into `_is_junk`, which 142 already MEASURED-AND-REJECTED (4 gate
tests regress: the extractor becomes as eager as the writer and eats prose that only
*mentions* a SERP-ish date). The licensing evidence was absent both ways: the current
reject streak was **8 against a whole-log max of 14**, and the last 60 `duplicate`
rejects carried **36 distinct `u`** (48 distinct `(u,a)`) — not the 121/128 "0/60
novel" saturation signature. **Attribute the census, then re-open only if the streak
exceeds the log's max or the share climbs while the rate falls.**

**Second streak sample (12.10.26): trailing 10 vs a historical max of 14** —
same verdict, no gate edit. `rejection_rate_table.py` now prints the line
`non-learn streak: trailing N   historical max M` and counts `no insight`
separately, because a `no insight` row (11 of that day's last 50 cycles) is a
cycle that stored NOTHING — not a pass, although the `pass%` column still counts
it as one. Only an accept (`learned:` / `paper-learn:` / …) resets the streak. Six consecutive
`--once` runs (48–72 s) stored 0; a later pair converted one
(`f_multi_domain`, 29.9 s).

**A stored row can be a DOCUMENTED CONTROL, not a leak.** The row that did land read
`China Semiconductors AI Infrastructure Geopolitics China AI Chip Boom: CAICT 417%
Demand vs 128% Supply 2026 Caixin Sept 15, 2026: …` — and it is the class-141
**China-chip control**, deliberately kept learnable because it repeats a bare `417%`
across *different verbs* (so it is no pct-pair) and its repeated runs are 2–3 tokens
(no 4-token window). Before filing a newly-stored row as a leak, grep the archive for
its distinctive number: a shape that *looks* chrome can be the counter-case that
proves the gate is correctly narrow.

**Second confirming sample of §2b, same day (23.09.26, buffer CAP-PINNED).** A later
cron turn opened on `cycle_a_technews: rejected … (46.1s)` with the buffer at exactly
**300/300** (`wc -l online_buffer.jsonl` → 300, keys `u`/`a`), and the tail-120 reason
split read `duplicate 57 · writer-gate 30 · junk 29 · no-tech-signal 4` — again
writer-gate second-largest with `junk` a minority. Same verdict, same reasoning: the
extractor gate passed those strings and the writer refused them, which is §5's
finding BC (cost in TIME, never a wrongly-stored row). **`duplicate` leading at the
cap is the expected shape** — a full buffer maximises near-dup hits — and per
SKILL.md's KTA note, `buffer at cap 300/300 — trim enforced on every write` is the
healthy steady state, not a fault to escalate. No gate edit. The escalation from
there was 3 further `--once` runs: 2 rejected (`c_github`, then a second `a`), 1
converted (`d_docs`, 111.0 s) — and the stored row was verified on-topic at the
buffer tail (`u`: "vLLM memory optimization techniques for 16GB GPU", `a`: chunked
prefill overlapping compute and memory access).

**23.09.26 needed FIVE runs, so budget for it** — one cron turn, `--once` in
sequence: `b_papers` rej 55.1 s → `c_github` rej 47.5 s → `d_docs` rej 56.3 s →
`e_competitors` rej 47.5 s → **`f_multi_domain` learned in 17.0 s**. Same verdict
as always: four honest rejects, one real learn, no gate edit. Two consequences for
the next turn:

- **Wall-clock is up to ~5 `--once` calls (~4.5 min)** when the rotation is cold,
  and each call must be its own `terminal()` invocation (the 60 s foreground clamp
  covers a *single* overrunning call, not the turn's budget). Do not stop after the
  first reject and do not shorten the streak into a single run and call the reject
  the outcome.
- **`elapsed_s` is NOT a signal** — the converting run was the FASTEST of the five
  (17.0 s vs 47.5–56.3 s for the rejects), and the existing sample has a convert at
  48.2 s alongside a reject at 52.5 s. The ranges overlap, so a fast run is not
  "a good sign" and a slow one is not "a doomed cycle". Read the `result` string,
  never the timing.

## 3. Attribute every `junk` hit to a NAMED rule

```bash
python skills/software-development/training-scripts-hygiene/scripts/which_rule_matches.py \
  --file candidates.txt
```

**Probe the FULL 300-char stored string.** A first pass over 120-char truncated
copies printed `INDIVIDUAL RULES MATCHED: none` and looked like a brand-new chrome
class; the full strings all matched existing documented helpers. Extract the
distinct full `a` values from the store and feed those.

Expected outcome when nothing is wrong: every leaf hit is an already-documented
helper (`_is_serp_snippet`, `_is_nav_chrome`, `_is_arxiv_abstract_chrome`,
`_is_own_plan_plus_run`, …), i.e. **zero novel shapes**. A composite
`_is_junk: False` alongside a leaf hit is also normal — the leaf is one component,
the composite gate is the verdict.

### 3b. Do not propose a gate edit before the two-sided replay

§3 names the rule that fired. The next question is the only one that justifies a
patch: **would changing that rule destroy already-stored knowledge?** Replay the
predicate over BOTH corpora — the stored `online_buffer.jsonl` (false-positive
floor: a sound predicate kills **0** rows carrying a verb + >=8 lowercase words)
and the `buffer_junk.jsonl` audit tail (true-positive yield, hand-read, not just
counted). Worked example (`_is_nav_list`, 21.09.26: 0 of 202 stored rows killed;
all 17 prosey audit survivors were reasoning-trace stubs → keep, patch nothing),
the "headline with no comma" strip→nav-list chain behind a mysterious docs-cycle
reject, and the source-level report template:
**`references/gate-false-positive-audit.md`**.

## 4. Are the `duplicate` rejects REAL duplicates?

Compare each rejected `(u, a)` against `online_buffer.jsonl` keyed by answer
prefix, then classify:

- answer already stored under the **same** `u` → true duplicate, gate is right;
- answer stored under a **different** `u` → near-duplicate, worth a look;
- answer not in the buffer at all → novel, the gate may be over-firing.

- Live: of 163 owned `duplicate` rejects, **162 were true duplicates** and 1 novel —
  the gate was correct. Buffer was at 291 of `MAX_BUF=300`, so this was genuine
  rotation exhaustion, not the 300/300 cap artifact.

**Re-measured 22.09.26 (answer-presence pass, 160-row tail):** of **71**
`duplicate` rejects, **64** had their `a` string already verbatim in the buffer ->
gate correct. Note the METHOD LIMIT: this pass only tests "is the answer already
stored", which is the first of §4's three classes. The **3-way keyed split**
(same `u` / different `u` / novel) was NOT run, so it does not supersede the
21.09.26 finding of 21 different-`u` + 6 novel rejects. Run the keyed pass before
quoting a true-duplicate ratio; answer-presence alone over-reports correctness.

Also worth logging per run: the store was at **247/300** (well below cap), so a
`duplicate`-heavy tail here is *genuine repetition*, not trim rotation (Root
cause B). Below-cap is the cheap way to rule B out before §1's record-vs-line
caveat matters.

### 4b. Two probes that LOOK like evidence and are not (measured 22.09.26)

A cron turn saw a 6-reject streak and set out to prove whether the gates had
become over-strict. Two of the measurements taken were structurally incapable of
answering that — both are worth naming, because each one alone would have
licensed an unjustified gate patch.

**Trap 1 — a reason histogram over `buffer_junk.jsonl` has foreign rows in it.**
Filtering the raw file (no owner split) printed
`last120 reasons: {duplicate 47, junk 30, writer-gate 23, pre-existing 17, no-tech-signal 3}`.
The `47 duplicate` looked like the smoking gun until the `u` values were read:
most carried `u:"verify question"` — that is the **foreign writer's** question
string, not a learner `OWNERS` prefix (§2). 47 counted both stores' traffic.
**Always run the §2 owner filter before quoting a reason histogram**, and note
that `buffer_junk.jsonl` rows carry **no `ts`** (keys are exactly
`reason`, `u`, `a`), so "last 120" is a pure tail slice with no time meaning —
say so instead of implying recency.

**Trap 2 — `_is_duplicate(rec, buf)` is a PURE predicate: False does NOT mean
"absent from the buffer".** A probe that replayed the audited texts as
`{'u': r['u'], 'a': cleaned}` printed `gate=False` for all six, which reads as
"the gate over-fires." The same rows also printed `in_buffer=True` (their first
50 chars are literally in `online_buffer.jsonl`). Both are correct at once: run
against the CURRENT buffer the predicate is False simply because their stored
`u` has aged out of the near-dup window — the ORIGINAL `duplicate` verdict was
taken at write time, against the buffer *as it then was*. So:

- **never conclude "duplicate gate over-fires" from a stale replay**, and
- **never conclude "these are honest duplicates" from `gate=True` either** — the
  same function answers True for any text in the file, which a substring check
  already tells you.

The honest reading is the PAIR: `gate` True-or-False **plus** the substring
presence **plus** which buffer state the original verdict saw. §4's keyed
same-`u`/different-`u`/novel split remains the only thing that classifies a
duplicate reject; the replay can only corroborate presence, never attribution.

**Also: the audit KEY is not `insight`.** `buffer_junk.jsonl` rows use `a` —
a probe written as `r.get('insight') or r.get('text')` silently reads `''`,
and `_clean_insight('')` then makes `_is_duplicate` return False for every row.
That is Trap 2 manufactured artificially: print `list(rec.keys())` first (§1c,
same failure family).

### 4c. Constructive control — prove the gates are NOT over-strict, without editing them

The cheapest positive evidence, and this session's decision-maker: take a topic
**provably absent** from the buffer, run the REAL pipeline once, and check it
lands.

```python
q = 'openamer documentation'                 # not in the buffer
text = il.deep_learn(q)                      # real page, real extractor
print(il._is_junk(text), il._writer_gate_refuses(il._clean_insight(text, 300)),
      buffer_store._is_duplicate({'u':'x','a':text}, 'online_buffer.jsonl'))
print(il.store('Internet learning (%s): What should an AI agent know?' % q, text))
```

Live result: `False / False / False` and `store() -> True`, buffer 274 -> 275
rows, the row present at the tail. A non-empty return from `store()` **is** the
end-to-end proof that extractor, both gates and the writer all pass clean prose —
which is what converts "6 rejects" from "suspect gate" into "rotation regime, no
patch." Do this BEFORE writing any verdict, and report it as the control; it is
strictly stronger than "the suites are green" (the suites never touch the live
buffer or the writer).

## 5. Check the extractor is not deterministic

`deep_learn(q, k=2)` vs `deep_learn(q, k=6)` on the same live query:

| query | k2 len | k6 len | k2 == k6 |
|---|---|---|---|
| `github trending AI agent framework 2026` | 251 | 251 | **True** |
| `vLLM optimization best practices` | 177 | 177 | **True** |
| `LLM prompt injection defense techniques 2026` | 144 | 144 | **True** |
| `arxiv new papers meta-learning LLM agents 2026` | 0 | 252 | False |

When they are byte-identical, the "second chance, wider net" retry re-proposes the
SAME string, so one honest refusal becomes a logged "both gated". That is a real
mechanism — but fixing it is an architecture change to URL selection, and this is
the documented **root cause AG** (deliberately unpatched). Do not fix it on a
rejection alone.

## Correct stopping state

Stop gate work when ALL of these hold:
- junk leaf hits are all pre-existing helpers (no novel shape);
- duplicate rejects are provably already stored (159/161 on 20.09.26; but
  **145/172 on 21.09.26** — the duplicate gate has since been over-firing: 21 of
  172 rejects reused an existing `u` with a DIFFERENT `a`, and 6 were
  unattributable/novel. Re-measure before concluding "already stored"; the ratio
  is not stable across dates, so the 20.09.26 figure alone must not be reused);
- and, refined 20.09.26 (finding BC): the `junk` rejects are 71 % WRITER-only
  (82 of 115 distinct candidates fire `buffer_store.is_junk` but NOT
  `internet_learner._is_junk`) -- the extractor gate deliberately lacks 6
  writer helpers (`_is_serp_snippet`, `_is_nav_chrome`, `_is_periodic_repeat`,
  `_is_binary_noise`, `is_prompt_echo`, `is_junk`), so a SERP-shaped candidate
  costs a full store -> deep_learn(k=2) -> deep_learn(k=6) excursion before the
  writer refuses it. Cost in TIME, never a wrongly-stored row -> not a gate bug.
- the buffer is below cap.

That combination means **the seed space is exhausted, not the gate miscalibrated**.
Record the finding and leave the code alone.

## Reporting what the cycle stored (the non-rejection case)

Triage above is for a REJECTED cycle. When the cycle returns `learned: …`, that line
is a claim about the gates having accepted a string — not proof that knowledge was
stored. The store-side evidence (which file, which keys, and the `u`/`a` case trap
that makes a naive probe die with `KeyError: 'U'`) plus the two tells that separate
real knowledge from an accepted abstract stub live in
**`references/cycle-evidence-reporting.md`**. Read it before writing up any cycle
result; it carries the one-line report template.

## Full library

The per-class root-cause archive (120+ numbered findings), the standing traps, and
the publish/verify recipe live in the **`internet-learner-stall-fix`** skill and
its `references/root-causes-archive.md`. Read it BEFORE touching any gate.

**That skill is USER-OWNED** (`created_by=None`) — autonomous curator writes are
refused, including `write_file`. When a new root cause belongs in it, do NOT retry
the write: record it here (or in a `references/` file of THIS skill) and tell the
user to run `openamer curator adopt internet-learner-stall-fix` if they want it
adopted for autonomous curation. Its SKILL.md is also at its 100 KB cap, so even a
foreground agent must append to `references/root-causes-archive.md` (LF-native —
a CRLF append flips ~60 lines) and add only a one-line pointer.
