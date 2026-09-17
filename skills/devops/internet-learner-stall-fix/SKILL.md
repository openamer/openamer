---
name: internet-learner-stall-fix
description: Use when internet_learner cycles all report rejected.
---

# Internet Learner stall fix
## Older root causes (15./16.09.26) — moved to references/

The per-class narratives for causes J–Z and AA–AG (15.–16.09.26) live in
`references/root-causes-archive.md` — they are historical, the rules are
already in the code and covered by `tests/scripts/test_internet_learner_gate.py`.
Read that file when you must understand WHY an old marker has its exact
shape; the operational sections below are what you need on a live stall.
Two entries there are still operative and are NOT merely history:

- **Root cause T** — the Darwin autopilot rewrites `internet_learner.py`
  WHILE you edit it. Re-read the file before every patch, and verify your
  change survived after the next autopilot pass.
- **Root cause AG** — `deep_learn` ranks the WRONG page; deliberately
  unpatched. Do not 'fix' it on a rejection alone.

## Trigger
`python internet_learner.py --once` (or the cron) reports
`cycle_x: rejected, not trained (shallow + deep read both gated)` on EVERY cycle,
and `online_buffer.jsonl` stays pinned at its cap (300 rows).

## Diagnose (fast)
0. Run the packaged rates table — this ONE table tells you whether it is a
   systemic regression (rate down across ALL cycles) or normal rotation noise
   (one weak source, or `duplicate` at the 300-row cap):

       python skills/software-development/training-scripts-hygiene/scripts/diagnose_learn_rates.py \
              --training-dir <live training dir>

   (lives in the sibling `training-scripts-hygiene` skill, alongside the other
   learner probes; formerly hand-written as scratch `_probe_rates.py` — bundled
   17.09.26 after the same table was re-derived yet again; see root cause U.)
   **Read the per-DAY table, not just the 7d one.** `--days 7` smooths a step
   change: on 17.09.26 the 7d row showed a healthy 70-77% while per-day showed
   the 13.09 gate-tightening (100% → ~48-68%, stable since) — a regime change
   and a fresh decline look identical in the aggregate. And the final per-day
   row is a PARTIAL day (cut at the current hour): never read it as a decline
   without saying so. `--json` for machine use.
1. `tail -5 internet_learn_log.jsonl` — confirm all cycles rejected.
2. `tail -100 buffer_junk.jsonl` — count reasons. `duplicate` = root cause A,
   `junk` on SERP-shaped text = shallow-path noise (fine), nav text = cause C.
3. `wc -l online_buffer.jsonl` + `cat .il_rotation` — cap reached?
4. Probe one query: run `deep_learn(q)` and print the result; if it returns page
   nav ("Generation RunPod SkyPilot ...") → root cause C.

## Root cause AH — ticker chrome + README changelog bullets, BOTH in one cron run (live 17.09.26)

Cron run started with the documented `cycle_e_competitors: rejected` line. The
rate check said **65% (last 20) / 57% (last 80) vs 82.6–82.9% all-time** — the
U/V signature — so U/V were verified present (`_fair_share_window` → 5 slices /
4000 chars ABCDE, `_search_urls(k=6)` → 6/6/6/6/6/6, `k2 != k6` 2/3) and the
file size was **stable** across the whole probe (no Darwin writer). No gate
change was warranted for the rejection itself: it was rotation noise.

**Both leaks below were found the cheapest way — run `--once`, then read the
tail of `online_buffer.jsonl` and eyeball the `u`/`a` pairs.** Neither showed up
in `buffer_junk.jsonl` (they were never rejected).

| cycle | u | a |
|---|---|---|
| `cycle_f_multi_domain` | Multi-domain learning (Walmart investors reject AI workplace report …) | `Walmart investors reject AI workplace report as automation expands in the US - The Economic Times Benchmarks CLOSED Nifty 23,118.` |
| `cycle_h_efficiency` | Efficiency learning (VPTQ: Extreme low-bit Quantization for real LLMs): How do agents run leaner? | `Inference: low decode overhead, best throughput, and TTFT News [2024-10-14] 🚀 Add Rocm support [2024-10-6] 🚀 Try it on Google Colab [2024-10-5] 🚀 Add free Huggingface Demo : Huggingface Demo [2024-10-4] ✏️ Updated the VPTQ tech report and fixed typos.` |

Both are 129 / 251 chars **with digits** → the `>=90` length trust AND the
technical-signal gate both fired; no existing marker matched.

**Markers added (data-only, BOTH files — the Q/R/S pitfall).** Commits
`1f5a17cbc` (ticker) and `95d4aa156` (changelog):

