---
name: internet-learner-stall-fix
description: Use when internet_learner cycles all report rejected.
---

# Internet Learner stall fix
## Older root causes (15./16.09.26) — moved to references/

Per-class narratives for J–Z, AA–AG (15./16.09.26) live in
`references/root-causes-archive.md`; the rules are in the code, covered by
`tests/scripts/test_internet_learner_gate.py`. Two entries are NOT mere history:

- **Root cause T** — the Darwin autopilot rewrites `internet_learner.py`
  WHILE you edit it. Re-read the file before every patch, and verify your
  change survived after the next autopilot pass.
- **Root cause AG** — `deep_learn` ranks the WRONG page; deliberately
  unpatched. Do not 'fix' it on a rejection alone.

**This SKILL.md is at its 100 KB cap.** New root causes go into
`references/root-causes-archive.md` -- append **LF** (that file is LF-native;
a CRLF append flips ~60 lines) -- and only a ONE-LINE pointer is added here.
AW/AY (77-85), 96/97 (AZ), 98, 122 -> MEASURED-AND-REJECTED,
102/103, 109/110, 113-115, 118, 123/124 (GitHub releases-row + slide-nav
chrome; leaked into KTA competitor_gap), BF (deterministic `deep_learn`,
291/300), BC (NON-FIX) and BG/126 (a platform's own client-SDK family: stored
3x -- the sentence DRIFTS, so exact `_is_duplicate` missed it; same-`u` Jaccard
MEASURED-AND-REJECTED, 0.24-0.33 vs a legitimate 0.40) in
`references/root-causes-archive.md`. BE/BC/BF NAMED only, never written.
**134** (a newsroom INDEX page is not an article — a card's country tag welded
to the next card's headline; PAGE-level rule, text-level cannot see it) is
archived there too.
**138** (an ALL-CAPS nav lockup welded to prose AND repeated in Title Case — a
competitor's "Platform Demo" banner stored TWICE; the discriminator is the CASE
SHIFT, not a vendor literal, so the rule generalises. WELD alone = 26 prose FPs,
CASE-SHIFT alone = 2; the pair = 0 over ~4,600 real texts) is archived there too.
**139** (a landing-page marketing-SLOGAN clause; the row had already been a
`duplicate` for a WEEK — the buffer rotates ~200 rows/day vs a 300-row cap so
exact `_is_duplicate` is a same-window guard, not a permanent one, and the leak
came back. Also: an EOL normaliser is NOT idempotent on an already-CRLF block —
guard `\r\r\n == 0`, and `git add` under global `core.autocrlf=true` stores an
LF blob: `git rm --cached` + `-c core.autocrlf=false add`) is archived there too.
TWO warnings stay live because they are behavioural, not history:

- run `which_rule_matches.py` BEFORE touching a rule -- the AJ/AQ/AR trap has
  fired FOUR times: your own control trips a PRE-EXISTING `_NAV_CHROME`
  marker, so add the topic-matched hostile control first. Probe the FULL stored
  string (300 chars) -- a truncated copy prints a false `INDIVIDUAL MATCHED: none`.
- never sync this LF-native archive with a text-patch tool: `patch` expanded a
  literal `\r` and corrupted the file at an UNCHANGED byte count. Append pure
  bytes, then assert byte-exact equality with the install copy.
- never wire a gate on a rejection alone (measured-and-rejected = delete the
  signature, keep the rows).

**109/110 (20.09.26)**: own-artifact echo family + 3 harness limits (probe
false-`SKIP`s mixed-case candidates; scores `a` ONLY, so no pair-rule is
measurable; `search_files` can NOT read `AppData/Local` → `grep`.
Pair-rule MEASURED-AND-REJECTED (archive).

CF/130-132 (22.09.26): source-tally CTA + date-stamp strip + credit byline; FIXED, refs/.
133 (22.09.26): doc-site product-nav weld; ALL 4 bare forms REJECTED, 3 two-token welds FIXED, refs/.
135/136 (22.09.26): arXiv submitter WELD + aggregator card header (needs a TitleCase-continuation test; 1+2 FPs without it), found by eyeballing the buffer tail -- FIXED, refs/.
149 (23.09.26): a nav-menu WELD run into a card title drawn TWICE; the discriminator is nav-run>=3@60 AND an ADJACENT exact repeat (d<=L) -- repeat-alone=88 ep FPs, nav-alone=13 prose FPs, pair=0/0; FIXED, refs/.

**116/117 (20.09.26)**: no gate class at all -- step -1 found a whole
TESTED-BUT-UNCOMMITTED batch (AV again): `dry_run` never reached
`world_model.prune`, MSYS `OPENAMER_HOME` made a phantom tree, `prune()`
re-normalised 250M times, one 5 s health probe burned a slot. NEW TRAP: the
repo's `test_no_hardcoded_paths` rejects a path LITERAL in a DOCSTRING --
describe the MSYS form in prose. The mirror is TWO-WAY (live was AHEAD), so a
repo->live copy would have DELETED fixes -- union first. See archive.

**111/112 (20.09.26)**: 81 = own-artifact plan THIRD title → WIDEN the class-80
regex, not a new helper; 82 = German nav WELD + colon headline; the news ticker
has NO clean discriminator → signature delete. The 109/110 rows were still in
the buffer: a written verdict is not a cleanup. Also: `skill_manage(write_file)`
REPLACES a reference file — restore from the repo copy. See archive.

**119/120 (20.09.26)**: no learner gate in either — 119 was `self_improve.py`'s P2
rule deleting the `CYCLE_SECONDS` assignment it guards (`920131e54`, RED→GREEN
3/3); 120 was a 3-tree drift round with **9 drifts pointing BOTH ways** (4 files
live-AHEAD with a half-applied `chat_default` migration, 5 live-BEHIND incl.
`tool_server.py` which had LOST two utf-8 captures — ported up as `3a0ca2912`).
TWO live traps, both re-confirmed: (1) an autocrlf-off commit in a `git worktree`
still summarises a whole-file rewrite (423+/432- for 14+/23-) because the blobs
are LF and the worktree CRLF — **census the CR bytes in the BLOB**, and
`git diff --stat HEAD~1 HEAD` vs `--ignore-cr-at-eol` is the clean read; (2) the
mirror is two-way and the same tree can be ahead on one file and behind on
another in one run — `verify_three_copies.py` compares against the repo WORKTREE,
which sits on a foreign branch 36 commits behind, so its MISMATCH lines are
branch noise; `git cat-file blob origin/main:<f>` is the only truth. Also: a
`newline="\n"` cleanup silently flipped `online_buffer.jsonl` CRLF→LF (text-mode
`append` means CRLF is the store's contract) and 2 more `Share a lesson you
learned`-family echo rows were finally removed by signature (294→292, the 16
genuine answers asserted intact). See archive.

**121 (20.09.26)**: rotation exhaustion RE-CONFIRMED for the third round --
last 60 `duplicate` rejects 60/60 the identical `(u, a)`, 0 with a novel `u`;
57 recent `junk` candidates attribute ONLY to pre-existing helpers, zero novel
shapes -> no gate change. Same trap as 119/120 (see archive).

**128 (21.09.26)**: 121 re-confirmed (0/60 novel `u`) and the MECHANISM measured
-- `.il_seen_queries` is 800 entries but only **177 distinct**, and the avoid
window (`_recent_queries`, n=60) is **7.5% of the ledger** while **95% of the 623
real repeats are >60 entries apart** (median gap 67, mean 96). Widening `avoid`
to the full ledger is MEASURED-AND-REJECTED: only 2/8 cycle keywords still yield
a live headline vs 8/8 at n=60. Domain saturated, not broken. See archive.

## Counting the rejections — `buffer_junk.jsonl` rows have NO `ts`
`internet_learn_log.jsonl` rows carry `ts/source/result/elapsed_s`; the audit
rows in `buffer_junk.jsonl` carry ONLY `reason/u/a`. So a `ts`-prefix filter
against the audit file silently returns **zero** — live 22.09.26 that made a
busy day look like "the rejections never reached `store()`", which is wrong.
Count by **append order** (the file is append-only: the last N audit rows are
the most recent N rejections), and only then match a rate shift.
Also: `diagnose_learn_rates.py` counts a row as REJECTED for ANY non-"learned"
result, so `no insight` (shallow+deep both returned nothing) lands in the
rejected bucket. A rate drop can be **fewer candidates**, not a stricter gate --
distinguish the two before designing a rule.

## Trigger
`python internet_learner.py --once` (or the cron) reports
`cycle_x: rejected, not trained (shallow + deep read both gated)` on EVERY cycle,
and `online_buffer.jsonl` stays pinned at its cap (300 rows).

## Diagnose (fast)
-1. **BEFORE anything else: `git status --porcelain scripts/training tests/scripts`
   + `git diff --stat` in the repo.** A previous cron session can die after
   applying + testing a gate fix but BEFORE committing; the log then looks like
   "nothing new" while the working tree already carries the next class (root
   cause AV). Finish/verify/commit that work first, and re-sync ALL THREE test
   copies (the laptop one is often synced while `openamer-agent` is not).
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

## Root cause AL — FOUR chrome classes in ONE cron run, and the pitfall that a NEW rule can break an OLD test (live 17.09.26)

Cron run began with the documented `cycle_c_github: rejected` line. Rate said
**50 % (last 20) / 51 % (last 80) vs 81 % all-time (n=1780)** — the U/V
signature — so U/V were verified BEFORE inventing anything (`_search_urls(k=6)`
→ 6; `deep_learn` k2/k6 on 4 diverse queries → 2/4 identical windows, and the
2 `False` cases were query-dependent content artifacts, not the dead-code bug).
`buffer_junk` last 25 = `duplicate` at the 299/300 cap + documented junk shapes
= rotation noise. **No gate change was warranted for the rejection itself.**

The whole find came from the prescribed cheapest method — run `--once`, read the
BUFFER TAIL, eyeball `u`/`a` — repeated after each fix. All four rows passed
BOTH gates and NONE ever appeared in `buffer_junk.jsonl`.

| class | helper | measured |
|---|---|---|
| 33 | `_is_news_card_stub` — card headline + glued relative-date label + truncated counter tail (`... misalignment Sep 17 7.`) | 1 hit, IS the leak / 0 FP / 0 le |
| 34 | `_is_relative_time_nav_chain` — relative-time bullet ANDed with `For You / Latest / Trending` nav labels | 1 hit, IS the leak / 0 FP / 0 le |
| 35 | `_is_date_heading_listing` — date-stamped headline listing (blog archive) | 2 hits, BOTH leaks / 0 FP / 0 le |
| 36 | `_is_repo_tab_statbar_chrome` — `Code Issues Releases` tab chain ANDED with a `\d+ MiB <Lang> \d` stat bar | 1 hit, IS the leak / 0 FP / 0 le |

Class 33 is only 70 chars, so the `>=90` long-prose trust never applied — a
reminder that the trust is not the only way chrome gets in. Its anchor is the
TAIL (`$`), because a bare `<Mon> <day>` is an ordinary date.

### THE PITFALL — a broad new structural rule can re-flag an OLD test's counter-case prose
For class 35 my first rule was `>=3 full dates` OR `>=2 dates AND slash-category
breadcrumb`. It measured **clean on the live buffer (2 hits, both leaks) and on
every hand-written control** — and then `pytest` went RED on
`test_blog_archive_listing_is_gated_on_both_paths` (class 24), whose counter-case
prose is

    `...posts under headings like Insights July 17, 2026 and News May 29, 2026,
     but the agent should parse the article body.`

Two full dates + TitleCase labels → my rule flagged real prose.

**Rule: candidate markers must be run against the EXISTING gate test suite's
counter-case prose, not only against your hand controls + the live corpus.**
Hand controls and the live buffer agreed with the broken rule; the repo's own
regression corpus caught it in 3 s. So: apply, then run
`test_internet_learner_gate.py` BEFORE the cleanup/commit, and treat a new
red as YOUR rule being wrong, not the old test being stale.

The fix that survived: discriminate on **Title-Case density** of a title
listing, not on the date count —
`len(_FULL_DATE_RE.findall(t)) >= 2 AND upper_words >= 8 AND upper/total >= 0.5`
(measured 0 buffer FPs, 0 ctrl FPs, 0/3,056 le, and the class-24 leak is still
gated by its own rule). `_TITLE_WORD_RE = r"[A-Za-z][A-Za-z'./-]*"`.

### THE OTHER PITFALL — appending a test with `rstrip("\r\n")` causes EOL churn
`txt.rstrip("\r\n") + "\r\n\r\n\r\n" + TEST` normalises the file's LAST line,
which was one of the 58 pre-existing **lone-LF** lines in
`test_internet_learner_gate.py` (that file is NOT pure CRLF — it has 58 lone LFs
at HEAD; do not "fix" them). Result: `git numstat` showed `48 added, 1 removed`
and the lone-LF census went 58 → 57. Correct approach — **pure byte append**:
`open(p,"wb").write(open(p,"rb").read() + TEST.replace("\n","\r\n").encode())`,
then assert `numstat` has **0 removed** and the lone-LF count is **unchanged**.

Note the gate modules themselves ARE pure CRLF (2597/1340 lines, 0 lone LF),
while the test file is not — check each file's census separately.

### Session shape that worked here
Fix 33+34 and 35+36 in two passes, but the loop is the same: measure → apply to
BOTH gates in all 3 copies → re-scan buffer → **run pytest** → cleanup by
signature → append test (pure bytes) → mirror to the laptop test copy → commit
with a msg FILE (backticks in a `-m` string get eaten by git-bash:
`command substitution: syntax error near unexpected token '<'`) → push.
Result: `56 passed` gate file, `212 passed` `tests/scripts`, post-fix live
cycles 2/3, 2/4 and 3/3 learned with no chrome in the tail.

The AM run (three classes, 37–39) confirmed the loop scales: one measure → apply
→ pytest → cleanup → test → commit cycle per class, `59 passed` / `215 passed`,
3 pushes, and only the alias trap above cost extra rounds.

## Root cause AM — THREE chrome classes in ONE cron run, and the `re` vs `_re` alias trap (live 17.09.26)

Cron run began on the documented `cycle_c_github: rejected` line. Rate said
**54.5 % for the partial day (12 ok / 10 rej) vs 81–83 % all-time** — inside the
documented band, so no gate change was warranted for the rejection itself. The
file size was **stable** over 20 s (`91496` both samples) → no Darwin writer;
`.il_rotation` = 1803. All three finds came from the prescribed cheapest method:
run `--once` a few times and read the BUFFER TAIL (`u`/`a`), repeated after each
fix. All three rows passed BOTH gates and NONE was ever in `buffer_junk.jsonl`.

| class | helper | measured |
|---|---|---|
| 37 | `_is_hn_feed_listing_chrome` — a repeated aggregator feed row: relative time + `\| N comments` + points + headline, **>=2 occurrences** | 1 hit, IS the leak / 0 FP / 0 le |
| 38 | `_is_marketing_hero_cta_chrome` — landing-page hero: availability line + nav CTA + tagline + `[*]` marker + brag opener `With over` / `Mit über` | 3 hits, ALL THREE the same page hero / 0 FP on 26 controls / 0 le |
| 39 | `_is_platform_selector_listing_chrome` — `macOS Apple Silicon (arm64)`-style selector within 200 chars of `r/<name> community` | 1 hit, IS the leak / 0 FP on 21 controls / 0 le |

**Class 37 — the discriminator is REPETITION, not the parts.** The single-occurrence
form `\b(?:minutes?|hours?|days?|weeks?|months?)\s+ago\s*\|\s*\d{1,5}\s*comments\b`
flagged the control `The review took 2 days ago | 4 comments per reviewer were
recorded.` → REJECTED as the shipped rule. `>=2` findall measured 1 buffer hit
(the leak), 0/12 controls, 0/3,056 episodes. `by <user> N days ago` and bare
`\d+ comments` were also rejected (real prose + 3 live episodes).

**Class 38 — one page hero stored THREE times in one buffer** (once in German via
`cycle_e_competitors`, twice in English at rows 17/87). Tell: rows 17 and 87 were
**byte-identical**; always group the flagged rows before designing a marker, or
you will write a marker for one third of the leak. The looser
`(?:Read docs|Doku lesen)[\s\S]{0,120}?\[\*\]` form was REJECTED on measurement
(3 control FPs: `Read docs to learn how the [*] wildcard expands in glob
patterns.`, `Doku lesen hilft, weil [*] die Pflichtfelder kennzeichnet.`,
`Read docs and [*] will be replaced by the matched text.`). Only the
`[*]`-adjacent brag opener survived.

**Class 39 — class 34's rule needs the `For You / Latest / Trending` labels;
this shape has none.** Platform selector + `DISABLED` + `…` + upvote count +
`r/... community` + relative time + forum title. Candidates A3/A4 (tighter
anchors) also measured clean; A2 (`r/<name> community`, the widget's own label)
shipped as the most specific. The `(arm64...)` + relative-time form was
REJECTED — 3 control FPs.

### THE PITFALL — `internet_learner.py` uses `re`, `buffer_store.py` uses `re as _re`
Copy-pasting one helper into both files raises `NameError: name 're' is not
defined` (or `_re`, in the other direction) **at import time**, which shows up as
a `pytest` collection error, not a gate failure. This cost two extra apply/fix
round-trips in one run (once for class 37 in `buffer_store`, once for class 38 in
`internet_learner`). Before writing the helper, grep the target file's import
alias:
```
grep -n "^import re" <file>     # `import re` vs `import re as _re`
```
Ship the constant with the correct alias per file — or avoid the issue entirely
by writing `import re`-free helpers. Never assume the two modules agree.

### Also: build the anchor with CRLF, and expect it to be the blank-line-separated two-line form
`"    if _is_relative_time_nav_chain(t):\r\n        return True\r\n"` is the
reliable insertion anchor (LF-only anchors match 0 times on these pure-CRLF
modules). Anchor on the PREVIOUS class's call, not on a line number — every
insert shifts the file.

Cleanup + verify (the standard shape, per class): remove leaks by signature with
the CRLF-split reader (`split("\r\n")`, never `readlines()`), assert the dropped
count, rewrite with `newline=""` + one record per CRLF. Live censuses:
300/7 → 299/7 (cls 37), 300/7 → 297/7 (cls 38), 300/7 → 299/7 (cls 39); **7 is
the baseline** writer-flagged count in this buffer (rows 5, 9, 19, 27, 29, 36, 45
= pre-existing SERP/listing shapes — do NOT "clean" those), 53
structural-connection rows preserved, 0 unparsable every time.
`pytest tests/scripts/test_internet_learner_gate.py -q` → **56 → 57 → 58 → 59
passed**; `pytest tests/scripts -q` → **212 → 213 → 214 → 215 passed**. Three
commits pushed. Post-fix live cycles: 2/3, then 1/3 where both rejects were
honest (`duplicate` at the 300 cap) — **read `buffer_junk` before calling a
rejection a regression.**

## Root cause AP — the learner's OWN deep-read prompt echoed back as a bullet chain (class 42, live 17.09.26)

Cron run began on the documented `cycle_g_security: rejected` line. Rate said
**30 % (last 10 and last 20) vs 80 % all-time (n=1828)** — the U/V signature —
so U/V were verified BEFORE inventing anything: `_search_urls(k=6)` → **6/6 on
all 5 diverse queries**; `_fair_share_window` → **5 slices**; buffer size
byte-stable (`90761` both samples) → no Darwin writer. `buffer_junk` last 25 =
`duplicate` at the 298/300 cap + documented `junk` shapes = rotation noise, so
**no gate change was warranted for the rejection itself**. Writer-gate census
**0 of 298** → the buffer was clean at entry.

**The leak was CREATED BY THIS RUN** — a reminder that "buffer was clean at
entry" does not survive six `--once` cycles. After 6 rejects the 7th cycle
(and the 8th) learned, and the 8th stored the learner's own task template:

    "\n   - Input is a list of daily paper submissions with titles, authors, and
     brief tags/counts\n   - I need to identify the single most valuable technical
     insight for an autonomous AI agent from these paper titles/descriptions\n
     - Output must be a sin"

190 chars **with digits** → the `>=90` length trust AND the technical-signal
gate both fired. **Do not read a `learned` line as success** — this one's log
line (`efficiency-learn: "\n - Input is a list of daily paper submissions …`)
was visibly suspicious, but the skill's rule stands: read the BUFFER tail
`u`/`a` pairs, because the stored form is what trains.

Why every existing marker missed it:
- `_INSTRUCTION_OPENER_RE` is **START-anchored** (`^\s*\**\s*…`) — this text
  opens with a `"` + newline, so the anchor never lands, even though `I need to`
  is literally in its alternation.
- `_is_nav_list` wants ≥6 TitleCase tokens with no comma — a mixed task-frame
  bullet chain is neither.

### The discriminator is the BULLET CHAIN, not the phrase
`_is_prompt_echo_bullet_chain(text)` = `>= 2` bullets each opening with a
task-frame word, via `_PROMPT_ECHO_BULLET_RE`:
`(?:^|[\r\n])\s*[-*•]\s+(?:Input\b|Output\b|I need to\b|I must\b|I should\b|The task\b|Identify the\b|Steps?\b|Constraints?\b|Format\b)`
Wired into BOTH gates (extraction `internet_learner._is_junk` + writer
`buffer_store._is_nav_chrome`) in all 3 copies — the AH both-files rule.

**Every single-phrase candidate was measured and REJECTED:**

| candidate | buffer | hand FP | verdict |
|---|---|---|---|
| `\bInput is a list of\b` | 1 = leak | **3** (`Input is a list of tokens…`, `The input is a list of papers…`, `In the benchmark, input is a list of 512 sequences…`) | REJECTED |
| `\bI need to identify the single\b` | 1 = leak | 1 | REJECTED |
| `\bfor an autonomous AI agent from these\b` | 1 = leak | 0 | ok but narrower than the class |
| `\bpaper submissions with titles\b` | 1 = leak | 1 | REJECTED |
| **bullet-triad (`>=2` task-frame bullets)** | **1 = leak** | **0** | **SHIPPED** |

Measured clean the strong way — **my rule ALONE**, not `_is_nav_chrome`:
1/300 buffer (= the leak), **0/3,056** `longterm_episodes`, **0/591** string
literals extracted from the gate test file, 0/13 hand controls.

### PITFALL — `_is_nav_chrome` FPs are NOT your rule; test YOUR helper in isolation
The first verify loop measured `control FPs writer=0 learner=1` and
`test-literal FPs: 35`, `episode FPs: 74/3056`. That looked like massive
collateral. It was not: the 35 and the 74 came from **pre-existing** markers
(GitHub repo-listing rows, `_NAV_CHROME` phrases like `Let Chat …`, date
headings) that those corpora legitimately trip. Only the learner control
(`I need to identify the single most valuable technical insight from the
report.`) was mine — and the diagnostic showed
`_INSTRUCTION_OPENER_RE.match(ctrl) == True` (pre-existing rule), while
`_is_prompt_echo_bullet_chain(ctrl) == False`. **Always probe the new helper
directly**; a corpus FP count through the composite gate tells you nothing
about your change. Same lesson as the AJ/AI control-corpus pitfall, third
occurrence — the skill now says: isolate first, diagnose which rule matched
second, only then conclude.

### Also — a `learned` cycle can hide the leak behind a clean-looking tail
After the cleanup, the post-fix cycles gave 1 learned of 3 (`cycle_c_github`,
real MAF content, `writer=False extract=False`) — read the buffer, not the
log, and re-run the census **after** every fix (`299` records, 0 unparsable,
53 structural rows, writer-gate 0).

Cleanup + verify (standard shape): leak removed by signature
(`Input is a list of daily paper submissions with titles`,
`I need to identify the single most valuable technical insight for an autonomous AI agent`),
**300 → 299** records, `0 unparsable`, CRLF intact, **53** structural-connection
rows preserved, writer-gate census **0**. Test appended as **pure bytes**
(lone-LF census 58 → 58 for the repo file, 0 → 0 for the laptop copy), and the
3 CODE copies + repo test verified byte-identical via `md5sum` (repo ==
laptop == openamer-agent: `230f36de…` learner, `70170f3e…` store).
`pytest tests/scripts/test_internet_learner_gate.py -q` → **61 → 62 passed**
(new `test_prompt_echo_bullet_chain_is_gated_on_both_paths` asserts BOTH gates
on the leak + 10 prose counter-cases); `pytest tests/scripts -q` →
**217 → 218 passed**. Commit `bb0d00ae2`, `numstat` **93 added / 0 removed**
(no EOL churn), pushed `HEAD:main` from the foreign branch
`fix/28-respawn-test-psutil-hermetic` (`merge-base --is-ancestor main HEAD` →
FF_SAFE), `origin/main` re-read = `bb0d00ae2…`, `git branch -r --contains`
confirms `origin/main`.

## Root cause AO — an EXISTING strip-helper whose guards were one variant too narrow (class 41, live 17.09.26)

Cron run began on the documented `cycle_h_efficiency: rejected` line. Per-day rate
37–60 % (15:00 hour partial, 0/4) vs 81 % all-time → inside the documented band, so
**no gate change was warranted for the rejection itself**; `buffer_junk` last 20 =
`12 duplicate` (buffer at 297–300 cap) + `6 junk` + `2 no-tech-signal`, all
documented shapes. Buffer tail was clean (0 of 298 writer-flagged).

**The leak came from running `--once` and reading the BUFFER TAIL — twice in a row.**
`cycle_b_papers` learned a row whose LOG LINE showed the chrome
(`Yash Thakker CoreWeave NVIDIA Sep 17, 2026 · 8 min read Databricks Deploys GPT-6 (56.2s)`)
even though the STORED text was clean — so *do not judge a cycle by its log line*.
The stored rows that *had* leaked were two `min read` blog cards:

| u | a (stored) |
|---|---|
| `Latest research insight: Breaking the 1.58-bit Barrier …` | `AI Agents 11 min read AI Agent Cost Benchmarks: Tokens, Latency, and Dollars per Task Original 2026 benchmark: …` |
| `AI model exit strategy` (fresh) | `Start the challenge Blog 18 April 2026 / 24 min read 8 best open-source AI agent frameworks on GitHub in 2026 The best …` |

### THE LESSON — check whether an EXISTING helper's GUARDS are too narrow before writing a new class
The repo already had `_strip_trailing_read_time_header` (17.09.26, class-40 era) for
exactly this family. Both live rows still got through because of TWO guards:
1. `body[:1].isupper()` — row 2's body starts with a **digit** (`8 best open-source …`).
2. `_BLOG_HEAD_DATE_RE.search(head)` required a dateline — row 1's head is a bare
   category label (`AI Agents`) with **no date at all**.

So the fix was to **relax two guards**, not to add a 4th chrome class. Guard 2's
replacement keeps a structural discriminator: without a dateline the head must be a
short (≤4 words) **pure-TitleCase label chain with no lowercase words**. Real prose
that merely mentions a read time sits inside a sentence and carries lowercase words,
so it stays untouched. New constant `_BLOG_HEAD_LOWER_RE = re.compile(r"\b[a-z]{2,}\b")`.

Measured (0-collateral proof): 2/2 leaks stripped with a **byte-identical body**;
**0 of 3,056** `longterm_episodes`; **0** hand-written prose controls; and — the
strongest form — a **pre/post module diff of `_clean_insight` output on all 8 control
strings = 0 diffs** (load the backup module with `importlib` and compare, instead of
only asserting the new behaviour).

**Do not treat a `min read` control that `_clean_insight` returns `""` for as YOUR
regression** — two of the 8 controls already returned `""` pre-edit (short non-tech
signal). Always diff old-vs-new module output before hunting a regression you did not
cause. The 2 hand-written "hostile" controls (`Machine Learning 5 min read The study
found that quantization helps.`) ARE correctly stripped — they are chrome-shaped by
construction, so a harness that lists them as `ctrlFP` is reporting the intended
behaviour, not a bug.

### PITFALL — the strip helper was applied to the LAPTOP copy only, so the REPO test went red
The first apply pass edited only `AppData/Local/openamer-laptop/scripts/training/internet_learner.py`;
`pytest` in `openamer-repo` then failed the new test because the repo copy still had
the old guards. **After any apply, `md5sum` all THREE copies before running pytest** —
one red suite here was purely a missing sync, not a wrong rule. (Standard: Repo=SoT,
laptop=LÄUFT, openamer-agent=older copy; all three must be byte-identical.)
The repo file is pure CRLF and the laptop copy too, so the same
`norm(s) = s.replace("\n", eol)` script applies to all three unchanged.

Cleanup + verify (standard shape): 2 chrome rows **plus the documented root-cause-AG
off-topic row** (`Databricks Deploys GPT-6 …`) removed by signature → **300 → 297**,
`0 unparsable`, CRLF intact, **53** structural-connection rows preserved, writer-gate
census **0 of 297**. The cleanup script's `assert len(dropped) == 2` fired on the
third row — **keep that guard and widen it deliberately** after identifying the extra
row, rather than deleting the assert.
`pytest tests/scripts/test_internet_learner_gate.py -q` → **60 → 61 passed** (new
`test_midtext_read_time_header_without_dateline_is_stripped`, appended as pure bytes:
42 added / 0 removed, lone-LF census 58 → 58); `pytest tests/scripts -q` →
**216 → 217 passed**. Commit `0cc459b21`, pushed `HEAD:main` (branch was again
`fix/28-respawn-test-psutil-hermetic`; `merge-base --is-ancestor main HEAD` → FF_SAFE,
`git branch -r --contains` confirms `origin/main`).
Post-fix live: 3 × `--once` → all rejected; `buffer_junk` shows honest reasons
(`duplicate` at the cap + already-gated shapes) and the buffer tail is 0-of-297
writer-flagged. **Read `buffer_junk` before calling a rejection a regression** — again.

## Root cause AN — mid-text byline + `Published <dd Mon yy>` header (class 40) + the foreign-branch trap (live 17.09.26)

Cron run began on the documented `cycle_d_docs: rejected` line. Rate check:
per-day 47 % for the partial hour vs 81 % all-time — inside the documented
50–80 % band, so **no gate change was warranted for the rejection itself**.
`buffer_junk` last 25: `13 duplicate` (buffer at the 300 cap) / `10 junk` /
`1 no-tech-signal` / `1 offtopic-drop` — all documented shapes = rotation noise.
The find came from the buffer tail, the prescribed cheapest method.

**Two leak rows, both passing BOTH gates, neither ever in `buffer_junk.jsonl`:**

| cycle | u | a |
|---|---|---|
| (row 23) | physical security CIO | `Pro Why CIOs are paying closer attention to physical security By Mark Coates Published 14 September 26 Connected physical security is reshaping how CIOs approach risk, data and resilience.` |
| (row 124) | AI model exit strategy | `Pro Why every enterprise needs an AI model exit strategy By Ganesh Padmanabhan Published 15 September 26 Model flexibility helps enterprises protect workflows, institutional knowledge and control as AI evolves.` |

188 / 210 chars **with digits** → the `>=90` length trust AND the
technical-signal gate (`14 September 26`) both fired.

### The insight that was already in the repo and still did not help
`_strip_byline_prefix` (class 29, 16.09.26) exists precisely for bylines — and
the test file **already contained the exact leak string** as
`assert IL._strip_byline_prefix("By Mark Coates Published 14 September 26") == ""`.
It did not catch the live row, because the helper only removes a **LEADING**
byline segment. Here the byline sits **AFTER the headline, mid-text**:
`<chip> <headline> By <Author> Published <dd Mon yy> <lede>`.
**Before concluding a shape is new, check whether an existing helper covers the
same vocabulary but not the same POSITION** — that is a new class, not a
duplicate.

### Marker (the tight pair, in BOTH gates — the AH both-files rule)
`_is_byline_published_article_header` →
`\bBy\s+[A-Z][a-z]+\s+[A-Z][a-z]+\s+Published\s+\d{1,2}\s+[A-Z][a-z]{2,9}\s+\d{2}\b`
The discriminator is the page's own furniture **pair** (byline welded to
`Published`, unlike the class-29 `Written by … · Published …` form).

| candidate | buffer hits | conclusion |
|---|---|---|
| `published <dd> <Mon> <yy>` alone | 2, both leaks | identical on this corpus, but less specific → the pair shipped |
| `pro why` (chip) | 2, both leaks | topic word, rejected as the marker |
| `By <First> <Last> Published` | 2, both leaks | **SHIPPED** |

Measured: **0 real-prose FPs** on a 12-sentence hostile control corpus (incl.
`By Mark Coates Published research shows …`, `The paper was published in
September 2026 by the ACM …`, `By contrast, the 2024 study found …`,
`Published 2026 benchmarks show vLLM …`); **0/3,056** `longterm_episodes`.

### PITFALL — your control corpus must not contain KNOWN leaks (AJ, recurred)
The first verify run reported `prose_FPs=1` on the class-29 string
`Written by Christian Gleitze · Published June 11, 2026 · … AI Consciousness …`.
That string IS a known leak from class 29's test, not a clean control.
Proof it was not my rule: `BS._is_byline_published_article_header(t) == False`
while **pre-edit** `_is_nav_chrome(t) == True` (reconstructed the pre-edit
module by deleting my own block and importing it). Rule as before: when a
harness reports an FP, **print which rule matched**; keep control corpora clean
and assert known leaks in their own `is True` assertion.

### PITFALL — the commit landed on a FOREIGN BRANCH (new, cost the push)
`git commit` succeeded, but the repo was checked out on
`fix/28-respawn-test-psutil-hermetic` — left there by an earlier cron. The
skill's "repo is the source of truth" step silently pushed nothing toward
`main`. Then `git checkout main` **aborted** because foreign crons had left
**65 dirty files** in the working tree.

Working recovery (do this, don't fight the dirty tree):
```
git branch --show-current                        # surprise: not main
git merge-base --is-ancestor main HEAD && echo FF_SAFE
git log --oneline main..HEAD                     # main is a clean ancestor -> FF
git push origin HEAD:main                        # no checkout needed
git fetch origin main && git rev-parse origin/main   # verify the SHA landed
```
Verify with `git branch -r --contains <sha>` — if it prints nothing, the commit
is on no remote at all and the work is not backed up.
The branch here was **13 commits ahead of `main`** (earlier class 37/38/39
fixes plus foreign cron auto-commits) and `origin/main` matched local `main`,
so the push fast-forwarded all of it cleanly. **Always check the branch and the
remote SHA before and after committing**, not just the commit's exit code.

Cleanup + verify (standard shape): both rows removed by signature
(`Published 14 September 26` / `Published 15 September 26`),
**300 → 298** records, 0 unparsable, CRLF intact, **53** structural-connection
rows preserved, writer-gate census **0 of 298** (no over-gating).
`pytest tests/scripts/test_internet_learner_gate.py -q` → **59 → 60 passed**
(new `test_byline_published_article_header_is_gated_on_both_paths` asserts BOTH
gates on both leaks + 7 prose counter-cases); `pytest tests/scripts -q` →
**216 passed**. Test file appended as **pure bytes** (lone-LF census 58 → 58,
`0 removed` in the diffstat).
Post-fix live: 3 × `--once` → all 3 rejected, and `buffer_junk` shows the
rejections were honest (`6 duplicate` at the cap + documented junk shapes).
**Read `buffer_junk` before calling a rejection a regression** — again.

### Also — the appended test needs its own `import buffer_store`
The gate test file imports `buffer_store` **lazily inside each test**, not at
module level. An appended test that references it fails with
`NameError: name 'buffer_store' is not defined` while every pre-existing test
stays green. Add `import buffer_store` inside the new test function.

## Root cause AQ — TWO chrome classes in ONE cron run + the import-time trap that `ast.parse` misses (live 18.09.26)

Cron run began on the documented `cycle_g_security: rejected` line. Rate check:
per-day **71.4 %** for the partial day (5 ok / 2 rej) vs the documented 50–80 %
band → **no gate change was warranted for the rejection itself**; `buffer_junk`
last 25 = `duplicate` at the cap + documented junk shapes = rotation noise.
The finds came from the prescribed cheapest method: run `--once`, read the
BUFFER TAIL `u`/`a`, repeat after each fix. Both rows passed BOTH gates and
NEITHER was ever in `buffer_junk.jsonl`.

| class | helper | measured |
|---|---|---|
| 50 | `_is_nav_widget_run_chrome` — a document-hosting page's nav-widget run (skip carousel / go to prev·next items / footer menu / back to top / about scribd), **>=4 labels** | 1 hit, IS the leak / 0 FP / 0 le |
| 51 | `_is_news_byline_share_header` — `By <First> <Last>` + full weekday dateline + the site's own `Share` within 40 chars | 1 hit, IS the leak / 0 FP / 0 le |

**Class 50 — the threshold IS the fix, and `>=2` is a topic-word trap.** A single
label is ordinary prose (`Skip the carousel and go to the previous items`), so the
discriminator is REPETITION. `>=2` measured **4 control FPs**
(`Back to top of the article, the footer menu lists the licence.`), `>=3` still
**2** (`The UI has a skip carousel button, …`), **`>=4` measured 0** on an
18-sentence corpus, 0/511 test literals, 0/3,058 episodes. The leak holds **6**
labels, so there is headroom. Do not stop at the first clean-enough threshold —
sweep `2,3,4,5` and ship the lowest one with 0 FPs on ALL corpora.
Also: adding a SITE-IDENTITY label (`about scribd`) to rescue a threshold does
NOT help — `about scribd` is itself ordinary prose (`About Scribd, Inc. is the
footer copyright line…`) and still left 1 FP.

**Class 51 — check whether an existing helper covers the vocabulary but not the POSITION.** `_strip_byline_prefix` (class 29) already exists for bylines and
still returned the leak **unchanged**, because it only removes a LEADING byline
segment — this byline sits after a brand chip. `_is_byline_published_article_header`
(class 40) keys on `Published`, not on a weekday dateline + `Share`.

### THE TRAP THAT COST THE MOST: a closing paren glued INSIDE the regex literal
My apply template emitted

    _NAV_WIDGET_RE = re.compile(
        r"skip carousel|…|back to top"
        r"|about scribd)",        <-- the ) is INSIDE the string
        re.IGNORECASE)

`ast.parse` **passed** (it is valid Python — just a string containing a paren), so
the syntax gate said OK, and the failure only appeared at **import**:
`re.error: unbalanced parenthesis`. Two fix attempts were wasted because the
first "fix" replaced the string with itself (I anchored on the already-broken
text). **After ANY apply, `exec_module` the file — never trust `ast.parse` alone.**
`ast.parse` proves it parses; only an import proves the module-level `re.compile`
and every other constant actually evaluate. Same rule catches the `re` vs `_re`
alias trap (root cause AM) in the same step.

### Also — my `{arg}` template assumed a parameter name; the store used `t`
The class-50/51 helpers were wired with `_is_nav_widget_run_chrome(text)` in
`buffer_store` but the file's own convention there is `t` (`_is_hn_item_chrome`
takes `text`, its neighbours do not). The apply script's anchor matched 0 times
and the learner copy got patched while the store copy silently did not — the
3-copy `md5sum` is what caught it. **Read the neighbouring helper's actual
signature before templating the call**, and re-run the 3-copy md5 after every
apply pass.

### Also — pre-existing gate FPs: attribute through the PRE-EDIT module
`The newsletter is published every Thursday, and the April 30, 2026 issue covered agents.`
tripped `_is_junk` through the composite gate. My rule returned `False`, and the
pre-edit module (still on disk from the backup) returned `True` **and did not
contain my helper at all** → pre-existing, not my regression. Always load the
pre-edit module and compare; a composite-gate FP count tells you nothing about
your change (third+ occurrence of this lesson).

### Also — a class-N rule landed MID-DAY, so a stale buffer row is not a new class
The buffer held a Hacker-News item row while `_is_hn_item_chrome` (class 49,
same day) already gated it → the rule was NEWER than the row. Before designing a
helper for a gated row, `grep` the file for a rule added today; if it exists, the
row is just a pre-rule leftover → delete it by signature, no code change.

Cleanup + verify (standard shape): class-50 leak removed by signature
(`community's uploads`) **300 → 298**, then class-51 (`By Mason Leib Thursday,
April 30, 2026 Share`) **299 → 298**; every time `0 unparsable`, **55**
structural-connection rows preserved, CRLF intact (loneLF 0), writer-gate census
**2 → 0** then **1 → 0**. Note the historical "**7 is the baseline** writer-flagged
count" (root cause AM) has since decayed to **0** — re-census, don't quote the
old number.
`pytest tests/scripts/test_internet_learner_gate.py -q` → **68 → 69 → 70 passed**
(new `test_nav_widget_run_chrome_is_gated_on_both_paths` and
`test_news_byline_share_header_is_gated_on_both_paths`, each asserting the helper
AND both gates on the leak + a prose counter-case corpus); `pytest tests/scripts
-q` → **225 → 226 passed**. Tests appended as **pure bytes** (31–32 added / **0
removed**, lone-LF census 58 → 58 both times).

### Remote-divergence recovery (new — cost one push)
`git push` was rejected `non-fast-forward`: `origin/main` had gained 2 foreign
chore commits (darwin refresh + daily release) while the branch was checked out on
`fix/28-respawn-test-psutil-hermetic`. Neither touched the training scripts
(`git diff --name-only HEAD...origin/main -- <my files>` → empty). Recovery that
worked:
```
git fetch origin main
git merge-base --is-ancestor origin/main HEAD   # NO_DIVERGED
git diff --name-only HEAD...origin/main -- scripts/training tests/...   # no overlap
git stash push -m "<tag>" -- pyproject.toml     # foreign cron dirt blocked the merge
git merge origin/main --no-edit                 # clean (ort)
git -c credential.helper= -c credential.helper=store push origin HEAD:main
git stash pop                                    # restore the foreign edit untouched
```
Merge instead of fighting the dirty tree — but **`git merge` aborts on ANY dirty
file it must touch**, so stash exactly the blocking path (never `stash -A`) and
pop it afterwards so the other cron keeps its change.
Two more traps in this repo:
- **`git commit -F` needs the WINDOWS path.** `/c/Users/.../msg.txt` gave
  `fatal: could not read log file` while `C:/Users/.../msg.txt` worked — the
  MSYS→Windows conversion does not apply to `-F`.
- **`core.autocrlf=true`**, so `git show origin/main:<file> | md5sum` will NEVER
  equal the working copy's md5 (blob is LF, the file is CRLF). Verify with
  `git cat-file blob origin/main:<file> | tr -d '\r' | md5sum` vs
  `tr -d '\r' < <local>` — both matched for both modules.
Confirm the push landed with `git branch -r --contains <sha>` printing
`origin/main`, then `git cat-file blob origin/main:<file> | grep` for the new
marker — do not trust the push exit code alone.

## Root cause AR — THREE chrome classes in ONE cron run, and the `_re` alias trap catching an apply that `ast.parse` passed (live 18.09.26)

Cron run began on the documented `cycle_b_papers: rejected` line. Rate said **41 %
(last 80) / 40 % (last 20) vs 78.5 % all-time (n=1900)** — the U/V signature — so U/V
were verified BEFORE inventing anything: `_search_urls(q, k=6)` → **6,6,6,6,6 on five
diverse queries**; `_fair_share_window` → **4000 chars / 1 slice… 5 slices**. No gate
change was warranted for the rejection itself; `buffer_junk` last 20 = `duplicate` at
the 296–299 cap + documented `junk` shapes = rotation noise. All three finds came from
the prescribed cheapest method: run `--once`, read the BUFFER TAIL `u`/`a`, repeat after
each fix. All three rows passed BOTH gates and NONE was ever in `buffer_junk.jsonl`.

| class | helper | measured |
|---|---|---|
| 55 | `_is_news_aggregator_listing_run` — a press-roundup pipe run `\| <Site> <Mon DD, YYYY> <Headline>` repeated, **>=2** | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 56 | `_is_devto_card_tail` — a dev.to cross-post card counter bar `<N> projects \| dev.` at the **TAIL** (`$`) | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 57 | `_is_services_menu_chain` — an ALL-CAPS `X & Y` nav label **ANDED** with >=2 service titles | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |

**Class 55 — again the discriminator is REPETITION, not the parts.** One
`| Techzine Oct 08, 2025` segment is ordinary prose (`Coverage appeared | Techzine
Oct 08, 2025 and again in the roundup.`); `>=2` measured 1 buffer hit (the leak), 0 on
a 14-sentence control corpus, 0 test literals (801 extracted), 0/3,058 episodes. The
first draft required `\|\s*[A-Z][A-Za-z0-9]*\s+DATE` (site name optional-word run) and
flagged the control `We compare | Vercel Feb 3, 2026 and | Linear Mar 4, 2026 and |
Stripe Apr 5, 2026 in the study.` → REJECTED; tightening to a single site token plus a
**Capitalized headline word after the date** (`…\d{4}\s+[A-Z]`) kept the leak at
`>=3` and stayed clean at `>=2`. **Sweep the threshold, then re-sweep the token shape —
a control FP at >=2 and a miss at >=3 means the PATTERN is wrong, not the number.**

**Class 56 — only 66 chars, so the `>=90` length trust never applied.** A reminder that
the trust is not the only way chrome gets in (class 33 precedent). The anchor must be
the TAIL: `We shipped 2 projects | dev.to published the writeups afterwards.` and
`The team closed 5 projects | dev. then moved on.` are both ordinary prose and are NOT
flagged by `$`.

**Class 57 — the bare ALL-CAPS-token count was the trap.** `\b[A-Z]{2,}\b` at `>=4`
measured **36 buffer hits / 384 episodes / 1 control FP** (`vLLM … 24 GB VRAM (USA).`),
`>=5` still 23 hits and 270 episodes. Adding `Data Engineering`/`DevOps Engineering` to
the service-label set **re-introduced** the FP
`We combine AI & ML research with DevOps Engineering and Data Engineering practice.`
Keep the label set to the four titles the live page actually ships
(`RPA Development|Computer Vision|AI Integration|AI Product Engineering`) and AND it
with the ALL-CAPS `&`-label — then the corpus is 1/1 and every control, including that
same sentence, stays clean.

### THE PITFALL — `internet_learner.py` uses `re`, `buffer_store.py` uses `re as _re` (again)
The learner copies took the shared block verbatim; `exec_module` on `buffer_store.py`
raised `NameError: name 're' is not defined. Did you mean: '_re'?` **at module level**,
`ast.parse` having been perfectly happy. This is root cause AM/AQ recurring a third
time — **the apply script must import every copy it writes**, and the store block must
be emitted separately with `_re.compile`. Build ONE block per file (they differ ONLY in
the alias), never one shared string.

### Also — the leak-row cleanup guard must be widened deliberately, not deleted
`assert len(drop) == 3` fired correctly; the dropped set was exactly the three intended
rows and 56 structural-connection rows survived (the historical 53 has drifted upward —
re-count, don't quote the old number). Every step: `0 unparsable`, lone-LF 0, CRLF
intact, writer-gate census **3 → 0**.

### Verify (the standard shape, all met)
3-copy `md5sum` identical for BOTH modules after every apply
(`4c1451c0…` learner, `40c2eb8a…` store, then `217ba253…` post-push verify);
`pytest tests/scripts/test_internet_learner_gate.py -q` → **73 → 76 passed**
(3 new tests, each asserting the helper AND `_is_junk` AND `_is_nav_chrome` AND
`is_junk` on the leak plus 4–6 prose counter-cases); `pytest tests/scripts -q` →
**232 passed**. Tests appended as **pure bytes** (58 → 58 lone LF, diffstat
**237 added / 0 removed** — no EOL churn). Commit `e5a6479a9`; branch was again
`fix/28-respawn-test-psutil-hermetic` → `merge-base --is-ancestor main HEAD` = FF_SAFE,
pushed `HEAD:main`; `git branch -r --contains e5a6479a9` → `origin/main`;
**remote blob verify**: `git cat-file blob origin/main:<file> | tr -d '\r' | md5sum`
== local `tr -d '\r' | md5sum`, and the remote blob greps 3 of 3 new markers.
Post-fix live cycles: 1 reject / 2 learned, all new rows `writer=False extract=False`,
buffer 296 → 299, writer-gate census **0**.

## Root cause AU — FIVE chrome classes in ONE cron run (67–71), and the "check the test suite's own REJECTED rules" lesson (live 18.09.26)

Cron run began on the documented `cycle_a_technews: rejected` line. Per-day rate
**56.1 %** (32 ok / 25 rej) vs the documented 50–80 % band → **no gate change was
warranted for the rejection itself**; `buffer_junk` last 12 = `duplicate` at the
289 cap + documented `junk` shapes (SERP `… — <date>`, `Self-critique:` echo) =
rotation noise. Writer-gate census at entry: **0 of 289**. All five finds came
from the prescribed cheapest method: run `--once`, read the BUFFER TAIL `u`/`a`,
repeat after each fix. **Four were created by POST-FIX cycles** (the AS lesson
again: "clean at entry" does not survive the next cycle — budget one cleanup
pass per class and re-census after every fix).

| class | helper | measured |
|---|---|---|
| 67 | `_is_journal_issue_index_chrome` — `NAME NN(NN) - Month YYYY :` issue token | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 68 | `_is_truncated_serp_tail` — site-suffix title + em-dash snippet + SPACE-glued trailing `…` at TAIL | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 69 | `_is_docs_feature_label_weld` — two docs feature labels separated by whitespace/colon ONLY | 5 hits, ALL the docs-listing family / 0 FP / 0 le / 0 lit |
| 70 | `_is_label_bullet_chain` — >=2 `<TitleCase Label> : <value>` bullets | 2 hits, BOTH the leak family / 0 FP / 0 le / 0 lit |
| 71 | `_is_repeat_badge_glyph_run` — the page's own `U+1F195` badge on >=2 entries | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |

### THE MOST IMPORTANT LESSON — grep the test suite for ALREADY-REJECTED rules before designing one
My first candidate for the 8-row `…;` SERP-run family (rows 88/147/182/199/213/
235/278) measured **7/7 buffer hits + 0 control FPs** and looked like a clean
class-67-shaped win. It was **already tried and rejected in a previous session**,
and the gate test file says so in the docstrings it uses as counter-case prose:

    A structural "\u2026;" gate was REJECTED because 7 of the 16 such buffer rows
    (vLLM, quantization) carry genuine technical prose; the marker is the
    dictionary's own call to action instead.

`_SERP_ELL_DASH`/`_SERP_PIPE_DASH`/`_is_docs_cta_serp_run` (class 53) exist
*because* that generic rule ate real prose. **A high buffer hit-count with 0 FPs
on YOUR hand controls is not proof** — those 8 rows are exactly the rows a
previously-rejected rule would eat, so they stay un-gated by design. Before
shipping any structural candidate, `grep` the gate test file for the marker
shape; if the suite documents it as rejected, stop. (Cheapest tell: the counter-
case literals inside `assert not is_junk(prose)` lists ARE the leak rows of a
rejected rule.)

### The trailing-ellipsis family has NO clean discriminator — remove by signature only
Rows 290 (`… scalable …`) and 221 both END in `…`. Bare `\u2026\s*$` measured
**2 buffer hits but 2–3 control FPs** at every tightening
(`He was unsure …`, `So the agent kept the trailing ellipsis…`,
`The report — titled Optimization — covers tuning …`). Class 68 only became
shippable once the anchor was the **site-suffix title shape**
(`[\w\)]\s-\s[A-Z]…em-dash`) ANDed with the space-glued tail — the
`S1 site-suffix+emdash+ell-tails` form: 1 buffer hit, 0/12 controls. **Do not
gate "text ends in an ellipsis"** — that is what a truncated model output looks
like too.

### Also — "check whether an existing helper covers the vocabulary but not the POSITION" (class 68)
`_SERP_TAIL = r"—\s*(?:…|\.\.\.)\s*$"` already existed and still returned the
Haystack row **unchanged**, because it requires the ellipsis DIRECTLY after the
em-dash; here a whole snippet body sits between them and the ellipsis is
space-glued. Same shape of gap as the class-29/40/51 byline family — a new
class, not a duplicate.

### Also — measure the WELD, not the vocabulary (class 69)
`OpenAI-compatible API server` alone = 6 buffer hits but **1 control FP**
(a prose sentence that names the same feature) → topic word, REJECTED. `>=2
labels` alone = 6 hits / 3 ctrl FP / 2 episode hits. `>=3 labels` = 1 ctrl FP.
Only the **welded pair** (two labels, whitespace/colon between them, no verb, no
punctuation) reached 5 hits / 0 FP / 0 le. The docs page lost its line
separators, so its own labels are glued together — that is the discriminator.

### Cleanup + verify (standard shape, all met)
Signature cleanups: **292 → 283 → 283** records, every step `0 unparsable`, CRLF
intact, **49** structural-connection rows preserved (the historical 55 has
drifted to 49 — **re-count, never quote an old number**), learner-gate census
**0** and writer-gate census **0**. 3-copy `md5sum` identical after BOTH apply
passes (`2a418f53…`/`84e9b631…`, then `43497fa3…`/`596bf1a3…`); every module
`exec_module`-verified (the `re` vs `_re` alias trap — `ast.parse` passes).
`pytest tests/scripts/test_internet_learner_gate.py -q` → **85 → 89 → 90 passed**
(5 new tests, each asserting the helper on BOTH gates plus 4–6 prose
counter-cases); `pytest tests/scripts -q` → **245 passed**.
Tests appended as **pure bytes** (`numstat` 88 added / **0 removed**, 24 added /
0 removed; lone-LF census 58 → 58 both times).
Commits `08cce810a`, `43a297707`; branch again
`fix/28-respawn-test-psutil-hermetic`, `merge-base --is-ancestor origin/main HEAD`
→ **FF_SAFE** both rounds → `git push origin HEAD:main`
(`dc18ae902..08cce810a`, `..43a297707`). Verified with `git branch -r --contains
<sha>` → `origin/main` AND `git cat-file blob origin/main:<file> | grep -c
<marker>` → 3/3 each AND the LF-normalized md5 comparison (local == remote blob
after `tr -d '\r'`) — the push exit code alone is not proof.
Post-fix live: 3 learned / 3 rejected across two runs; the last 3 rejections are
honest (`duplicate` at the cap + a documented `GitHub - <owner>/<repo>: …` SERP
shape) with both censuses at **0 of 283**.

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
openamer-repo/.venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py -q   # 56 passed (17.09.26)
openamer-repo/.venv/Scripts/python.exe -m pytest tests/scripts -q                                 # 212 passed
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

## Root cause AS — SIX chrome classes in ONE cron run (58–63), and the "post-fix cycles create the next leak" loop (live 18.09.26)

Cron run began on the documented `cycle_a_technews: rejected` line. Per-day rate
**54.5 %** vs the documented 50–80 % band → **no gate change was warranted for
the rejection itself**; `buffer_junk` last 20 = `duplicate` at the 296–300 cap +
documented `junk` shapes = rotation noise. All six finds came from the prescribed
cheapest method: run `--once`, read the BUFFER TAIL `u`/`a`, repeat after each
fix. **Every single leak was created by a POST-FIX live cycle** — i.e. the buffer
was clean at entry every time and the next two-or-three cycles produced the next
class. Budget accordingly: six classes needed ~20 `--once` runs in one session.

| class | helper | measured |
|---|---|---|
| 58 | `_is_pagination_newsletter_widget` — `Previous Page N of M Next` within 200 chars of `New articles by email` | 1 hit, IS the leak / 0 FP / 0 le |
| 59 | `_is_fullscreen_toggle_chrome` — `Enter fullscreen mode` + `Exit fullscreen mode` space-glued | 1 hit, IS the leak / 0 FP / 0 le |
| 60 | `_is_hashtag_run_after_headline` — >=3 whitespace-adjacent hashtags AND a TitleCase headline (>=4 caps words) before them | 1 hit, IS the leak / 0 FP / 0 le |
| 61 | `_is_dated_tag_strip_chrome` — `\u00b7 #` AND a strip of >=5 tokens with >=3 mixed-case/digit tokens | 2 hits, BOTH the leak / 0 FP / 0 le |
| 62 | `_is_model_listing_run_chrome` — >=2 `Updated <Mon DD, YYYY>` AND a `size \u00b7 Updated` separator | 1 hit, IS the leak / 0 FP / 0 le |
| 63 | `_is_trending_repo_row_chrome` — star counter `\u2605 <N>k +<M>` AND owner/slug AND a language-% stat | 2 hits, BOTH the family / 0 FP / 0 le |

### The single most useful rule from this run: measure the CONJUNCTION, not the phrase
Every class above first failed as a single-literal or single-count candidate.
The repeated shape of the failure:

| class | single-part candidate | why REJECTED |
|---|---|---|
| 58 | `Previous Page N of M Next` OR `New articles by email` alone | bounded AND flagged my own control at whole-text scope; 200-char window fixed it |
| 59 | `Enter fullscreen mode` / `Enter…Exit…mode` generic | 1–3 control FPs |
| 60 | bare hashtag count >=3 / >=4 | **71 then 42 episodes**, 2 then 1 control FPs |
| 61 | `\u00b7 #` separator; then token-count 5/6/7 | 2–3 control FPs at EVERY threshold |
| 62 | repeated `Updated <date>` alone | 2 control FPs |
| 63 | `\u2605 <N>k +<M>` star counter alone | 2 control FPs; `>=2` occurrences still 1 FP |

**So: when a count threshold is 2-FP-clean but you cannot lower it without FPs,
the PATTERN is wrong, not the number.** Add a second structural co-occurrence
(window, adjacency, density, three-way pair) and re-measure. Classes 61 and 63
both went 0-FP only after the *density* / *three-way* form.

### Also — "the buffer is clean" does NOT survive the next cycle
The AP lesson repeats: after every cleanup the census read **0**, and the next
two cycles produced the next class. Re-census after every fix; never conclude the
run is done from an entry-time census.

### Cleanup guards — widen deliberately, and re-derive the drop set
`assert len(drop) == 4` fired correctly on the class-58 pass (1 leak + 2 stubs +
1 root-cause-AG off-topic row). Class 60 needed its own separate pass because I
had applied the gate but not yet deleted the row it caught — **after applying a
gate, immediately delete the matching rows in the same step**, or the next
census reads non-zero and looks like a regression. Class 58/59/60/61/62/63
censuses: 300→296, 298→297, 300→296, 300→296, 297→296, 298→295; every time
`0 unparsable`, lone LF 0, **55** structural-connection rows (the historical 53
has drifted to 55 — re-count, never quote the old number).

### Tests — the pure-byte append again, now the standing routine
Six appends, each `git diff --cached --numstat` showing **0 removed** and the
repo file's lone-LF census **58 → 58** (the laptop copy 0 → 0). Gate-file suite
**76 → 82 passed**; `tests/scripts` **233 → 238 passed**. The test file imports
`buffer_store` lazily inside each test — an appended test MUST `import
buffer_store` itself (root cause AN pitfall, recurred). One class (63) asserts a
list of TWO leaks in a loop plus 8 prose counter-cases, because the leak family
had two shapes.

### Push — six commits, all landed on the same foreign branch
Branch was `fix/28-respawn-test-psutil-hermetic` every time;
`merge-base --is-ancestor origin/main HEAD` → `NO_DIVERGED` each round, so
`git push origin HEAD:main` fast-forwarded cleanly six times
(`e5a6479a9..995fa727e`, `..1c3907827`, `..1f1466297`, `..36709d638`,
`..f44a1c568`). Verify with `git branch -r --contains <sha>` AND
`git cat-file blob origin/main:<file> | grep -c <marker>` — the push exit code
alone is not proof.

### One leak deliberately left un-gated — the model-hallucination repetition
Row 297 (`zero-copy, zero-copy-free, and zero-copy-free`) is a 2B-model
degradation artifact. A repetition detector was measured and **REJECTED**:
`immediate repetition of a long token` flagged 8 buffer rows and **1 real
episode**, and the matches included `announcement Announcement` and
`Communications , Communications` — ordinary editorial prose. **No clean
discriminator exists for "the model broke down mid-generation", so do not gate
it**: remove by signature only. Same call as root cause AG.

## Root cause AT — THREE chrome classes in ONE cron run (64–66), and "the rejection was NOT the regression" again (live 18.09.26)

Cron run began on the documented `cycle_b_papers: rejected` line. Per-day rate
**56.0 %** (28 ok / 22 rej) vs the documented 50–80 % band → **no gate change was
warranted for the rejection itself**; `buffer_junk` last 12 = `duplicate` at the
296–300 cap + documented `junk` shapes (`Self-critique:` echo, SERP `… — <date>`,
`Nuxt HN | News …`) = rotation noise. All three finds came from the prescribed
cheapest method: run `--once`, read the BUFFER TAIL `u`/`a` pairs, repeat after
each fix. All three rows passed BOTH gates and NONE was ever in
`buffer_junk.jsonl`. Buffer was clean at entry in the sense that only 4 stale
pre-gate SERP rows were flagged — re-census after every fix anyway (the AP/AS
lesson: "clean at entry" does not survive the next cycle).

| class | helper | measured |
|---|---|---|
| 64 | `_is_de_portal_fact_box_chrome` — a German portal's own byline label + summary label pair (`\bAutor(?:in)?\s*:\s*[A-Z][A-Za-z]+\b[\s\S]{0,140}?K[üu]rze\s*:`) | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 65 | `_is_prompt_echo_fragment` — the learner's own task template stored as the answer, whole-segment anchored | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 66 | `_is_generated_plan_echo_fragment` — own-artifact title + `+`-list + DANGLING list marker | 5 hits, ALL the leak family / 0 FP / 0 le / 0 lit |

**Class 64 — "check whether the existing helper covers the vocabulary but not the
LANGUAGE".** Three byline helpers already exist (29 `_strip_byline_prefix`, 40
`_is_byline_published_article_header`, 51 `_is_news_byline_share_header`) and all
three are English-keyed (`By <First> <Last>`, `Published`, `Share`). A German
portal's `Autor: <Name> … in Kürze:` pair matches none of them. The discriminator
is the welded PAIR of the portal's OWN two labels; `in Kürze:` alone AND
`Autor: <Name>` alone are both ordinary German prose. Sweep note: the
order-reversed form (`in Kürze: … Autor:`) measured **0 buffer hits** — keep the
orientation that the live page ships, and prefer the tighter variant
(`Autor` + name + `Kürze:` = 0/11 controls) over the looser one
(`in Kürze:` + any of `[Autor|Banff|Alberta]` = 1 control FP, because the control
`Banff Nationalpark in Kurze: ein Park in Alberta.` contains two of the three
alternatives).

**Class 65 — a 41-char fragment: the length trust is NOT the only way chrome gets
in (class-33 precedent, third occurrence).** `Shared underlying pattern one
sentence.` is the instruction the cycle was given, stored as its answer. Why every
existing marker missed it: `_INSTRUCTION_OPENER_RE` is **START-anchored on
imperative verbs** and this is a bare noun-phrase fragment;
`_is_prompt_echo_bullet_chain` (class 42) needs **>=2 bullets**. The surviving
form is the **whole-segment anchor** (`^…pattern…one sentence.?$` with `re.M`).
All non-anchored candidates were REJECTED after measuring: any-context
`shared underlying pattern` + `one sentence` → 1 control FP; bare
`shared underlying pattern one sentence` substring → 1 control FP; `Have you
ever …?` teaser → **2–3 control FPs** (`Have you ever wished you could predict
the future, especially when it comes to your investments?` IS the leak and IS the
shape, so no discriminator exists — removed by signature only, like root cause AG
and the model-hallucination row).

**Class 66 — the leak is the AGENT'S OWN prior output, and it had FIVE copies.**
The `Structural connection between energy efficiency and …` cycles stored their
own deliverable list `KI-Performance-Optimierung: Python-Skript für
RAM/Disk/Cron-Monitoring + Optimierungsvorschläge + Skill + Cron-Job alle 12h` +
newline + `2.` (four German variants, one English). Tell: title-with-colon +
`+`-joined feature list + a **DANGLING** list marker, ending abruptly — the model
enumerated a plan and the extractor kept item 1 plus the marker. **Always group
the flagged rows before designing the marker** (root-cause-AM class-38 rule):
here the group was 5 rows of 2 languages, so the title alternation had to include
both. Threshold/shape sweep that mattered: the bare title alone hit **1 real
`longterm_episodes` row**, the bare dangling marker alone flagged the control
`Our toolchain: script + docs + tests + CI.` + newline + `2.`, and a *generic*
`^<title>: … + …` + dangling-marker form also flagged that same control. Only
adding the own-artifact title **AND** the `+`-join kept it at 0. The leak being
the agent's own prior generation is what makes the site-identity anchor
legitimate here — unlike the "`about scribd` is itself prose" rejection from
class 50.

### Also — the class-66 family was NOT the rejection's cause, and one variant slipped the first cleanup
The German signature removed 4 of the 5 copies; the **English** variant
(`Python script for RAM/Disk/Cron-Monitoring + optimization suggestions …`) had
to be deleted in a second pass. A signature-based cleanup that only lists the
language you just looked at is incomplete — after any cleanup, re-run the writer
census AND look for the same family in the other language.

### Also — always sweep the buffer for stale PRE-GATE leftovers in the same pass
The entry census read 4 flagged rows (idx 4/6/10/19) that were
`GitHub - <owner>/<repo>: …` and `<Title> | <Site> — <desc>` SERP shapes. Those
are gated by `_is_serp_snippet` (class 15, landed **15.09.26**) — the rows
**predate the rule**, which is exactly the AS precedent ("a stale buffer row is
not a new class: grep for a rule added that day; if it exists, delete by
signature, no code change"). The same pass removed them.

Cleanup + verify (standard shape): 297 → 290 → 285 records, every step
`0 unparsable`, lone LF 0, **structural-connection rows 55 → 49** (the historical
count keeps drifting — re-count, never quote an old number), writer-gate census
**4 → 5 → 0** and learner-gate census **0**.
`pytest tests/scripts/test_internet_learner_gate.py -q` → **82 → 85 passed**
(3 new tests, each asserting the helper AND `_is_junk` AND `is_junk` on the leak
plus 5–7 prose counter-cases); `pytest tests/scripts -q` → **241 passed**.
Tests appended as **pure bytes** (75 added / **0 removed**, repo lone-LF census
58 → 58), and the repo test file mirrored to the laptop + openamer-agent test
copies.
Commit `dc18ae902` on the same foreign branch `fix/28-respawn-test-psutil-hermetic`
(`merge-base --is-ancestor origin/main HEAD` → FF_SAFE), pushed `HEAD:main`;
verified with `git branch -r --contains dc18ae902` → `origin/main` **and**
`git cat-file blob origin/main:<file> | grep -c <marker>` → 3/3/3 + 1 for the new
test (the push exit code alone is not proof).
Post-fix live: 3 × `--once` → **3 learned**, all new rows writer-gate clean,
census **0 of 288**.

### Pitfall — the `-c` options must precede the SUBCOMMAND
`git push -c credential.helper= -c credential.helper=store origin HEAD:main`
prints the push `--help` and pushes **nothing** (the `-c` after the subcommand is
parsed as a push option). Correct: `git -c credential.helper= -c
credential.helper=store push origin HEAD:main`. Same reason `git commit -F`
needs the **Windows** path (`C:/Users/.../msg.txt`) while `/c/Users/...` gives
`fatal: could not read log file`.
## Root cause AT — moved to references/
AT (three chrome classes 64-66 in ONE cron run, and "the rejection was NOT
the regression" again) plus the `-c` options-before-subcommand pitfall and
the always-sweep-for-stale-PRE-GATE-leftovers rule are in
`references/root-causes-archive.md`.

## Root cause AV — TWO classes (75, 76) + the "a previous cron left gate work UNCOMMITTED" trap (live 19.09.26)

Cron run began with the documented `cycle_c_github: rejected` line. Per-day rate
**50 % (12 ok / 12 rej)** vs the documented 50–80 % band → **no gate change was
warranted for the rejection itself**; `buffer_junk` last 12 = `duplicate` at the
288/300 cap + documented `junk` shapes = rotation noise.

**THE NEW TRAP — check the repo working tree FIRST.** `git status` showed
`M scripts/training/internet_learner.py`, `M buffer_store.py`,
`M tests/scripts/test_internet_learner_gate.py`, and `git diff` revealed a
**finished class-74 + class-75 fix** (`_is_decorative_alt_text_chrome`,
`_is_bio_page_furniture_pair`) that the PREVIOUS cron run had applied to all
three copies and tested, but **never committed** — the session died after
cleanup. Head said `1508f630b fix(training): gate welded decorative alt-text
chrome (class 74)` while the working tree already carried 75. Consequences:
- The 75 leak row (`Read Full Bio Mary Cunningham …`) was **already deleted from
  the buffer** by that run (it survives only in `online_buffer.jsonl.bak75b`,
  which is how it was recovered for the commit message).
- Only the **laptop** test copy had been synced; the `openamer-agent` test copy
  still carried the old md5 → sync it before pytest.
**So the first step of every run is now `git -C <repo> status --porcelain
scripts/training tests/scripts` + `git diff --stat`** — an unfinished previous
run looks exactly like "nothing to do" from the log, and re-designing a class
that is already in the tree wastes the whole session.

| class | helper | measured |
|---|---|---|
| 75 | `_is_bio_page_furniture_pair` — publisher byline card welded to the lede (`Read Full Bio <Name>` + `Updated on: <date> / <time>` dateline) | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 76 | `_is_tag_counter_run_chrome` — a tag-cloud counter strip, `>=8` `word (n)` pairs with **single-digit** counts, `len <= 400` | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |

**Class 75 — the PAIR is the marker.** `Read Full Bio` alone flagged 2 hostile
controls, a bare `Mon DD, YYYY / H:MM AM` dateline 3. Only the welded pair of the
page's OWN furniture reached 0.

**Class 76 — single-digit counts are the discriminator against real prose.**
Real prose carries 4-digit counts (dates, scores) or `(12)/(8)`-style counts for
list items; the widget prints `tag (2)`, `tag (1)`. Sweep that mattered:
`>=6` pairs → **3 control FPs** (an ablation sentence naming 6 methods with
counts, a score series, a sidebar sentence), `>=8` → 0 of 7 hostile controls,
`>=10` → 0 too but the leak holds **15** so 8 keeps headroom. `len <= 400` and
`len <= 260` were equivalent here; keep the 400 cap.
Note a deliberate harness distinction: a control sentence that **is** the widget
shape (`Tag counts were AI (2), mcp (2), … across the sidebar.`) is asserted as a
**leak** (its own `assert IL._is_tag_counter_run_chrome(...) is True`), never
listed in the false-positive set — the AJ/AN/AQ/AU control-corpus rule again.

**Verify (standard shape, all met):** 3-copy `md5sum` identical for both modules
after the apply (`35c5ba0f…` learner, `a711e236…` store) and after the class-75
commit; every module `exec_module`-verified (the `re` vs `_re` alias trap —
`ast.parse` was already green); `pytest tests/scripts/test_internet_learner_gate.py
-q` → **94 → 95 passed**; `pytest tests/scripts -q` → **251 passed**; test file
appended as **pure bytes** (41 added / **0 removed**, lone-LF census 58 → 58);
buffer census **0 / 0** (learner / writer) at 290 records, **49** structural rows
preserved. Commits `929b4f919` (75) and `d50ec4231` (76) on the foreign branch
`fix/28-respawn-test-psutil-hermetic` (`merge-base --is-ancestor origin/main
HEAD` → FF_SAFE), pushed `HEAD:main`; verified with `git branch -r --contains`
→ `origin/main`, `git cat-file blob origin/main:<file> | grep -c <marker>` →
3/3/1, and the LF-normalized md5 (remote blob == local after `tr -d '\r'`).
Post-fix live: 3 × `--once` → 1 learned (real paper prose) / 2 rejected, both
rejections honest (`duplicate` at the cap + a documented SERP shape), new row
`writer=False extract=False`.

137 (22.09.26): a docs-site breadcrumb welded to a REPEATED title prefix, AND
`_FULL_DATE_RE` (class 35) accepting ABBREVIATED months -- it was wired but had
a blind spot for `Sep 24, 2025`. Also: the per-FILE merge resolution (HEAD vs
origin/main measured, not assumed), and `clean_buffer.py` has NO `--help`
(it just runs). refs/.
**140** (a paper/arXiv AUTHOR LIST with affiliation superscripts -- `cycle_g_security` stored an author block twice; discriminator is the affiliation segment repeated, with a STRUCT-word guard so "Section 3, Figure 2, Table 1, ..." stays learnable; the `_re`/`re` alias fired via `_recompile`, and the guard was red from pre-existing scratch litter) is archived there too.
**141** (a year-welded SERP TITLE restated by its own SNIPPET -- 4 rows of one family in the buffer tail, incl. `Grok Pricing 2026:` and `Claude Opus 5 Review 2026:`. Neither conjunct separates: the year-colon weld alone hits 6 prose controls, a bare repeat hits 201 real episodes + 35 asserted gate literals; the PAIR is 0 FP everywhere. The restatement is an identical price token, an identical `<verb> <n> %` pair, or an identical 4-token run of PLURAL-STEMMED tokens -- a backreference cannot see the NER row's `LLMs`->`LLM` drift. The China-chip row (real article, bare `417%` across different verbs) survives by construction and is the control that decides the rule. The `_re`/`re` alias returned a THIRD time on a new face: alias `re.IGNORECASE` too, not just `re.compile`; and `open(p,'wb',newline='')` is a TypeError that half-applies a patch BEFORE the census assert) is archived there too.
**142** (the SILENT-DROP family: `internet_learner._is_junk()` accepted what `buffer_store.is_junk()` refused -- 368 of 600 audited junk rows; missing detectors `_is_serp_snippet` 222 / `self-critique` marker 109 / `_is_nav_chrome` 88. Fix = `_writer_gate_refuses()` consulted at the write decision in `store()`, audited under the new reason `writer-gate`; plus `active_learn.store_if_trainable()` + `_strip_reasoning_trace()`. PITFALL: never fold the writer into `_is_junk` -- `_clean_insight` depends on the extractor's looser rule, 4 tests regress) is in refs/.
**143/144** (22.09.26: 143 = the silent drops were NOT the rejection rate -- fixing 142 moved the loss from invisible to visible without raising yield; 144 = class 142 shipped as a pure REJECT predicate and over-rejected, 24 of 60 refused rows carry real prose behind the header stack. Fix = `_strip_article_byline_header(region=100)`, applied where `store()` judges the RAW text -- a strip inside `_clean_insight` is UNREACHABLE because `_is_junk(raw)` fires first. `region=200` broke 36/6,128 episodes, `region=100` breaks 0. PITFALL: `write_file` TRUNCATES -- append to this archive with a BINARY `'ab'` write only) is in refs/.
**145** (22.09.26: the spelled-out read-time WELD (`Reading time 5 min`) and the
ORDINAL dateline (`March 6th, 2025`) -- the class-142 vocabulary had neither, so two
rows were STORED; the bare weld is a topic-word trap and was MEASURED-AND-REJECTED,
the ANCHORED form is +2 leaks / 0 FP) is in refs/.

**146** (22.09.26: a SINGLE aggregator feed row -- handle + relative time +
`| N comments` + points + a capitalized second handle + headline. class 37
wants the unit REPEATED, 49 the aggregator's name, 83 an arXiv year tail, so a
one-item row passed both gates; fix = the trailing points/handle pair. Also:
`(?-i:[A-Z])` scoped case-sensitivity -- under IGNORECASE a bare `[A-Z]` token
re-admits lowercase prose. Also: regex NEVER via shell heredoc, and a whole-file
`cp` across diverged trees pulls unrelated work in) is in refs/.
**147** (22.09.26: German consultation/contact chrome -- `Wir beraten Sie
persönlich unter 0681 5866-4466 (Mo-Do 9-18 Uhr)` welded to a nav lockup. The
conjunction of a consultation term and a contact marker within 90 chars on ONE
line; scan forward from EACH match and cut at the newline) is in refs/.
**148** = the learner's OWN bare `Need ...` generation PLAN, stored 12x -- class 142 MIRRORED (here the WRITER was looser than the learner). LESSON: a predicate on only ONE of the two gates is a hole, either direction. Archived in refs/.
**149/150/151** (23.09.26: 149 = the cycle was FINE -- the LIVE tree is a second stale copy, diff it against ~/openamer-repo before any gate fix; traces ONE rejection via a buffer_store._audit spy, 60/70 writer-gate hits are _is_serp_snippet, which the learner has no counterpart for. 150 = a 0-BYTE marker file proves an "install root" in 12 consumers -> _vaultfinal phantom swarm, 781 runs "ok" on 0 tasks; rule: file marker NON-EMPTY, dir marker >=1 NON-EMPTY file. 151 = git push HANGS while ls-remote is fast -> the GCM credential helper, NOT the network:  -> 124; fix , then ls-remote sha == HEAD) in refs/.
**152** (23.09.26: "the live tree is AHEAD of the repo" is NOT "work is unlanded" -- a pairwise diff against ONE checkout is BRANCH NOISE; measure the content UNION over ALL refs: 0 live-only lines, the 143/144 gaps already published on open PR #47, 0 refs shipping the class-143 gate without the `(?-i:)` scope, and the unscoped `[A-Z]` hazard measured at 0 corpus cost) in refs/.
