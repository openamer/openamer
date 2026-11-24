# Pending measured candidates — gate leaks found, NOT yet implemented





A cron cycle can store garbage that BOTH learner gates accept. Do not


half-implement a gate to patch it: a gate is only wired after the FULL 0-FP


control work (hand counter-cases asserted on BOTH gate functions, 3 identical


code copies, tests appended as PURE BYTES, worktree commit off `origin/main`,


push verified with `git cat-file blob`). A half-applied gate leaves uncommitted


learner code in the tree — the AV trap that wastes the next session. So:


record the candidate, leave the tree CLEAN.





## The mirror case — a discriminator that was REJECTED

Not every candidate should be wired. When a marker measures **badly** — a
legitimate hit in the episode corpus, or a token that already appears in the gate
test's own literals — do NOT park it here: parking it invites a future run to wire
it. Record it in `references/measured-and-rejected-discriminators.md` instead
(the mirror ledger).

Already rejected there and not to be re-proposed: **glyph/symbol marks** (`★`,
`✘/✔` — `★` is used legitimately for GitHub star counts) and **bare price
tokens** (`$N/mo` occurs 11× in the gate test's own literals).

Also there: the cron job `internet-learner-247` fires **every 5 minutes**, so
foreign `cycle_*` lines in `internet_learn_log.jsonl` are normal — never attribute
them to your own loop without checking the timestamp.

## Where to record it when the learner skill's archive is not writable





- `internet-learner-stall-fix` is USER-OWNED (autonomous writes refused) and its


  SKILL.md/archive are at their size caps. `patch` on a >100 KB SKILL.md is


  refused, so a new class cannot even get its one-line pointer added.


- **The two archive copies can DIVERGE.** Measured 12.10.26:


  laptop `references/root-causes-archive.md` = 405,022 B vs the


  `openamer-repo` copy = 404,242 B — different md5 even after `tr -d '\r'`.


  Never byte-append to one of a diverged pair; reconcile the union first


  (`git cat-file blob origin/main:<f>` is the only truth).


- **Safe fallback that leaves the tree CLEAN:** write the measured candidate to


  a NON-GIT scratch log inside OPENAMER_HOME — `logs/learner-candidate-classes.md`


  (outside git ⇒ no uncommitted work, nothing for the next session to trip over


  as "unfinished work"). Name the file in the cron report so it is traceable.


- The learner's own diagnose/rate skill (`internet-learner-stall-fix`) still


  owns the deep stall workflow — this file only parks candidates that could not


  be filed there.





## CANDIDATE 2026-10-12 — arXiv paper GPU-memory TABLE row stored as knowledge





- **Trigger line:** `cycle_b_papers: paper-learn: B-Instruct 1 × \times


  A6000-48G BFloat16 ✘ 65.53 GB DFloat11 (Ours) ✔ 45.53 GB D`


- **Page:** arXiv "Lossless LLM compression for efficient GPU inference via


  dynamic-length floating point" (DFloat11).


- **Two buffer rows share the SAME `u`** (a same-`u` dedupe would be WRONG — it


  would delete the real prose row that sits beside the leak).


- **Both gates PASS the leak:** `internet_learner._is_junk(leak) is False`,


  `buffer_store.is_junk(leak) is False`.





### First-pass discriminator measurement





Corpora: `memory/longterm_episodes.jsonl` = 8,401 rows, `scripts/training/online_buffer.jsonl` = 300 rows.





| candidate regex | episode hits | buffer hits |


|---|---|---|


| `\d+\.\d+\s*GB` (unbounded, ≥2) | 3 | 2 |


| `[\u2718\u2714]` (✘/✔ marks) | 6 | 1 |


| `\d+\.\d+\s*GB.{0,60}?\d+\.\d+\s*GB` | **0** | **1** |


| `BFloat16.{0,60}?\d+\.\d+\s*GB` | **0** | **1** |


| `(?:RTX\|A100\|A6000\|H100\|A800\|L40S\|H200\|A10\|V100\|A40)\s*[- ]?\s*\d{1,2}G\b[^\n]{0,80}?\d+\.\d+\s*GB` | **0** | **1** |





The bounded/conjunctive forms are 0-FP on both corpora and hit exactly the one


leak row; the unbounded `GB`×2 and bare ✘/✔ marks are too broad. Standing rule:


**measure the CONJUNCTION, not the phrase.**





## CANDIDATE 2026-10-12 (b) — LinkedIn byline + GitHub project-page chrome stored as knowledge





- **Trigger line:** `cycle_g_security: security-learn: Email LinkedIn Otto Sulin Project Leader GitHub


  Rico Komenda Project Leader GitH`


- **Query `u`:** `Security learning (OWASP Just Dropped an AI Security Testing Guide): What should a safe agent know?`


- **Stored row:** LAST row of `scripts/training/online_buffer.jsonl`, mtime `16:51:39.402` = the


  cycle's own log ts `16:51:39.441` → the accept is REAL (not a false claim); md5 before/after


  not captured this run, mtime + matching `u` is the evidence.


- **`a` (300 chars):** `Email LinkedIn Otto Sulin Project Leader GitHub Rico Komenda Project Leader


  GitHub Russ Memisyazici Project Leader LinkedIn Project Information 💡 Incubator Project


  Classification 📘 Standards License Creative Commons Attribution Share Alike 4.0 International


  Latest Version 1.0 Contributors 51 GitHub`


  → a LinkedIn people-search byline chain welded to a GitHub **project-landing-page sidebar**


  (`Project Information` / Incubator / Classification / Standards / License / Contributors N).


- **Both gates PASS the leak:** `internet_learner._is_junk(leak) is False`,


  `buffer_store.is_junk(leak) is False` (measured 12.10.26).


- **Sibling of the same-day class above and of the `_is_article_byline_chrome` family** — this one


  is NOT caught by the existing byline/org/github chrome gates, because the byline chain is


  separated from the sidebar by other tokens.





### First-pass discriminator measurement





Probe: `logs/_tmp_linkedin_project_chrome_probe.py` (non-git scratch).


Corpora: `memory/longterm_episodes.jsonl` = **8,579** rows (key is `text`, NOT `a`),


`scripts/training/online_buffer.jsonl` = 300 rows, `scripts/training/buffer_junk.jsonl` = 14,091 rows.





| candidate regex | episode hits | buffer hits | junk hits |


|---|---|---|---|


| `(?:Project\s+Leader\|Project\s+Lead).{0,400}?(?:Project\s+Leader\|Project\s+Lead)` | **0** | **1** | 0 |


| `Project\s+Information.{0,200}?Classification` | **0** | **1** | 0 |


| `Contributors?\s+\d+.{0,200}?(?:License\|GitHub)` | **0** | **1** | 0 |


| `Email\s+LinkedIn.{0,300}?LinkedIn` | **0** | **1** | 0 |


| `Incubator.{0,200}?Classification.{0,200}?Standards` | **0** | **1** | 0 |


| `(Classification\|Standards\|License)` ×2 within 400 chars (TOO BROAD) | 0 | **3** | 102 |





All five bounded/conjunctive forms are 0-FP on the 8,579-row episode corpus and hit exactly the


one leak row; the loose 2-of-3 marker form also drops 3 real buffer rows → rejected as too broad.


Standing rule again: **measure the CONJUNCTION, not the phrase.**





### Still required before a gate (why nothing was shipped)





- Hand counter-cases (real prose that names a project leader / contributors + a license) asserted


  on BOTH gate functions; 3 identical code copies; tests appended as PURE BYTES; worktree commit


  off `origin/main`; push verified with `git cat-file blob`. A cron run must NOT half-wire this.


- The `u` is legit — do NOT same-`u` dedupe the whole query.





## CANDIDATE 2026-10-12 (c) — docs "Skip to content" accessibility link welded into a fake technical claim





- **Trigger line:** `cycle_d_docs: doc-learn: vLLM's skip-to-content feature enables


  zero-copy, in-memory content caching for `


- **Recurrence (3 accepts, same class, one day apart at 23:19 and 23:44):**


  `2026-09-18T23:02:17` (`…zero-copy, zero-copy-free, and zero-copy-`),


  `2026-10-12T23:19:25` (`…non-blocking memory access for`),


  `2026-10-12T23:44:35` (`…in-memory content caching for `).


- **Stored row:** LAST row (idx 299) of `scripts/training/online_buffer.jsonl`, keys `{u,a}`:


  - `u` = `Best practice from official docs: vLLM optimization best practices


    limitations and failure modes`


  - `a` = `vLLM's skip-to-content feature enables zero-copy, in-memory content


    caching for chat completions, reducing disk I/O and improving throughput by


    avoiding repeated disk reads during streaming.`


- **Both gates PASS the leak:** `internet_learner._is_junk(leak) is False`,


  `buffer_store.is_junk(leak) is False` (measured 12.10.26).


- **Root:** a docs page's *"Skip to content"* accessibility link is scraped as


  page content; the model then hallucinates a plausible vLLM feature around it.


  Family: page chrome / boilerplate nav text — a *plausible-looking fabrication*,


  the hardest kind to gate by wording alone.





### First-pass discriminator measurement





Probe: `logs/_tmp_skip_to_content_probe.py` (non-git scratch).


Corpora: `memory/longterm_episodes.jsonl` = **8,579** rows (key `text`),


`scripts/training/online_buffer.jsonl` = 300 rows (key `a`),


`scripts/training/buffer_junk.jsonl` = **14,475** rows (key `a`).





| candidate regex | episode hits | buffer hits | junk hits |


|---|---|---|---|


| `skip[- ]?to[- ]?(?:the[- ]?)?content` | **0** | **2** | **0** |


| `skip-to-content.{0,200}?(?:zero-copy\|caching\|throughput)` | **0** | **2** | **0** |


| `feature enables.{0,80}?zero-copy` | **0** | **2** | **0** |


| `zero-copy.{0,60}?(?:reducing disk I/O\|avoiding repeated disk reads)` | **0** | **1** | **0** |





The tight conjunctive form is 0-FP on episodes+junk and hits exactly the one


buffer row; the bare `skip[- ]?to[- ]?content` is also 0-FP but matches 2 buffer


rows (both are this same class). Standing rule again: **measure the CONJUNCTION,


not the phrase.**





### Still required before a gate (why nothing was shipped)





- Hand counter-cases (real prose that legitimately discusses vLLM zero-copy /


  caching *without* a nav-chrome artifact) asserted on BOTH gate functions;


  3 identical code copies; tests appended as PURE BYTES; worktree commit off


  `origin/main`; push verified with `git cat-file blob`. A cron run must NOT


  half-wire this — the tree was left CLEAN.


- The `u` is legit — do NOT same-`u` dedupe the whole query.





## CANDIDATE 2026-10-13 — GitHub FILE-VIEW header chrome welded to real prose (STRIP class)





- **Trigger line:** `cycle_c_github: github-learn: Copy path Top File metadata and


  controls Preview Code Blame 247 lines (192 loc)` (accept logged


  `2026-10-13T10:16:51.396255`).


- **Stored row:** `scripts/training/online_buffer.jsonl` idx **288** (299 records,


  keys `{u,a}`), `len(a) = 300` (clamped):


  - `u` = `What new agent architectures are trending on GitHub?`


  - `a` = `Copy path Top File metadata and controls Preview Code Blame 247 lines


    (192 loc) \u00b7 8.07 KB Raw Copy raw file Download raw file Outline Edit and raw


    actions Anus AI Agent Architecture Overview Anus (Autonomous Networked


    Utility System) is an open-source AI agent framework designed to provide accessibl`


- **Both gates PASS the leak:** `internet_learner._is_junk(leak) is False`,


  `buffer_store.is_junk(leak) is False` (measured 13.10.26, venv python, probe


  `logs/_tmp_github_fileview_chrome_probe.py`).


- **STRIP, not REJECT:** the body after the chrome is real prose; the GitHub


  file-view furniture eats ~86 of the 300-char clamp. Rejecting the row would


  throw away the only stored knowledge.


- **Family:** leading-chrome STRIP family (`references/leading-chrome-strip-family.md`,


  classes 12-15). NOT the project-landing-page sidebar chrome of


  CANDIDATE 2026-10-12 (b) — this is the *file view* header


  (`Copy path` / `File metadata and controls` / `Code` / `Blame` / `N lines (M loc)`


  / `Raw Copy raw file Download raw file` / `Outline Edit and raw actions`).





### First-pass discriminator measurement





Probe: `logs/_tmp_github_fileview_chrome_probe.py` (non-git scratch).


Corpora: `memory/longterm_episodes.jsonl` = **8000** rows (key `text`),


`scripts/training/online_buffer.jsonl` = **299** rows (key `a`),


`scripts/training/buffer_junk.jsonl` = **14869** rows (key `a`).





| candidate regex | episode hits | buffer hits | junk hits | leak |


|---|---|---|---|---|


| `^Copy\s+path\b[\s\S]{0,200}?\bBlame\b` | **0** | **1** | **1** | hit |


| `^Copy\s+path\b[\s\S]{0,200}?\d+\s+lines\s*\(\d+\s+loc\)` | **0** | **1** | **1** | hit |


| `File metadata and controls[\s\S]{0,120}?\b(?:Preview\|Blame\|Raw)\b` | **0** | **1** | **1** | hit |


| `Raw Copy raw file Download raw file` | **0** | **1** | **1** | hit |


| `Outline\b[\s\S]{0,20}?Edit and raw actions` | **0** | **1** | **1** | hit |


| `Download raw file[\s\S]{0,60}?Outline` | **0** | **1** | **1** | hit |


| `\d+\s+lines\s*\(\d+\s+loc\)\s*\u00b7\s*[\d.]+\s*KB` | **0** | **1** | **1** | hit |





All seven bounded forms are 0-FP on the 8000-row episode corpus and hit exactly


the one buffer row. The single **junk** hit is the SAME shape with


`reason: duplicate` — i.e. it was dropped by the *duplicate* gate, not by any


chrome rule, so no existing rule covers this class. A loose token scan


(`Copy path|File metadata and controls|Download raw file`) is also 0 episodes /


1 buffer / 1 junk: the shape is absent from real knowledge.





Standing rule again: **measure the CONJUNCTION, not the phrase.**





### Still required before a gate (why nothing was shipped)





- Hand counter-cases (real prose that legitimately says "Copy path" / names file


  metadata) asserted on BOTH gate functions; 3 identical code copies; tests


  appended as PURE BYTES; worktree commit off `origin/main`; push verified with


  `git cat-file blob`. A cron run must NOT half-wire this — the tree was left CLEAN.


- A STRIP fix must keep the body byte-identical minus the prefix (class 12-15 recipe);


  a blanket chrome marker would gut prose that merely mentions a "Raw" control.


- Do NOT delete buffer row 288; do NOT same-`u` dedupe (the `u` is legit).


- **Measurement-time state:** `online_buffer.jsonl` = **299** records at the probe run; a

  parallel `cycle_d_docs` accept at 11:31:03 took it to the 300-row cap. Row idx 288 is

  unchanged (append-only), so the leak is still live.

## Re-run-safe filing recipe (added 13.10.26)

A cron run may only PARK a candidate. Two habits make parking cheap and re-runnable:

1. **Byte-append, EOL-matched, idempotent** — read the target as bytes, pick the EOL the
   file ALREADY uses (`

` if `count(b'

') > count(b'
') - crlf`), and skip when the
   entry marker is already present. A second run must print `skip`, never append twice.
   Verify after every write: `CRLF=N bareLF=0` (skills tree) or the inverse (`logs/` tree).
   Ready-made and re-runnable — use it instead of retyping a heredoc:
   `python scripts/append_block_eol_safe.py <target-file> <block-file> <marker> [--dry-run]`
   (in this skill; `--dry-run` reports the byte delta without writing).
2. **Assert the doc's own claims** — do not eyeball the probe. Parse its stdout and assert
   the numbers you are about to archive: every candidate row must show `episodes=0`,
   `leak=True`, and both gate lines `= False`, plus the leak row still sitting at its
   documented index. That turns the archive entry into an executable check.
3. **Hoist backslashes OUT of f-strings (Python 3.11).** A verify line written as
   `print(f"... bareLF={new.count(b'\n') - crlf} ...")` dies with
   `SyntaxError: f-string expression part cannot include a backslash` (PEP 701 allows it only
   from 3.12; this install runs 3.11.15). The syntax error itself is not the trap — it fires
   **before** the write, so the append silently never happened and a later read looks like a
   clean no-op. Compute `barelf = new.count(b"\n") - crlf` on its own line first, then print it.
4. **Corollary found while writing habit 1 — a `\r\n` escape inside a Python string is a real
   CR+LF, not the two characters you meant to document.** Habit 1's detection expression got
   mangled exactly that way in this file. The expression, in terms that survive a string
   literal, is:

   ```python
   crlf = raw.count(b"\r\n")
   eol = b"\r\n" if crlf > raw.count(b"\n") - crlf else b"\n"
   ```

   When the prose must SHOW `\r\n`, write it as `\\r\\n` in the Python source (or keep it out of
   the f-string/escape context entirely). This is the same family as habit 3: the escape is
   resolved by the interpreter before the text ever reaches the file.

## CANDIDATE 2026-10-13 (b) -- class 160/AG leak still live in the training buffer

Measured in this cron run (2026-10-13 ~11:50, one internet_learner --once cycle):

- `online_buffer.jsonl` idx **251 / 300** carries an off-topic row under a SECURITY query:
  - `u`: "Security learning (Prompt engineering is collapsing - GPT-5 just proved it): What should a ..."
  - `a`: "With average text-to-image prompt prices collapsing to $1.99-$4.99 and a 20% commission fee, sellers net just $3.19 on a $3.99 sale-failing to compensate for hours of iterative testing."
- The page is storefront economics, not security. This is the class-160/AG signature already noted as "partially fixed, NOT closed" (topic tokens diluted by generic words let an off-topic page pass the primary extractor).
- This run's own cycles did NOT add it: `cycle_g_security` and `cycle_h_efficiency` were both rejected by the gates (`buffer_junk.jsonl` reasons `duplicate` / `writer-gate` -- the security candidate was this same off-topic sentence seen again, the efficiency candidate was YouTube podcast chrome). So the gates held for the new fetch; the leak is the pre-existing buffer row.
- No gate change made here: the counter-case measurement + test coverage for a new rule belongs to a dedicated session (class 160/AG reference work), not to a cron pass.

## CANDIDATE 2026-10-14 (b) -- geospatial vendor blurb, stored by cycle_a_technews

Measured 2026-10-14 16:03 in this cron run (two `--once` cycles, neither stored anything:
`cycle_b_papers` = `no insight`, `cycle_c_github` = `rejected, not trained`; buffer md5
`531c5c955aa3a3c2a919d2e57cceaeea` unchanged before/after).

- The row was stored EARLIER today (15:46:21, `cycle_a_technews`), NOT by this run. It is the
  LAST row of `online_buffer.jsonl`:
  - `a`: "The system geolocated over 200,000 individual palm trees and calculated precise
    greenery surface area estimates (in m2), providing executive-ready data for national
    policy and environmental planning." (199 chars)
- Shape: vendor/product copy -- third-person product voice plus a sales close
  ("providing executive-ready data for national policy"). The subject is genuine geospatial
  AI, so relevance/topic matching is NOT the discriminator; the page's own PROMOTIONAL VOICE
  is (same family as class 22 course CTA and class 31 meta blurb).
- It clears both gates the usual way: >=90 chars with a real technical keyword, so the
  "long prose is trusted" rule never looks closer. No 0-FP discriminator measured yet.
- NOT gated here: a counter-case measurement + test coverage belongs to a dedicated session,
  not to a cron pass (a half-applied gate unattended is the AV trap). Class number left
  UNASSIGNED -- grep the skill for the page/phrase before citing one.

## CANDIDATE 2026-10-16 -- LLM scratch/meta fragments from active_learn's UNGUARDED actions

Measured in a cron run (one `internet_learner --once` cycle). **The cycle itself was a clean
rotation-noise rejection** (`cycle_g_security: rejected, not trained (shallow + deep read both
gated)`, 97s; per-source rates 38-63% = the documented post-13.09 band, `buffer_junk` last 60 =
47 `duplicate` / 9 `writer-gate` / 4 `junk`). The find came from the **BUFFER TAIL**, not from a
rejection -- the prescribed cheapest method, again.

- **ATTRIBUTE BEFORE YOU BLAME.** A buffer row carries ONLY `{u, a}` -- the writer is NOT in the
  row. Grep the `u` TEMPLATE back into the modules (`grep -rl "<u text>" scripts/training/`)
  before naming a culprit. This run matched the learner's mandate yet **every** fragment belonged
  to `active_learn.py`, not to `internet_learner`. Do not file a leak against the module you
  happened to be running.
- **13 / 300 rows (4.3%)** are the 2B model's thinking-out-loud, at indices **5...293** =>
  persistent, not a one-run artifact:
  - `Maybe discuss impossibility?`
  - `Could mention empirical studies: distributed training failures at scale (Meta, Google, Mic`
  - `We can say no single property; safety is multi-layered.`
  - `They give two situations: / 1.`
  - `Could structure: What is memory consolidation?`
- Both learner gates PASS them (`_is_junk` False, `_is_nav_chrome` False) -- but they are not
  learner rows. Writer-gate census `_is_nav_chrome` = **0 / 300** at entry (clean by the current
  gate, which is exactly why the tail has to be read by eye).
- **ROOT (durable code fact):** `active_learn.py` has a substance floor in **ONE** action only --
  `cross_connect()` (~L311, `len(_ins) < 25` + `_ECHO_OPENER_RE` / `_ECHO_TAIL_RE` /
  `_ECHO_TEMPLATE_RE`). `self_test`, `world_explore` and `skill_challenge` buffer the raw LLM
  answer through `store_if_trainable()` with **no floor at all**.

### First-pass discriminator measurement

Probe: non-git scratch, training-venv python. Corpora: `scripts/training/online_buffer.jsonl` =
300 rows (key `a`); `memory/**/*.jsonl` = **76,684** texts (keys `text|a|content|summary`).

| candidate regex | buffer hits | text FP | hand-control FP |
|---|---|---|---|
| opener-only `^\s*(?:maybe\|we can\|we could\|could\|also maybe\|they ask\|they give\|let's\|i would\|might\|perhaps)\b` | 17 | 2 | **4/4** -> REJECTED |
| meta-verb form below | **13** | **0** | 2 (same-family, correct) |

```
^\s*(?:also\s+|and\s+|or\s+)?(?:maybe|perhaps|we can|we could|could|might|they ask|they give)\s+
(?:mention|discuss|include|structure|frame|note|add|list|consider|say|explain|elaborate|cover)\b
```

The opener ALONE dies on real prose -- `We can reduce inference latency by batching requests
across the fleet.` is a legitimate technical claim and it trips the bare form. The 2 "control FPs"
of the meta-verb form are `We could mention this in the release notes later.` / `Maybe mention the
caveat in the docs when writing the guide.` -- both are **meta-writing-advice of the same family**,
so flagging them is correct behaviour, not a false positive. Standing rule again:
**measure the CONJUNCTION, not the phrase.**

- Escapees (2 rows the meta-verb form does NOT catch): `They give two situations: / 1.` and
  `They ask "Find structural connection...`. Bare `they give` / `they ask` are legit declaratives
  (`They give the model a prompt.`), so no bare marker -- it would need the continuation.

### Still required before a gate (why nothing was shipped)

- Put the guard where the defect IS: mirror `cross_connect`'s floor in `self_test` /
  `world_explore` / `skill_challenge` (per-action guard = far lower blast radius than the shared
  writer gate, which would also cover the learner and every other producer).
- Hand counter-cases asserted on the guard; 3 identical code copies; tests appended as PURE
  BYTES; worktree commit off `origin/main`; push verified with `git cat-file blob`.
- A cron run must NOT half-wire this (AV trap). Tree left CLEAN: `git status --porcelain
  scripts/training tests/scripts` and `git diff --stat` both empty, scratch probes deleted,
  verified before AND after.