| marker | where | measured |
|---|---|---|
| `closed nifty` | both | 1 hit, and it IS the leak → 0 FP |
| `the economic times benchmarks` | both | 1 hit, IS the leak → 0 FP |
| `add free huggingface demo` | both | 2 hits (same row duplicated), BOTH the leak → 0 FP |

**Candidates measured and REJECTED — the topic-word trap again:**
| candidate | why rejected |
|---|---|
| `nifty` (bare) | 1 hand FP + 1 live FP: `Benchmarks from the Nifty index showed a 2% gain…`, `…encompassing Nifty 100 intraday and daily price data…` |
| `benchmarks closed` (bare) | 1 hand FP: `The agent benchmarks closed-source and open-weight models on the same harness.` |
| `add rocm support` | 1 hand FP: `Add ROCm support for AMD GPUs to the inference backend.` |
| `try it on google colab` | 1 hand FP: `You can try it on Google Colab without installing anything locally.` |
| `low decode overhead` | 1 hand FP: `The agent benchmarked low decode overhead and best throughput on TTFT.` |
| `best throughput, and ttft` | 1 hand FP (declarative on the same topic) |

A **structural alternative** measured clean and is a candidate for a future
class-wide detector: **`>=3` bracketed dates `\[\d{4}-\d{1,2}-\d{1,2}\]` → 2
hits, 0 FP both corpora** (`>=2` was rejected: 2 live FPs on the `[2024-10-18]
🌐 Open source community contributes…` row). Same for `>=2` rocket-emoji
bullets (2 hits, 0 FP). Not needed for these single leaks — prefer the tight
literal while only one row shape is live.

**Cleanup + verify (the standard shape):** both leaks removed **by signature**
(`is_junk` would drop the 12-row baseline), census 297/13 → 296/12, then
297/14 → 295/12, 0 unparsable, 53 structural-connection rows preserved.
`pytest tests/scripts/test_internet_learner_gate.py -q` → **42 passed**
(new `test_market_ticker_chrome_…` and `test_readme_changelog_bullet_list_…`,
each asserting BOTH gates plus prose counter-cases); `tests/scripts` →
**182 passed**. Two commits pushed.

### Trap that cost a cycle here: `patch` DELETED my own previous marker
Patching `_NAV_CHROME` with `old_string = '    "the economic times benchmarks",'`
**replaced that line** with the new block — the nifty marker vanished, leaving
only the changelog one. The probe caught it (`nifty marker line: []`). When
appending to a tuple with `patch`, anchor on the **line BEFORE** the insertion
point (or just use the byte-level AST-anchored script). Fix was a 3-line
re-insert, then `ast.parse`. Always re-grep every marker you believe is in the
file after any `patch`/`write_file` on these modules.
Related: after an insert, **all hardcoded line numbers shift** — the second
`_NAV_CHROME` edit asserted `lines[371] == b")"` and blew up with the previous
comment text. Re-derive the anchor with `ast` each time; never reuse a line
number from an earlier probe.

## Verify a writer-gate change like this (what "0 collateral" looks like)
1. `is_junk(bad) == True` on the exact leaked strings, `False` on 3 real prose
   samples + the engine's own baseline row.
2. Re-scan the whole buffer: flagged set must grow by **exactly** the leaked
   rows (live: 24 → 26, i.e. 2 new hits), then drop back to **24** after deleting
   them (`flagged: 26 -> 24`, the historical baseline).
3. `openamer-repo/.venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py -q`
   → `12 passed` (added `test_writer_gate_agrees_on_the_new_chrome_and_binary_shapes`,
   which asserts BOTH gates on both shapes). Suite grew with each shape:
   **`23 passed` as of 16.09.26** (root cause Y added
   `test_german_dictionary_serp_chrome_is_gated_on_both_paths`, which asserts the
   leak is gated on BOTH paths AND that two real `…;` vLLM/quantization rows stay
   clean — the one-directional version would pass the wrong fix).
4. Sync the two modules into `openamer-repo/scripts/training/` (they must be
   byte-identical to the laptop copies — `diff` first), commit, push.
5. Run 3–4 × `--once`. Post-fix live: 1 learned / 2 rejected, where both
   rejections were `junk` (SERP-shaped deep-read fallback) and `duplicate`
   (buffer at cap) — **read `tail -6 buffer_junk.jsonl` before calling it a
   regression.**

## Root cause AI — company/Wikipedia infobox FINANCIAL label chain (live 17.09.26)

