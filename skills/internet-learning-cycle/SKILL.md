---
name: internet-learning-cycle
description: Run one internet learning cycle to gain new knowledge.
category: autonomous-learning
---

> A cycle's logged `result` is truncated to ~80 chars; the full insight is the `a` field in `scripts/training/online_buffer.jsonl`. Recipe: `references/full-insight-retrieval.md`.
>
> Before reporting a cycle's outcome: one invocation is NOT the whole rotation (run 2–3, a second learner process shares `.il_rotation`), and a `learned` line's named artifact needs a lookup before you relay it. Detail + the 16.10.26 rate/reason numbers: `references/reject-triage-and-concurrent-cycles.md`.

## Which interpreter: bare `python` is the WRONG venv (live 18.11.26)

```
$ python scripts/training/internet_learner.py --once
[internet-learn] cycle_c_github: error: No module named 'lxml' (21.8s)
```

`python` on this host's PATH resolves to
`$OPENAMER_HOME/openamer-agent/venv/Scripts/python.exe`, which has **no lxml** — the learner
needs it for the docs/github cycles, so the cycle was lost and reported an error. The training
venv does have it (`lxml 6.1.3`). Always name the interpreter:

```bash
"$OPENAMER_HOME/venv/Scripts/python.exe" scripts/training/internet_learner.py --once
```

Same command, right venv: `cycle_d_docs: … (36.6s)`, `cycle_f_multi_domain: … (43.7s)` — both
learned. A cycle that dies with an ImportError is an environment verdict, not a "no insight"
result; do not read it as a learning stall.

## Run the cycle in the BACKGROUND — foreground `terminal()` hangs (17.10.26)

`python internet_learner.py --once` took **65 s** when run via
`terminal(background=true, notify_on_complete=true)`, but the SAME command via
foreground `terminal(timeout=300)` and `terminal(timeout=600)` both returned
**exit 124 (timed out)** and wrote NO log entry — the cycle never finished in the
foreground, even though it completes quickly in background. Reproduced twice.

A single `--once` invocation does 1–3 live web fetches plus a
`/v1/chat/completions` round-trip, so wall time ranges **65–245 s** (measured:
`cycle_d_docs` 245.1 s, `cycle_g_security` 65.3 s). Foreground terminal kills it
before it lands.

Rule for this skill:
- Always run a cycle as `terminal(command=..., background=true,
  notify_on_complete=true)`, then `process(action='wait', timeout=...)`.
- Never report "the cycle failed" from a foreground timeout — re-run in
  background and read the log (match `ts` + `elapsed_s`, see
  `references/reject-triage-and-concurrent-cycles.md`).

## Filing a gate candidate (never half-implement a gate in a cron run)

A cycle can store garbage that BOTH learner gates accept. Do NOT start wiring a
gate when you find one unattended — a half-applied gate leaves uncommitted
learner code (the AV trap). Record the exact leak string plus its 0-FP
discriminator measurement in `references/pending-candidates.md` (and, if the
learner skill's archive is not writable, in the non-git
`OPENAMER_HOME/logs/learner-candidate-classes.md`) so nothing is left
uncommitted, and say so in the report.

## Measure health BEFORE calling it a stall (23.09.26)

A single `rejected, not trained (shallow + deep read both gated)` line is NOT a
stall. Measured 23.09.26: 152 cycles that day, **65 accepted = 43%**, and the six
most recent accepts were minutes apart (12:12, 12:19, 12:27, 12:42, 12:48).
Treat one rejected line as normal noise and measure first.

**The trap that fakes a stall.** `internet_learn_log.jsonl` rows are
`{ts, source, result, elapsed_s}` — there is **no `accepted` boolean**. A
rejection is the literal `result == "rejected, not trained (shallow + deep read
both gated)"`; an ACCEPT is encoded in the SAME field as
`<prefix>-learn: <text>` (`security-learn:`, `doc-learn:`, `paper-learn:`,
`github-learn:`, `domain-learn:`, `competitor-learn:`, `efficiency-learn:`, and
sometimes the bare `learned:`). So `r.get('accepted')` is `None` for EVERY row
and filtering on it reports "0 accepts / learner is dead" on a healthy learner.
This is the same family as the `"learned" in result` UNDERCOUNT noted at the top
of this file — both come from guessing the log's shape instead of counting it.
Use:

    def ok(r):
        res = str(r.get('result') or '')
        return bool(res) and 'rejected' not in res

**`buffer_junk.jsonl` has NO timestamp.** Rows are `{reason, u, a}` only, so
`'2026-09-23' in str(r.get('ts',''))` finds nothing and reads as "nothing
happened today". Date a class via `internet_learn_log.jsonl` (timestamped); the
junk log gives COUNTS and ordering (`idx N of total`) only, never age.

**An accept string is a CLAIM, not proof.** Verify with
`md5sum scripts/training/online_buffer.jsonl` before/after — do NOT compare line
counts: the buffer sits at its 300-row cap and `enforce_cap` trims it back, so a
REAL append leaves the count unchanged (documented at `internet_learner.py`
~L335; re-measured 23.09.26: md5 `c6b65ddd` -> `7af6a18b`, `wc -l` 300 -> 300).

**Rotation:** `.il_rotation` holds the next cycle index; the learner walks
a,b,c,d,e,f,g,h. Two consecutive `--once` runs hit DIFFERENT sources and may
legitimately disagree — never compare them as the same experiment.

**When the rejections ARE real**, triage `references/rejection-triage.md`.

**A stored row is not a GOOD row.** An accepted cycle can still write a bad
example — `references/non-english-distillate.md` (a German Azure paragraph as
the `a` under an unrelated English `u`, let through by the `deep_learn`/
smart_route door because the distill prompt does not constrain language;
measured 2/300, and the two obvious fixes are already MEASURED-AND-REJECTED
in-repo, so do not re-ship them. Its class number is UNVERIFIED — do not cite
one: 164 already collided, so grep first).

Use when you need to run one iteration of the Mini-OpenAmer internet learning cycle to acquire new knowledge from tech news, papers, GitHub, docs, or competitors.

> "Rejected" = rotation exhaustion; never edit a gate on one rejection. Triage
> `references/rejection-triage.md`: `rejection_rate_table.py` (rates),
> `gate_attribution_probe.py` (attribution), `query_ledger_audit.py` (§1b),
> §1b-ter log-order + regex-escape traps, gate positive control, §1c store-KEY
> trap (`u`/`a`) + §1d live probes, §2b writer-gate-dominant split (a
> `duplicate+writer-gate` tail with `junk` in the minority = gates working,
> still no patch) + `_novel_query()` ×4 generator control, §4b owner-filter + stale `_is_duplicate`
> replay traps, §4c constructive `store()` control (proves the gates are NOT
> over-strict without editing them); skill-only change →
> `references/skill-change-verification.md`; cron traps (incl. §8: `--help` HANGS,
> `learn_rates.py` is a phantom, and a `"learned" in result` census UNDERCOUNTS
> every `*-learn:` source — the most damaging measurement error in this workflow)
> → `references/cron-cycle-constraints.md`; an off-topic row that PASSED every gate
> (hallucinated query in `u` / vLLM server-log chrome) and the purge tool's
> `--text-key` field trap →
> → `references/offtopic-rows-and-purge-tool-field-trap.md`.

**Run the PACKAGED probes before hand-writing a census, and calibrate the rate
before calling it a fault** (both re-learned 23.09.26 on a single `--once` that
reported `rejected, not trained`):

- A rate census and a stage-probe were hand-written as two new temp scripts;
  both already ship here (`scripts/rejection_rate_table.py`,
  `scripts/gate_attribution_probe.py`). Triage order: **packaged probes → read
  the audit reasons → only then write something new.**
- The census reproduced §2b's rule: audit reasons over the last 400 refusals were
  `duplicate 210 / writer-gate 99 / junk 84 / no-tech-signal 7` — a
  `duplicate+writer-gate`-dominant tail with `junk` in the minority, i.e. **the
  gates are working and no patch is warranted.**
- **Calibration: ~55–60% rejection over the recent window is the NORMAL steady
  state here**, not a stall. Measured: 33% across all 2,716 logged cycles,
  57–60% over the last 100–300, 56% that day; 5 of the last 12 cycles learned.
  A lone `rejected, not trained` is the success signal for gate work — never
  grounds to edit a gate on one observation. An `_is_article_byline_chrome`-shaped
  candidate in particular needs a before/after delta over `buffer_junk.jsonl`.
- **Name every throwaway probe `_tmp_*`.** The 23.09.26 probes were called
  `_probe_e.py` / `_probe_byline.py` — NOT matched by the documented cleanup glob
  (`rm -f _tmp_*.py`) — so they lingered and kept resurfacing in changed-path
  reports after deletion. `scripts/training/` already carries this litter from
  earlier sessions (`probe_gatecause.py`, `probe_rates.py`, `probe_urlcount.py`,
  `tmp_junk_probe.txt`, plus `.bak<date>-<time>` siblings). One prefix, one glob,
  deleted in the same turn, confirmed with a per-file existence loop (never a
  recursive `find`).

## Steps