Second cron run of the day. Started on the documented `cycle_d_docs: rejected`
line. Rate: last 10 50 % / last 20 50 % / last 80 50 % vs **all-time 82 %**
(n=1711) = the U/V signature, so U/V were verified **before** inventing anything:
`_search_urls(k=6)` → `6,6,6,6,6,6`; `_fair_share_window` → 5 slices / 4000
chars; file size **stable** over 30 s (no Darwin writer). No gate change was
warranted for the rejection — rotation noise. `buffer_junk` last 40:
`21 junk / 18 duplicate / 1 no-tech-signal`, all documented shapes.

The find came from the buffer tail, twice:

**1. Two root-cause-AG rows (NOT gate leaks — deleted, no code change):**
| cycle | u | a |
|---|---|---|
| `cycle_g_security` | Security learning (Detecting prompt injection attacks …) | `Kraków – Wikipedia, wolna encyklopedia — Kraków jest położony … ; Oficjalny serwis BIP …` |
| `cycle_h_efficiency` | Efficiency learning (Pushing the Limits of LLM Quantization via the Linearity Theorem) | `November 5, 2025 Share 2 Min Read Photo by Abid Shah on Unsplash Amazon has issued a cease-and-desist letter to Perplexity …` |

Both measured `writer=False extract=False` — **topically unrelated whole
articles**, i.e. the documented root cause AG (deep_learn ranks the wrong page).
Do NOT invent a gate for these: the `Kraków` row is a Polish SERP pair and the
Amazon row is a news lede, so any "news-ness"/"encyclopedia" marker would be a
topic word. Removed by signature (`wolna encyklopedia`, `on unsplash`) →
300 → 298 rows.

**2. A REAL leak the very next `--once` produced — the infobox (this root cause).**
```
u = Competitor intelligence: JetBrains IDEs Go AI: Coding Agent, Smarter Assistance, Free Tier
a = CEO [ 1 ] Revenue 15,065,029,000 Czech koruna (2024) Operating income
    2,041,654,000 Czech koruna (2024) Net income 2,479,110,000 Czech koruna
    (2024) Total assets 17,426,568,000 Czech koruna (2024) Number of
    employees 2,800 [ 2 ] Website jetbrains .
```
248 chars **with digits** → the `>=90` long-prose trust AND the technical-signal
gate both fired; `_is_nav_list` wants ≥6 TitleCase tokens with no comma, so a
mixed label chain never matched. Commit `aaf11271e`.

### Marker selection was the whole cost — every literal is a topic-word trap
| candidate | buffer hits | HAND-prose FP | verdict |
|---|---|---|---|
| `operating income` | 1 | **3** | REJECTED |
| `czech koruna` | 1 | **3** | REJECTED |
| `revenue [\d,]{6,}` | 1 | **1** | REJECTED |
| `ceo \s*\[\s*1\s*\]` | 1 | 1 | REJECTED |
| `\(\s*20\d\d\s*\)\s*operating income` | 1 | 1 | REJECTED |
| `number of employees…website` | 1 | 0 | ok but narrower need |
| **structural: ≥2 (label, year-paren)** | **1 (the leak)** | **0/13** | **SHIPPED** |

`grouped-numbers >= 3` also scored clean on the buffer (1 hit / 0 FP) but is
**useless as a corpus scan**: on RAW JSON lines it reads 437/437 and 3056/3056
(the JSON has lots of long numbers). Scan the **text fields** — then it is 7/3056
on `longterm_episodes`, all in unrelated X-batch report texts.

### The fix — structural, in BOTH gates
`buffer_store.is_financial_infobox(text)` = `len(_FINANCIAL_LABEL_RE.findall) >= 2`
where `_FINANCIAL_LABEL_RE = (revenue|operating income|net income|total assets|
number of employees)[^()\n]{0,30}\(\s*(?:19|20)\d\d\s*\)`, cap `len <= 1200`.
An infobox row *repeats* `Label <huge grouped number> … (yyyy)`; real prose does
not. Wired into `buffer_store._is_nav_chrome` (writer gate → covers
`active_learn` / `online_learning`) AND called from `internet_learner._is_junk`
via the lazy `from buffer_store import …` sibling idiom (logic, not a page
phrase → **no `_JUNK_RE` mirror**, exactly like `is_contact_block`).

Measured: leak `writer=True extract=True`; **0 FP on 13 hostile counter-cases**
including `Llama 2 (2023) and Llama 3 (2024) improved long-context reasoning`,
`GPT-4 (2023) scored 91.2% while GPT-5 (2024) reached 95.1%`,
`Total assets ( 2023 ) were 17,426,568,000 koruna at the end of the year.`,
`Number of employees grew to 2,800 ( 2024 ) across the Czech and German offices.`
(only a deliberately infobox-shaped synthetic — `Revenue 2024 ( 2024 )` ×3 —
flags, which is correct); 0 hits over 3,056 `longterm_episodes` texts.

Cleanup by signature (`czech koruna`): **299/13 → 298/12** (baseline), 53
structural-connection rows preserved, 0 unparsable, CRLF intact.
`pytest tests/scripts/test_internet_learner_gate.py -q` → **46 passed** (new
`test_financial_infobox_label_chain_is_gated_on_both_paths` asserts BOTH gates on
the leak + 11 prose counter-cases); `pytest tests/scripts -q` → **186 passed**.

### Mechanical traps that cost the most time here
- **The `_is_nav_chrome` wire anchor must be the two-line form.** `"    if
  _is_package_index_chrome(text):\n        return True"` — a **one-line**
  anchor silently matched 0 times and the apply script aborted on the assert.
  Build the anchor as `crlf("…\n        return True")`, not as a bare line.
- **Appending a test needs a separator.** `raw.rstrip(b"\r\n") + TEST` glues the
  new `def` onto the previous line's tail → `SyntaxError: invalid syntax` at
  `assert not IL._is_junk(meta), metadef test_…`. Use
  `body + b"\r\n\r\n\r\n" + TEST.replace("\n","\r\n").encode() + b"\r\n"`.
- **`git status` in this repo is NOISY with foreign cron paths** (`tools/mcp_tool*`
  deletions, `reports/darwin-*`, `.bugbot/bugbot.log`, `scripts/auto-code-review.py`).
  Always `git add` the three explicit paths and check `git diff --cached
  --name-only` before committing — never `git add -A`.
- Live re-verify after the fix: 3 × `--once` → 2 learned / 1 rejected. The
  rejected one and the two learned rows all measured `writer=False extract=False`;
  the remaining off-topic row (`Physics … antiprotons`) is root cause AG again,
  which stays deliberately unpatched.

## Not every rejection is a regression — check the reason first
On 15.09.26 09:35–09:41 five `--once` cycles gave 1 learned / 5 rejected, after a
6/6 learned run at 09:02–09:27. Do NOT assume the latest gate change broke it:
read `tail -12 buffer_junk.jsonl` for the *reason* on those cycles. `duplicate`
= the buffer is at its 300 cap and the same (query, answer) pair came round
again — normal rotation noise, not a gate bug. Only a `junk` reason on a NEW
text shape indicates a leak worth a new root cause entry.

## Root cause AI — rate drift with rejects rotating = NO fix needed; the leak is elsewhere (live 17.09.26)

Cron run began on the documented `cycle_e_competitors: rejected` line. The skill's
order of operations was followed exactly and **no code change was warranted for
the rejection itself**:

1. **Rate first** (`internet_learn_log.jsonl`, reject-prefix rule): last 10 30 %,
   last 20 45 %, last 80 51 %, **all-time 82.6 % (n=1688)**. That is the U/V
   signature, so U/V were verified before inventing anything:
   `_search_urls(k=6)` → `6,6,6,6,6,6`; `_fair_share_window` → 5 slices / 4000
   chars ABCDE; and for `deep_learn` k2/k6 on 8 diverse queries → **5 of 8 True**.
   The 3 `False` cases were **not** a V regression: all 6 URLs fetched at 6000
   chars in each, so the fair-share windows were identical *by content* — a
   query-dependent artifact, not the dead-code bug. Do not re-patch on
   `k2 == k6` alone; fetch the pages and compare first.
2. `buffer_junk.jsonl` last 40: `16 junk / 23 duplicate / 1 no-tech-signal`. The
   junk rows were the documented shapes (2B `Self-critique:` echo, SERP
   `… — <German date> · …`) and the rest is `duplicate` at a 295/300 cap =
   **rotation noise**. No new chrome shape → correct verdict: gates untouched.
3. `.il_rotation` 1693, file mtime 17 min old, size stable → no concurrent Darwin
   writer.

What WOULD have looked like a reason to patch, and was not: a flat 30 % last-10.
Two consecutive honest rejections are the correct stopping state for gate work.

**The real find was in the buffer, not the rate**: run `--once` a few times and
read the tail of `online_buffer.jsonl` (`u` vs `a`). That produced class 23
(blog archive listing) and, after its verification cycles, class 24 (GitHub issue
page) — both of which had passed BOTH gates and were **never** in
`buffer_junk.jsonl`. Rate analysis and leak-hunting are different jobs; a healthy
rate does not mean a clean buffer.