1. **Tool server**: `curl -s http://localhost:8081/health` must show
   `"status":"alive"`; else start it:
   `scripts/training/tool_server.py` (same dir as step 2's script).

2. **Run once** — in the BACKGROUND, never foreground:
   ```bash
   python C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/internet_learner.py --once
   ```
   Foreground `terminal(timeout=300/600)` returns exit 124 and writes NO log entry
   even though the cycle completes in ~65–245 s (see the section at the top of
   this file). Start it with `terminal(background=true)`, then
   `process(action='wait', timeout=...)`; match the result by `ts` + `elapsed_s`.

4. **Capture the output**.  
   The script prints a single line starting with `[internet-learn]` describing what was learned.  
   Example: `[internet-learn] cycle_a_technews: learned: AI News Today, September 13: Top Stories | AI Weekly — The companies cited a McK (10.4s)`

5. **Handle missing dependencies**.  
   If the tool server fails to start due to missing packages (e.g., `torch`, `accelerate`, `peft`, `transformers`), install them in the Hermes agent venv:
   ```bash
   /c/Users/damir/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe -m pip install torch accelerate peft transformers
   ```

## Verify the cycle actually learned something

A cycle that prints `rejected, not trained (...)` or `no insight` **learned
nothing** — that is the honest outcome, not a success. Since 13.09.26 every
cycle writes through `store()` (`internet_learner.py`), which refuses page
chrome before it can pollute the LoRA training buffer:

- `_is_junk` — nav text, login walls, marketing slogans, DE/PL ad chrome
  (Wikipedia donation banner, "Werbepartner/Ferienwohnungen", "Przepisy/Kuchnia"),
  **vendor first-person boilerplate** (SSL/website-compliance chrome in the
  site's own plural voice — "Für die sichere Datenübertragung nutzen wir
  256-Bit-TLS-…"; the bare digit 256 satisfies the technical-signal gate, so
  the voice is the only reliable giveaway; live 14.09.26),
  and **leaked LLM instruction templates** — the fallback model's own
  extraction scaffolding echoed back verbatim ("Identify the Core Task …
  Extract ONE technical insight … Target audience: autonomous AI agent.",
  live 14.09.26).
  When adding a pattern of this class, key it on the *voice*/phrase, never on
  the topic — a genuine "TLS 1.3 removes a handshake round trip" insight must
  still pass (counter-case already in the test corpus).
- `_clean_insight` — percent-escapes are decoded first (the digits of `%20`
  otherwise satisfy the technical-signal gate), then a candidate under 90 chars
  must contain a number or a technical noun/verb.
- Every refusal is appended to `buffer_junk.jsonl` with a reason, so check
  `tail -n 5 scripts/training/buffer_junk.jsonl` when a cycle "learns" nothing.

**Adding a new junk class** (extractor + writer gate, case-sensitive
affordances, measure-before-patch, mtime-not-sort backup selection, live/repo
sync): `references/new-junk-class.md` — read it before touching the gates.

After a change to the gates, verify for real:
```bash
python3 -m pytest scripts/training/test_internet_learner.py -q           # pure-logic suite (no network)
python -m pytest tests/scripts/test_internet_learner_gate.py -q  # 6 hermetic gate tests
python scripts/training/scrub_rejected_buffer.py                  # archive pre-fix pollutants
tail -1 scripts/training/online_buffer.jsonl                      # what actually got stored
```
**Interpreter note.** `python` in this shell = `openamer-agent/venv`, which has
**no pytest** — an import failure there is an interpreter mismatch, not a test
failure. Use the **live venv** (real dependency set) for live `scripts/training`:
`venv/Scripts/python.exe -m pytest`, git-bash form
`/c/Users/damir/AppData/Local/openamer-laptop/venv/Scripts/python.exe`.
`py_compile` needs the native path form (`"C:/Users/.../f.py"`), not `/c/...`.

**`npm run test` — RE-MEASURED 14.10.26: read the target from `package.json` at
call time; it is now `bash scripts/run_tests.sh`, and the note below is STALE.**
`scripts/run_research_tests.sh` **no longer exists** (`ls` → `No such file or
directory`), so the 23.09.26 line "`research suite: 46 passed, 0 failed`" cannot
be reproduced — do not repeat it, and do not report `--fast` output that no
script can produce. Measured this session: the full `npm run test` run
**exceeded the 600 s foreground cap** and was killed by the tool (a cap, not a
suite failure) — budget it as a background job, never as a bounded foreground
call. What IS usable in a bounded run is the runner SCOPED to paths:
`bash scripts/run_tests.sh <file> [<file>]` spawns one `python -m pytest <file>`
per file (which also satisfies the "one file per process" rule below). Measured
14.10.26 on the two gate files: **248 passed, 0 failed** (`224✓` + `24✓`, 74.1 s,
32 workers). A remembered npm-script behaviour is the same class of error as a
remembered metric. Traps + per-workspace error table:
`references/verification-traps.md`, `references/monorepo-npm-verification.md`.

Also: passing both gate-suite paths in one pytest run aborts with
`import file mismatch` — run **one file per process** (both paths share a
basename).

**There are THREE copies of `scripts/training/` — know which one you are
testing** (live 16.09.26, cost a full false-failure cycle):
1. `~/openamer-repo/scripts/training/` — source of truth, git, what you commit.
2. `$OPENAMER_HOME/scripts/training/` — **what cron actually executes**; not a
   git repo; updated by copying from (1).
3. `$OPENAMER_HOME/openamer-agent/scripts/training/` — a **separate, older git
   checkout** (its own `.git`, same `origin`, tens of commits behind,
   diverged). Running ITS test suite against new expectations fails loudly and
   means nothing. Never `cp` fixes here; check `git -C … log --oneline -1`
   before trusting any directory's version. `git status` in this checkout
   accumulates junk files (e.g. names with a `\357\200\272` byte) — leave them.
Confirm the runtime module before claiming a live fix:
```python
import internet_learner as il; print(il.__file__)
# -> .../openamer-laptop/scripts/training/internet_learner.py   (copy 2 = live)
```
`scrub_rejected_buffer.py` backs up the buffer (`online_buffer.jsonl.bak.<ts>`)
before moving rejected rows to `buffer_junk.jsonl`; on 13.09.26 it removed 136
of 300 rows that were accumulated chrome. Changes must be made in
`~/openamer-repo/scripts/training/internet_learner.py` (source of truth) and
then copied to `$OPENAMER_HOME/scripts/training/` — the cron runs the HOME copy.

**Diff repo vs HOME BEFORE editing** (live 14.09.26): the two copies had drifted
36 lines apart — HOME carried the newer `store_or_deep()` fallback while the repo
still held the pre-refactor `if not store(` cycle bodies, so "edit the source of
truth" was editing stale code. Always:
```bash
diff <(tr -d '\r' < ~/openamer-repo/scripts/training/internet_learner.py) \
     <(tr -d '\r' < $OPENAMER_HOME/scripts/training/internet_learner.py)
```
**Reconcile direction is NOT fixed — verify which side is right** (live
15.09.26): the 14.09.26 note below had the repo ahead; two days later HOME led
by 218 lines (`_fresh_headline` HN-Algolia path, `.il_seen_queries` novelty
ledger, `_usable_urls`) while the repo still held the pre-fix bodies. Decide by
evidence: run both suites on the candidate copy
(`python3 -m pytest scripts/training/test_internet_learner.py tests/scripts/test_internet_learner_gate.py -q`
→ 26 passed) and check a live `--once` reports `learned:`/`paper-learn:`. The
verified-correct copy wins, gets copied over the loser, and is committed with
the reasoning in the message (commit `75b564c5d`). Sync the *test* file too —
it drifts with the code (`test_internet_learner.py` was 19 lines stale).
If they differ, reconcile *first* (verified-correct direction wins), then add the
gate pattern, commit, and re-diff to confirm IDENTICAL.

Full junk corpus (every chrome class with the verbatim string it produced), the
two-layer gate design (`store()` → `_is_junk` / `_clean_insight`) and the recipe
for extending it without swallowing real insight:
`references/junk-classes-and-quality-gates.md`.

**The gate is not enough — the DOWNSTREAM WRITER needs its own relevance check**
(live 16.09.26). A row your `_is_junk` misses does not stop at the buffer: the
`auto_skill_creation` cron reads `kta_log.jsonl` / `online_buffer.jsonl` and
writes it into a permanent `skills/auto-generated/*/SKILL.md`. Live: a Chinese
software-download SEO page became
`auto-efficiency-learning-efficientqat-llm`, whose description and trigger were
pure ad copy — **even though the KTA experiment had itself reported "no
mappable capability in latest signal"**. A correctly-detected non-result is not
honoured by the writer; the check must exist where the file is written.
Writer-side detail (the two rejected gate shapes, the structural two-marker fix):
`training-scripts-hygiene` → `references/writer-side-relevance-gate.md`.

Rule that generalises: **for every new junk class, ask how far down the pipeline
it travels.** A learner-level gate protects the LoRA buffer; a writer-level gate
protects the repo. Same class, two different sinks — fix the one you can prove,
then check whether the sink downstream needs the same predicate.

**A cycle that still reports `learned: <chrome>` is not a broken run — the gate
is stale.** Take the offending string verbatim from the log, add the narrowest
pattern at the right layer, add a counter-case to the test in the same change,
rerun the scrub, then run one real cycle to confirm. Never widen a pattern to a
bare word (`login`, `tools`) to make a symptom disappear — real insights die
with it.

### A fifth junk class: mis-decoded BINARY bytes (live 15.09.26)

`cycle_b_papers` logged `paper-learn: T?p?%??;?"???J?8??j?s?Y?k?????\` — ~80 chars
of raw arxiv **PDF/compressed bytes** that `deep_learn` had decoded as text. It
cleared BOTH gates: length ≥ 25, and the digits inside the blob satisfied the
technical-signal gate; `is_glued_motif` / periodic-repeat see noise, not a motif.

Spot it in one line (do not eyeball the log — the terminal renders it as `?`):
```python
import json
g = json.loads(open('scripts/training/internet_learn_log.jsonl',encoding='utf-8',errors='replace').read().splitlines()[-1])['result']
sum(1 for c in g if (ord(c) < 32 and c not in "\t\n\r") or ord(c) == 0xFFFD)   # >3 = binary blob
```

Fix (commits `455a31dfe` + `af1967714`): `internet_learner._looks_binary(text)` —
reject when >8% of the chars are control chars (excluding tab/newline) or U+FFFD —
wired as the FIRST check inside `_is_junk`, so `store()` audits the row as `junk`
and the cycle retries via `deep_learn` instead of poisoning the buffer. The class
is *mis-decoded bytes*, not a page, so any byte-shaped candidate is covered.

Build the char class WITHOUT literal escapes (`" \t\n" + chr(13)`): the `patch`
tool converts `\r`/`\n` inside a `new_string` literal into real control characters
and breaks the file (`SyntaxError: unterminated string literal` at your inserted
line) — see `windows-aware-file-edits` §4f.

Regression test lives in `tests/scripts/test_internet_learner_gate.py`: the exact
logged byte string as `_PDF_NOISE`, built as
`"".join(chr(c) for c in (0x54, 0xef, 0x70, …))` (no escapes anywhere), added to
the `CHROME` corpus plus a dedicated
`test_binary_blobs_are_rejected_and_prose_is_not`. Verify:
```bash
OPENAMER_HOME/venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py -q   # 11 passed
```
and assert against the REAL log line as well (garbage → `_is_junk` True, real prose
→ False), not only the synthetic fixture.

### A sixth junk class: bare-digit "signal" + App-blurb + task scaffolding (live 16.09.26)

Three shapes passed BOTH gates in one run and sat in the buffer as LoRA data:
`cycle_e_competitors` stored an **App-Store blurb** ("Things - To-Do List App
for Mac & iOS - Cultured Code — Things is the award-winning personal task"),
`cycle_f_multi_domain` stored a **bare document heading** ("Distinction between
classical and modern physics 2."), and the connection cycles stored the
extractor's **own task instructions** ("Situation 2: These", "Need find shared
underlying pattern.").

Root cause (one line): `_clean_insight` trusted any short (<90) candidate whose
`_TECH_HINT_RE` matched — but that alternation *also matches a bare digit*, so a
section numeral counted as technical signal. Fix: `_has_alpha_signal(text)`
requires an ALPHABETIC keyword below 90 chars; wired as
`if len(t) < 90 and not _has_alpha_signal(t): return ""`.
`_INSTRUCTION_OPENER_RE` handles the scaffolding — **anchored at the START and
imperatively voiced**, which is the whole point: the same cycles emit genuine
declarative ANSWERS ("The shared underlying pattern IS a closed-loop feedback
system …", 16 of them, all >=90 chars) that must stay learnable. A bare phrase
match eats both; only the opener voice discriminates.

**Prove a gate change with an old-vs-new DELTA over the live buffer, never with
"the tests pass".** Load `git show HEAD:…` as the old module and the working
copy as the new one, then diff their verdicts row by row:
```python
delta = new_rej - old_rej      # newly rejected -> every one must be junk
fixed = old_rej - new_rej      # newly ACCEPTED -> regressions, must be 0
```
Live result: 13 newly rejected, **0 regressions**, all 16 declarative answers and
all rows with a real keyword kept. Also assert the real prose survives explicitly
(`_is_junk` False on the sample insights) — a rejected insight is invisible.

**Re-runnable probe — do not hand-write this a fifth time:**
`scripts/gate_delta_probe.py` encodes the whole recipe (unique module names to
dodge the `sys.modules` collision, `__file__` assertions that you measured the
LIVE copy, leak/counter-case reporting, an empty-alternative guard, and a warning
when a counter-case is under 90 chars). Two modes:
```bash
# measure a CANDIDATE before editing anything (cand.py defines CAND/COUNTER/LEAK)
$OPENAMER_HOME/venv/Scripts/python.exe scripts/gate_delta_probe.py --candidate-file cand.py
# verify the pattern already applied to _JUNK_RE
$OPENAMER_HOME/venv/Scripts/python.exe scripts/gate_delta_probe.py --applied
```

### Pitfall: the two ways a regex alternation silently self-destructs

Both hit during the 16.09.26 gate change and both are invisible in review:

1. **A missing `|` at the end of a fragment WELDS two phrases together.** The
   whole `_JUNK_RE` is ONE implicitly-concatenated literal, so
   `r'"wt":"'` + `r"award-winning…"` became `"wt":"award-winning` — the previous
   rule was destroyed and its test failed. **Every fragment must end with `|`**,
   including the one you are inserting after.
2. **A trailing `|` before `)` creates an EMPTY alternative that matches every
   string** — the junk gate becomes "reject everything". Caught only by the
   delta measurement (300/300 rejected). **The last fragment must NOT end with
   `|`.**

`py_compile` passes in both cases — the file is valid Python, the regex is just
wrong. Neither the import nor a syntax check will tell you; the delta will.

### A seventh junk class: leading BYLINE chrome — strip, don't reject (live 16.09.26)

`cycle_f_multi_domain` stored a >90-char row headed by page furniture:

```
Written by Christian Gleitze · Published June 11, 2026 · Last reviewed July 23, 2026 AI Consciousness asks whether an Artificial Intelligence system could have subjective experience, ...
```

The extractor had legitimately pulled the article's **opening sentence** — the
byline merely *prefixed* it. At >=90 chars the "long prose is trusted" rule in
`_clean_insight` never looked closer, so chrome rode into the LoRA buffer.

Fix: `_strip_byline_prefix()` (commit `41d8e9aa4`) removes **leading**
byline/dateline segments before the text is judged, wired as the first
transformation in `_clean_insight` (right after the `%20` decode). **Strip, not
reject** — the knowledge is the sentence *behind* the byline; a reject-pattern
would have thrown a real insight away. Separators: `·`, `|`, `•`; also handles a
bare leading attrib with no separator (`... · Last reviewed July 23, 2026 AI
Consciousness asks ...`).

Guard that makes it safe: **both byline regexes require a real date literal or
`<verb> by <Name>`**. That is what keeps genuine prose alive — `"Published
research from Stanford in 2024 shows transformers scale ..."` and `"By contrast,
the 2024 study found ..."` match neither, so they pass untouched. Counter-cases
are asserted in `tests/scripts/test_internet_learner_gate.py::
test_byline_prefix_is_stripped_not_stored` (plus a bare-byline-with-no-body case
that must still be rejected).

### Second leak, same run: `_has_alpha_signal` saw only the FIRST match

Independent bug found while proving the above. The old body was:

```python
m = _TECH_HINT_RE.search(text)      # <- FIRST match only
return bool(m) and any(c.isalpha() for c in m.group(0))
```

`_TECH_HINT_RE`'s alternation starts with `\d+`, so real prose whose opening
technical-ish token is a bare number was rejected even though it carries a real
keyword: `"By contrast, the 2024 study found quantization recovers 97% of fp16
accuracy at INT4."` matched `"2024"`, never saw `"quantization"`, and scored as
signal-less. Fix: `for m in _TECH_HINT_RE.finditer(text): if any(c.isalpha()…)`.
Strictly *widens* acceptance to text carrying a genuine keyword, so no junk class
can slip in (delta-confirmed below). Regression test:
`test_alpha_signal_scans_past_a_leading_digit`.

### Prove a strip, not just a rejection: the delta must show the BODY intact

A strip-gate is a third verdict beside accept/reject, so a plain
newly-rejected/regressions delta is not enough — assert the surviving text is
**byte-identical to the original minus the byline**, or you may have quietly
truncated a real insight. Two traps hit while doing this:

- Compare full strings, not `_clean_insight(...)` output — the latter applies the
  300-char `max_len`, so three untouched rows looked "changed" purely from
  truncation. Use `_strip_byline_prefix` for the equality check.
- `re.Pattern` has no `.join` — a joined-remainder needs a separate string
  constant (`_BYLINE_SEP = " · "`), not the compiled separator regex.

Live result over the 270-row buffer: **0 newly rejected, 0 regressions, 8 rows
de-chromed** with the body byte-identical. Both suites: **40 passed**.

### An eighth junk class: live NEWS-TICKER loops + social-share widget chrome (live 16.09.26)

`cycle_a_technews` learned a row that is a **news ticker**, not a sentence:

```
Trump praised Bezos for reversal 03:15 White House blasted Amazon for tariffs
explainer, Trump praised Bezos for reversal (03:15) OpenAI backs measure that
would require independent audits of AI models The AI bubble is leaking air, some
economists say.
```

A ticker **re-renders the same headline with a fresh clock**, so the extractor
receives several unrelated headlines glued together and one phrase is present
**twice**. Both gates passed: the timestamps' digits satisfied the
technical-signal gate and the row exceeded the >=90 "long prose" trust.

Fix (commit `a735ebcc0`): `_is_ticker_loop(text)` — a time code (`_TIME_CODE_RE`)
**plus** a >=15-char phrase the text itself repeats. Wired into `_is_junk` and
mirrored in `buffer_store._is_nav_chrome` so every writer path is covered
(`buffer_store` must not import the learner — circular).

**A bare "two clock times" rule was measured and rejected as too broad**: real
prose can legitimately cite two times ("Two runs measure 03:15 and 04:20 wall
clock; the quantized model has lower inference latency in both."). Only the
*self-repeated phrase* is the ticker's structural signature. Delta over the
live buffer: catches the leaking row, **0 real-prose rows**.

Same run, same class — a **social share/follow widget** and a **counter
truncated at its own digit**:

```
March 17, 2026 (UPDATED Sep 8, 2026) 2026-09-08T13:12:23-04:00 Reddit Post Share Threads Support my work.
K followers 59-year-old woman found dead in Bay Ridge apartment; ...
```

`"K followers"` means the count's number was cut off — the text starts
mid-widget. Rules: the phrase `"support my work"` (a donation CTA, never a
technical statement) plus an anchored `^\W*[kKmM]\s+followers\b`. Both are
keyed on the widget **voice**, so a real sentence reporting a follower count
("Mistral has 30k followers on GitHub and ships its weights under Apache 2.0.")
still passes — asserted as a counter-case in
`test_social_share_widget_chrome_is_rejected`.

**Two lessons that generalize:**

- **A regex with `^` inside a big `|` alternation is a landmine.** The
  detached-counter fragment was written as its own compiled pattern and used
  via `match()` in `_is_nav_chrome`, NOT appended to `_JUNK_RE` — `re.search`
  would have let `^`-anchored branches fire mid-string and a `match()` on the
  whole alternation would have anchored every other fragment too.
- **When a counter-example fails, check WHICH rule rejected it** before
  "fixing" the test. Here `"The batch job starts at 03:15 CET and finishes
  before the morning traffic peak."` was rejected by the PRE-EXISTING short-
  candidate rule (no alphabetic technical keyword under 90 chars), not by the
  new ticker rule. The honest fix was to give the counter-case a real keyword
  and say so in a comment — not to widen the new pattern or delete the case.

**Verify a new gate class end to end** (all three commands, in this order):
```bash
# 1. old-vs-new delta over the live buffer: newly rejected must ALL be junk, regressions == 0
#    (load `git show HEAD:...` as the old module, the working copy as the new one)
# 2. the suites
OPENAMER_HOME/venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py \
    scripts/training/test_internet_learner.py -q          # 42 passed
# 3. scrub the stale pollutants, then ONE real cycle on a non-news source
python3 scripts/training/scrub_rejected_buffer.py
python scripts/training/internet_learner.py --once
```
This run's scrub dropped 13 stale rows (`kept=270 dropped=0` after), and the
next cycle learned a genuine technical row: `cycle_d_docs: doc-learn: ZMQ :5555
— data plane (vLLM connects here) Infrastructure requirements … GPU 16 GB VRAM
(CUDA 12+) 40 GB+ (A100, H100, GB10)`. **Do not stop at the first cycle** — the
leaking cycle may itself be the only one that ran; run one more and check the
LAST buffer row is on-topic.

### An eleventh class: blog header stacks + share widgets — strip, and mind WHITESPACE (live 16.09.26)

Three live rows of one family, each cleared both gates (timestamps fed the
technical-signal gate, length cleared the >=90 trust):

```
1  Team / JUN 1, 2026 / 0 comments AI Coding Agents: The Complete Guide to … 32 min read Share on Twitter , LinkedIn Software development is undergoing …
2  3 min read Illustration The Agent Times // Share X LinkedIn HN Copy link The specific article at the center of the storm remains …
3  AI agents Home News MIT News Published On: Nov 22 2024 Published on: May 21, 2026 Share Facebook Twitter Bluesky Fields ranging from …
```

All three are page furniture WELDED to real article text → **STRIP, not reject**
(the body is the knowledge). Four rules, each measured over the live buffer
(3 hits total, 0 real-prose rows):

| Rule | Shape | 
|---|---|
| `_BLOG_HEADER_STACK_RE` | `<name> / <DATE> / <N> comments` dateline |
| `_SHARE_WIDGET_RE` | share CTA **anchored** to a date / read time / `//` |
| `_LEADING_SHARE_WIDGET_RE` | a **>=2-platform** list opening the text (`Share X LinkedIn HN`) |
| `_COPY_LINK_RE` | the widget's own button label (`Copy link`) |

plus `_strip_read_time_header` also terminates on a `//` nav separator.

**Two measured-and-rejected candidates — keep them in the record:**
- *Voice-only* `share\s+on\s+<platform>` anywhere: ate real prose
  (`"We share on Twitter the benchmark results …"`) and truncated a second row.
- *Generic leading header* `(?:<verb>: <date>|<TitleCase run>){1,8} <N> min read`:
  matched `"A 32 min read of the vLLM docs shows …"` and
  `"The write-up is a 6 min read; …"` — 2 counter-cases. Rejected.

**The whitespace trap (cost a full delta cycle):** the first version ended with a
blanket `re.sub(r"\s+", " ", t)`, which reported **9 touched rows** where only 3
were chrome — 6 innocent rows were "changed" purely by whitespace collapse.
Collapse ONLY when something was actually removed:

```python
if t != (text or "").strip():      # something was stripped
    t = re.sub(r"\s+", " ", t).strip()
```

**And the suffix assertion is not universal.** After stripping the `//` header
the row 2 body reads `Share X LinkedIn HN The specific article …` — the anchor
that `_SHARE_WIDGET_RE` needs was consumed by the earlier read-time rule, so the
leading-list rule is what catches it. That means the survivors are **slices, not
suffixes**; assert `all(w in original for w in out.split())` instead of
`original.endswith(out)`, or you will "prove" a mangling that is really correct
behaviour. Final delta: **touched=3, all chrome, bodies pristine, 0 regressions,
0 whitespace-only diffs**, suites **46 passed**.

**FIXED 17.09.26 for the "read-time-CLOSED" shapes** (the family below), via
`_strip_trailing_read_time_header` — wired into `_clean_insight` after
`_strip_blog_header_stack`. Structure, not a word list: the head BEFORE the
read time must carry a real DATE literal AND **no sentence terminator once the
date matches are removed** (page furniture is a label chain and never ends a
sentence; prose that *mentions* a read time carries full stops). Head window
capped at 220 chars, body must be >= 5 words and start with an uppercase
letter. Measured live: 3/3 documented shapes stripped with the body
byte-identical, **0 of 8 counter-cases changed**, live buffer touched=7 (all
genuine header chrome), regressions=0, mangled=0; `tests/scripts/
test_internet_learner_gate.py` + `scripts/training/test_internet_learner.py`
→ **73 passed**. A rewrite pass (`_clean_insight`-style strict prefix
predicate: `new` is a suffix of `a`) de-chromed the 7 stale rows,
`de-chromed=7 skipped_non_suffix=0`.

**Two shapes remain open — both MEASURED, do not re-derive:**
- `"Start the challenge Blog 18 April 2026 / 24 min read 8 best open-source AI
  agent frameworks on GitHub in 2026 …"` — refused only because the headline
  opens with a **digit**. Relaxing the body-start condition to
  `isupper() or isdigit()` catches it and **eats a counter-case**
  (`"February 3, 2026 12 min read 4 of the 6 benchmarks in that suite were
  rewritten later, …"` → body truncated to `4 of the 6 …`). Measured:
  extra rows touched = 1 of 300. Accepted trade-off, stated in the code.
- `"AI Agents 11 min read AI Agent Cost Benchmarks: …"` — the read time sits
  **before** the headline instead of after, so there is no head to gate on.
  Class known, fix pending.
The earlier 4 `"… min read"` shapes (`"Updated: September 7, 2026 15 min read …"`,
`"General Compute · March 18, 2026 · 6 min read …"`, `"Building is my Passion
Post Cancel … 3 min read …"`, `"Feb 7, 2026 18 min read …"`) are covered.

### A fresh observed leak, NOT yet guarded: bare title + author HANDLE (17.09.26)

Final verification cycle (`cycle_e_competitors`) stored 89 chars with no prose:

```
U: Competitor intelligence: An AI agent coding skeptic tries AI agent coding, in excessive detail
A: Feb 2026 An AI agent coding skeptic tries AI agent coding, in excessive detail minimaxir.
```

A HN-style headline plus a trailing **author handle** (`minimaxir.`) — a title
restated, not a sentence. It clears the >=90 trust *and* `_has_alpha_signal`
(a real keyword is present), so **neither gate fires and no reject pattern is
warranted yet**: gating the handle alone would eat prose that names a source.
The honest state is "observed, unguarded". The next cycle's row
(`cycle_f_multi_domain`: "A collection of methods in an intelligent software
structure allows the user to focus on fine-tuning and model selection, while
TorchPhysics takes care of the technical details in the background.") WAS
genuine technical prose, so **one leak does not make the cycle broken**.

### Classes 26–27: status banners + release-note chains — both keyed on the PAGE's own shape

Two leaks found in one 17.09.26 verification session, one per source. Both
cleared both gates the same way (the familiar **number-fed hole**: a date or
version stamp satisfies `_TECH_HINT_RE`, whose alternation starts with `\d+`,
and the length clears the ≥90 trust). Verbatim strings, the full counter-case
sets and the round-by-round measurements: `references/status-and-release-chrome.md`.

| # | Live string | Guard | Discriminator |
|---|---|---|---|
| 26 | `Login This service will be unavailable from Sep 18, 2026 19:00 PDT to Sep 19, 2026 2:00 PDT due to maintenance.` | `_is_maintenance_banner` | TWO markers ANDed (a dated **window** joined by `to`/dash AND the **announcement voice**) **plus** `head ≤ 40` / `tail ≤ 40` around the announcement span |
| 27 | `FLUX ( QEffWanPipeline , QEffFluxPipeline ) More [12/2025] Enabled disaggregated serving … [12/2025] Added support for wav2vec2 Audio Model … [12/2025] Added support for diffuser video generation model WAN 2.` | `_is_changelog_chain` | ≥3 (version token, release verb) pairs AND **no prose connector** |

**Class 26 — the head/tail condition is the whole safety argument.** The window
marker alone was measured and REJECTED: `unavailable|downtime|outage` + one
dated timezone stamp hit four real-prose counter-cases ("The service will be
unavailable from Nov 3, 2026 22:00 UTC **for four hours**, so the retriever
queues requests…"). A banner ANNOUNCES a window and is essentially the whole
message; prose that DESCRIBES one carries context around it. Measured over 7,070
rows: leak head=0/tail=18 caught; the hostile counter-case ("A row like service
unavailable from … is a banner, not an insight; the gate must reject it.")
scored head=35/tail=52 and survives. **Sweep the threshold and print the
head/tail numbers of every candidate row** — that table is what picks 40/40,
not taste.

**Class 27 — the connector prohibition, not the version count, is the
discriminator.** `x2` entries caught the leak but ate prose that cites two
versions ("The v0.9.1 release added streaming output **and** v0.9.3 improved
KV-cache reuse, **so** …") and even prose that says the same words run-together.
`x3` + "no prose connector" (`which|so|because|therefore|thus|hence|although|
whereas|while|is exactly|making|allowing|giving`) landed at 6/7 listings caught,
**0/16 counter-cases hit, 0 genuine-buffer FPs, 0 hits across
kta_log/internet_learn_log/world_model**. That is the same rule as the nav-strip
family: *a menu is a LABEL CHAIN, a sentence has grammar.*

**Accepted trade-off, stated in the code:** a **two-entry** listing is NOT
caught. Two version+verb pairs are genuinely ambiguous against prose, so the
rule stops at three. Write that into the docstring — an unmeasured "we handle
changelogs now" claim is worse than the gap.

**Both guards are their OWN compiled predicates**, never fragments of the big
`_JUNK_RE` alternation (the missing-pipe / empty-alternative traps are
structural there). Mirror each in `buffer_store._is_nav_chrome` by calling the
same-shaped local function — `buffer_store` must not import the learner.

### Classes 28–29: ad-wall CTA chains + dated header stacks (live 17.09.26)

Two leaks in one session, one per source, both through the familiar
**number-fed hole** (`_TECH_HINT_RE` starts with `\d+`, so a price or a date
counts as technical signal) plus the ≥90-char trust.

| # | Live string | Guard | Discriminator |
|---|---|---|---|
| 28 | `Adblocker ausschalten Duden im Abo Nutzen Sie Duden online ohne Werbung und Tracking auf allen Endgeräten für nur 2,99 €/Monat.` | `_is_adwall_notice` (REJECT) | notice **voice** (blocker + `ausschalten`) AND an **offer signal** inside one 240-char span |
| 29 | `OWASP GenAI LLM Top 10 2026 OWASPGenAIProject Editor / August 3, 2026 / Resources OWASP Top 10 for LLM Applications 2026 is the latest community-driven guide …` | `_strip_dated_header_slash_stack` (STRIP) | **label-like head** (no terminator, ≤1 lowercase word, no function word) + date between slashes + **single-token** closing label + body that opens a sentence |

**Class 28 — key the notice's own CTA shape, never the topic.** `_is_adwall_notice`
is one regex (a bounded `[\s\S]{0,240}?` between the two halves), so a bare
`adblocker`/`Werbe`/`ohne Werbung` token can never fire. Counter-cases asserted:
a RAG sentence about an interstitial, an ad-blocker-**detection** fingerprinting
sentence, a paywall sentence citing `4,99 €`, and the leak's own reworded meta
sentence. Measured over 7,180 live rows: 2 hits, both the SAME leaking row
(buffer + learn log), 0 real-prose rows.

**Class 29 is the SECOND variant of a page already in the record** — the class-14
rule strips its `SECURITY resources Whitepapers/Guides …` head. When a leak looks
familiar, grep the skill for the page/site before inventing a new rule; same
family, and class 14's discriminator transfers verbatim: **a menu is a LABEL
CHAIN, a sentence has grammar.** The two strings that killed the generic
`<nav-run> <date> <body>` rule on 16.09.26 (`Whitepapers/Guides are listed on the
site; the August 3, 2026 revision adds …`, `The paper compares German/English
tokenizers on a March 3, 2026 benchmark …`) are the regression fixtures and stay
untouched. Delta: 1 row de-chromed, body **byte-identical**, 0 regressions,
0 whitespace-only diffs.

**Two gate-shape rules that keep biting:**

- **`buffer_store.py` has no bare `re`** — it does `import re as _re`. A copied
  learner pattern using `re.compile` / `re.IGNORECASE` imports fine and dies at
  call time with `NameError: name 're' is not defined` *inside the module*,
  29 tests red at once. Mirror with `_re`.
- **A counter-case can be killed by a PRE-EXISTING marker, not by yours.** The
  meta counter-case for class 28 contains the word `subscribe` → refused by
  `_NAV_CHROME hit ['subscribe']` (16.09.26 class). `diagnose_gate_rejection.py`
  named the culprit in one call; the honest fix was to rephrase the fixture and
  state why, not to touch either rule.

**Cleanup pairing, same session:** REJECT → `_drop_offtopic_row.py "<marker>"`
(`rows=300 dropped=1 kept=299`); STRIP → `rewrite_buffer_strip.py --strip-fn
_strip_dated_header_slash_stack --apply` (dry run first; it backs the buffer up
and prints the LAST ROW). Then ONE real cycle: it learned a genuine row
(`cycle_h_efficiency: Part 2: Introduction to Quantization … 32-bit floating
point to 8-bit integers`).

### Class 31: the page's own `About <Title> ... is the latest ...` META blurb (live 17.09.26)

`cycle_g_security` stored the OWASP landing page's **self-description** as if it
were a fact about the world:

```
About OWASP Top 10 for LLM Applications 2026 is the latest community-driven
guide to the most critical security risks facing applications powered by large
language models.
```

**The instance is ON-TOPIC, so relevance cannot be the discriminator** — the
same lesson as class 22 (course CTA). The discriminator is the page's own
promotional **VOICE**: a nav label welded to a self-descriptive predicate.

Guard `_is_page_meta_blurb` — two markers ANDed, **both anchored**:
`^\s*About\s+\S[\s\S]{0,200}?\bis the latest\b`.

**Measure each marker ALONE before ANDing — both were REJECTED:**

| candidate | hits | proseFP | counter-case that killed it |
|---|---|---|---|
| `^About\s+\S` | 7 | **5** | `About half of the quantized models we benchmarked lose under 1 point of accuracy …` / `About GDPR compliance, the 2026 rules require …` |
| `\bis the latest\b` | 7 | **2** | `This paper is the latest work on post-training quantization, and it recovers 97% …` / `Home page rendering is the latest bottleneck our profiler found …` |
| `^About\s+[A-Z]` | 4 | 2 | `About OpenAI's safety framework, the interesting part is …` |
| **both ANDed** | **4 (1 unique)** | **0** | — |

`^About \S` **alone is far too broad**: the adverb `About` is ordinary English
openers. Only the anchored PAIR is the meta voice. The anchor is what keeps
`The docs page opens with About OWASP Top 10 … is the latest guide, and the
index below lists all ten risks.` learnable (asserted).

**The trap this class set — a PRE-EXISTING test asserted chrome learnable.**
`test_leading_nav_label_stack_is_stripped_not_stored` (class 14) uses the
VERBATIM logged row of THIS page, whose `body` is precisely this meta blurb, and
asserted `_clean_insight(leak) == body`. The rule correctly killed it, the suite
went red, and the honest fix was **not** to weaken the rule: assert the class-14
*contract* ("the sentence behind the nav survives") with a genuine insight
(`Prompt injection is the first of ten categories in the 2026 guide, and the new
agent-tooling class covers tool-call abuse directly.`), and move the meta-blurb
case into `test_page_meta_blurb_is_rejected` where it belongs. **When a gate
change kills an old fixture, ask whether the fixture was testing the right
thing** — do not relax the gate to keep a chrome assertion green.

**One leak can hide inside another class's fixture, and the delta will not tell
you.** The delta is clean (4 newly rejected = 4 copies of the one row,
regressions 0); the conflict surfaces ONLY in the suite, because the same string
serves as a *body* elsewhere. Run the suites in the SAME change as the delta.

Cleanup: `_drop_offtopic_row.py "is the latest community-driven guide to the most
critical security risks"` → `rows=300 dropped=4 kept=296`. One real cycle then
learned a genuine on-topic row (`cycle_h_efficiency: Quantized LLMs: Advanced
Techniques … low-bit precision for weights and activations, significantly
reducing computational and memory overhead.`). Suites: **76 passed**.

### Classes 163–164, 166: a publisher AGE NOTICE (strip) + section-TOC chain + badge weld

All shipped 23.09.26, all found the cheap way — a `--once` that STORED, then
reading the last buffer row. All cleared BOTH gates through the familiar
**number-fed hole** (`_TECH_HINT_RE`'s alternation *starts* with `\d+`) plus the
≥90 trust. Verbatim strings, per-candidate measurement tables and the refuted
variants: `references/news-age-notice-and-section-toc.md`.

| # | Live string (truncated) | Guard | Discriminator |
|---|---|---|---|
| 163 | `I violated every principle I was given’ This article is more than 4 months old PocketOS was left scrambling … Supported by About this content Sanya Mansoor Thu 30 Apr 2026 00.12 CEST Last modified on …` | `_strip_news_age_notice` + `_is_news_age_notice` (STRIP) | the publisher's OWN label PAIR: age notice **AND** `Supported by About this content` |
| 164 | `Report Issue Back to Abstract Download PDF Abstract 1 Introduction 2 DeepSeek-R1-Zero 2.1 Group Relative Policy Optimization … 3.2.1 Traini` | `_is_section_toc_chain` (REJECT) | the `Download PDF` affordance **AND** a run of ≥3 `N.N <Title>` labels |
| 166 | `… Latest AI Resources 2yrs agorelease AI Sharing Circle 101.9K 0 0 General Introduction ANUS …` | `_is_ago_release_badge_weld` (REJECT) | the badge WELD: `ago`+`release` with **no separating space** |

**Class 163 — the label pair is the whole safety argument, and the WIDER form is
the trap.** Every single marker was measured and REJECTED: the bare age notice
(2 hostile prose FPs: *"This article is more than 4 months old, so the benchmark
numbers it quotes are stale…"*), bare `About this content` and bare `Last
modified on` (1 each), `Supported by` as a token (1 asserted gate-test literal:
*"Tool calling and reasoning parsers are supported by the server."*). The obvious
conjunction — `age AND (About this content|Last modified on)` — **eats a real
control** that carries both halves inside ONE genuine sentence. Only
`age AND Supported by About this content` is clean: 1 hit (the leak) across all
six corpora, 0 of 16 hostile controls. **STRIP, not reject** — the lede between
the notice and the byline is the knowledge (class-142 doctrine), and the rescued
body must be asserted a pristine SLICE.

**Class 164 — "a listing is a label chain, a sentence has grammar," once more.**
The numbered-chain ALONE is refuted by **4 real `longterm_episodes` rows**
(*"Section 2 introduces the policy optimization, Section 3 covers training and
3.1 lists the reward models."*). `≥6 N.N pairs` alone misses the leak, and
`≥6 pairs AND no finite verb` misses it too — `Download` reads as a verb. The
affordance **AND** the run is what survives: 1 hit (the leak), 0 across the other
five corpora, 0 of 9 prose controls, 0 of 7 adversarial near-misses carrying BOTH
halves inside a sentence. Threshold is stable from 2–5 pairs; 3 is chosen.

**Class 166 — the missing SPACE is the discriminator (the class-9 `-->` argument).**
The loose form `<n> <unit> ago release` (a space allowed) hits **3 real-prose
counter-cases** (*"2yrs ago release was announced in the changelog …"*, *"The model
card was updated 6 months ago release notes say …"*); only the strict weld
`<n><unit>agorelease` is markup a human sentence cannot contain: 1 hit (the leak),
0 across all six corpora. The one remaining strict hit is a meta control that
merely QUOTES the badge — that string IS the chrome, so refusing it is correct;
rephrase the fixture, never loosen the pattern (same as class 28's `subscribe`).

**A gate test that asserts on the WRITER module must `import buffer_store` inside
the test body** — the test file has no module-level `BS` alias, so `BS.is_junk(...)`
dies with `NameError` at the first assertion and never reaches the gate. Cost: one
red suite run, and the `NameError` masks whether the gate itself works.

**A measured-and-REFUTED candidate is a result — record it, do not force it.**
The same session's third leak (class 165, a quantization TABLE label chain:
`FP32 (32-bit) FP16 (16-bit) … Batch Size 32 130.39 GB`) has **no clean marker
yet**. The only clean-looking form, `≥5 PREC (N-bit)` pairs, was measured and
**refuted — 3 real-prose FPs** (*"The config exposes FP32 (32-bit), FP16
(16-bit), BF16 (16-bit), INT8 (8-bit) and INT4 (4-bit) modes…"*); raising the
threshold to 6 loses the leak. So class 165 is recorded as **observed,
unguarded** and the row was dropped with `_drop_offtopic_row.py`. Do not re-derive
it and do not ship the `≥5` form.

**Measurement hygiene that cost cycles here:** a windowed/backtracking regex in a
throwaway probe **hung past 400 s** on 9k junk rows — bound every quantifier and
prefer counting `findall()` hits over nested `[\s\S]{0,n}` scans. And the fifth
(long-form prose) corpus from `training-scripts-hygiene` is what caught `≥6 N.N
pairs`; the four-corpus packaged probe would have passed it.

### `git commit <paths> -m "…"` FAILS — the `-m` is parsed as a pathspec

Live 17.09.26: `git commit -q -- <paths> -m "<multi-line msg>"` exits 1 with
`error: pathspec '-m' did not match any file(s) known to git` (the whole message
is then treated as another pathspec). Nothing is committed, nothing is staged
away — but it is easy to read the failure as "commit refused". Write the message
to a file and use `git commit -F <file> -- <paths>` (order: options first, then
`--`, then paths). Verify with `git log --oneline -3` — a sibling cron's commit
(`chore(darwin) …`, `chore(kanban) …`) can land between your `update-index` and
your commit, so never assume your commit is HEAD without looking.

### Class 43: benchmark METRIC-TABLE rows — a label block with no sentence (live 17.09.26)

`cycle_g_security` logged `security-learn: Attack Success Rate (360 runs — 60
payloads × 2 models × ~3 reps) Paradigm gemma` — 126 chars of **benchmark table
row**: column labels + counts welded together, zero prose. Same number-fed hole
(`_TECH_HINT_RE` starts with `\d+`, so the counts count as technical signal)
plus the ≥90 length trust.

Guard `_is_metric_row_fragment` — the nav-strip family rule once more, *a menu is
a LABEL CHAIN, a sentence has grammar*:

```python
_METRIC_RATIO_RE  = re.compile(r"\([^)]{0,90}?\d+\s+\w+\s*[—–-]\s*\d+\s+\w+")  # (360 runs — 60 payloads
_METRIC_XTILDE_RE = re.compile(r"×\s*~\s*\d")                                  # × ~3 reps
# True when (ratio OR xtilde) AND no finite verb
```

**The verb probe must EXCLUDE `run`/`runs`** — in the leak `runs` is a NOUN, so
listing it makes the rule blind to its own target. That one omission is what
separates the leak from its own counter-cases.

| candidate | hits | proseFP | verdict |
|---|---|---|---|
| bare `×` | 32 corpus | 2 | REJECT — math derivations (`W_quantized × scale`), `3.6× faster` |
| `\d+ \w+` pair | many | — | REJECT — ordinary prose |
| no finite verb alone | 3,448 | 2 | REJECT — far too broad |
| **ratio OR xtilde, AND no verb** | **1 (the leak)** | **0** | **ADD** |

Measured over the live 300-row buffer + 5,580 junk rows with 12 counter-cases —
**several reuse the leak's own words inside a sentence**
(`"Attack success rate (360 runs — 60 payloads × 2 models) was measured on the
local Ollama build and landed at 73% for the hosted model."`). Delta: 1 newly
rejected, **regressions 0**, 12/12 counters learnable, writer gate agrees on both
verdicts. Suites: `tests/scripts` + `scripts/training/test_internet_learner.py`
→ **86 passed**; canonical `pytest` tree → 66 passed.

**Number the class from the REPO HEAD, not from memory:** the skill's last entry
said class 41 while HEAD already carried a class 42 commit, so this landed as 43.
`git log --oneline -5` in `~/openamer-repo` first, then pick the number.

Cleanup pairing as usual: `_drop_offtopic_row.py "Attack Success Rate (360 runs"`.
Then **three** real cycles: two honest `rejected, not trained` (the success
signal), and one that stored an off-topic row from an AI-agent seed
(`"The apartment has about 2,000 square feet indoors…"`) — dropped as
`offtopic-drop`. Topic matching is still NOT the answer; that row is a
deep-read off-topic acceptance, handled by the dropper, not by a new pattern.

### `re` vs `_re` when one block goes into BOTH gates — and temp-probe hygiene

`internet_learner.py` uses bare `re`; `buffer_store.py` uses `import re as _re`.
Paste one guard block into both and the wrong copy dies: `re` in the writer at
**call** time (29 tests red), `_re` in the learner at **import** time (every cycle
dead). Hit live 17.09.26 on class 43's three regexes — the learner copy ended
`_re.IGNORECASE`. **Both `ast.parse` and `py_compile` PASS** (valid Python), so
the only detector is an `importlib` load or a real `--once`: after inserting a
shared block, load BOTH modules and print `m.__file__`, and grep the block for
`_re` before writing the learner copy. Also: delete every `_tmp_*.py` probe in the
same turn (`rm -f _tmp_*.py`, confirm with a per-file existence loop, never a
recursive `find` — it times out over node_modules/venvs), and when a changed-path
list arrives check `ls -l --time-style=full-iso <f> && date` before believing a
path is yours: a stale `_tmp_post.py` (mtime 02:18 vs now 16:49) and paths like
`reports/darwin-*`, `openamer_cli/kanban_db.py`, `docs/wiki/**` belong to other
crons. Full detail + the failure-direction table:
`references/gate-insertion-and-probe-hygiene.md`.

### Read the LAST BUFFER ROW after every verification cycle — that is where the next class is

This session's sequence was 26 → 27, and class 27 surfaced ONLY because the
cycle run to verify class 26 was inspected rather than trusted. The leaking
cycle is often the only one that runs, so **the fix for one class is what
exposes the next**. Budget several real `--once` cycles per gate change, and
each time print the last stored `a` (length + first ~280 chars) and ask "is
this on-topic?". A `learned:` line containing a number is the alarm, not the
confirmation; an honest `rejected, not trained` is the success signal.

**Cleanup that belongs with every gate commit:**
```bash
python3 _drop_offtopic_row.py "<marker unique to the leaking row>"   # backs the buffer up first
tail -1 online_buffer.jsonl                                          # confirm the LAST row is on-topic
```
The marker may hit the row several times (e.g. the changelog leak sat in the
buffer twice — rows 22 and 299); `dropped=2 kept=298` is the expected shape.

**And verify the commit actually landed:** a sibling cron's commit can interleave,
so `git log --oneline -5` after finishing — do not assume your commit is HEAD
just because `git commit` printed a SHA. An earlier class-26 commit in this
session (`fae8c77bc`) was already two commits deep by the time class 27 was
committed. Anchor on the explicit pre-work SHA, never on `HEAD~N`.

### Classes 23–24: archive listings + GitHub issue pages, found by READING THE BUFFER TAIL

Both live 17.09.26, found the cheap way — run `--once`, then eyeball the last
rows' `u`/`a` pairs. Neither appeared in `buffer_junk.jsonl` (never rejected).
Both cleared both gates via the familiar **number-fed hole** (`_TECH_HINT_RE`
starts with `\d+`, so a date counts as technical signal) plus the ≥90 trust.

| # | Live string (truncated) | Guard | Discriminator |
|---|---|---|---|
| 23 | `LM Serving white-paper July 24, 2026 Thinking Machines Lab Inkling, Explained: … insights July 17, 2026 Top 7 … insights July 6, 2026 What Is a Good AI Harness?` | `_is_archive_listing` | **≥2** `<label> <Month D, YYYY>` **AND no period anywhere** |
| 24 | `Description AnasBenAmor10 opened on Jul 23, 2024 Issue body actions Confirm this is an issue with the Python library … Describe the bug Error: …` | `_is_github_issue_chrome` | **TWO** independent template markers, ANDed |

**Class 23 — the discriminator is "no sentence terminator", not the label count.**
`>=2 labels` alone reported `proseFP 2-3`: prose that *names* two labels
(`The archive page lists posts under headings like Insights July 17, 2026 and
News May 29, 2026, …`) is a topic-word hit, and `>=3 labels` still caught one.
Also rejected: every literal form (`insights july 17, 2026`, `insights july 17,
2026 top`, `white-paper july`, `lm serving white-paper`) — each is a topic
phrase. What survived is **`>=2 labels AND "." not in text`**: a listing
concatenates entry titles and never ends a sentence, while prose about the same
labels always carries a full stop. Measured 1 hit (the leak) / 0 bufFP / 0
proseFP over buffer + world_model + kta_log + internet_learn_log (3,191 rows).
**Watch the terminator set:** `[.!?]` FAILS — the live row ends
`What Is a Good AI Harness?`, so the `?` excluded it and the rule silently
matched 0 rows. Measured discriminator is the **period** specifically.

**Class 24 — one marker is always a topic word.** Each candidate alone hit a
hand-written counter-case:
`issue body actions` → *"The issue body actions menu on GitHub … should skip"*;
`opened on Jul 23, 2024` → *"A maintainer opened on Jul 23, 2024 an issue about
the embedding client"*; `confirm this is an issue with the` → *"Confirm this is
an issue with the Python library and not an unrelated bug"*; `describe the bug`
→ *"Describe the bug in two sentences …"*. ANDing two of them keeps prose ABOUT
issues learnable (0/7 FPs, 0/2,897 corpus hits).

### The repo-commit trap that cost THREE extra commits: blob EOL ≠ working-tree EOL

`core.autocrlf=true` here means the **working tree is CRLF** (what the live
runners execute) but the **blob must be LF**. A plain
`cp Running → repo && git add` stores CRLF into the index:

```
git diff --cached --numstat                    → 1061/1026  (looks like a rewrite)
git diff --cached --numstat --ignore-cr-at-eol →   35/0     (the real change)
```

Every prior gate commit (`95d4aa156`, `1f5a17cbc`, …) has a **pure-LF blob**
(`git show <ref>:<file>` → `CRLF=0`). So after copying the file you must rewrite
the index entry as LF, keeping mode 100644:

**CHECK PER FILE — the convention is NOT uniform** (live 17.09.26): the two
training scripts are LF in HEAD, but `tests/scripts/test_internet_learner_gate.py`
has a **CRLF** HEAD blob (`git show HEAD:<path> | grep -c $'\r'` → 2090). A plain
`git add` on that file normalised it to LF and the numstat jumped to
`2191/2090` for an **101-line** change. Rule: for every staged path, compare
`git diff --cached --numstat` with and without `--ignore-cr-at-eol`; when they
differ, stage the RAW working-tree bytes (`hash-object -w --stdin` on the
unmodified `read('rb')`, no `.replace`) instead of the LF variant. Both numbers
must then be equal and equal to the real change size.

```python
blob = open(tree_path,"rb").read()
assert b"\r\r" not in blob
lf = blob.replace(b"\r\n", b"\n")
h = git(["hash-object","-w","--stdin"], input=lf).stdout.strip()
git(["update-index","--cacheinfo","100644,"+h+","+path])
```

Then the acceptance test is: `git diff --numstat <parent> HEAD` and the same with
`--ignore-cr-at-eol` return **identical numbers**. Also check
`git ls-tree` for a mode flip — `cp` set files to `100755` while HEAD had
`100644`. And **derive the LF blob from the WORKING TREE, never from the HEAD
blob**: doing it from HEAD while HEAD still held the `\r\r\n` corruption left a
lone `\r` on each inserted line (4 files-lines + 2), which the raw numstat then
reported as a 1061-line change.

**`git diff HEAD~N` is not a safe reference on this box** — a sibling cron's
commit (`chore(kanban) …`) landed inside my commit sequence and shifted every
`~N` I had counted on. Anchor on the explicit pre-work SHA captured at the start,
not on a relative offset.

### Insert-script pitfall, hit AGAIN: `.replace("\n","\r\n")` on a CRLF call anchor makes `\r\r\n`

The block body needs the `\n→\r\n` conversion, but the call-site anchors I built
already ended in `\r\n`, so converting them too produced `\r\r\n` on exactly the
inserted lines (caught only because the gate showed `^M^M` in a `cat -A` diff).
Convert the **block** only; pass `call_new` with explicit `\r\n` and never run it
through the replace. Always assert `b"\r\r" not in raw` after writing (the
`ast.parse` passes regardless — valid Python, wrong bytes).

### Class 25: the 2B plan-scaffold BULLET echo — and the extract gate was blind to it

Third leak of the same session, found the same cheap way. **The log line itself
was the tell** — the value STARTS with a quote and a bullet, which no real insight
does:

```
doc-learn: "\n   - Input text: A very long, fragmented, and repetitive list of
vLLM documentation topics/headings. It's essentially a dump of section titles
from a vLLM documentation website.\n   - Goal: Extract the "ONE most valuable
technical insight" from this
```

Same family as the documented plan-scaffold echo (root cause AE), but a **new
paraphrase**: "most **valuable** technical insight" where AE recorded "most
**relevant/valuable**". The model re-paraphrases its own prompt every time — budget
for one new variant per session.

**Why the extract gate could not fire, even on AE's exact string.** Root cause AE's
markers (`most relevant/valuable technical insight`, `**survey the papers:**`) live
in `buffer_store._NAV_CHROME` **only**; `internet_learner._JUNK_RE` never received
them (`'most relevant/valuable technical insight' in _JUNK_RE` → False while
`_NAV_CHROME` has it). So only the WRITER gate could ever catch that class. **When
adding an echo-class marker, grep BOTH files:** an existing twin in one gate does
not cover the other, and the extract gate is the one that saves the cycle (it
retries instead of burning a full deep read).

**Guard = the plan's BULLET+LABEL form, never the bare phrases.** Measured on the
live 298-row buffer with a 6-sentence counter-case set:

| candidate | hits | not-yj | bufFP | proseFP | verdict |
|---|---|---|---|---|---|
| `input text:` | 1 | 1 | 0 | **1** — `The input text: field of a dataset card points at the original corpus …` | REJECT |
| `one most valuable technical insight` | 1 | 1 | 0 | **1** — `Extract the one most valuable technical insight from each retrieved document …` | REJECT |
| `most valuable technical insight` | 1 | 1 | 0 | **1** | REJECT |
| **`- input text:`** | 1 | 1 | 0 | **0** | **ADD** |
| **`- goal:`** | 1 | 1 | 0 | **0** | **ADD** |

The leading **bullet-dash** is the whole discriminator: a plan renders
`<dash> <Label>:`, prose writes the same words inside a sentence. Implemented as
`_is_plan_scaffold_echo` (`^\s*["'“”]*[-*•]\s*(?:input text|goal|content|task|text
source|output format)\s*:` with `MULTILINE|IGNORECASE`, `len > 1200` bail-out),
wired into BOTH gates. 0 hits over `world_model` (436) + `kta_log` (765).

Counter-cases to assert: the `input text:` dataset-card sentence, the
`one most valuable technical insight` instruction, the `The goal: reduce peak
KV-cache memory …` sentence, **and a meta sentence that legitimately discusses the
leak format** (`The extractor should emit one technical insight and never its own
plan; a bullet like - Goal: extract the insight is a leak.`) — that last one proves
you gated the *shape*, not the topic.

**This session went 23 → 24 → 25, each class surfaced only by the real `--once`
cycles run to VERIFY the previous fix.** That cascade is the norm (the leaking
cycle is often the only one that runs). Budget several cycles per gate change,
read the LAST buffer row after each, and stop only on an honest
`rejected, not trained`.

### Classes 20–22: three leaks in ONE verification run — and the rule that found them

Verifying a gate change with **real `--once` cycles**, not just the suite, surfaced
three junk classes back to back (each fix revealed the next — the leaking cycle is
often the only one that runs). All three cleared BOTH gates the same way: the
**number-fed hole** (`_TECH_HINT_RE`'s alternation *starts* with `\d+`, so a
version string, a date or a price counts as "technical signal") plus the ≥90-char
"long prose" trust.

| # | Live string | Guard | Shape |
|---|---|---|---|
| 20 | `OKF Agent Memory resolves this dilemma with the Dual-Memory Agent Architecture (DMAA) : flowchart TD subgraph PUSH["1.` | `_is_diagram_markup` | **DSL keyword AND markup punctuation** |
| 21 | `B view details ) Uploaded Jun 28, 2024 Python 2 Python 3 File details Details for the file openpyxl-3.` | `_is_package_index_chrome` | **TWO** independent label markers |
| 22 | `Certified Agentic AI Security Expert (CAASE) Coming Soon Attack, poison, & harden AI agents: reasoning loops, memory stores, tool-calling, & multi-agent identity.` | `_is_course_cta_chrome` | promo **CTA AND** course bundle |

Class 20 is an extractor lead-in sentence **welded to diagram source** — the
knowledge is a picture description, not prose. The guard needs a DSL keyword
(`flowchart TD`, `sequenceDiagram`, `subgraph X`, `digraph X`, `graph LR`,
`styling node`) *within 400 chars of* real markup punctuation (a labelled node
`ID["` or an edge arrow `-->` / `---` / `==>` / `-.->`). A single `->` is
deliberately **not** listed: it is ordinary ASCII prose. Prose that merely *names*
a diagram type therefore stays learnable.

Class 22 is the instructive one: it is **on-topic** for its cycle, so *relevance
cannot be the discriminator — page VOICE is*. Expect sales copy to arrive
topically correct; do not reach for topic matching.

**Every guard is its OWN compiled predicate, never a fragment of `_JUNK_RE`.**
That is not style: the big alternation is ONE implicitly-joined literal, and a
missing/extra pipe welds two rules together or creates an empty branch that
matches everything (both hit on 16.09.26). A new predicate cannot break an
existing rule by construction. Mirror it in `buffer_store._is_nav_chrome` by
calling the same-shaped local function.

**Delta for all three** (identity-rebind attribution — a sibling cron edits these
files, so `git show HEAD:` is not a clean reference):

```python
NEW = load(working_copy, "il_new")
REF = load(working_copy, "il_ref")          # same file, second module instance
REF._is_diagram_markup = lambda text: False # disable ONLY my rule
```

Result over the live corpora (296-row buffer + 1674 cycle results + 760 kta rows):
**regressions 0** for every guard, every newly-rejected row IS the leaking row,
and 12+ hand-written counter-cases that *talk about* diagrams / releases / courses
all stay learnable. Suites: `tests/scripts/` → **180 passed**.

**Use the packaged probe instead of hand-writing measurement code.**
`training-scripts-hygiene` ships `scripts/probe_marker_candidates.py`; this run
re-derived an equivalent probe **four more times** before noticing. It prints
`hits / not-yet-junk / bufFP / proseFP` per candidate against the live buffer plus
its own hand-written prose corpus, and its decision rule (`ADD` only when
`hits == not-yet-junk` and both FPs are 0) is exactly the one above. Run it with
`--training-dir <live dir>`; it is read-only.

**Gate work is ITERATIVE — each fix reveals the next class, and the leaking cycle
is often the only one that runs.** The three classes above were not found by
reading the buffer once; each was surfaced by a real `--once` run, and the fix for
one exposed the next. So after any gate change, budget **several** real cycles
(not one), read the LAST buffer row after each, and only stop when a cycle reports
an honest `rejected, not trained` — a rejection is the success signal for gate
work, a `learned:` line containing a number is the alarm. Confirmed live: this run
ended on two consecutive honest rejections, which is the correct stopping state.

**And a gate test whose fixture the gate itself refuses tests NOTHING.** After
adding a guard, check that every EXISTING test fixture still *passes through* the
gate: a fixture refused by `is_junk` never reaches the function under test, so the
assertion dies with `FileNotFoundError` and the test has been vacuous all along.
Live: `test_buffer_store.py::test_truncation_limits` had been dead this way. Fix
the FIXTURE (give it varied prose that survives), never widen the gate — and prove
it pre-existing via `git show <sha>~1:<path>` in a temp dir first. The full recipe
is in `training-scripts-hygiene` → "Ein Test Fixture muss das Gate ÜBERLEBEN".

### A tenth class: arXiv ABSTRACT-PAGE label chains (live 16.09.26)

`cycle_b_papers` logged `paper-learn: Xiv-issued DOI via DataCite Submission
history From: Shuming Ma [ view email ] [v1] Tue, 27 Feb 2024 18:56:19 UTC
(201 KB) Full-text links: Access Paper: View a PDF of the paper titled The Era
of 1-bit LLMs: All Large Language Models are in 1.` — 243 chars of pure page
**labels welded together**, zero prose. Both gates passed it: the submission
timestamp fed the technical-signal gate and the length cleared the >=90
"long prose" trust.

Fix: `_is_arxiv_abstract_chrome()` — a row must carry **TWO independent** arXiv
page labels to be judged chrome. Keyed on the LABEL CHAIN
(`view email`, `submission history`, `full-text links`, `view a pdf of the
paper titled`, `cite as arxiv`, `xiv-issued doi`), never on the topic or a bare
token like `arxiv`:
- a genuine insight ABOUT a paper ("BitNet stores its weights in ternary form,
  so a 7B model fits in about 2 GB at int4.") stays learnable;
- **one label alone is NOT chrome** — real prose can legitimately mention a
  submission history or a revision.

Wired into `internet_learner._is_junk` AND mirrored in
`buffer_store._is_nav_chrome` (writer gate must agree, else any other writer
path still lands it — `buffer_store` cannot import the learner, circular).

**Delta proof** (old module = `git show HEAD:…`, new = working copy) over the
live 275-row buffer: `newly_rejected=1` (the leaking row, fully gated),
**regressions=0**, writer gate agrees. Suites: **45 passed**. The row was then
removed with `_drop_offtopic_row.py "Xiv-issued DOI via DataCite Submission history"`
(`rows=275 dropped=1 kept=274`), and the next `--once` learned a genuine doc
row: `cycle_d_docs: doc-learn: Optimization and Tuning - vLLM`.

**Pitfall in the delta script itself:** loading the OLD `buffer_store` from a
temp dir via `importlib` and then importing the NEW one normally resolved the
NEW name back to the *temp* copy (module-name collision in `sys.modules`),
which faked a "writer-gate leak". Before concluding a leak, assert
`buffer_store.__file__` points at the real training dir.

### A ninth class: leading NAV/HEADER chrome — strip it three ways (live 16.09.26)

Same run as the ticker class, three more shapes, all of the **byline-prefix
family**: page furniture WELDED to a real headline. Every one of them cleared
both gates because the furniture contributed digits or length. All three are
**strips**, not rejects — the headline behind the chrome is the knowledge.

| Shape | Live string | Boundary rule |
|---|---|---|
| read-time + category nav | `11 min read China Semiconductors AI Infrastructure Geopolitics China AI Chip Boom: CAICT 417% Demand …` | the nav **repeats a word the headline re-uses** (`China … China`) → the 2nd occurrence is where the article starts |
| read-time + nav (Nvidia) | `12 min read Nvidia AI Infrastructure GPUs FinOps Wall Street Nvidia $500B AI Compute Fund …` | same rule (`Nvidia … Nvidia`) |
| nav + HTML-comment arrow | `Studies Blogs Contact Arsha --> Posted on May 2, 2025 by admin --> Prompt Engineering Is Dead in 2025 …` | `-->` is **leaked HTML comment markup**; it must sit in the leading <120 chars |

Wired into `_clean_insight` after `_strip_byline_prefix`:
`_strip_read_time_header` then `_strip_arrow_nav_prefix`.

**Both rules are structural, and that is the whole safety argument.** The
read-time rule demands a **duplicate word** in the leading TitleCase run; with no
duplicate it returns the text **untouched**. So real prose that merely mentions a
read time survives by construction — no "strip N words" guess, no word list:

```
"The 11 min read time on that post is misleading; the quantization section is
 only 200 words."                                     -> UNTOUCHED
"Benchmarks show 40% latency reduction at int4; the write-up is a 6 min read."
                                                     -> UNTOUCHED
```

**A measured-and-rejected attempt is worth keeping in the record.** The first
version of the arrow rule was a generic `<TitleCase run> <--|-->>` signature. It
looked fine on the leaking row and the delta showed 5 buffer rows touched — but
it **deleted product names in ordinary prose**:

```
"OpenCode | The open source AI coding agent — What is OpenCode? …"
  -> "The open source AI coding agent — What is OpenCode? …"      WRONG
```

Only the `-->`-as-markup rule survived. **A generic "leading TitleCase run"
signature is never safe**: title-cased product names and headlines start the same
way. Key on markup that prose cannot contain.

**Two traps that cost a test cycle each (both my fixture, not the code):**

- `_is_nav_list` fires on a **>=6 TitleCase token run with no comma or
  semicolon**. A hand-shortened fixture therefore gets rejected by THAT rule and
  looks like your new strip failed. The real live rows carry a comma in the
  trailing clause that keeps them prose. **Always assert on the verbatim logged
  string**, never on a paraphrase — a paraphrase silently tests a different gate.
- When a counter-example fails, identify **which** rule rejected it before
  touching the new pattern. Three separate fixtures here were killed by the
  pre-existing short-candidate/`_is_nav_list` rules, not by the new code; the
  honest fix was to use the real text and say so in a comment.

### Rewriting already-stored rows: key on a strict SUFFIX, never on `output != stored`

A strip-gate needs a **rewrite** pass over the buffer (the existing
`scrub_rejected_buffer.py` only DROPS). The first rewrite script compared
`_clean_insight(a) != a` and reported **54 changed rows** — almost all of them
fake: `_clean_insight` also applies the 250-char `max_len`, so every long row
looked "changed" from truncation alone. It was reverted from the backup and
rewritten with the correct predicate:

```python
if cleaned and len(cleaned) < len(a) and a.endswith(cleaned):   # prefix was dropped
    rewrite
```
→ `de-chromed=2 truncation-only-skipped=52`. **Assert the body is a pristine
suffix of the original** — that is the only proof a strip did not truncate or
mangle a real insight.

### Classes 12–16: the leading-chrome STRIP family, and how to prove a strip

Live 16.09.26 added four more shapes of the byline family (page furniture WELDED
to real prose → STRIP, never reject) plus one REJECT class. The generalizable
parts are the guard designs; verbatim strings, measured counter-cases and the
rejected candidate rules live in `references/leading-chrome-strip-family.md`.

| Class | Leading chrome | Guard that keeps real prose alive |
|---|---|---|
| 12 | `Publications [ edit ] OWASP Top Ten …` (MediaWiki section control) | name must be SENTENCE CASE and apostrophe-free; body must OPEN a sentence |
| 13 | `at 11:44 am we asked four ai coding agents to In a recent experiment, …` | literal lowercase `at` required (capitalized `At 12:30 pm the batch job …` untouched); boundary = first Capitalized token |
| 14 | `SECURITY resources Whitepapers/Guides OWASP GenAI LLM Top 10 2026 August 3, 2026 About …` | head must be LABEL-LIKE: slash-joined Capitalized pair AND **no function word, ≤ 1 lowercase word** |
| 15 | `Simon Lermen Feb 24, 2026 54 5 8 Share TL;DR: …` | bare counters (no nouns) followed DIRECTLY by `Share`; anchored at the start |
| 16 | `Auch die neue Kundin … erhält eine Prämie von 300 €, was eine Gesamtprämie von 600 € ergibt!` | REJECT, keyed on the offer's own phrases — never a bare `Prämie`/`Rabatt`, so German prose citing a discount stays learnable |

Three lessons that generalize:

- **A STRIP class must NOT also be a blanket REJECT in the writer gate.** A
  `"[ edit ]"` entry in `buffer_store._NAV_CHROME` looks harmless and is not: it
  refuses a real sentence that merely mentions an edit button — `"Wikipedia's
  [ edit ] button is a MediaWiki control, not content; the RAG pipeline should
  strip it before chunking documents for retrieval."` Mirror the *anchored rule*
  instead so reader and writer gate agree by construction. The counter-case that
  catches this is a sentence ABOUT the chrome, not a paraphrase of it.
- **A nav run is separable from a sentence by SHAPE, not by a word list.**
  Class 14's generic `<nav-run> <date> <body>` rule was measured and REJECTED: it
  ate four GitHub-advisory rows (`Critical Authenticated Arbitrary Data Export
  Theft via Mass Assignment in sendFileMessage GHSA-fhc2-x8cp-c5ch …`) plus two
  counter-cases. What survived is "no function word (the/of/and/is/…) and at most
  one lowercase word" — a menu is a LABEL CHAIN, a sentence has grammar. Reach
  for that discriminator before adding more words.
- **`_DATE_ALT` is LOWERCASE and needs `re.IGNORECASE`.** A new pattern built from
  it without the flag compiles, imports, and *silently never matches*; the delta
  catches it and nothing else does.

### Classes 17–18: two REJECT gates keyed on a page's own LABEL CHAIN

Two more shapes cleared BOTH gates in one run — one per source — plus the
generalizable rules they produced. Verbatim strings, the marker measurements
and the counter-cases: `references/quality-gate-fixture-and-delta-hygiene.md`.

| Guard | Shape | How it stays safe |
|---|---|---|
| `_is_qa_portal_chrome` | Chinese Q&A/answer-portal scrape (Baidu Zhidao: verified badge, vote widget, fan badge, ask-me button, answer counter) | **TWO** independent portal markers required |
| `_is_de_pricing_chrome` | German SaaS pricing/checkout table (monthly-cancel wording, direct debit, invoice, annual package, per-seat-per-month, €/year) | **TWO** independent billing markers required |

Both fed the technical-signal gate the SAME way: `_TECH_HINT_RE`'s alternation
*starts* with `\d+`, so a bare price (`49`, `4`) or a clock (`11:44`) counts as
"technical signal", and the length then cleared the ≥90 long-prose trust. **That
is the single most productive hole in the gate.** When a cycle reports
`learned: <text containing a number>`, suspect a number-fed pass first — not a
novel failure mode.

`_is_de_pricing_chrome` is the **commerce-copy** family: it belongs with class 16
(`Prämie`/`Rabatt` offer copy) and with the English twin `billed annually`
already in `buffer_store._NAV_CHROME`. **Check for an existing twin before
inventing a second rule for a class you have already seen.**

**Never gate on the language.** A "reject CJK" rule was measured and REJECTED:
the corpus holds genuine Chinese technical prose (an LLM-agent survey summary)
that must stay learnable. Both gates key on the page's own label chain instead,
so a row that merely *mentions* a price or an author statement passes.

**Counter-cases under ~90 chars test a DIFFERENT gate than the one you wrote.**
Three fixtures in one session failed not because the new rule misfired but
because the PRE-EXISTING short-candidate rule (`len < 90 and not
_has_alpha_signal`) rejected them first: a 41-char Chinese sentence, a 69-char
one, and a counter-case whose only technical keyword was German —
`_has_alpha_signal` wants an ENGLISH keyword, so a CJK sentence is
signal-less by definition. Keep every counter-case ≥90 chars or give it a real
English technical noun, and say why in the comment. **When a counter-case fails,
identify WHICH rule rejected it before touching the new pattern** — that trap has
now cost three separate sessions (see also the class-8/9 notes above).

Same run, third leak — the mid-sentence snippet echo (`at 11:44 am we asked four
ai coding agents to In a recent experiment, …`). That is **class 13 above**; the
guard is `_strip_clock_fragment`, and its three-condition form is worth pinning
because it is stricter than "boundary = first Capitalized token": it fires only
when the text **starts lowercase**, carries a clock-with-meridiem marker, **and**
the real sentence follows with a capital. Measured over ~4870 rows: 1 row
touched, body a clean suffix, 4/4 counter-cases unmodified — including
`11:44 am The job starts …` and `At 11:44 am the retriever …`, which is exactly
what the lowercase-start condition buys.

### Fixture, CRLF and pre-existing-failure hygiene

- **A red test in a file you did NOT touch: prove it is PRE-EXISTING before

### Isolating YOUR rule's delta when HEAD is contaminated by a parallel writer

Live 16.09.26: several crons edit `scripts/training/` concurrently, so
`git show HEAD:<file>` is **not** a clean "old" reference — another cron committed
a *different* junk class into the same file mid-work, and a HEAD-based reference
would have attributed its hunks to my rule. Load the SAME working file twice and
set YOUR transform to identity in the copy:

```python
NEW = load(working_copy, "il_new")
REF = load(working_copy, "il_ref")           # same file, second module instance
assert REF._clean_insight(leak) != ""        # sanity: the strip is active here
REF._strip_wiki_section_prefix = lambda text: (text or "").strip()
# _clean_insight resolves the name via its module globals at CALL time, so the
# rebind is what takes effect — no source surgery, no regex deletion.
```

`newly_rejected == 0`, `regressions == 0`, `touched == 1` with the body pristine
is then a clean attribution. **Use the VERBATIM logged row for the sanity assert** —
a hand-shortened fixture under 90 chars dies on the unrelated short-candidate rule
and fakes a *failed isolation*; that trap has now cost two sessions.

Operational note from the same session: with crons committing in parallel,
`git status` / `git diff --cached --numstat` can contain FOREIGN hunks, and your
work may already be in HEAD (another cron can commit the tree it shares with you).
Before committing, check `git show HEAD:<file> | grep -c <my_marker>` and
`git log -S <my_marker> -- <file>`, then stage ONLY your own paths.

**Strips apply at WRITE time only.** Rows already in the buffer keep their chrome,
so after adding a strip class run a rewrite pass with the strict suffix predicate
(see "Rewriting already-stored rows" above) and confirm every `dropped` row is
genuinely junk before accepting the result.

- **A red test in a file you did NOT touch: prove it is PRE-EXISTING before
  "fixing" it** (live 16.09.26). `test_buffer_store.py::test_truncation_limits`
  failed while I was working on the gates — different file, different fixture.
  Do not assume you broke it and do not start patching someone else's test.
  Load the module as it was BEFORE your change and run the same probe:
  ```python
  # git show <ref>:scripts/training/buffer_store.py  ->  temp dir, then import it
  # (importlib.util.spec_from_file_location with a UNIQUE module name per copy)
  ```
  Identical behaviour PRE and POST ⇒ pre-existing, your change is innocent. Only
  then decide whether to fix it, and say in the report that it was pre-existing.
  Root cause found this way: the test's own fixture
  (`" ".join("Antwort%d mit echtem Inhalt" % i …)`) is a **degenerate motif** that
  the junk gate correctly refuses, so `append` never wrote and the truncation
  branch was unreachable. `is_junk` runs on the fixture BEFORE the 3000/4000-char
  cut — a truncation test needs text that survives the gate first.
- **Inserting a fixture block into a CRLF Python file: verify TWO things**
  (live 16.09.26, both mistakes made in one session):
  1. **`bare LF count == 0`** —
     `d.count(b"\n") - d.count(b"\r\n")`. A helper that joins chunks with a bare
     `"\n"` writes lone LFs into a CRLF file; invisible in review, corrupts the
     diff. Normalise with `.replace("\r\n", "\n").replace("\n", "\r\n")` before
     writing, then assert.
  2. **`ast.parse(...)` succeeds — and still does not prove the fixture is what
     you think.** Adjacent string literals inside parentheses **concatenate**:
     `_CLOCK_PROSE = ("first sentence." "second sentence.")` silently becomes ONE
     string, and the test then exercises a different input. `ast.parse` passes
     (valid Python); the failure surfaces only as a baffling assertion on a
     one-character value. Write fixture LISTS with explicit commas/parens per
     item, and assert `len(fixture)`/`fixture[0] != fixture[1]` for the list.
- **A measured-but-UNFIXED finding is worth recording, with its severity.**
  `buffer_store.is_glued_motif` counts the most common 4-gram over the whole text,
  **including 4-grams that span a word boundary**. Real English repeats `" the"`
  densely, so genuine prose longer than ~1000 chars trips it (`" the"` ×16, rate
  0.064 ≥ the 0.045 threshold) — which is exactly why the truncation fixture could
  never reach its branch. Its own docstring says "glued **into** most tokens", so
  the honest correction is to count only 4-grams containing no whitespace
  (measured: the SALAD true-positive stays caught at 0.208, long prose stops
  firing). Impact today: **0 live rows** — the longest stored row is 362 chars —
  so it is latent, not live. Left unfixed because the 15 junk-log rows the
  correction would release each need a per-row check first. **Report latent
  findings with the measurement and the blast radius, and fix the test fixture
  to reach a different branch rather than widening the gate.**
- **A sibling cron edits the same file and commits to the same repo** (live
  16.09.26). Two concrete consequences:
  - `git commit` fails with `fatal: Unable to create '.git/index.lock': File
    exists`. The lock is transient — retry in a bounded loop with a short sleep.
    Do NOT delete it by hand; another process may be mid-write.
  - Your delta can show a hit from THEIR uncommitted rule. Before attributing a
    delta row to your change, run `git diff HEAD -- <file>` and look for hunks you
    did not write. Never `git checkout --`/`git stash` another agent's work to
    "clean up": if they staged it, commit it together (their hunks ride along) and
    say so in your report.
- **A comment block inserted by a re-run duplicates itself.** Making the insert
  script re-runnable is right, but its idempotence check must cover the COMMENT
  block, not just the assignment: a partial re-run left the 5-line header comment
  twice above `_CLOCK_ECHO`. Check `marker in src` BEFORE assembling any part of
  the block, and re-read the region afterwards.

### Class 19: HN/Metafilter comment-listing PAGINATION chain (live 16.09.26)

`cycle_c_github` stored a listing label chain, zero prose:

```
LegionWithin on March 10, 2025 | prev | next [–] best acronym of 2025 (so far)
emiliog07 on March 9, 2025 | prev [–] What a name.
```

Both gates passed: the dates fed `_TECH_HINT_RE` (its alternation *starts* with
`\d+`) and the length cleared the ≥90 long-prose trust. It is the same
number-fed hole as classes 17–18, this time from a *listing* rather than a page.

Guard: **PIPE+NAV ADJACENCY**, never the bare words.

```python
r"\|\s*prev\s*\|\s*next\b|\|\s*next\s*\|\s*prev\b|\|\s*prev\s*\[\u2013\]|\|\s*next\s*\[\u2013\]|"
```

Why adjacency is the whole safety argument — three measured counter-cases, all
staying learnable (learner **and** writer gate both False):

| Counter-case | Why it passes |
|---|---|
| `"The pagination handler renders a prev and next control, so the RAG crawler must skip those links …"` | prose writes the words with **no pipe** |
| `"In the retry loop the batch job compares the previous checkpoint with the next one …"` | `previous`, not `prev`; no pipe |
| ``"A markdown table row looks like `| key | value |`, …"`` | pipes exist but carry **no nav token** |

A **bare `[–]` fragment was measured and REJECTED as too broad** — an en-dash in
brackets is ordinary typography and would have eaten real prose. Only the
pipe-adjacent forms survived.

Wired into `_JUNK_RE` (inserted **before** the trailing
`r"^\W*[kKmM]\s+followers\b"` fragment, which must keep the `|`-free last
position) AND mirrored as literal strings in `buffer_store._NAV_CHROME` so the
writer gate agrees by construction. Delta over the live 287-row buffer:
`newly_rejected=0` (the leaking row had already been dropped with
`_drop_offtopic_row.py`), **regressions=0**, and the verbatim leak scores
`_is_junk=True` while all three counter-cases score False. Suites: **55 passed**.

**Insert-script hygiene (this class cost one broken attempt):** the `patch` tool
converted `\\|` inside a `new_string` into a real `\|` and produced
`SyntaxError: unexpected character after line continuation character`. For regex
fragments containing pipes/escapes, **write the insert script with `write_file`
and build the fragment as an explicit list of source LINES** (one list element
per line, no `\n` inside), then join with `\r\n` — never a single concatenated
string literal. Keep the idempotence marker check on `prev\s*\|\s*next` before
assembling anything, and assert `bare_LF == 0` after writing.

### Pitfall: the `re.error` that was NOT yours — a sibling cron's PARTIAL write

`--once` came back with

```
re.error: missing ), unterminated subpattern at position 2731
```

at `_JUNK_RE = re.compile(`. That looks exactly like the class-19 weld / empty-
alternative trap and invites regex surgery. It was neither: `ls -l
--time-style=full-iso internet_learner.py` showed the file written **40 seconds
earlier**, and the next import — same file, fresh interpreter — loaded clean
(`OK junkre len 2767`). A parallel cron had `write_file`'d the module mid-read;
the `--once` had simply lost the race.

**Before touching a regex because of a compile error, prove the error
reproduces in a fresh interpreter:**

```bash
ls -l --time-style=full-iso internet_learner.py && date    # mtime seconds ago?
$OPENAMER_HOME/venv/Scripts/python.exe -c "import importlib.util as u; \
 s=u.spec_from_file_location('il','C:/…/internet_learner.py'); m=u.module_from_spec(s); \
 s.loader.exec_module(m); print('OK', len(m._JUNK_RE.pattern))"
```

If the fresh load is clean, **re-run `--once`** instead of editing. Editing a
file a sibling process is mid-write on is how you corrupt it for real. Same
shell, same moment: `git -C /c/Users/damir/openamer-repo log` failed with
`cannot change to … No such file or directory` while `cd /c/Users/damir/openamer-repo`
worked fine — an MSYS `-C` path quirk, not a missing repo. `cd` first.

### The verification probe is a TEMP script (and `npm run test` is now a REAL command)

Asked for "build + tests", three traps worth pre-empting:

- **`npm run test` is a real, GREEN command as of 23.09.26** (see the revised
  interpreter note above). The two historical failure shapes — `Missing script:
  "test"` and `BLOCKED (hardline)` — did not reproduce; do not pre-emptively
  report either one. Run it, then run the pytest pair, and state plainly which
  number came from which command.
- **`npm run check` is repo-WIDE — a red run is usually NOT yours.** It is
  `npm run --ws check` across `apps/*, ui-tui, ui-tui/packages/*, web, tests-js`,
  each running `typecheck && test && lint`. Live symptoms, all pre-existing:
  `tsc: command not found` (a workspace whose `node_modules` is EMPTY, 0
  entries), `Cannot find package '@typescript-eslint/eslint-plugin'`,
  `Cannot find type definition file for 'three'`, `Cannot find module 'react'` /
  `@nanostores/react` + `TS7026 JSX.IntrinsicElements`. **Prove innocence with
  four read-only probes before attributing anything to your change:**
  ```bash
  git status --short -- tests-js/            # empty -> no working-tree edits
  git diff HEAD --stat -- tests-js/          # empty -> not even modified
  git check-ignore -v tests-js/node_modules  # .gitignore:56:node_modules
  ls tests-js/node_modules | wc -l           # 0 -> never installed
  ```
  `node_modules` being gitignored is exactly what makes a 0-entry install
  invisible to `git status` — that is why the probes are needed, not an
  assumption. Then `git show --stat --oneline <your-sha>` to confirm your change
  is confined to your own paths.
- **Advance the run without over-claiming, and watch the TRACKED lockfile.** After
  `cd tests-js && npm install --no-audit --no-fund` the workspace's own
  `npm run test` goes green (`Test Files 3 passed (3) / Tests 9 passed (9)`) and
  `typecheck` passes; `check` then stops further along on other workspaces'
  uninstalled deps. Report the progress and the remaining pre-existing blocker as
  two separate sentences. Also: that install made `git status` show
  ` M package-lock.json` — a **one-line `apps/desktop` version bump**
  (`2026.09.14` → `2026.09.17`) that the install did NOT produce. Inspect with
  `git diff --numstat` + `git diff | head -25`, then **leave it alone**: never
  stage it, never revert it (same rule as a sibling cron's hunks). Full
  transcript, per-workspace error table and the pytest pair that is the real
  evidence: `references/monorepo-npm-verification.md`.
- **A `.py` probe you create for the delta WILL be reported as a changed path.**
  Use one `_tmp_`-prefix convention and delete them in the same turn — full rules
  (and why `find` is forbidden for the check) are in the `_re`/temp-probe section
  above and `references/gate-insertion-and-probe-hygiene.md`.
- **A very long `python -c` is refused by the command parser** ("malformed
  executable payload", unconditional blocklist — retrying with `--yolo` does not
  help). Short one-liners are fine; for anything multi-line use `write_file` →
  run the file. Keep probes small and single-purpose so they stay under the limit.
- **A buffer that grows between snapshots is normal.** Rows went 287 → 290 → 291
  across this session (sibling cycles writing concurrently). Re-read the LAST
  line and sanity-check it is on-topic before declaring the buffer clean — and
  report a concurrent row you inspected rather than silently counting it.

### Prove the gate on the LIVE module, and run the WHOLE suite folder you touched

Two closing habits that caught real gaps here:

- **Assert on the live HOME module, not only the repo copy.** The cron executes
  `$OPENAMER_HOME`, so the final check must load *that* file and print
  `IL: <path>` from `m.__file__` before trusting a verdict. A green suite run
  against the repo copy says nothing if HOME was not synced. Cheap combined
  probe (short, single-line-per-statement so the parser accepts it):

```python
print('gate self-broken (||):', '||' in m._JUNK_RE.pattern)   # must be False
print('leak  L/W:', m._is_junk(leak), w._is_nav_chrome(leak)) # both True
print('prose L/W:', m._is_junk(real), w._is_nav_chrome(real)) # both False
```

- **If you edited `buffer_store.py`, run `tests/scripts/` in full.** Learner gate
  and writer gate are separate sinks (see "the DOWNSTREAM WRITER needs its own
  relevance check"). Touching the writer makes `-k "buffer or store or nav"`
  (12 passed) *insufficient* evidence — the full folder was **171 passed** here.
  Run the folder and state which command produced which number.



















































































































































## Moved to references/ (same content, loaded on demand)

- `references/moved-to-references-same-content-loaded-on-deman.md` — Moved to references/ (same content, loaded on demand)