## Bare phrase vs. anchored instruction opener (live 16.09.26)
The "structural connection" cycles buffer their OWN task instructions. The naive
fix — adding `shared underlying pattern` to `_JUNK_RE` — is WRONG: it also
swallows the genuine declarative answers (`The shared underlying pattern is a
closed-loop feedback system …`) that must stay learnable. The instruction voice
is the only reliable discriminator, so use a separate **start-anchored,
imperative** rule instead of a `_JUNK_RE` phrase:
```python
_INSTRUCTION_OPENER_RE = re.compile(r"^\s*\**\s*(?:need\b|task\s*:|goal\s*:|"
    r"find\s+(?:the\s+)?(?:structural\s+)?connection|identify\s+(?:the\s+)?(?:shared\s+)?pattern|…)", re.IGNORECASE)
```
Verify BOTH directions: 4 instruction strings must CATCH, and 2 declarative
answers (`The shared underlying pattern is …`, `Both systems use a feedback
loop …`) must stay clean. A one-directional test passes the broken version.

## Buffer record shape
`online_buffer.jsonl` rows are `{"u": <question/query>, "a": <answer text>}` —
NOT `{"text": ...}`. To inspect fresh learnings:
```python
import json
recs=[json.loads(l) for l in open('scripts/training/online_buffer.jsonl',encoding='utf-8') if l.strip()]
print(recs[-1]['u'], '|', recs[-1]['a'][:200])
```
A `tail -1 | json → r.get('text')` prints empty and looks like a silent failure
while the write actually succeeded — always read `u`/`a`.

## Apply
File: `scripts/training/internet_learner.py` (`buffer_store.py` read-only).
Wire each cycle: `q = _novel_query("<domain keywords>", queries)`.
After editing, sync the copy into `C:\Users\damir\openamer-repo/scripts/training/`
and commit + push (repo is the source of truth).

## Verify
```
python internet_learner.py --once   # run 4x; expect >=1 "learned:"/"-learn:"
```
Success rate went 0/~20 → ~2/4. Confirm `online_buffer.jsonl` tail shows fresh,
substantive prose (real sentences with numbers/verbs), not nav lists.

**`npm run test` is NOT a verifier in this repo — do not reach for it.** There
is a root `package.json` (workspaces: web, ui-tui, apps/desktop) but its
`scripts` block has no `test` entry at all; the training scripts are pure
Python. If a post-edit check tells you to run `npm run test`, the correct
substitute is:
```
openamer-repo/.venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py -q   # 33 passed
openamer-repo/.venv/Scripts/python.exe -m pytest tests/scripts -q                                 # 173 passed
```
Only `test_internet_learner_gate.py` references `buffer_store`/`internet_learner`
(`grep -rln` to confirm there is no `test_buffer_store.py` — there is not), so
the gate file is the focused check and `tests/scripts` is the no-collateral one.

Two Windows traps when running them from the agent's bash:
- **Do not prefix with `timeout`** — git-bash resolves it to Windows
  `timeout.exe`, which fails with `Ungültige Syntax. Die Standardoption darf
  nicht mehr als 1 Mal verwendet werden.` Pass `timeout=` to the terminal tool
  instead, or just run pytest directly (the suite is ~20 s).
- Quote absolute training paths (`cd "C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"`).
  A bare `cd C:/Users/damir/openamer-laptop/...` (the `AppData/Local` segment
  dropped by a typo) **silently creates** that directory tree via the
  write_file path resolution, leaving a stray `openamer-laptop/` beside
  `openamer-repo/`. Found and removed once; verify with
  `ls -d C:/Users/damir/openamer-laptop` → must not exist.

## Both gates now share the structural detectors (live 15.09.26)
`internet_learner._is_junk` calls `buffer_store.is_glued_motif` (the detector was
renamed from `_is_glued_motif` to its public name for exactly this reason, commit
`85c305a18`), using the same `sys.path.insert(0, dirname(__file__))` sibling-
import idiom as `store()`. Why it matters: a candidate the WRITER gate would drop
must be rejected at EXTRACTION time, or the cycle burns 30–160 s producing a value
that never lands. The `_JUNK_RE` markers stay duplicated on purpose — they are
concrete page phrases, not logic. Do NOT hand `internet_learner._is_junk` the
whole `buffer_store.is_junk`: its SERP gate would then fire on every
`Title — snippet` the shallow path builds, forcing every cycle onto the slow deep
read.

## Verify a specific cycle WITHOUT waiting for the rotation
`--once` advances `.il_rotation`, so a targeted repro means running one cycle
function directly:
```python
import importlib.util, sys
T = "C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
spec = importlib.util.spec_from_file_location("il", T + "/internet_learner.py")
m = importlib.util.module_from_spec(spec); sys.path.insert(0, T); spec.loader.exec_module(m)
print(m.cycle_h_efficiency())     # or cycle_b_papers, ... real write, real gate
```
With `OPENAMER_HOME` poisoned this still works (see `_training_dir()` above).

## Removing a row that landed before its gate existed
Back up `online_buffer.jsonl`, filter the bad lines out on the `a` field, write
back with `newline=""` and `"\r\n".join(...) + "\r\n"` (the file is CRLF), then
re-check `sum(is_junk(r["a"]))` — it must drop by exactly the number you removed.
Live 15.09.26 this was 27 → 26 (baseline) for the salad and 27 → 26 for the
GitHub org row.

## Pitfalls
- **Truncated SERP titles + GitHub result-list titles pass `_is_serp_snippet`
  (found live 15.09.26).** `_SERP_TAIL` only fires when the em-dash+ellipsis sits
  at the very END of the text, so these two shapes were stored as learnings:
  (1) `<Title> … — <next title/snippet>` (ellipsis mid-string), e.g.
  `Jailbreaking Large Language Models: Techniques, … — This article explores …`;
  (2) `GitHub - <owner>/<repo>: <description>` incl. its SERP form
  `GitHub - amd/gaia: … — GAIA is AMD's open-source framework …`.
  Measured on the live 300-row buffer: **14 rows matched, all search-result
  chrome, 0 real-prose rows affected** (`is_junk` had flagged 0 of 300 before).
  Fix (commit `64cd94335`): two new constants `_SERP_ELL_DASH` (`…\s*[—–]\s`) and
  `_SERP_REPO_TITLE` (`GitHub\s*-\s*[\w.\-]+/[\w.\-]+\s*:`) wired as extra
  `return True` branches in `_is_serp_snippet` — a *tightening*, never a loosening.
  Verify: `8 passed` in `tests/scripts/test_internet_learner_gate.py` **and**
  re-run `is_junk` over the whole buffer (expect exactly the 14, 0 elsewhere).
  Do NOT try the generic `^<title> — <rest>` rule: it flags 115/300 rows.
  Run the gate tests with `openamer-repo/.venv/Scripts/python.exe -m pytest`
  (the live venv has no pytest).
- **Glued JSON records in `online_buffer.jsonl` (live 15.09.2026).** A writer
  appended a record WITHOUT a separator, producing `...}"}{"u": ...` on one
  line. `json.loads` then raises `Extra data`, and every loader that skips bad
  lines silently drops BOTH records — a real learning is lost with no log entry.
  Detect/fix: `python scripts/training/repair_buffer.py` (report) then `--fix`
  (backs up + rewrites). Records the buffer at 300 lines; a glued line means
  `unparsable=1` and `records` is one short.
- **`patch`/`write_file` tools mangle indentation in this file** (they re-wrapped
  a nested `for` body into an `IndentationError` twice on 15.09.26). Edit with a
  Python heredoc instead: read with `newline=''`, match anchors with
  `'\r\n'.join(...)` / `.replace('\n','\r\n')`, write back `newline=''`, then
  `ast.parse` to verify. The file is single `\r\n` (no `\r\r\n` any more).
- **`patch` silently flips CRLF→LF across the WHOLE file** (repo `tests/` and
  `scripts/` files are CRLF). Editing `tests/scripts/test_internet_learner_gate.py`
  on 15.09.26 turned a 10-line insertion into a 183/172 full-file churn commit
  (and the pushed commit can't be cleanly force-rewritten on shared `main`).
  ALWAYS edit CRLF repo files with a Python script that reads the blob
  (`git show HEAD:path`), splits on `b'\r\n'`, inserts, rejoins with `b'\r\n'`,
  writes `'wb'` — then confirm `git diff --stat <base>` shows only your added
  lines and the EOL census is unchanged. Fix-forward with a new commit (restore
  the original blob + minimal insert), never force-push `main`.
- **Doubled CR line endings**: (historic) `internet_learner.py` had `\r\r\n`; the
  `patch` tool's fuzzy matcher SILENTLY no-ops on it. Normalise to single `\r\n`
  with a small Python script BEFORE editing.
- Cron blocks `powershell -Command/-File`; use script files, not one-liners.
- **Shallow path stored GitHub repo-page chrome (found live 15.09.26).** A
  `cycle_c_github` row read `ANUS Public Notifications You must be signed in to
  change notification settings Fork 925 Star 6.` — the shallow path accepted it
  while `deep_learn`'s nav gate would have dropped it. Measured rate: 1 in ~60
  buffer rows, not systemic, but it poisons training.
  Fix (applied, commit `0fc4cbfca`): add `"signed in to change notification"`
  to `_NAV_CHROME` in `buffer_store.py` — DATA-ONLY tightening of the marker
  tuple, no logic change. Verify with `is_junk()` on the bad string (True) AND
  on 3 real prose samples (False) plus `test_internet_learner_gate.py` (8 pass).
  If more GitHub chrome appears (repo sidebar, "Watch"/"Fork" counts), extend
  the tuple the same way; never touch `_is_junk` logic.
- **Multi-line CRLF insert trap**: when inserting via a Python heredoc, the
  COMMENT lines are the ones that silently get `\n` while your code line gets
  `\r\n` → 3 lone LFs in an otherwise-CRLF file. Always end every inserted line
  (comments included) with `\r\n` and re-check `lone_lf == 0` against the
  pre-edit census before committing. `git diff --cached --stat` must show only
  `+N`.
- `buffer_store.is_junk` also rejects SERP snippets (`title … — snippet`) — that
  is correct; the deep fallback in `store_or_deep` is what recovers the cycle.
- Never loosen `_is_junk`/gates to force a pass — fix the extraction instead.

## Root cause AI — blog-sidebar post-listing widget (live 17.09.26)

Symptom: the documented `cycle_x: rejected` line, rotating across cycles. Rate
check said **60% for the day** — inside the normal 50–80% band, so NOT a
regression. U/V verified intact (`_fair_share_window` → 5 slices / 4000 chars
ABCDE; `_search_urls(k=6)` → 6/6) and the buffer byte-size stable across the
probe (no foreign writer). The rejects were genuine: 19/40 `junk` + 20/40
`duplicate`. Two independent findings from that run:

1. **The gate was right; the deep read was off-topic.** The >2/8 test
   (8 realistic queries) returned 5/8 off-topic pages — Lufthansa/SAP landing
   pages, dictionary corpora, a Berlin security firm, 2018 Wikipedia history,
   pagination chrome. `_search_urls` takes URLs in **DOM order** and
   `_usable_urls` only drops stubs: there is NO relevance check on the URL
   itself. That is a real class-level weakness, but it is NOT a stall — the
   gate correctly rejected every one of them. **Do not loosen a gate to raise
   the rate.** The fix point is deep-read URL selection.
2. **A learning that DID pass was a leak.** `cycle_a_technews` stored
   `September 2, 2026 5 Views How to Spot AI Generated Images in 2026 (The Old
   Tricks Stopped Working) September 3, 2026 3 Views Our Picks Apple Added TV
   and 200 Games to Its Cheapest iCloud Plan.` — a two-entry "recent posts"
   sidebar (date + view-counter + headline, twice). 189 chars and it carries
   digits, so the `>=90` length trust AND the technical-signal gate both fired
   and no existing marker matched.

Marker: `_is_sidebar_listing_chrome` → literal `"views our picks"`, in BOTH
gates (extraction `internet_learner._is_junk` + writer
`buffer_store._is_nav_chrome`, the AH both-files rule). Measured before touching
anything: **1 buffer hit and it IS the leak → 0 real-prose FPs** on an
8-sentence control corpus. Candidates rejected — the counter/topic trap:

| candidate | why rejected |
|---|---|
| bare `\d+ views` | 2 hand FPs: `The survey gathered 500 views…`, `In my view, prefix caching matters…` |
| `>=2 'N Views'` | ctrlFP 0 but wider than needed while one shape is live |
| `>=2 Month D, YYYY` | 4 live buffer hits — would drop real rows |

Verified: **51/51** `tests/scripts/test_internet_learner_gate.py`, census
**0 of 300 rows** flagged by the writer gate afterwards (no over-gating), and a
post-fix cycle learned real content (vLLM `Optimization and Tuning`).

### PITFALL that cost time - NEVER hand-rewrite `online_buffer.jsonl`
Removing the leak row with a plain `open(..., "w")` write **corrupted the
file**: all 299 records survived but each gained a blank line after it
(a CRLF-split yields 301 parts / 150 parsable / 151 blank). The file is CRLF,
so `.readlines()` still reports 300 while a CRLF-split reader sees 150 -
**the two readers disagree, which is the tell.** Recovery: restore the newest
intact `online_buffer.jsonl.bak.*` (check record count AND byte size, not just
mtime) and merge newer rows back by JSON signature
(`json.dumps(rec, sort_keys=True)`), then write with `newline=""` and one
record plus a CRLF per record. Prefer the buffer's own helpers
(`clean_buffer.py` / `buffer_store`) over hand-editing, and after any cleanup
re-read with a CRLF split - never `readlines()` - then assert `unparsable == 0`
and that the structural-connection rows are still there (53 in this buffer).

## Root cause AK - GitHub repo-LISTING row: counters + `Updated <date>` + label (live 17.09.26)

**Symptom**: `cycle_c_github` reports `rejected` and — the real tell — the
BUFFER contains a search-result listing row that trained as an insight:

    Python 0 MIT 3,612 0 0 Updated Jun 13, 2025 ComfyUI Public Forked from
    Comfy-Org/ComfyUI The most powerful and modular stable diffusion GUI,
    api and backend with a graph/nodes interface.

Language + counters + license + relative `Updated <date>` + the repo's own
one-line description. 186 chars cleared the `>=90` long-prose trust and the
counters/license digits fed the technical-signal gate -> BOTH gates passed it.
A second shape sat in `buffer_junk.jsonl` (`no-tech-signal`):
`Updated Oct 29, 2024 QuIP Public Code for paper: "QuIP: 2-Bit Quantization ..."`.

**This is a BUFFER leak, not a rate problem.** The rate was healthy (all-time
81 %, last-20 65 %); the rejects in the same window were honest (`duplicate` at
the 297/300 cap + documented junk shapes). Rate analysis and leak-hunting are
different jobs — a healthy rate does NOT mean a clean buffer. Scan the buffer
tail (`u`/`a`) on every run, not just the log.

**Fix**: `_is_gh_listing_row` in BOTH files (learner `_is_junk` + store
`_is_nav_chrome`), anchored PAIR:

    _GH_LISTING_ROW_RE = re.compile(
        r"\bUpdated\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b[\s\S]{0,40}?"
        r"\bPublic\s+(?:Forked|Code|Archive|Mirror)\b")

Never key on the parts: `Updated <Mon DD, YYYY>` alone is ordinary dates and
`Public` alone is ordinary English ("Public health agencies ..."). A bare
`Forked from` was measured and REJECTED — it matches a REAL episode
("openclaw (386k GitHub stars) ... forked from ...").

**Measured** (the 0-collateral proof): 2 buffer hits, both ARE the leak; 0 of
3,056 `longterm_episodes`; 0 of 323 test-asserted clean control literals; 5
hand-built counter-cases (prose mentioning a public code repo, an updated date,
a MIT licence) all stay learnable.

**Sync pitfall found the same run**: the repo (SoT) had the class-31 test
update staged while the LAPTOP copy still carried the OLD assertion, so
`pytest tests/scripts/test_internet_learner_gate.py` was RED for a reason that
had nothing to do with the live code (the two `.py` files were
functional-AST-identical — comments only). On a red suite, FIRST diff the
laptop test file against the repo's; do not go hunting for a code regression.
Sync via `cp repo/tests/... laptop/tests/...`, then re-run.

## Root cause AJ - byline + timestamp + `| N` counter chrome (live 17.09.26)

Found the cheapest way, same cron run as AI: run `--once`, then read the tail
of the buffer and eyeball the `u`/`a` pair. `cycle_e_competitors` stored

    Kyle Orland and Benj Edwards - Dec 19, 2025 12:29 pm | 192 Which mines are
    mine, and which are AI?

an Ars Technica **article-header chrome run**: two-author byline, dateline,
comment-counter, glued to a headline whose prose tail ends in a `?`. It carries
digits and a question mark, so the length trust, the technical-signal gate and
every existing marker let it through.

Marker `_is_byline_counter_chrome` = `time + "| N"`
(`\d{1,2}:\d{2}\s*(?:am|pm)\s*\|\s*\d{1,4}\b`), wired into **both** gates
(extraction `internet_learner._is_junk` + writer
`buffer_store._is_nav_chrome`) in all 3 code copies.
Measured: 1 buffer hit and it IS the leak -> 0 real-prose FPs.
**The broad `\|\s*\d{1,4}` was REJECTED** - 1 hand FP
(`We compared | 192 | and | 256 | batch sizes in the benchmark.`) plus 3 live
buffer hits. Only the time-anchored form is safe. Verified 51/51 gate tests,
leak row dropped CRLF-safely (300 -> 299 records, 0 unparsable).

### PITFALL - your control corpus must not contain KNOWN leaks
The byline probe's control list still carried the class-29 sidebar string, so
`_is_junk` correctly flagged it and the harness reported `prose_FPs=1` for all
6 copies - a **harness bug, not a code bug**. Before calling a marker broken,
print *which* rule matched (`re.search(marker, c)`) instead of assuming the new
one did. Keep control corpora to genuinely clean prose, and put every known-leak
string in its OWN assertion (`_is_junk(known_leak) is True`), never in the
false-positive set.

### PITFALL - do not chain a ternary for keep-vs-drop
A one-line `(dropped if ... else keep).append(s)` list-selection silently
dropped 0 rows and tripped the `assert len(dropped) == 1` guard (which is
exactly why the guard belongs there). Write the plain `if/else` - KISS beats
clever when the cost of a wrong branch is silent data loss.
