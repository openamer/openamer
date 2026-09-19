# internet-learner-stall-fix — archived root causes (15./16.09.26)

## Root causes (all three were live on 14.09.2026)
**A. Static seed lists saturate.** Each cycle drew `random.choice(_rotate(seeds))`
from ~3 fixed seeds × 8 angles. Once every (seed, angle) pair was learned the
exact-duplicate gate rejected every later cycle forever.
→ Fix: `_novel_query(domain_kw, seeds)` — pulls a REAL current HN headline via
HN Algolia (`https://hn.algolia.com/api/v1/search?query=..&tags=story&numericFilters=points%3E10`),
falls back to an LLM-synthesised query, then to `_rotate`. Novel by construction.

**B. `store()` false-negative at buffer cap.** `store()` returned `after > before`
on line count. At cap, `buffer_store.enforce_cap` trims the buffer back to
MAX_BUF, so a SUCCESSFUL append leaves the count unchanged → status reported as
"rejected" while rows actually rotated.
→ Fix: success = record present now AND absent before
(`buffer_store._is_duplicate(rec, buf)`), never a count comparison.

**C. Deep extractor takes the FIRST sentence-shaped string.** On most pages that
is nav/menu chrome ("Blog - Neutree Projects ▾ ... project updates."), which
passed the `>=90 chars` length-trust in `_clean_insight` and got stored.
→ Fix: `_is_nav_list(t)` (>=6 TitleCase tokens, no comma/semicolon) + score ALL
candidate sentences in `deep_learn` and pick the best, requiring a verb
(`_VERB_RE`) or a tech hint (`_TECH_HINT_RE`).

## Wasted cycles after the big fix (~1 in 2, live 15.09.26)
Partial stalls remain even with `_novel_query` wired into every cycle. Two more:
**D. `_fresh_headline` falls back to Show/Ask HN posts.** The old loop ran
`for want_article in (True, False)`, so when no article-grade hit existed it
returned e.g. "Show HN: A murder mystery game built on an open-source gen-AI
agent framework" — a product landing page whose deep read is ad copy → gated.
→ Fix: single pass, skip `_SELF` prefixes, `return ""` (falls through to the
LLM-synthesised query, which yields a narrow term like "python openai agent
framework").
**E. `deep_learn` k=2 finds no qualifying sentence.** Page had no verb/tech-hint
sentence → both gates unsatisfied → cycle wasted.
→ Fix: in `store_or_deep`, second pass `deep_learn(query, k=6)` before giving up.
Measured on 9 consecutive `--once` cycles after the change: 7/9 learned (pre-fix
baseline was ~1 in 2). Cost: a failing cycle that the retry rescues takes 40–160s
instead of ~30s — acceptable for a 10-minute cron, do not lower k.

**F. LLM-synthesised `module:attr` queries hit stdlib doc TOC (live 15.09.26).**
When `_novel_query` falls through to the LLM-synth path it can emit a
`python:inspect.getsourcefile`-style term. The deep read then returns the
Python-stdlib docs *table of contents* ("Unix Specific Services 37 Mac OS X
specific services … api » inspect »"), every candidate is nav junk, all gates
fail → `cycle_e_competitors` / `cycle_c_github` rejected repeatedly.
→ This is CORRECT gating, not a bug: there is no insight on that page. Do NOT
loosen `_is_junk`. The real fix is a better synth-query prompt (ask for a
narrow *topic phrase*, ban `module:attr` / `pkg:func` shapes); treat as a
low-priority improvement, the cycle simply rotates to the next source.
Known today: `cycle_c_github` and `cycle_e_competitors` are the two weakest
sources; `cycle_a_technews`, `cycle_b_papers`, `cycle_d_docs`,
`cycle_g_security`, `cycle_h_efficiency` carry the learning rate.

**G. HN page-1 exhaustion (live 15.09.26, second regression).** `_fresh_headline`
read ONLY Algolia page 0 (`points>10&hitsPerPage=12`). Once those 12 titles sat in
`.il_seen_queries` the function returned `""` for EVERY keyword, so every cycle
fell through to the LLM path. Detect in one second:
`python -c "import importlib.util;...;print(m._fresh_headline('AI agent news', m._recent_queries()))"`
→ `''` for all keywords while `curl hn.algolia.com` still works = this bug.
→ Fix: rotate 4 pages × 2 thresholds (`points>10`, then `points>3`), i.e. top ~96
hits instead of 12 (commit `5d09f5b04`). Measured 1/7 → 4/7 keywords yield a
live headline.

**H. Local 2B synth query degenerates (live 15.09.26, same regression).**
`_llm_novel_query` posts to `:8081`, and `mini-openamer` answers with
(a) a phrase loop — `"vLLM v2.12.0 kv_cache_prefill_prefetch"` ×20 = 300+ chars,
so `8 <= len(q) <= 120` rejected it, or (b) ONE glued token —
`python:openai:chat-history-search-history-search-…` (79 chars, passes the guard,
then lands on a stdlib-docs TOC = root cause F). When both G and H are live the
learner always falls back to the saturated static seeds → 4/4 rejects.
→ Fix: `_collapse_repeats()` (word-level loop cut + char-level ≥6-char period
repeated ≥3× at any offset, guarded to `len(t.split()) <= 3` so normal prose such
as `arxiv meta-learning LLM agents` is never touched), a `q.rstrip(" -_.,:")`, and
a ban on `module:attr` shapes (`q.count(":") >= 2 or re.search(r"[\w.]+:[\w.]+:", q)`).
Never loosen the length guard itself.
Verify after ANY change here: 4 × `--once` → expect ≥3 learned (pre-fix 0/4, post-fix 3/4).

## Not a stall: the learner CRASHES on a stale `OPENAMER_HOME` (live 15.09.26)
Symptom is different from everything above — no log line at all, just a traceback:
`FileNotFoundError: ...\Temp\repo-ac-test2\home\scripts\training\.il_rotation`.
The desktop/cron env exports `OPENAMER_HOME` pointing at a throwaway test dir
(`%TEMP%/repo-ac-test2/home`) where `scripts/training` does not exist, and line 21
built `T` straight from it → **every** run (cron = every 5 min) died before doing
anything, silently, for as long as that env lived.
→ Fix (commit `ea6768318`): `_training_dir()` — a *valid* env override
(`isdir(env/scripts/training)`) wins, else `~/AppData/Local/openamer-laptop/scripts/training`,
else `Path(__file__).parent`. Verified by re-running `--once` **with the bad env
still set** (must succeed) — that is the whole test, it needs no env surgery.
Do not "fix" it by editing the cron prompt: any other script reading
`OPENAMER_HOME` would still break, and the env is set by the harness, not the job.
Quick check of whether the env is poisoned: `echo "$OPENAMER_HOME"` in a terminal.

**`internet_learner._is_junk` is NOT `buffer_store.is_junk`.** The learner module
has its own `_is_junk` (`_JUNK_RE`) that filters *search results*; the writer's
gate — where every SERP/nav tightening actually lives — is `buffer_store`. A test
written against `IL._is_junk` looks right and fails with a mystifying
`assert False`. Always assert `buffer_store.is_junk(...)` in the gate tests.

**Fourth SERP shape: `<title> | <site> — <snippet>` (no ellipsis).** Stored live
by `cycle_c_github` (`Fable Studio Review | TheAISelect — …`); `_SERP_ELL_DASH`
requires the `…` so it never fired. Fix (same commit): `_SERP_PIPE_DASH =
_compile(r"\|[^|]{1,40}\s—\s")` + a `return True` branch. Measured on the live
300-row buffer: **13 hits, all chrome, 0 real prose**; buffer junk count 14→26.
Beware when measuring: building the probe string as `u + " || " + a` injects pipes
and inflates the hit count (~34) — always test the `a` field alone.

**Single-em-dash `Title — snippet` rows are deliberately NOT gated (15.09.26).**
`cycle_d_docs` / `cycle_f_multi_domain` store e.g. `Optimization and Tuning - vLLM
— Chunked prefill allows vLLM to process …`; the body is genuine technical text
with only a title prefix. Measured 5 such rows, all carrying real content → left
alone. Do NOT reach for `text.count(" — ") >= 2`: that flags **78/300** rows,
mostly legitimate prose. It is not a signal.

**I. Topic-mismatch: right gates, WRONG page (live 15.09.2026).** `cycle_a_technews`
stored row `u="Internet learning (OpenAI and four rivals just agreed on one standard
for AI agents): What should an AI agent know?"` / `a="Southbound 4 Train at
Manhattan's Spring Street Station A 24-year-old woman and a man in his 20s were
killed…"` — a genuine news *lede*, so `_is_nav_list`/`_is_junk`/verb gate all pass,
but it is from an unrelated front page (the deep read fetched the wrong URL / a news
homepage). 7 of the last 8 rows were on-topic, so this is ~1/8, not systemic.
There is NO cheap text-shape gate for it — do NOT try to regex "news-ness"; you
would kill real learnings. Detection is by *content inspection only*: sample the
last ~8 rows (`recs[-8:]`, read `u`/`a`) and look for an `a` whose subject is
off-topic vs its `u`. Keep as a low-priority note; the buffer is a 300-row rolling
cap so one stale row ages out. If it becomes >2/8, revisit the deep-read URL
selection in `deep_learn` (it appears to accept any sentence-shaped string from a
page reached via a generic search URL) — that, not the gates, is the fix point.

## Root cause N — blog-post header chrome (live 15.09.26)
`cycle_c_github` stored `August 5, 2026 · 15 min Read article Guides What is MCP
(Model Context Protocol)?` — pure page meta (date + reading time + `Read
article`), zero prose, and BOTH gates passed it (`is_junk=False`,
`_is_serp_snippet=False`).
→ Fix (commit `c3400a54b`): `"min read article"` added to
`buffer_store._NAV_CHROME` (data-only). Measured over the live 300-row buffer:
1 hit, 0 real-prose rows carry it. Patching the loose `"min read"` variant was
deliberately REJECTED — measured 4 hits and 2 of them (`Updated: September 7,
2026 15 min read As enterprises rapidly deploy LLMs …`) have real prose after
the prefix; the tight `"min read article"` tail fires only on the header-only
shape.
Bad row removed after gating (flagged set 25 → 24, buffer 300 → 299 rows).
Verify: `is_junk(bad)==True` on the exact string, `False` on 3 real prose
samples, `10 passed` in `tests/scripts/test_internet_learner_gate.py`.

## Root cause O — GitHub releases-page chrome (live 15.09.26)
`cycle_f_multi_domain` stored `No results found View all tags openai-sdks released
this 14 Sep 23:28 v3.` — pure releases-page meta, no prose, both gates passed it
(`released this <date>` even satisfied the technical-signal gate).
→ Fix (commit `5abfc69f3`): `"view all tags"` in `buffer_store._NAV_CHROME` +
`r"view all tags|released this \d|"` in `internet_learner._JUNK_RE` (reject at
extraction so the cycle retries instead of burning a 30–160 s read).
Measured on the live 300-row buffer: 1 hit, 0 real-prose rows carry it.

## Root cause P — binary noise only gated on the CYCLE path (live 15.09.26)
Row `Latest research insight: Adaptive LLM routing under budget constraints` /
`a=T\ufffdp\ufffd%\ufffd…` (raw PDF bytes mis-decoded). The extraction gate
`internet_learner._looks_binary` covers only `internet_learner`; **every other
writer** (`active_learn`, `online_learning.collect_new`) reached the buffer
unguarded, so the mojibake trained as a research insight.
→ Fix (same commit): `buffer_store._CTRL_NOISE = [_re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd]")]`,
`_is_binary_noise()` = ratio `> 0.08` for text `>= 20` chars, wired into
`is_junk` as a structural check (before `_is_nav_chrome`).
Do NOT count CJK as noise — a naive "non-ASCII ratio" flags **4** live rows of
legit Chinese/Japanese content (0.18–0.83). Control chars + U+FFFD only: the
live mojibake row scores **0.576**, the next highest real row **0.000**.

## Root causes Q/R/S — three chrome leaks found in ONE session (live 16.09.26)
Commit `5acfa6e5d`. Four rows had reached the 300-row buffer through BOTH gates.
Measured with the standard "1 hit, 0 real-prose rows" method before touching
anything; all are DATA-ONLY additions to `buffer_store._NAV_CHROME` +
`internet_learner._JUNK_RE`, no gate logic changed.

| cycle | shape | marker (lowest common) |
|---|---|---|
| `cycle_d_docs` | raw MediaWiki film-box wikitext | `"wt":"` |
| `cycle_c_github` | GitHub pricing-table copy | `billed annually` |
| `cycle_g_security` | AI-chat feature list | `let chat calculate`, `hand off real-world tasks`, `ai chat can make mistakes` |
| `cycle_f_multi_domain` | review-site header + nav | `products considered`, regex `based on [\d,]{4,} reviews` |

Pitfalls learned here, in order of how much time they cost:
- **Add the marker to BOTH files.** The first pass put `billed annually` only in
  `_JUNK_RE`; verification caught `writer=False extract=True` — the leak would
  still land via `active_learn` / `online_learning`. Always re-run the two-gate
  assertion table after the edit, never trust one file.
- **Do NOT "empty the flagged set" when cleaning up.** `is_junk(bad_string)` on
  the *full* buffer returns 14 historical baseline rows that are deliberately
  left alone (documented). Filtering on `is_junk(r["a"])` dropped all 16 and
  silently deleted the baseline. Filter on a **signature** of the row you are
  removing (`any(s in a for s in SIGS)` AND `is_junk(a)`), keep a `.bak`, and
  assert `flagged == baseline` afterwards — 18 → 14, not → 0.
- **`sed`/`read_file` hide the escapes.** The `_JUNK_RE` rule ends
  `r"(?:\b\d{1,3} ){6,}\s*next\b)",` and the next line is
  `re.IGNORECASE)` — the insertion must NOT close the `re.compile(` call. A
  hand-typed-bytes anchor silently failed twice (`assert n == 1` on a
  `\\\\b`-vs-`\\b` mismatch); build the anchor **from the file** via an ASCII
  predicate (`startswith(b'    r"(?:') and b"next" in l`), append `|"`, and let
  the existing `re.IGNORECASE)` close it. Then `ast.parse` proves you got it.
- Two of the four leaks (`S` shape) appeared in cycles run *minutes* after the
  buffer was cleaned — expect the tail to re-poison while you work, and re-verify
  `flagged` between cycles instead of assuming your earlier pass was final.

## Root cause U — the CDP search path STARVES at every k (live 16.09.26)

Symptom: success rate slid 83.7% (all-time, n=1516) → 55% (last 20) → 40%
(last 10). Rejections rotate across ALL cycles, not one weak source, and the
junk reason is the documented SERP shape — so no single gate change explains it.

Cause: `_search_urls` is CDP-first (`PRIMARY: via the CDP browser`) and returned
early on `if good:`. Bing's *rendered DOM* shows **truncated result paths**
(`https://cybersecuritynews.com/ai-coding-agent-deletes`, `independent.co.uk/tech`)
and the `"…" in u` guard correctly skips them — so the browser path yields far
fewer than `k` fetchable URLs. Measured over 6 fixed queries:

| path | k=2 | k=6 |
|---|---|---|
| CDP (DOM regex) | 11/36 | 20/36 |
| HTTP (ck/a decode) | — | **36/36** |

`independent.co.uk/tech` is a *section* page and `arxiv.org/pdf` has no path —
both fetch 6000 chars of chrome, i.e. the cycle burns a full deep read and then
both gates correctly reject. Crucially the documented k=6 second chance
(`store_or_deep`) could **not** compensate: it calls the SAME `_search_urls`,
which returned **2** URLs for `AI coding agent news` even at k=6.

→ Fix (commit `097790a95`): extract the HTTP path into `_http_search_urls(q, k)`
and TOP UP instead of returning early:
```python
good = _usable_urls(urls, k)
if len(good) >= k:
    return good
merged = list(good)
for u in _http_search_urls(q, k):
    if u not in merged:
        merged.append(u)
if merged:
    return merged[:k]
```
Keep the `"…"` skip — the truncation is real, the HTTP path is the fix, not a
looser URL regex. Measured after: **36/36 at k=6** (was 20/36).

Verify in one shot (no buffer writes):
```python
for q in [...6 queries...]:
    print(len(m._search_urls(q, k=6)))   # must be 6,6,6,6,6,6
```
Honest effect note: the CYCLE-level gain is directional, not yet proven —
post-fix 3/6 learned vs 2/6 in the immediately preceding 6, n far too small to
claim a restored 83%. The URL-count measurement (20/36 → 36/36) is the hard
evidence; re-measure the rate after ~30 cycles before calling it closed.

## Root cause V — the k=6 retry is DEAD CODE (live 16.09.26)

Symptom identical to U's tail: rate slid to **50% (last 20)** with rejects
rotating across ALL cycles and reason = `junk`. Root cause U's fix was already
in place and verified (`_search_urls(k=6)` → 6/6 URLs), yet the cycle still
rejected — so the starvation was NOT in the URL count.

Cause: `deep_learn` built its distillation input with
`combined = " ".join(texts)[:4000]`, while `_fetch_page` truncates each page to
**6000** chars. The FIRST page therefore ate the whole 4000-char window and
pages 1..k-1 contributed **0 characters**. Measured on the live VPTQ query:

| page | chars | contributed to the 4000-char window |
|---|---|---|
| [0] github.com/microsoft/VPTQ | 6000 | **4000** |
| [1] arxiv abs/2409.17066 | 5426 | **0** |
| [2] aclanthology | 6000 | **0** |
| [3] arxiv pdf | 6000 | **0** |
| [4] arxiv/pdf/…v1 | 6000 | **0** |

So `deep_learn(k=2)` and `deep_learn(k=6)` returned the **byte-identical**
string, and `store_or_deep`'s guard `if deep2 and deep2 not in (insight, deep)`
skipped the k=6 second chance **on exactly the cycles it exists to rescue**.
k=6 burned ~140 s fetching 5 pages and changed nothing. 2 of 4 sampled rejects
were this. Any earlier "the k=6 retry rescues E" claim was never true in
practice whenever page[0] alone filled the window.

→ Fix (commit `ffc2331a2`): `_fair_share_window(texts, budget=4000, floor=700)`
gives EVERY page an equal slice, then `" ".join(_fair_share_window(texts, 4000))`.
Also skip raw `%PDF` pages at fetch time (`not t.lstrip().startswith("%PDF")`)
so they cannot occupy a fair-share slot or leak mojibake (root cause P).

Verified, in this order (the order matters — the first two are cheap):
```python
m._fair_share_window(["A"*6000,"B"*5400,"C"*6000,"D"*6000,"E"*6000], 4000)
#   -> 5 slices, total 4000, page letters ABCDE  (OLD: only 'A')
m.deep_learn(Q, k=2) != m.deep_learn(Q, k=6)     # must be True now
```
Measured live: `--once` 3/3 learned, then 2/4, then **last 8 = 75% / last 12 =
83%** (pre-fix last 20 = 50%; all-time 84.8%). Reject reasons were `duplicate`
(8, buffer near the 300 cap = normal rotation) and `junk` (12, no new shape).
Do NOT read `deep2 not in (insight, deep)` as a bug guard — it is correct; the
bug was that `deep2` was never actually different.

**Measuring pitfall that cost time here:** `_fetch_page` defaults to
`max_chars=6000` and `deep_learn` *uses* that default. A probe that fetches at
3000 chars and then asks `buffer_store.is_junk(whole_page)` measures the
navigation HEAD, not the sentence production sees — it reported "all pages
junk" and nearly sent me chasing a non-existent gate false-positive. Probe at
**6000** and gate the *extracted sentence*, never the whole page.

Also: a diagnostic `m.store("PROBE user_text", text)` **writes a real row** into
`online_buffer.jsonl`. Remove it afterwards (filter on the `u` field, keep CRLF,
re-assert `unparsable == 0`) — a probe row is indistinguishable from a learning
to the trainer.

## Root cause Z — HN listing chrome + Wikipedia infobox chain (live 16.09.26)

Two shapes reached the 300-row buffer through BOTH gates in one session.
Commit `9bde078f3`.

| cycle | shape | markers added |
|---|---|---|
| `cycle_f_multi_domain` | HN front-page listing chrome: `by alepeak visit website #14 Launch HN: April (YC S25) – Voice AI to manage your email and calendar 98 points · 95 comments · Aug 25, 2025 · by nehasuresh1904 visit website #15 Launch HN: Twill.` | `visit website`, `points by `, `points ·`, `comments ·` |
| `cycle_g_security` | Wikipedia infobox label chain: `Model Context Protocol Developed by Anthropic Introduced November 25, 2024 ; 21 months ago ( 2024-11-25 ) Industry Artificial intelligence Connector type TypeScript Python Java Kotlin C# Go PHP Perl Ruby Rust Swift` | `connector type`, ` months ago (` |

Why both cleared both gates: the HN row is >90 chars **and** contains digits,
so the length trust plus the technical-signal gate both fired; the infobox row
is a bare label chain **with no comma**, so `_is_nav_list` (which wants ≥6
TitleCase tokens AND no comma) never matched. Same structural hole as the CNBC
header (root cause X).

Data-only additions to `buffer_store._NAV_CHROME` **and**
`internet_learner._JUNK_RE` (the Q/R/S both-files pitfall). Measured on the live
buffer before touching anything: **1–2 hits each, 0 real-prose FPs** on a
12-sentence hand-written prose set.

**Bank T&C rows were deliberately left UNGATED.** A third leak in the same run
(`cycle_h_efficiency`: `Customers with a Wells Fargo consumer account can send
up to $3,500 in a rolling 24-hour period and up to $20,000 in a rolling 30-day
period.`) looked like the easiest fix of the three — and every candidate marker
failed the FP test: `consumer account` hit **1**, `checking account` **1**,
`savings account` **1** hand-written real-prose sentence. Those are *topic*
words (`A consumer account typically earns interest while a checking account
does not…`), not chrome, exactly like `nachrichtendienst` in root cause Y. The
correct verdict is **leave it**: one stale row ages out of a 300-row rolling
cap, whereas the marker would silently drop a whole topic class. If it recurs
>2/8, fix the deep-read URL selection, not the gate.

Verified: 3 leaked strings → `writer=True extract=True`; 4 prose samples →
`writer=False extract=False`; census **14 baseline + 3 leaks = 17**, then back
to **14** after removing the 3 pre-gate rows (290 → 287, 0 unparsable);
`pytest tests/scripts/test_internet_learner_gate.py` → **31 passed** (new
`test_hn_listing_and_wikipedia_infobox_chrome_is_gated_on_both_paths` asserts
both paths *and* the prose counter-cases — a one-directional test passes a
broken marker).

### Fifth shape in the same session — product-page header (commit `f13340075`)
`cycle_e_competitors` stored a Frontierbeat product-page header verbatim:
`July 30, 2026 2 min read Explore the desk Every Frontierbeat desk, organized
Artificial Intelligence AI reporting, policy, models, and market structure.`
152 chars → cleared the `>=90` length trust, and the digits (`30`, `2026`)
satisfied the technical-signal gate. The documented `"min read article"` marker
does not fire (no `article` token here), and the bare `/ N min read` variant is
deliberately ungated because it prefixes real prose elsewhere.

Markers: `every frontierbeat desk`, `min read explore` — both tight tails of
the header shape. **Rejected candidates** (each hit real hand-written prose, so
0-FP rule kills them): `explore the desk`, `organized art`, bare `min read`.

### Two mechanical traps that cost the most time here
- **Do NOT append a new `r"..."` line before `re.IGNORECASE)` in `_JUNK_RE` when
  the preceding fragment already ends with `,`.** That produced
  `TypeError: compile() takes from 1 to 2 positional arguments but 3 were
  given` — the fragment landed *after* the comma, as a third positional arg.
  The last fragment must have **no** trailing comma (it is the one the
  `re.IGNORECASE)` closes); append the marker into the *preceding* fragment
  (e.g. `r"auf duden online|"` → `r"auf duden online|visit website|…"`) and
  leave the comma placement alone.
- **Escape the markers with `re.escape` before splicing them into `_JUNK_RE`.**
  The literal `" months ago ("` left an unbalanced group and blew up with
  `re.error` at *import* time. `buffer_store._NAV_CHROME` takes plain
  substrings (no escaping) because it is a tuple, not a regex — the two files
  need different treatment for the same marker list.
- Find the tuple's/compile's closing line with **`ast`** (`node.end_lineno`),
  never by counting parens: `re.compile(\n  r"...("\n)` has parens inside its
  own argument strings, so a naive depth counter terminates on the wrong line
  and `assert L[ci]` fails on a comment.

## Root cause AD — prompt-echo FOURTH shape: the marker at the END of a stub (live 16.09.26)

Found by running `--once` and reading the buffer tail (no new instrumentation).
`active_learn.cross_connect` buffered **three** of its own prompt fragments as
"structural connection" answers (commit `a4ceb5640`):

| row | text | length |
|---|---|---|
| A | `User asks: "Find the structural connection between these two situations:  1.` | 74 (truncated) |
| B | `Shared underlying pattern?` | 26 — clears the 25-char producer floor by ONE char |
| C | `Continuous Learning Loop: Fehler-Capture + … + Trend\n\nWhat is the shared underlying pattern?` | 122 |

**Why both existing echo rules missed all three.** `_ECHO_SITUATION_RE`
(`^\s*\**\s*situation\s*\d…`) needs the *numbered* marker — none of these has
`situation N` at the start. `_ECHO_OPENER_RE` (`^\s*\**\s*(?:need\b|task\s*:|…`)
only anchors at the START, so B and C — whose marker sits at the END — escaped
entirely. A is a *fragment* of the prompt, not the prompt.

→ Fix, mirrored on **all four** layers (writer `buffer_store.is_prompt_echo`,
extraction `internet_learner._JUNK_RE`, producer `active_learn`, store cleanup
`clean_buffer.py`):
```python
_ECHO_FRAGMENT_RE = re.compile(r"user\s+asks\s*:|"
    r"find\s+the\s+structural\s+connection\s+between\s+these\s+two\s+situations\s*:", re.I)
_ECHO_TAIL_RE = re.compile(
    r"(?:what\s+is\s+the\s+)?shared\s+underlying\s+pattern\s*\??\s*$", re.I)
```
The **colon** and the **`$` end-anchor** are the discriminators — a topic-phrase
marker (`shared underlying pattern` bare) would kill the genuine declarative
answer that must stay learnable, exactly the bare-phrase-vs-anchored-opener trap
documented above.

Measured: 3 buffer hits, all 3 ARE the leaks → **0 real-prose FPs** on a
12-sentence hand-written set; **0 hits over 3,169 `longterm_episodes` rows**.
Cleanup by SIGNATURE → 300 → 297 rows, flagged baseline **14** restored,
0 unparsable. `tests/scripts`: **174 passed** (new
`test_cross_connect_prompt_echo_fourth_shape_is_gated_on_both_paths` asserts
BOTH gates AND six prose counter-cases).

**Two traps worth the time they cost:**
- **An "FP" that was already there.** The counter-case
  `What is the shared underlying pattern behind vLLM's chunked prefill?` shows
  `writer=False extract=True`, which looks like your new marker leaking. It is
  the PRE-EXISTING `_INSTRUCTION_OPENER_RE` (`what\s+(?:is\s+)?(?:the\s+)?(?:shared|structural)`),
  flagged identically pre-fix. Always re-run the FP corpus against the `.bak`
  copies before blaming your edit — load them from a temp dir with
  `importlib` (a `/tmp` MSYS path resolves to a bogus `C:\tmp\...`).
- **`\r\r\n` from a blanket `\r\n` conversion.** When appending to the CRLF
  test file, `.replace("\n", "\r\n")` on the WHOLE text turns every existing
  `\r\n` into `\r\r\n` → Python's universal-newline splitter counts ~2× the
  lines and `ast.parse` reports a phantom `IndentationError` far past the end
  (line 1607 in a 1329-line file). Convert **only the appended block**:
  `raw.rstrip(b"\r\n") + TEST.replace("\n","\r\n").encode() + b"\r\n"`, then
  assert `b"\r\r" not in new`. (The clean_buffer.py anchor also needed the
  closing `re.IGNORECASE)` line in the anchor, not just the regex string —
  a bare-string anchor put the new constant inside the call and failed
  `ast.parse`; the apply script correctly refused to write.)

## Root cause AF — SIXTH echo shape + chopped-TOC stub, in ONE buffer tail (live 16.09.26)

Found the cheap way — run `--once`, then read the tail of `online_buffer.jsonl`
and eyeball the `u`/`a` pairs. Two shapes had reached the 300-row buffer through
BOTH gates. Commit `39e585a83`, test added to
`tests/scripts/test_internet_learner_gate.py` (gate file now **37 passed**,
`tests/scripts` **177 passed**).

| cycle | value |
|---|---|
| `active_learn.cross_connect` | `Question: Find structural connection between these two situations. What` |
| `cycle_f_multi_domain` | `Probabilistic methods for uncertain reasoning 2.` (48 chars) |

**Why the existing rules missed the echo.** The prompt is
`Find the structural connection between these two situations:` but the model
parroted it as `Find structural connection …` — **article dropped, period instead
of colon**. `buffer_store._ECHO_FRAGMENT_RE` needs `find the structural
connection` WITH the article and a trailing colon, and every opener rule
(`_ECHO_OPENER_RE`, `_INSTRUCTION_OPENER_RE`, `_ECHO_SITUATION_RE`) is anchored on
other words, so `Question:` was never a candidate at all.
→ Fix: `_ECHO_QUESTION_RE = ^\s*\**\s*question\s*:\s*(?:find|identify|what|how|why)\b`,
mirrored into `active_learn._ECHO_OPENER_RE` and `clean_buffer._ECHO_OPENER_RE`.

**Why the existing rules missed the stub.** `_has_alpha_signal` was added for
exactly this class (`Distinction between classical and modern physics 2.`) but
cannot see it, because **"reasoning" IS an alphabetic `_TECH_HINT_RE` keyword**.
→ Fix: `buffer_store.is_ordinal_stub()` — `<=120` chars, `^(.*)\s(\d{1,2})\.\s*$`,
**no digits in group(1)**, and no `_ORDINAL_VERB_RE` verb. Called from
`internet_learner._is_junk` (extraction → cycle retries) and `clean_buffer`
(store cleanup). `internet_learner` imports it lazily inside `_is_junk` by the
same sibling-import idiom as `is_glued_motif` — one implementation, not a mirror.

### Root cause AG — GitHub repo-page TOOLBAR chrome, 4 rows at once (live 16.09.26, same session)

Found by re-reading the buffer tail after the verification cycles — the tail
re-poisoned within minutes, exactly as documented under Q/R/S. Commit `fe537729f`.

Four rows, all the same GitHub repo-page toolbar:
`Code Pull requests Actions Projects Security and quality Insights main Branches
Tags Go to file Code Open more actions menu Latest commit History 4,190 Commits
Folders and files Name Name …`

>230 chars **with digits**, so the length trust and the technical-signal gate both
fired. The existing `"Code Issues Pull requests"` marker (root cause M) does not
match — this header reads without "Issues".

Marker: **`"open more actions menu"`** — data-only, `buffer_store._NAV_CHROME`
**and** a title-cased fragment in `internet_learner._JUNK_RE`.
Measured: 4 buffer hits and **all 4 ARE chrome** → 0 real-prose FPs (284-row
corpus), 0/77 test-asserted-clean strings, 0/11,342 corpus values.
Rejected alternatives (each hit REAL data): bare `"go to file"` → 1
`longterm_episodes` row; `"security and quality insights"` → 2 such rows.

**Anchor trap that cost a cycle:** the `_JUNK_RE` anchor must NOT include the
closing quote. Splicing after `'r"Code Issues Pull requests|"'` puts the new text
*outside* the string literal →
`SyntaxError: unterminated string literal`. Anchor on
`'    r"Code Issues Pull requests|'` (no trailing `"`). The apply script correctly
refused to write because `ast.parse` ran before `open(...,"wb")` — always assert
parse-before-write, and a failed apply leaves the file untouched (verify with
`grep -c` on the marker before re-running).


The **first draft of the ordinal rule went red on three existing tests** and the
fix looked broken. `^\s*N.\s*$` with a whitespace guard still fires on real
sentences that merely END on a number:
- `Training the 7B adapter took 2:40 on 4 A100s at an effective batch of 16.`
- `Kontakt: Universitaet Hamburg, Mittelweg 177, 20148 Hamburg, Tel. +49 40 42838-0.`

A `<=60`-char cap only "fixed" it by luck (the FP was 71 chars). The condition
that actually carries the precision is **no other digits before the ordinal** —
a genuine TOC heading has none, while both FPs are digit-rich sentences.
Measured table (before/after, one probe):

| variant | leaks | testFP | bufRealFP | corpHits |
|---|---|---|---|---|
| ws-guard only | 2/2 | **1** | 0 | 0 |
| + no-preposition | 2/2 | **1** | 0 | 0 |
| + `<=60` chars (lucky) | 2/2 | 0 | 0 | 0 |
| **+ no-other-digits + `<=120`** | **2/2** | **0** | **0** | **0** |

**Build the FP corpus from the test file itself**, not from hand-written sentences
alone: parse every string literal near an `assert not …is_junk` line (73 of them
here). Hand-written prose missed the `batch of 16.` counter-case that the suite
already asserted, so the suite went red on a rule a hand-written corpus called safe.

Verify: `openamer-repo/.venv/Scripts/python.exe -m pytest
tests/scripts/test_internet_learner_gate.py -q` → **37 passed**; the new
`test_question_echo_and_ordinal_stub_are_gated_on_both_paths` asserts BOTH gates
on both leaks plus six prose counter-cases (incl. a declarative answer on the
*same* "structural connection" topic). Buffer census: **300 → 297 rows, flagged
back to the 12-row baseline, 0 unparsable, CRLF preserved, all 53 genuine
structural-connection rows kept.**

**Gate census drift check:** the old notes pin "14–15 flagged". On this buffer the
PRE-patch baseline measured **12** — re-measure with the `.bak` copies rather than
assuming the number; `NEW == OLD + (number of leaks you removed)` is the assertion
that actually matters (here 12 → 15 with the patch, → 12 after cleanup).

## Root cause AE — 2B PLAN-scaffold echo, FIFTH echo shape (live 16.09.26)

Found the cheap way: run `--once`, then read the **tail of `online_buffer.jsonl`**
and eyeball the `u`/`a` pairs. No new instrumentation needed.

`cycle_h_efficiency` learned the extractor's OWN numbered plan back at itself:

```
u = Efficiency learning (Pushing the Limits of LLM Quantization via the
    Linearity Theorem): How do agents run leaner?
a = "\n   - **Content:** I need to browse the provided list of papers, identify the
    most relevant/valuable technical insight for an autonomous AI agent, and output
    it in the exact format.\n\n2.  **Survey the Papers:**\n   Let me list the
    papers with their ti...
```

~300 chars -> cleared the `>=90` length trust; the `2.` of the numbered plan fed
the technical-signal gate. No existing rule matched, and the reason is worth
remembering: **every earlier echo rule keys on a phrase the caller already knows**
(`must be a single technical insight`, `**text source:`, `the user pasted`,
`identify the goal:`) — those are *prompt* phrases. This one is the model's own
*plan* voice, so the discriminator has to come from the plan itself.

→ Fix (commit `60410e931`): two markers in **both** files (the Q/R/S pitfall) —
`buffer_store._NAV_CHROME` **and** `internet_learner._JUNK_RE`:
- `"most relevant/valuable technical insight"` (the task-voice tail)
- `"**survey the papers:**"` (the plan heading)

**Marker selection was the whole cost here — three candidates measured, two
rejected:**
| candidate | buffer hits | real-prose FP | verdict |
|---|---|---|---|
| `provided list of papers` | 1 | **1** — `The agent should browse a provided list of papers only when the query is genuinely open-ended…` | REJECTED |
| `identify the most relevant` | 1 | **1** — `We need to identify the most relevant failure mode when a cron job dies mid-run…` | REJECTED |
| `most relevant/valuable technical insight` | 1 | 0 | **ADDED** |
| `**survey the papers:**` | 1 | 0 | **ADDED** |

Both rejected forms are *topic* words in a declarative sentence — the
`nachrichtendienst` / `consumer account` / `Transparenzliste` trap again. The
`/`-joined adjective pair and the bold plan heading are the tight discriminators.
Also measured: **0 hits over the 433-row `world_model` corpus** and 0 over the
`longterm_episodes` / `train` corpora (whatever those load as — print the corpus
sizes, they vary by artifact).

### Two probe bugs that cost time here (both silent, both mine)
- **The buffer read must split on `\r\n`, not universal newlines.** Reading with
  `open(..., encoding="utf-8", errors="replace")` + `for l in f` while iterating
  *and appending* to the same list gave **0 buffer hits for every marker**, while
  a plain `any(k in b["a"] for b in buf)` found the row. Read the bytes once,
  `.decode().split("\r\n")`, then `json.loads` each line. A 300-row file is
  small; there is no reason to stream it.
- **`real = [r["a"] for r in buf if not is_junk(r["a"])]` is a CONTAMINATED FP
  corpus while the leak is still in the buffer.** The leaking row *passes*
  `is_junk`, so it lands in "real" and every candidate marker reports
  `prose_FP=1` — which looked like my own marker was unsafe. Exclude the known
  leak first:
  ```python
  LEAKS = ("provided list of papers",)
  real = [r["a"] for r in buf if not bs.is_junk(r["a"])
          and not any(k in r["a"].lower() for k in LEAKS)]
  ```
  (Same trap already documented under root cause AA/AB — it re-bit anyway. Print
  the corpus size and check it moved.)

### Verify an FP that was already there (the documented trap, hit again)
Two counter-case sentences showed `writer=True` immediately after the edit
(`We need to identify the most relevant failure mode…`, `I need to look at how
the buffer store enforces its 300-row cap…`). **They are the PRE-EXISTING
`_INSTRUCTION_OPENER_RE`**, not my marker: loading the `.bak_ae` copies from a
real `tempfile.mkdtemp()` dir and re-running both gates on those sentences gave
the identical `old writer=True old extract=False`. Always re-run the FP corpus
against the backups before blaming the edit. (A `/tmp` MSYS path resolves to a
bogus `C:\tmp\...` — use `tempfile`.)

### Cleanup + verify (the standard shape)
- Removed the one pre-gate row **by signature**
  (`any(s in a.lower() for s in ("provided list of papers", "survey the papers"))
  AND is_junk(a)`), never by bare `is_junk` — the latter drops the historical
  baseline.
- Census: **300 rows / 15 flagged -> 299 / 14**, 0 unparsable, CRLF preserved,
  **55 genuine structural-connection rows preserved**.
- `pytest tests/scripts/test_internet_learner_gate.py -q` -> **36 passed**
  (new `test_2b_plan_scaffold_echo_is_gated_on_both_paths` asserts BOTH gates on
  the leak plus 4 prose counter-cases). `pytest tests/scripts -q` -> **176 passed**.
- **Test-file API gotcha:** that file imports the learner as `IL`
  (`importlib.util.spec_from_file_location("internet_learner", …)`), and every
  other test does `import buffer_store` **lazily inside the test body** — they
  are not module-level names. Writing `buffer_store.is_junk(...)` /
  `internet_learner._is_junk(...)` at test scope fails with
  `NameError: name 'buffer_store' is not defined` on a file that otherwise
  reports `35 passed`. Use `IL._is_junk(...)` + a local `import buffer_store`.
- **CRLF append recipe that worked (no `\r\r\n`):**
  `raw.rstrip(b"\r\n") + TEST.replace("\n", "\r\n").encode("utf-8") + b"\r\n"`,
  then assert `b"\r\r" not in new` and `new.count(b"\r\n") == new.count(b"\n")`.
  Convert **only the appended block** — a blanket `.replace` on the whole file
  doubles every existing CR (documented in root cause AD, and 1 failed attempt
  here would have hit it).

Live re-verify after the fix: 3 consecutive `--once` -> **2 learned / 1 rejected**
(rejection reason `junk` on the documented SERP shape). No new leak.

## Root cause Y — a German-DICTIONARY SERP pair clears both gates (live 16.09.26)

`cycle_c_github` stored **two dictionary SERP snippets joined by `;`**:
`Agent Rechtschreibung, Bedeutung, Definition, Herkunft Duden — Definition,
Rechtschreibung, Synonyme und Grammatik von 'Agent'  Auf Duden online
nachschlagen  Wörterbuch der deutschen …; Agent (Nachrichtendienst) – Wikipedia
— Agent ist im deutschen Sprachraum ein allgemeinsprachlich uneinheitlich`

It cleared both gates for a *structural* reason worth remembering: the first
fragment ends `…` but the em-dash+ellipsis sits **mid-string**, so
`_SERP_TAIL` (END-anchored) never fires; the leading German word list has
commas, so `_is_nav_list` (which wants no comma) never fires; and the row is
`>= 90` chars, so the long-prose trust waves it through. It is the *same*
mid-string-ellipsis hole that `_SERP_ELL_DASH` was added for — the `;`
separator just means no `—` follows the ellipsis on the German half.

**The tempting fix is wrong.** A structural `…;` gate measured **16 hits, and
7 of them are NOT junk** — six of those seven are genuine technical prose:
`Parallelism and Scaling - vLLM — … parallelism of experts …; Optimization and
Tuning - vLLM — Data parallelism …`, `Quantization Format Comparison 2026 — …
throughput, …; 4.8`, `Surpassing vLLM With a Generated Inference Stack — …;
Surpassing vLLM with a Generated Inference Stack - AI News`, `Philosophy of
artificial intelligence - Wikipedia — …; Artificial consciousness - Wikipedia`,
and two more vLLM `Optimization and Tuning` rows. The multi-result shape is a
*source* the deep read legitimately uses; do NOT gate the ellipsis, the `;`, or
the `Title — snippet` pattern. (Same lesson as the single-em-dash rows above.)

→ Fix: the dictionary's own call to action, `"auf duden online"` — data-only,
in `buffer_store._NAV_CHROME` **and** `internet_learner._JUNK_RE` (the Q/R/S
both-files pitfall). Measured on the live buffer: **1 hit, and that hit IS the
leaking row → 0 real-prose false positives.** Competing candidates from the same
probe, all 1 hit / 0 FP, rejected as broader: `\bduden\b` and
`rechtschreibung\s*,\s*bedeutung` (both FP on hand-written prose),
`nachrichtendienst` (also 1/0 but names a *topic*, not chrome — a real
intelligence-service insight would be wrongly dropped).

Cleanup: removed the one row by **signature** (`"duden" in a` AND one of the
SIGS), never `is_junk` — the latter drops the historical baseline.
Census on this run: **14 flagged / 281 rows → 15 with the leak → 14 / 280 after
removal, 0 unparsable.** (The skill's older "15 / 269" figure was a different
day's buffer; re-measure, don't assume.) The very next `--once` rejected with
reason **`duplicate`** on real NASA/MERRA-2 prose — verify a new marker did not
cause the following rejection by reading `buffer_junk.jsonl`'s `reason`, not by
blaming your own edit.

## Root cause AA — a German legal-IMPRINT block clears both gates (live 16.09.26)

`cycle_c_github` stored a 106-char company-address block as a "github learning":
`Transparenzliste GAIA AG Hans-Henny-Jahnn-Weg 53 22085 Hamburg Deutschland
+49 40 3510520 info@gaia-group.`
It cleared both gates because the `>=90` length trust waved it through and its
house number / postcode satisfied the technical-signal gate; `_is_nav_list`
wants >=6 TitleCase tokens AND no comma, so the mixed-case address chain never
matched it. Commit `4c78f0cd8`.

**The tempting marker is WRONG.** `transparenzliste` scored 1 hit / 0 FPs on the
*first* probe set — but on a wider hand-written set it hit a genuine sentence
(`The Transparenzliste of the state media authority lists providers that must
disclose their algorithmic recommendation systems.`). It is a *topic* word, not
chrome — exactly the `nachrichtendienst` / `consumer account` trap. Same verdict
for `umsatzsteuer`, `handelsregister`, `deutschland` (hit
`Deutschland 2026: the BSI reported 412 new CVEs…`), `info@` and any-email
(`Reach the team at info@example.org for a security disclosure…`),
`street+nr+zip` (`Kontakt: Universitaet Hamburg, Mittelweg 177, 20148 Hamburg…`),
and bare `tel + zip`. **All measured, all rejected.**

→ Fix: a **structural** detector, `buffer_store.is_contact_block()` — postcode
AND international phone AND e-mail must ALL be present:
```python
_CONTACT_ZIP_RE = _re.compile(r"\b\d{5}\b")
_CONTACT_PHONE_RE = _re.compile(r"\+\d{1,3}[\s-]?\d")
_CONTACT_EMAIL_RE = _re.compile(r"[\w.+-]+@[\w-]+")   # NO TLD requirement --
_CONTACT_MAX_CHARS = 600                               # the live row ends "info@gaia-group."
```
Wired into `_is_nav_chrome` (writer gate, so `active_learn` / `online_learning`
are covered too) AND called from `internet_learner._is_junk` at extraction.

**The loose e-mail regex is deliberate.** A strict
`[\w.+-]+@[\w-]+\.[a-z]{2,}` MISSES the live row (`info@gaia-group.` is
truncated, no TLD) — 3-of-3 then measured 0 hits and the fix looked dead. Do not
"tighten" it; the phone + postcode co-occurrence is what keeps precision.

Measured: 1 buffer hit and that hit IS the leaking row → 0 real-prose FPs on a
22-sentence set; **0 hits over 3,834 rows** of
`longterm_episodes` / `train` / `world_model` corpora (the skill's older
"5080-row corpus" is a different artifact — re-measure, don't assume).

## Root cause AB — German Wikipedia list/glossary page chrome (live 16.09.26)

`cycle_g_security` stored a 210-char list-page header:
`Liste aller Wikipedia-Artikel, deren Titel Agent enthält Wiktionary: Agent –
Bedeutungserklärungen, Wortherkunft, Synonyme, Übersetzungen Dies ist eine
Begriffsklärungsseite zur Unterscheidung mehrerer mit demselben Wort
bezeichneter Begriffe.`
210 chars → cleared the `>=90` length trust; the digits fed the
technical-signal gate. Commit `641921b2b`.

Markers (data-only, BOTH files): `"liste aller wikipedia-artikel"`,
`"deren titel"`, `"wiktionary:"`.

**Two over-broad candidates were measured and REJECTED:** the truncated German
stems `bedeutungserkl` / `begriffskl` each flagged a hand-written real-prose
counter-case (`Bedeutungserklaerungen und Synonyme helfen beim
Sprachverstaendnis…`, `Dies ist eine Begriffsklärungsseite: ein Hinweis in
Nachschlagewerken…`). Keep the FULL page phrases only — a truncated stem is a
topic word, not chrome.

## Root cause AC — numbered-prompt ECHO, third shape (live 16.09.26)

`active_learn.cross_connect` buffered its OWN numbered prompt back at itself —
2 of 58 `Structural connection` rows:
```
Situation 2 learning process: Continuous Learning Loop: error capture + categorization + memory + auto-skill generation + trend.
Situation 1: "learning process: Continuous Learning Loop: Fehler-Capture + Kategorisierung + Memory + Auto-Skill-Generierung + Trend" German: error capture + …
```
The existing `_ECHO_OPENER_RE` (root cause W) covers
`need|task:|goal:|ask:|find … connection|identify … pattern|they want me to|what is the …`
but NOT this prompt marker, so the producer guard passed both.

→ Fix: an anchored rule in the **producer** (`active_learn._ECHO_OPENER_RE`)
AND a mirrored `buffer_store.is_prompt_echo()` wired into `is_junk` (so any
other writer path is covered too):
```python
r"^\s*\**\s*situation\s*\d\s*(?::|\b(?:learning|system|energy|tool)\b)"
```
**The alternation is the whole trick.** `^\s*\**\s*situation\s*\d\s*:` alone
caught only 1/2 (the quoted variant has no colon after the number);
`^\s*…situation\s*\d\b` alone caught 2/2 but ALSO killed a genuine declarative
(`Situation 1 and situation 2 share a common failure mode…`). The
colon-OR-topic-word form: **2/2 leaks caught, 0/5 real answers killed.**

Cleanup: removed 2 rows → 295 → 293, 0 unparsable, flagged back to baseline 14,
all 56 genuine structural-connection answers preserved. Verified with `pytest`
→ **32 passed**.

### The `_JUNK_RE` insertion trap that cost the most time here
`_JUNK_RE`'s **last fragment** is the one whose trailing `,` the following
`re.IGNORECASE)` closes. Appending a new `r"…"` line *before* it is fine **only
if the new line ends with `|`**; and you must not leave the old last fragment
stranded after your comment block. Two failure modes hit in this session:
- appending after the closing line → `SyntaxError: invalid syntax. Perhaps you
  forgot a comma?`
- replacing `re.IGNORECASE)` textually inside a multi-line `re.compile(` whose
  final fragment ends `))",` → the substitution landed *outside* the string
  literal → `SyntaxError: unexpected character after line continuation char`.

Safest recipe: extend the **preceding** fragment in place
(`r"auf duden online|"` → `r"auf duden online|new marker|"`) and leave the last
fragment + its comma exactly as they are. `ast.parse` before write catches both.

### `active_learn.py` is pure LF — and its `_ECHO_OPENER_RE` spans lines
Re-confirmed: `active_learn.py` has `CRLF=0, loneLF=283` while
`internet_learner.py` / `buffer_store.py` / `clean_buffer.py` are CRLF and
`test_buffer_store.py` LF. A `load()` helper that asserts CRLF will refuse it —
parameterise on the file's own separator and assert the convention did not
change after writing.

## Root cause AF — Microsoft landing-page CTA clears both gates (live 16.09.26)

`cycle_h_efficiency` stored the Microsoft SERP/landing-page call-to-action:
```
Microsoft – AI, Cloud, Productivity, Computing, Gaming & Apps — Explore
Microsoft products and services and support for your home or business. Shop
Microsoft 365, Copilot, Teams, Xbox, …
```
297 chars -> cleared the `>=90` long-prose trust; the digits fed the
technical-signal gate. Commit `2b14c89bc`. Data-only, BOTH files (the Q/R/S
pitfall): `buffer_store._NAV_CHROME` + `internet_learner._JUNK_RE`.

**Marker choice was the whole cost — the obvious short form is a TRAP.**
| candidate | first probe (buffer only) | wider FP set | verdict |
|---|---|---|---|
| `explore microsoft products and services` | 1 hit / 0 FP | **flags `Explore Microsoft products and services to understand the pricing model of the API.`** | REJECTED |
| `explore microsoft products and services and support for your home or business` | 1 hit (the leak) / 0 FP | 0/6 counter-cases | **ADDED** |
| `shop microsoft 365` | 1 hit / 0 FP | flags `Shop Microsoft 365 for the enterprise agent team.` | REJECTED |
| `for your home or business` | 1 / 0 | 0/6 | ok but broader than needed |

The lesson repeats the `nachrichtendienst` / `consumer account` /
`provided list of papers` trap: a marker that is really a *verb phrase over topic
words* passes a small probe and dies on a hand-written counter-case. ALWAYS run
the counter-case set (`HAND` list), not just the live buffer.

Verified: both gates True on the leak, 6/6 prose counter-cases False (writer AND
extract), `flagged` census 13 -> 12 after removing the pre-gate row,
`pytest tests/scripts/test_internet_learner_gate.py -q` -> **37 passed**.

## Root cause AG — `deep_learn` ranks the WRONG page, and the fix is NOT cheap (live 16.09.26) — OPEN, deliberately unpatched

**This is the biggest remaining quality defect.** It is NOT a gate problem: the
rows below pass both gates and get buffered as learnings.

### Symptom — off-topic rows in the buffer
```
u = Security learning (AI agent security vulnerabilities guardrails benchmark …)
a = The system geolocated over 200,000 individual palm trees and calculated
    precise greenery surface area estimates (in m²), providing executive-ready
    data for national policy …
u = Internet learning ('Rogue' Cursor AI agent loses control and wipes company's
    database): What should …
a = The apartment has about 2,000 square feet indoors and nearly 1,000 square
    feet of private outdoor space.
```
Measured 16.09.26: ~2 of the last 6 buffer rows. The skill's earlier note called
this "~1/8, content-inspection only, no cheap gate" — two of these are NOT
off-topic chrome, they are **topically unrelated whole articles**, and they are
reproducible.

### Mechanism (reproduced, `deep_learn` lines ~1188–1224)
`deep_learn` scores every sentence-shaped string across all k pages and takes the
**global max**. The scoring is:
```python
score = tech * 10 + (5 if has_verb else 0)      # tech = len(_TECH_HINT_RE.findall(s))
if n < 60 or n > 220: score -= 5
```
`_TECH_HINT_RE` **starts with `\d+`**, so raw digits score identically to the
word `agent`. There is **no query/topic overlap term at all**. Result: a numeric
table or a date-dense sentence wins over the real, on-topic article sentence —
and the search URL for `'Rogue' Cursor AI agent loses control …` resolves to the
**Rogue Fitness** Wikipedia page (fitness equipment).

Reproduce in ~4 s (no buffer writes):
```python
# replicate deep_learn's candidate loop, then print max by score
# q = "'Rogue' Cursor AI agent loses control and wipes company database"
# OLD pick: "Rogue Fitness had 200 employees in 2014, [ 11 ] increasing to 600 …"  score=85
# NEW-ish:  only reaches a *different* Rogue-Fitness sentence (both off-topic)
```

### Two candidate fixes measured — BOTH rejected, do not ship either
1. **Query-overlap FILTER** (`drop candidates with 0 overlap`): measured **121 of
   279 genuine buffer rows have zero overlap** (43%) — it would delete nearly
   half the real knowledge. Dead.
2. **Query-overlap BONUS + digit de-weight**
   (`score = non_digit_tech*10 + digits*1 + 20*min(overlap,3)`, plus a
   `subsection|toggle` penalty): on the 3-query eval it fixed 2 (removed
   `Rogue Fitness … 2014` and `Regulation 5 History 6 Philosophy Toggle …`) but
   made the third **worse** (`Net |date=18 janvier 2024 …` ->
   `Lancements mondiaux 3 Popularité 4 …`). n=3 is far too small to justify
   touching the core scorer — a half-validated heuristic here would silently
   degrade every cycle.

### What to do instead (next session)
- Build a **proper eval before touching the scorer**: N>=40 recorded
   `(query, candidate_set, correct_sentence)` triples from real cycles, then
   measure top-1 accuracy OLD vs NEW. Anything less is guessing.
- The likely-correct fix point is **URL selection in `_search_urls` / the
  deep-read**, not the sentence scorer: a query mentioning `'Rogue' Cursor`
   should never fetch `en.wikipedia.org/wiki/Rogue_(company)`. Add a
   title/domain relevance check between the query and the fetched page
   *before* extraction, so an unrelated page cannot contribute candidates.
- Do NOT reach for `text.count(" — ")`, an overlap *filter*, or a bare
  `subsection`/`toggle` marker without the eval — each was measured and is
  either a topic-word FP or insufficient.

### Cheap detection while this is open
Sample the last ~8 rows of `online_buffer.jsonl` (`u` vs `a`) — an `a` whose
subject has nothing to do with its `u` is this defect, not a gate leak. It does
not show up in `buffer_junk.jsonl` (it was never rejected).

## Root cause W — a DEAD writer: `cross_connect` buffers `chat()` UNVALIDATED (live 16.09.26)

Found while investigating a `cycle_h_efficiency` rejection. The rejection itself was
rotation noise (70% last-20 / 83.4% all-time), but the buffer scan turned up
something worse: **9 degenerate rows** had trained as "insights".

| rows | value |
|---|---|
| 5 | `""` (empty string) |
| 1 | `"S"` |
| 2 | `"What is the shared underlying pattern"`, `"Need shared underlying pattern. One"` |
| 1 | `"Need find structural connection. Shared underlying pattern? One sentence"` |

Every one came from `active_learn.py` `cross_connect()` (the cycle that writes
`Structural connection between X and Y?`). It called `chat(...)` and passed the
result **straight** to `add_to_buffer()` with no check \u2014 and `chat()` returns
`""` on failure, so a failed/truncated generation was buffered verbatim.
`web_learn()` in the same file DOES guard (`if "[INSIGHT]" in learning`);
`cross_connect()` was simply never given the same treatment.

**Why no gate caught it \u2014 three deliberate contracts, all correct:**
1. `internet_learner._is_junk` rejects `< 25` chars, but only the *internet*
   cycles run through it.
2. `buffer_store.is_junk` returning `False` for `""` is **pinned by a test**:
   `test_buffer_store.py:134` `assert bs.append("q", "", buffer=buf) == 1`, and
   `buffer_store.is_junk`'s docstring says empty is tolerated because callers may
   record a placeholder. Do NOT "fix" this by making `is_junk("") == True` \u2014 it
   breaks a documented, tested contract and reddens the suite.
3. `clean_buffer.py` DOES drop empty answers (reason `"empty"`) \u2014 but only when
   that cleanup actually runs, and it never covered the two \u226525-char ECHOES.

\u2192 Fix (commit `4d3c460bc`), in three files:
- **producer** (`active_learn.cross_connect`): a 25-char floor **plus**
  `_ECHO_OPENER_RE`, an anchored imperative rule mirroring
  `internet_learner._INSTRUCTION_OPENER_RE` (same lesson as the *Bare phrase vs.
  anchored instruction opener* section above \u2014 the bare topic phrase cannot be
  gated, because the genuine declarative answers must survive).
- **cleanup** (`clean_buffer.py`): the same two checks, so the STORE layer can
  reach rows that landed before the producer guard existed.

Verified both directions before committing \u2014 8 echo shapes all rejected, and 4
genuine declarative answers (`"The shared underlying pattern is a closed-loop
feedback system ..."`) all survive. Then removed the 10 degenerate rows from the
live buffer (**274 \u2192 264**): filter on **`u` starts with `"Structural connection"`
AND degenerate**, never on `is_junk` \u2014 the latter drops the 14-row historical
baseline (documented in Q/R/S). All **57** genuine structural-connection answers
were preserved.

**Measuring pitfall:** a dry-run replica of a cleanup loop is the way to size a
deletion \u2014 but replicate the loop *exactly* (including any rule you have not
written yet) or you will under-count. The first dry run here reported only `1`
stub because it predated the echo rule; the real number was 10.

**`active_learn.py` is pure LF, not CRLF.** `internet_learner.py`,
`buffer_store.py` and `clean_buffer.py` are CRLF; `active_learn.py` and
`test_buffer_store.py` are LF. Check `raw.count(b"\r")` per file first and build
the inserted lines with THAT file's separator \u2014 a `\r\n` insert into an LF file
produced 7 stray CRs and had to be normalised back.

**The repo runs `core.autocrlf=true`.** `git show HEAD:path` is pure LF while the
working tree is CRLF, so a byte-compare against the blob always "differs". Sync
with each file's **working-tree** convention and judge the change with
`git diff --stat --ignore-cr-at-eol` (identical numbers with and without the flag
= no EOL churn).

**Do NOT `git checkout --` a file to "get the repo version" before copying.** The
first attempt here clobbered a legitimate *uncommitted* repo-side improvement
(a `model_config.chat_default` migration) that existed in BOTH copies and simply
had not been committed yet. `checkout` reverts to HEAD, silently discarding
uncommitted work; read `git diff` first and patch minimally instead.

## Root cause X — a news-site article HEADER clears both gates (live 16.09.26)

`cycle_a_technews` stored a **238-char** CNBC article header verbatim:
`Published Tue, Mar 10 2026 1:12 PM EDT Updated Tue, Mar 10 2026 4:39 PM EDT
Annie Palmer @in/annierpalmer/ WATCH LIVE Key Points Amazon won a temporary
injunction ...`

It passed both gates because every marker was absent: `_SERP_DATE` wants the
German `\u00b7` form, `_is_nav_list` wants \u22656 TitleCase tokens with no comma, and
the `>= 90` "long prose" trust never looks closer. Its own author/date stamps are
not bylines either \u2014 `_strip_byline_prefix` needs `\u00b7` separators or an
END-anchored date, and CNBC separates with plain spaces.

\u2192 Fix: `"watch live key points"` added to `internet_learner._JUNK_RE` **and**
`buffer_store._NAV_CHROME` (data-only, both files \u2014 the Q/R/S pitfall). Measured
on the live buffer: **1 hit, 0 real-prose rows** carry it.

Chosen over a surgical prefix-strip: a dedicated "strip the CNBC date/author
prefix" regex was rejected as too risky for **1 row in 274** \u2014 a mis-anchored
date pattern would eat real prose, whereas the marker costs one discarded row.
Note the row DID carry a real lede after the chrome, so this is a gate
(cycle retries, source rotates), not an extraction fix. If the shape recurs, the
fix point is the deep-read URL/sentence selection, not a looser gate.

## Verify## Root cause AA/AB — self-critique echo + sports-fixture list (live 16.09.26)

Two shapes cleared BOTH gates in one cron session, found by simply running
`--once` four times and reading `online_buffer.jsonl`'s tail rows (the cheap
move — no new instrumentation needed). Commit `7351ad0e7`, test `b17b26be7`.

| cycle | shape |
|---|---|
| `cycle_d_docs` | 2B self-critique echo: `"\n   - **Context:** The user pasted a long documentation page from vLLM, but the actual content is just the table of contents and section headings.` |
| `cycle_c_github` | sports results-page fixture list: `Napoli vs Lazio 0-2 \| 12/04/2026 Parma vs Napoli 1-1 \| 12/04/2026 Parma vs Napoli 1-1 SSC NAPOLI OFFICIAL APP` |

Both are >90 chars **with digits**, so the long-prose length trust AND the
technical-signal gate fired; no existing marker matched either.

→ Fix, both files (the Q/R/S rule):
- `"the user pasted"` in `buffer_store._NAV_CHROME` **and**
  `internet_learner._JUNK_RE`.
- new **structural** `buffer_store._FIXTURE_LIST_RE` — a scoreline immediately
  followed by a pipe and a fixture date
  (`\b\w+\s+vs\.?\s+\w+[^|]{0,25}\d{1,2}\s*[-\u2013]\s*\d{1,2}\s*\|\s*\d{1,2}[/.]\d{1,2}[/.]\d{2,4}`),
  mirrored as a fragment in `_JUNK_RE` and wired into `_is_nav_chrome`.
- A bare `A vs B` is deliberately **NOT** gated: measured **6 hits, all real
  prose** (`CUDA vs ROCm vs Vulkan vs Metal`). Same verdict for the fixture
  regex embedded in prose (`.venv`-run test includes a `vs … 12.04.2026`
  sentence as a counter-case).

### The measurement trap that cost a cycle here — a CONTAMINATED FP corpus
`real = [r["a"] for r in buf if not is_junk(r["a"])]` is **wrong as an FP
corpus whenever the leak is still in the buffer**: a row that leaks *by
definition* passes `is_junk`, so it lands in "real" and every candidate marker
reports `real_prose_FP=1` — looking like your own marker is unsafe. Exclude the
known leaks first:
```python
LEAKS = ("**context:**", "napoli vs lazio")
real = [r["a"] for r in buf if not bs.is_junk(r["a"])
        and not any(k in r["a"].lower() for k in LEAKS)]
```
Live: 295 rows → 281 "real" → **280 genuine** → both markers `hits=1
genuine_FP=0`. Always print the corpus size and eyeball whether it moved.

### `_is_junk` has no `is_junk`-style structural hook for fixtures — mirror it
`buffer_store` must not import the learner (circular), so a mirror is the only
option; keep the two regexes textually identical and note it in both comments.

Cleanup: both pre-gate rows removed **by signature** (`is_junk` would drop the
14-row historical baseline). Census **296 → 294, flagged 16 → 14**, 0
unparsable, CRLF preserved. `pytest tests/scripts/test_internet_learner_gate.py`
→ **33 passed** (new `test_selfcritique_echo_and_fixture_list_chrome_is_gated_on_both_paths`
asserts BOTH gates + 4 prose counter-cases). Full `tests/scripts` suite: **173
passed**. Both commits pushed.

## Root cause T — the Darwin autopilot rewrites this file WHILE you edit (live 16.09.26)
`scripts/darwin_engine.py --autopilot` runs 24/7 and edits
`internet_learner.py` in place. Symptom that costs the most time: you patch a
broken regex, re-run, and get the **byte-identical traceback back**. That is not
a failed patch — a concurrent writer overwrote your edit (measured: file size
55146 → 55462 → 56577 and mtime 01:41 → 01:43 → 01:46 over five minutes).
Same cause for `re.error: missing ), unterminated subpattern` /
`TypeError: compile() takes from 1 to 2 positional arguments but 3 were given`:
you are importing a file caught mid-rewrite, whose `re.compile(` call is
momentarily unbalanced or has a stray `,` before `re.IGNORECASE)`.
How to tell it apart from a real bug, in order:
1. `stat -c '%s %y' scripts/training/internet_learner.py` twice, ~1 min apart.
   A changing size = concurrent writer; do NOT keep patching.
2. `ps -W` / `Get-CimInstance Win32_Process` filtered on
   `self_improve|darwin|internet_learner|training` — look for
   `scripts/darwin_engine.py --autopilot`.
3. `diff C:/Users/damir/openamer-repo/scripts/training/internet_learner.py scripts/training/internet_learner.py`
   — `IDENTICAL` means the writer already propagated its own (often *better*)
   fix to both copies.
What to do: wait for the size to stop changing, then re-`import` and run the
two-gate prose assertion. Usually the autopilot has already fixed it — do not
fight it by re-applying your own patch. Verify the *current* file, never the
state you read five minutes ago. If you must edit under a live writer, re-verify
`stat` immediately before AND after, and treat your own `patch` result as
unconfirmed until `ast.parse` passes on a re-read.

## Root cause J — a DEAD single domain keyword (live 15.09.26)
`cycle_h_efficiency` was rejected on EVERY run (0/3 by 08:10) and `cycle_b_papers`
2/2, while a/b/c/d/e/f/g/g all learned at their usual rate.
Cause: each cycle called `_fresh_headline` with ONE narrow keyword.
`"quantization LLM inference efficiency"` has **2** Algolia hits (both Show HN,
skipped by `_SELF`), `"arxiv meta-learning LLM agents"` has **0** → the HN path
returned `""` for all 4 pages × 2 thresholds, the LLM synth degenerated, and the
saturated static seeds were gated.
→ Fix (commit `fa531a4f2`): `_novel_query` accepts a **list** of keyword fallbacks
and tries each in order. cycle_b/cycle_h each carry 3–4 keywords now.
Diagnose a dead keyword in one curl (no traceback needed):
```
curl -s "https://hn.algolia.com/api/v1/search?query=<urlenc+kw>&tags=story&numericFilters=points%3E3&hitsPerPage=12&page=0" \
 | python -c "import sys,json;print(json.load(sys.stdin)['nbHits'])"
```
`nbHits` 0–2 (and what exists is Show/Ask HN) = dead keyword → give that cycle a list.

## Root cause K — GitHub org-page chrome (live 15.09.26)
`cycle_b_papers` stored `Updated Dec 19, 2013 People This organization has no
public members.` — a GitHub org page, and `is_junk` let it through.
→ Fix (same commit `fa531a4f2`): `"has no public members"` added to
`buffer_store._NAV_CHROME` (data-only).

## Root cause L — glued-motif degeneration (live 15.09.26)
`cycle_h_efficiency` stored a 2B word salad (`Here's a ali with aminoellsかけて
subject et recessellsells deep this urbanellscriptsells ...` — `ells` inside 14 of
~43 tokens). The periodic-repeat AND the token-ratio gate both MISS it: the motif
sits INSIDE otherwise-distinct words, so every token looks unique and the
unique-token ratio stays high.
→ Fix (commit `4177a4576`): new `buffer_store._is_glued_motif()` — a distinct
4-char window repeated `>=12` times AND covering `>=4.5%` of the characters.
Measured over the live 300-row buffer: the salad scores 14 hits / 0.056 rate, the
highest-scoring REAL row 8 / 0.027 → both thresholds sit in a clean gap.
Cleanup of that one row took the flagged set 27 → 26 (26 = the historical
baseline). Guarded by `test_glued_motif_degeneration_is_gated` (10 tests pass).

## Prompt-echo leak, SECOND shape (cycle_d_docs, live 15.09.26)
Stored `" exactly). - Must be a single technical insight extracted from the given
text. - **Text Source:** The provided text is a lengthy table of con…` — the 2B
extractor echoed its own template past the `>=90 chars` long-prose trust.
→ Fix (commit `6a8f41683`): `"must be a single technical insight"` and
`"**text source:"` added to `internet_learner._JUNK_RE` **and**
`buffer_store._NAV_CHROME`. Do NOT use the bare `text source:` — it flags real
prose ("The Text Source: field in a dataset card links to the original corpus").
Note the leak is now rejected at the *writer* gate, so the cycle reports
"rejected, not trained" instead of poisoning the buffer — a wasted cycle is the
cheaper failure; the extraction-side fix is still open.

## Root cause M — GitHub repo-page header (live 15.09.26)
The deep read leaks the repo header: `Updated Jul 12, 2025 Jupyter Notebook
owner/repo Star 1 Code Issues Pull requests …` (3 such rows measured, incl.
`Updated Sep 14, 2026 Python … Sponsor Star 294 …`). 0 real-prose rows carry the
phrase, so the signature is safe to gate.
→ Fix (commit `be51a3e84`): `"code issues pull requests"` in
`buffer_store._NAV_CHROME` **and** title-cased `r"Code Issues Pull requests|"` in
`internet_learner._JUNK_RE` (that regex runs on raw text — case matters; the
writer gates on `text.lower()`). Prose with the singular `issue pull requests`
still passes.

## Re-verified 16.09.26 04:2x — U/V intact under the Darwin autopilot, rate 60–70%
Cron run found `cycle_c_github: rejected`; the full diagnostic took ~4 min, no code
change was correct. Reusable order of operations:

1. **Rate first, not the last log line.** Parse `internet_learn_log.jsonl` and
   print last-10/20/40/80 + all-time. Live: `60% / 70% / 62% / 65%`, all-time
   **84.7%** (n=1544). A drift to ~65% with rejects rotating across ALL cycles is
   the U/V signature — go verify U/V before inventing a new root cause.
   **CRITICAL — the success criterion is `not result.startswith("rejected")`, NOT
   `startswith("learned")`.** The log carries a *different prefix per cycle*
   (`github-learn: `, `domain-learn: `, `paper-learn: [`, `doc-learn: `,
   `competitor-learn: `, `security-learn: `, `efficiency-learn: `) plus a bare
   `learned: ` for only ~174 of 1553 rows. Grading with `startswith("learned")`
   reports **all-time 11%** and a flat `last 10/20/40/80 = 10/10/10/9%` — a
   *fake systemic collapse* that looks exactly like a new root cause and will
   send you re-patching working code (cost: a full diagnostic cycle on
   16.09.26). Regrade with the reject-prefix rule and the same file reads
   `all-time 85%`, `last 10 = 40–50%`: normal rotation noise. Sanity-check any
   rate computation by printing the distinct `result[:14]` prefixes first.
2. **Prove U/V are still present** (the autopilot rewrites these files): assert
   `hasattr(m,'_fair_share_window')` and `hasattr(m,'_http_search_urls')`, then
   `_search_urls(q,k=6)` → must be `6` for 6 diverse queries (live: 6/6/6/6/6/6),
   and `deep_learn(q,k=2) != deep_learn(q,k=6)` (live: True for 3/3). Both passed →
   the starvation is fixed; do NOT re-patch.
3. **Concurrent writer, always check.** `stat -c '%s %y'` twice + a
   `Get-CimInstance Win32_Process` grep for `darwin|autopatch|self_improve`. Live
   this run: `internet_learner.py` grew **61728 → 63198 bytes** mid-diagnosis, and
   `darwin_engine.py --autopilot` was running under a bash wrapper. Both copies
   (laptop + repo) are touched together — that is root cause T working as
   designed. Wait for size to stop changing, re-import, then verify the file you
   actually have. Never edit while it is live.
4. **Read `buffer_junk.jsonl` reasons before calling a regression.** Last 30:
   `19 junk / 9 duplicate / 2 no-tech-signal`. The 19 junk were almost all the
   documented SERP shape (`… — <German date> · …`, 7 hits) — that is CORRECT
   gating of a deep read that landed on a results page, plus normal `duplicate`
   rotation. No new chrome shape appeared.
   Re-confirmed 16.09.26 04:5x (`24 junk / 14 duplicate / 2 no-tech-signal` over
   40): the junk rows were again `<Title> … — <German date> · <snippet>` SERP
   lists (MIT/DeepSeek-R1/vLLM/Uncomfortable-Truths, each `len=300`, two
   `;`-joined results) plus the CNBC `WATCH LIVE Key Points` header already
   documented as root cause X — all `is_junk=True`, i.e. a *wasted cycle*, never
   a poisoned buffer. `buffer_junk.jsonl` rows are `{"u","reason","a"}`.
   **Also in that tail: 2B self-critique echo** (`We can answer directly.
   Self-critique: So inaccurate/incomplete.`, `… transformer memory?
   Self-critique: Answer seems tentative, lists terms, no explanation.`). Do NOT
   add a `self-critique`/`answer seems tentative` marker — measured **0 buffer
   hits, 0 not-yet-junk** on both counts: the rows are already caught at
   extraction (verb/tech-signal gate), which is why they show up as rejections.
   A marker would be a redundant `_JUNK_RE` entry with zero live effect.
   **Clean-baseline census (re-measured 17.09.26): `12 flagged / 298–300 buffer
   rows`.** (The older `15 / 269` figure was a different day's buffer; earlier
   notes pin 14–15.) Re-run the same census after any gate change; drift off the
   baseline means either a new leak or a new false positive — then apply the
   "1 hit, 0 real-prose rows" test. The assertion that actually matters is
   `NEW == OLD + (number of leaks you removed)`, e.g. 12 → 13 with the leak
   → 12 after cleanup.
5. **Two MORE rows in the deliberately-ungated class** (do NOT gate these — they
   carry real prose after the header, exactly like the single-em-dash rows above):
   - `cycle_c_github`: `Start the challenge Blog 18 April 2026 / 24 min read 8 best
     open-source AI agent frameworks on GitHub in 2026 The best open-source AI
     agent frameworks in 2026: LangGraph, AutoGen, CrewAI, and LangChain.`
   - `cycle_g_security`: `Claude Opus 5 Review 2026: $5/$25, 61 Score, Real API
     Catch Claude Opus 5 launched at $5/$25 per million tokens with 1M context and
     128K output.`
   Measured: 1 buffer hit each, 0 live-prose false positives, and the body itself
   is on-topic technical prose. A `, \d{1,3} Score` badge or a `/ N min read`
   header sitting before a real sentence is NOT junk. The existing `"min read
   article"` marker already covers the header-only variant — that is why the bare
   `/ N min read` was (correctly) never added.
   Note the same row is also what makes `cnbc_pub_edt` look like a leak: the
   Amazon/Perplexity row already matches the existing `"watch live key points"`
   marker, so `not-yet-junk == 0`. Always print `hits` AND `not-yet-junk`; only
   `not-yet-junk > 0` is a real leak.
6. **Verify a marker candidate in ONE probe before touching a file.** Print, per
   candidate regex: buffer hits, `not-yet-junk` count, and a live-prose FP list
   (4–6 hand-written real sentences). Reject any marker with a live-prose FP; a
   bare marker with 0 FPs but only chrome hits is still only worth adding if the
   row it targets is chrome-only.
## Root cause AW (live 19.09.26) — classes 77-80: advisory row, site headline stub, fact box, own plan WITHOUT dangling marker

Cron run began on the documented `cycle_b_papers: rejected` line. Per-day rate
**47 % (15 ok / 17 rej)** vs the documented 50-80 % band -> **no gate change was
warranted for the rejection itself**; `buffer_junk` last 8 = `duplicate` at the
287/300 cap + documented junk shapes = rotation noise. U/V verified BEFORE
inventing anything: `_search_urls(q, k=6)` -> 6 on all five diverse queries;
`_fair_share_window` -> 4000 chars; buffer size byte-stable over 2 s. Working
tree clean (no uncommitted predecessor work). All four finds came from the
prescribed cheapest method: run `--once`, read the BUFFER TAIL `u`/`a`, repeat.
All four passed BOTH gates and NONE was ever in `buffer_junk.jsonl`.

| class | helper | measured |
|---|---|---|
| 77 | `_is_advisory_row` -- vendor/product run welded to `-- <Mon DD, YYYY> CVE-<id>`, OR a CVE id with a trailing `<SEVERITY> <score>.` | 1 hit, IS the leak / 0 FP on 9 hostile security-prose controls / 0 le / 0 lit |
| 78 | `_is_site_headline_stub` -- brand run + colon + `<year> Comparison of ...`, nothing else | 1 hit, IS the leak / 0 FP on 6 controls / 0 le / 0 lit |
| 79 | `_is_fact_box_label_chain` -- `Key Points` welded within 200 chars of `Affected objects:` | 1 hit, IS the leak / 0 FP on 6 controls / 0 le / 0 lit |
| 80 | `_is_own_plan_plus_run` -- own-artifact title AND a 3-way `+`-joined deliverable run | 1 hit, IS the leak / 0 FP on 6 controls / 0 lit |

**Class 77 -- the advisory FURNITURE pair, not the CVE.** A bare CVE id is
ordinary security prose and `-- <date>` alone is an ordinary dateline. Four
candidate forms each measured 1 buffer hit / 0 FP / 0 le / 0 lit and are
equivalent on this corpus; the shipped alternation covers both live facets.
Hostile controls that must stay clean: `The Cisco IOS XE firmware update fixes
CVE-2025-20337, a critical RCE flaw rated 10.0 by NVD.`, `CVE-2024-12345 was
rated CRITICAL 9.8 and patched in the October 16, 2023 firmware release.`,
`The report lists five CVEs: CVE-2026-5430 CRITICAL 9.8, CVE-2026-5431 HIGH 8.1
in the appendix table.`

**Class 78 -- a bare `20xx Comparison of` measured 3 control FPs** (`A 2026
Comparison of quantization methods shows 4-bit wins on memory.`), so the brand
run BEFORE the colon is the marker. The sibling "brand run + colon + `<year>`"
form (no `Comparison of`) measured **2 buffer hits** -- it also eats row 195,
which class 79 legitimately owns; keep the `Comparison of` anchor.

**Class 79 -- `Affected objects` alone and `Key Points` alone are BOTH ordinary
prose.** The 200-char weld of the page's own two labels is the whole
discriminator. Do not gate the bare labels.

**Class 80 -- the AP/AO "check the EXISTING helper" rule applied to an own
artifact.** Class 66's `_PROMPT_PLAN_ECHO_RE` already covers this family and
still missed the live row, because it requires a **DANGLING list marker**
(`[
]+\s*\d{1,2}\.\s*$`): the live row ends in prose (`... + cron job every
12h.`). Same vocabulary, new SHAPE -- a new class, not a duplicate. Sweep that
mattered: bare `RAM/Disk/Cron` hits **5 episodes**, bare `skill + cron` hits
**3 episodes + 1 control FP**; only the own-artifact title AND a **3-way** `+`
run reached 0. The 2-way form measured 1 control FP (`The pipeline: data
ingestion: raw logs + normalization + dedup + feature extraction runs hourly.`)
plus 1 test literal. **A `longterm_episodes` hit is not automatically world
knowledge -- here the single hit was the SAME own-artifact string in German.**

### THE DELIBERATE NON-FIX -- the 9-row em-dash + semicolon + ellipsis SERP run
Rows 19/87/146/181/197/210/218/231/272 are two search-result blocks welded with
`; `. Every conjunction form measured **16-18 buffer hits** but flagged real
prose: emdash+semi+ell -> **33 episode hits** (incl. an interrupted-run system
note and a German technical answer) + 2 test literals; the len<=900 helper ->
9 buffer hits but **1 real episode**. This is the root-cause AU shape -- those
SERP rows are exactly what a previously REJECTED rule eats -- so they stay
**un-gated by design**. A high buffer hit-count with 0 FPs on hand controls is
not proof; grep the gate test file for the shape first. Row 195 sits in the same
family and IS gated, because it carries the page's own label pair.

### Pitfall -- `crlf()` on an ALREADY-CRLF anchor matches 0 times
Passing the two-line CRLF gate anchor through the same `crlf()` helper used for
the LF-only insertion BLOCK turns `
` into `
` and `count()` returns
**0** -> the apply script aborted with `gate anchor count 0`. Keep ONE helper
(`.replace("
", "
")`) for LF-only text and pass anchors to
`count()`/`replace()` as raw `bytes`. Assert the anchor `count() == 1` before
replacing (root cause AI/AM/AR trap, fourth occurrence).

Cleanup + verify (standard shape, all met): 4 rows removed by signature
**291 -> 287**, 0 unparsable, CRLF intact (lone LF 0), structural-connection
rows **49 -> 48** -- the dropped row 235 was ITSELF a structural-connection
cycle, so re-count and explain the delta instead of asserting an old number.
Writer-gate census **4 -> 0**, learner-gate census **0**. 3-copy `md5sum`
identical for BOTH modules after the apply (`eb977536...` learner,
`14fa6d94...` store), every copy `exec_module`-verified (`ast.parse` is not
enough). `pytest tests/scripts/test_internet_learner_gate.py -q` -> **95 -> 99
passed** (4 new tests, each asserting the helper on BOTH gates on the leak plus
6-8 prose counter-cases); `pytest tests/scripts -q` -> **255 passed**. Tests
appended as **pure bytes** (155 added / **0 removed**, lone-LF census 58 -> 58),
mirrored to both other test copies. Commit `5cda85ea0` on the foreign branch
`fix/28-respawn-test-psutil-hermetic` (FF_SAFE) ->
`git -c credential.helper= -c credential.helper=store push origin HEAD:main`
(`d50ec4231..5cda85ea0`). **The `-c` options must precede the SUBCOMMAND.**
Verified: `git branch -r --contains 5cda85ea0` -> origin/main, remote blobs grep
8/8 learner + 8/8 store + 4/4 test, LF-normalized md5 remote == local.
Post-fix live: 3 x `--once` -> 1 learned / 2 rejected; the learned row is real
prose (`$1,600, $2,500, even $5,000+ ...`) with `writer=False extract=False`, the
rejections are honest and both censuses read **0 of 288**.


## Root cause AY (live 19.09.26) — FIVE chrome classes in ONE cron run (81-85), the "post-fix cycle makes the next leak" loop, and the CLASS-NUMBER collision trap

Cron run began with the documented `cycle_g_security: rejected` line. Rate check:
per-day **39.5 % (15 ok / 23 rej)** vs the documented 50-80 % band -> **no gate
change was warranted for the rejection itself**; `buffer_junk` last 8 =
`duplicate` at the 288/300 cap + documented junk shapes (`Self-critique:` echo,
SERP `... - <date> · ...`) = rotation noise. U/V verified BEFORE inventing
anything: `_search_urls(q, k=6)` -> 6,6,6,6,6 on five diverse queries;
`_fair_share_window` -> 4000 chars / 5 slices; buffer size byte-stable.
Working tree `scripts/training` + `tests/scripts`: the only dirty files were
FOREIGN (`active_learn.py`, `tool_server.py`, ...), NOT the two gate modules ->
no uncommitted predecessor work in my lanes (the AV trap, checked first).

All five finds came from the prescribed cheapest method: run `--once`, read the
BUFFER TAIL `u`/`a`, repeat after each fix. **Every single leak was created by a
POST-FIX live cycle** (the AP/AS/AU lesson, now certain): the buffer was clean at
entry, and each fix was followed by 3-4 more `--once` runs that produced the
NEXT class. Five classes needed ~15 `--once` runs in one session.

| class | helper | measured |
|---|---|---|
| 81 | `_is_institution_abstract_tail_chrome` -- institution label AND a bare abstract ORDINAL welded at the TAIL | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 82 | `_is_trending_card_header_pair` -- `This Week Last Update: <n> days ago` + `See Project <n>`, single space between | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 83 | `_is_aggregator_row_year_tail` -- a feed row's `<rel-time> | N comments` AND the arXiv `(yyyy)` tail within 80 chars | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 84 | `_is_pipe_byline_shares_header` -- byline AND a PIPE dateline AND the bare `Shares` token | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 85 | `_is_portal_counter_bar_comparison` -- `Instant <dd-Mon-yyyy> <n> <n> <Category>` AND `Complete Comparison` within 120 chars | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |

### THE TRAP THAT COST THE MOST: class NUMBERS are not reserved across sessions
My first two helpers were labelled **class 77** and **class 78** -- and the
SAME-DAY predecessor run (commit `5cda85ea0`) had already shipped classes 77-80
(`_is_advisory_row`, `_is_site_headline_stub`, `_is_fact_box_label_chain`,
`_is_own_plan_plus_run`). The collision only surfaced when grepping the module:

    grep -n "^# class 7[0-9] markers" scripts/training/internet_learner.py

Fix was a comment/docstring-only renumber commit (77->81, 78->82) across all
three code copies AND all three test copies. **Before numbering a new class,
grep the module for `# class NN markers`** -- a parallel or predecessor session
can have taken the number, and a silent collision sends the next session hunting
a duplicate that does not exist. (The archive has the SAME shape: root cause AW
claims 77-80; the numbers are a naming convention only, not a registry.)

### Class 81 -- the PAIR at the TAIL, and "check the existing helper's SHAPE"
`cycle_h_efficiency` stored
`Language-model groups overstate consensus when replaying human deliberation on a
reasoning task Waseda University Abstract 9.` -- 125 chars WITH digits, so the
length trust AND the technical-signal gate both fired. Existing helpers all
False: `_is_arxiv_abstract_chrome` needs the viewer labels (`View PDF` /
`HTML (experimental)`), `_is_nav_list` wants >=6 TitleCase tokens with no comma,
the byline family is English-keyed on `By <Name>` / `Published` / `Share`.
Sweep: the bare `Abstract <n>.` TAIL alone measured 1-2 control FPs
(`The paper is summarized in Abstract 9.`), the institution label without the
TAIL period measured 1 (`The Laboratory Abstract 5 was rejected by the
reviewers.`). Only the anchored PAIR (`(?:University|...|School)\s+Abstract\s+\d{1,3}\s*\.\s*$`) reached 0/29 hostile controls. A 6-caps-word prefix
variant measured **0 buffer hits** (too narrow) -- do not over-specify.
Pre/post `_clean_insight` diff on 29 controls: **0 diffs**.

### Class 82 -- the WELD, not the labels
Post-fix `cycle_c_github` stored a trending card header welded onto the repo
description: `This Week Last Update: 2 days ago See Project 2 OpenManus ...`.
Every repo-listing helper was False by design: `_is_trending_repo_row_chrome`
wants the star counter + a language stat, `_is_repo_stat_footer_run` wants a
commits/branches/tags footer, `_is_gh_listing_row` wants `Updated <Mon DD, YYYY>`
+ `Public Forked`.
**My hand-written hostile controls were themselves widget-shaped** and produced
5-6 "FPs" (`This week last update was 2 days ago. See project 2 for the
benchmark.`) -- i.e. the harness was reporting the INTENDED behaviour. Rewriting
them as NATURAL prose (`This week's last update to the repo was 2 days ago, so
the fix is fresh.`) took every variant to 0. The AJ/AN/AQ/AU/AV control-corpus
rule again: a control that IS the chrome shape is asserted as a leak, never
listed in the false-positive set.
Shipped form is the exact WELD with a single space between the halves
(`...days?\s+ago\s+see\s+project\s+\d{1,3}`); punctuation between the halves
means prose.

### Class 83 -- a SINGLE occurrence is deliberately NOT gated (class 37 boundary)
Post-fix `cycle_b_papers` stored `CameronBanga 5 hours ago | 10 comments 58
Cache-to-Cache: Direct Semantic Communication Between LLMs (2025) (arxiv.` --
only 115 chars. `_is_hn_item_chrome` / `_is_hn_feed_listing_chrome` (classes
37/49) both returned False because they require the unit to REPEAT (>=2).
**The single-unit marker measured 4-9 control FPs** at every unit spelling --
including class 37's OWN clean control `The review took 2 days ago | 4 comments
per reviewer were recorded.`, which the existing test asserts must stay
learnable. So the AU rule applied: the threshold could not be lowered without
FPs, therefore the PATTERN was wrong -> add a second structural co-occurrence.
The arXiv `(yyyy)` tail within 80 chars of the feed unit reached 0 on all
corpora. **Verify explicitly that the old class's clean control stays
`is_junk == False`** after shipping -- the boundary is part of the contract.

### Class 84 -- third occurrence of "same vocabulary, different SHAPE"
Post-fix `cycle_f_multi_domain` stored a portal article header: brand chip +
headline + byline + **PIPE** dateline + the site's bare `Shares` glued to the
lede. `_is_news_byline_share_header` (class 51) already keys on `By <First>
<Last>` + a dateline + `Share` and STILL returned False -- it requires a full
WEEKDAY dateline; this page ships a pipe dateline. `_strip_byline_prefix`
(class 29) only strips a LEADING byline, and here the byline follows a brand
chip. Proven mechanically: the class-51 helper returns False on the leak AND the
pre-edit module's `_is_junk` returns False on it (the AQ/AR "attribute through
the PRE-EDIT module" step).

### Class 85 -- the CONJUNCTION again (AU rule, fourth occurrence)
Post-fix `cycle_g_security` stored `Instant 23-Aug-2026 0 207 Technology OpenAI
Workspace Agents vs Google Gemini Enterprise: Complete Comparison 2026 ...`.
Sweep that mattered, on a deliberately HOSTILE control set of recombinants:
| candidate | buffer | hostile FPs |
|---|---|---|
| `date + 2 counters + Category` | 1 | **4** (`The log line 23-Aug-2026 0 207 Technology was parsed by the tool.`) |
| `Instant + date + 2 counters + Category` | 1 | **2** (`Instant 23-Aug-2026 0 207 Technology is the scraped badge text.`) |
| `Instant + date` only | 1 | 2 |
| **`...Category` AND `Complete Comparison` within 120** | **1** | **0** |
| `...Category` AND `vs` within 120 | 1 | 0 (equivalent; the headline label shipped) |
| three-way (`+ '(yyyy)' + 'vs'`) | **0** | 0 (over-specified) |
Note the last row: adding a THIRD condition can make the rule MISS the leak
entirely -- sweep conjuncts in both directions, not only for FP reduction.

### THE DELIBERATE NON-FIX -- a truncated model output has no discriminator
Row 288 (`IFM Uno: Lossless LLM Speedup via Diffusion Adapter (2026) IFM
released Uno on Sep 17, 2026 - a diffusion adapter for autoregressive LLMs
delivering up to 2.`) is a generation truncated mid-number. A "text ends in a
digit + period" detector was considered and NOT shipped: the buffer holds
**20+** rows ending that way and they are legitimate (`--gpu-memory-utilization
0.`, `92.`, `Gemini 3.`). Same call as root cause AG and the model-hallucination
repetition row: **remove by signature only**. Do not gate "the output looks cut
off".

### Cleanup + verify (standard shape, all met, five passes)
Signature cleanups: 289 -> 288 (cls 81), 289 -> 288 (cls 82, after a post-fix
cycle had refilled to 289), 291 -> 290 (cls 83), 291 -> 289 (cls 84 + the
truncation row), 291 -> 290 (cls 85). Every step: `0 unparsable`, lone LF 0, CRLF
intact, **48** structural-connection rows preserved (the historical 53 -> 55 -> 48
drift continues; re-count, NEVER quote an old number), writer-gate and
learner-gate censuses **0**. 3-copy `md5sum` identical after EVERY apply
(`51666bdf/2390c8bc`, `3539bdb6/53e126f0`, `1b8c7f53/66d7fcc5`, `b0d110b8/d8ae047b`),
every copy `exec_module`-verified -- `ast.parse` is not enough (the `re` vs `_re`
alias and glued-paren traps).
`pytest tests/scripts/test_internet_learner_gate.py -q` -> **99 -> 100 -> 101 ->
102 -> 103 -> 104 passed** (5 new tests, each asserting the helper AND
`_is_junk` AND `_is_nav_chrome` AND `is_junk` AND `_clean_insight == ""` on the
leak(s) plus 12-18 prose counter-cases); `pytest tests/scripts -q` ->
**256 -> 257 -> 258 -> 259 -> 260 passed**. Every test appended as **pure bytes**
(`numstat` 0 removed each time, repo lone-LF census **58 -> 58**), mirrored to
both other test copies.
Commits `82e41ec62`, `244ed508b`, `d3e3ef5b6` (the renumber), `9981e58ae`,
`964dc639b`, `1e7c0843b` -- all on the foreign branch
`fix/28-respawn-test-psutil-hermetic`, `merge-base --is-ancestor origin/main
HEAD` -> **FF_SAFE** each round, `git push origin HEAD:main` with the `-c`
options BEFORE the subcommand. Verified each time with `git branch -r --contains
<sha>` -> `origin/main`, `git cat-file blob origin/main:<file> | grep -c <marker>`
-> 3/3, and the LF-normalized md5 (remote blob == local after `tr -d '\r'`).
**The push exit code alone is not proof.**
Post-fix live: 3 x `--once` -> 1 learned / 2 honest rejections; the last 3-row
census reads **0 of 290** on both gates.

### Session shape that worked (five classes, ~15 cycles, one session)
Per class, one pass: measure (buffer tail + hostile + NATURAL controls + junk +
episodes + test literals + pre-edit module diff) -> apply to BOTH gates in all
3 copies -> `exec_module` -> re-scan buffer -> DELETE the matching rows in the
same step -> pytest -> append test (pure bytes) + mirror -> commit -> push ->
verify -> 3 x `--once` -> read the buffer tail AGAIN (the next class is usually
already there).

## Root cause AW/AY follow-on — EIGHT chrome classes in ONE cron run (86-94, live 19.09.26)

Cron run began on the documented `cycle_e_competitors: rejected` line. The rate
check said **43.1 % for the partial day (25 ok / 33 rej) vs the documented
50-80 % band**, and per-hour was 40-52 % across the previous six hours -- a
regime-shaped band, not a step change -- so **no gate change was warranted for
the rejection itself**; `buffer_junk` last rows were `duplicate` + the
documented `Self-critique:` / plan-echo junk shapes = rotation noise. The entry
census read **0 / 0 (learner / writer)**: every one of the eight leaks was
created by a post-fix live cycle (the AP/AS/AU lesson, third+ occurrence).

All eight finds came from the prescribed cheapest method: read the BUFFER TAIL
`u`/`a` pairs, then scan the WHOLE buffer with a few broad heuristics
(`rel_time`, `share_word`, `views_word`, `min_read`, `updated`, a bare
`\d+\s+\d+\s+\d+` counter run, `( #N )`) and inspect every hit by hand.

| class | helper | measured |
|---|---|---|
| 86 | `_is_release_notes_pr_bullet` | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 87 | `_is_midtext_byline_counter_run` | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 88 | `_is_relative_time_counter_row` | 2 hits, BOTH the leak family / 0 FP / 0 le / 0 lit |
| 89 | `_is_project_count_news_tail` | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 90 | `_is_course_cta_opener` | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 92 | `_is_code_linenum_run` | 2 hits, BOTH the leak family / 0 FP / 0 le / 0 lit |
| 93 | `_is_share_exec_summary_header` | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |
| 94 | `_is_citation_counter_run` | 1 hit, IS the leak / 0 FP / 0 le / 0 lit |

(`le` = `longterm_episodes`, `lit` = string literals extracted from the gate test
file. Class 91 was probed and NOT needed -- see below.)

### THE POSITION TRAP, fourth occurrence (class 87) — check for a STRIP helper, not just a `_is_` helper
`_strip_byline_stack` (class 15, 16.09.26) exists for EXACTLY the class-87
vocabulary: `<Name> <date> <bare counters> Share`. It still returned the live row
unchanged, because it uses **`_BYLINE_STACK_RE.match()`** — it only fires when
the byline LEADS the text. Class 87 has a TitleCase **headline run** in front of
it, so `.match()` never lands. This is the same shape of gap as the class
29/40/51/84 byline family, but the tell is different: those were `_is_` helpers
keyed on a *different position token*; this one is a *strip* helper keyed on the
wrong ANCHOR (`match` vs `search`). **Grep for both `_strip_*` and `_is_*`
helpers covering the vocabulary before declaring a class new** — the module has
17 `_strip_*` helpers and they are easy to miss.

Corollary: class 15's own test literal
(`Simon Lermen Feb 24, 2026 54 5 8 Share TL;DR: ...`) still matches the
*loose* form of the class-87 regex. That is a FALSE positive on the test corpus,
not a bug: the loose form (without the headline run) was measured at **2 control
FPs** and REJECTED. Only the headline-run-prefixed form shipped, and it scores
**0 lit / 0 ctrlFP**. A test-corpus hit on a REJECTED variant is not a reason to
widen the shipped rule.

### THE SINGLE-PART TRAP, fourth occurrence: every bare candidate was measured and rejected
| class | rejected candidate | why |
|---|---|---|
| 86 | bare `\(\s*#\d{3,}\s*\)` | 1 control FP (`The patch ( #1234 ) was reverted after the regression report.`) + 3 episodes |
| 87 | loose byline form (no headline run) | 2 control FPs (`Authors: Smith Feb 3, 2026 12 4 9 Share the findings in the appendix.`) |
| 88 | bare relative time `\d+ (min|hour)s? ago` | ordinary prose (`It ran 3 hours ago with 12 4 retries recorded in the log.`) |
| 89 | `N projects \| news.` WITHOUT the `$` anchor | mid-sentence prose (`We reviewed 3 projects \| news. and wrote summaries afterwards.`) |
| 90 | bare `Start this course` | 1 control FP (`Start this course to learn how agents work and how they fail in production.`) |
| 92 | bare digit run `1 2 3 4 5 6` | matches the docs PAGINATION chrome (a known leak) + prose (`` `1 2 3 4 5 6 # setup` ``) |
| 93 | `Share` alone / `Executive Summary` alone | ordinary English (`Readers can Share an Executive Summary with their team.`) |
| 94 | bare four-number run | matches a KNOWN leak literal and ordinary tabular prose |

**Rule restated: the discriminator is the CONJUNCTION / the WELD, never the
phrase.** Same as classes 58-63 (AS), 69/84/85.

### Class 91 — probed, measured, deliberately NOT shipped
`GHSA-... + Previous 1 2 3 Next` measured **1 buffer hit BUT `lit=1`** — the
literal is a gate-test counter-case that is **already asserted as junk** via the
pre-existing `_is_nav_list` rule (the test's own docstring says so: *"PRE-EXISTING
`_is_nav_list` rule rejects it (a different gate)"*). A candidate that hits a
test literal already pinned as a LEAK is a true positive, but shipping a marker
for a shape the repo already gates is redundant. Removed by signature only; no
code change. **Read the test literal's CONTEXT (assert-junk vs assert-clean)
before counting it as an FP.**

### Class 94's literal is a leak, verified the same way
The one literal class 94 matches
(`Onboarding Code Comprehension ... 1 2 3 4 5 6 7 8 9 10 11 Next ...`) sits in
the module-level `CHROME` list, which is iterated with
`assert IL._is_junk(text)` — i.e. a known LEAK, so the hit is a true positive.

### ALSO: a stale strip-helper leftover, not a new class
Row 188 (`Simon Lermen Feb 24, 2026 54 5 8 Share TL;DR: ...`) is present in the
buffer AND passes both gates — but `_strip_byline_stack`/`_clean_insight` handle
it (they strip the byline and keep the TL;DR). The stored `a` is the RAW form
because the row PREDATES the strip helper (class 15, 16.09.26). Exactly the AS
"stale buffer row is not a new class" precedent: **remove by signature, no code
change.** Before designing a helper for a gated-looking row, run
`_clean_insight(row)` and check whether it returns a CLEANED version — if it
does, the row is a pre-rule leftover.

### Cleanup + verify (the standard shape, all met)
Signature cleanups dropped all 10 rows in one pass: `291 -> 281` records, every
step `0 unparsable`, lone LF `0`, CRLF intact, **49** structural-connection rows
preserved (re-counted, not quoted -- this number has drifted 53 -> 55 -> 49
across sessions), writer-gate census **10 -> 0** and learner-gate census
**10 -> 0**. 3-copy `md5sum` identical for BOTH modules
(`e490fcffb040145915219484f11462eb` learner, `4dbf459fab4db7086ed94a5f03e8ce17`
store) and every module `exec_module`-verified (the `re` vs `_re` alias trap --
`ast.parse` was green the whole time).

Tests appended as **pure bytes** to all THREE test copies
(`230602 -> 240...` bytes, `10442` added, lone-LF census **58 -> 58** both, i.e.
no EOL churn). `pytest tests/scripts/test_internet_learner_gate.py -q` ->
**104 -> 112 passed**; `pytest tests/scripts -q` -> **268 passed**.
Commit `071ff9b3a`, `numstat` **239 / 0** and **239 / 0** and **211 / 0** (no
EOL churn anywhere). Branch was again `fix/28-respawn-test-psutil-hermetic`;
`git merge-base --is-ancestor origin/main HEAD` -> **FF_SAFE**, pushed
`HEAD:main` (`1e7c0843b..071ff9b3a`) with the `-c` options BEFORE the
subcommand. Verified `git branch -r --contains 071ff9b3a` -> `origin/main` AND
`git cat-file blob origin/main:<file> | grep -c <marker>` -> **3/3 for all eight
helpers** in both modules. **The push exit code alone is not proof.**

Post-fix live: 7 x `--once` -> 1 learned / 6 rejected; every rejection reason was
`duplicate` at the 281-282 cap or a documented `Self-critique:` / plan-echo
shape, the learned row is clean prose (LLaMA-2 benchmark dimensions), and the
census stays **0 / 0** at 282 records. **Read `buffer_junk` before calling a
rejection a regression** -- again.

### Mechanical trap that cost one round: normalizing anchors but not the file
The apply script compared LF-normalized anchors (`norm(anchor)`) against the RAW
CRLF file with `raw.count(...)` -> `helper anchor count 0` abort. The file is
pure CRLF (`internet_learner.py` 4502 lines, `buffer_store.py` 3108 lines, both
lone-LF 0). **Work entirely in LF space**: decode, assert
`raw.count("\n") == raw.count("\r\n")`, convert the WHOLE text once
(`text = raw.replace("\r\n","\n")`), do every count/replace there, and convert
back with `out.replace("\n","\r\n")` at the single write. Do not mix normalized
anchors with un-normalized text.

## Root cause AW (cont.) — class 95: a dated newsroom feed run welded to its own composite relative stamps (live 19.09.26)

Cron run began on the documented `cycle_e_competitors: rejected` line. Per-day
rate **39.4 % (26 ok / 40 rej)** for the partial day vs the documented 50–80 %
band -> no gate change was warranted for the rejection itself; `buffer_junk` tail
= `duplicate` at the 282 cap + documented `junk` shapes (`Self-critique:` echo,
plan-echo, `Need likely discuss ...`) = rotation noise. Writer-gate census at
entry **0 of 282**, learner-gate census **0 of 282**.

**The leak was created by a POST-FIX cycle** (the AP/AS/AU lesson again):
the 3rd `--once` after the previous commit stored

    "OpenAI is buying failed biotech trade secrets to train medical models
     3 days, 11 hours ago Salesforce built Koa to stop paying Anthropic and
     OpenAI millions 3 days, 12 hours ago Anthropic and OpenAI want an AI freeze."

217 chars WITH digits -> the `>=90` length trust AND the technical-signal gate
both fired; no existing marker matched. New helper
`_is_relative_stamp_news_run` (class 95), wired into BOTH gates in all 3 copies.

### Why every existing relative-time helper missed it
| helper | why it returned False |
|---|---|
| `_is_relative_time_nav_chain` (34) | needs the `For You / Latest / Trending` labels -- this page ships none |
| `_is_hn_feed_listing_chrome` (37) / `_is_hn_item_chrome` (49) / `_is_aggregator_row_year_tail` (83) | all key on a `\| N comments` unit -- this row has no comment counter |
| `_is_relative_time_counter_row` (88) | needs TWO bare counters after the stamp |
| `_REL_TIME_AGO_RE` (33/34) | `\d{1,3}\s+(minutes?\|hours?\|days?)\s+ago` -- **this is the POSITION/vocabulary gap, fifth occurrence**: it matches the *plain* stamp, not the *composite* `<n> days, <n> hours ago` |
| class-94 archive entry | the bare relative stamp was ALREADY probed and REJECTED: `\d+ (min\|hour)s? ago` is ordinary prose (`It ran 3 hours ago with 12 4 retries recorded in the log.`) |

### THE HARNESS TRAP that nearly shipped a topic word: `re.IGNORECASE` destroys a `[A-Z][a-z]` anchor
The rule's discriminator is the capitalised headline word after the stamp. My
first measurement pass evaluated every candidate with `re.findall(pat, t, re.I)`
-- which makes `[A-Z][a-z]` match **any** lowercase word, so all 13 control
strings scored `1`–`2` hits and the rule looked like a 100 %-FP topic word.
Re-measuring **case-sensitively** (no `re.I`) gave the correct picture:

| candidate (case-sensitive) | buffer | junk | le | lit | ctrl FP |
|---|---|---|---|---|---|
| bare relative stamp `\d+ (min\|hour)s? ago` | many | - | - | - | already REJECTED (class 94) |
| composite stamp, no capitalised word | 1 (=leak) | 0 | 0 | 0 | **4** declarative prose controls -> REJECTED |
| composite stamp `>=2` (count form) | 1 (=leak) | **1** | 0 | 0 | 2 -> REJECTED |
| `N days, N hours ago` + `[A-Z][a-z]`, `>=1` | 1 (=leak) | 0 | 0 | 0 | **1** (`Row A appeared 3 days, 11 hours ago Salesforce followed; ...`) |
| **same, `>=1`, REPEATED (the shipped form)** | **1 (=leak)** | **0** | **0** | **0** | **0 / 13** |

**So: if a candidate scores FPs on controls that are obviously NOT the shape
(`The migration finished 3 days, 11 hours ago and the report captured it.`), check
your `re` FLAGS before you check your pattern.** An `IGNORECASE` on a
case-anchored rule is a silent no-op discriminator -- same class of mistake as the
`re` vs `_re` alias trap and the `.match()` vs `.search()` trap, but it hides in
the PROBE, not in the module.

### The shipped rule (the AU conjunction rule, fifth confirmation)
`_RELATIVE_STAMP_NEWS_RUN_RE = re.compile(r"(?:\d{1,2}\s+days?,\s*\d{1,2}\s+hours?\s+ago\s+[A-Z][a-z])[\s\S]{0,80}?(?:\d{1,2}\s+days?,\s*\d{1,2}\s+hours?\s+ago\s+[A-Z][a-z])")`
-- the COMPOSITE stamp, the REPETITION (bounded 80-char window) and the
capitalised headline word must all hold. `len(t) > 1200` guard, no `re.I`.
Both copies use `re.compile` (learner) / `_re.compile` (store) -- build ONE block
per file, never one shared string.
The test deliberately documents the flag trap so the next session does not
re-introduce `re.IGNORECASE` (`assert not IL._is_relative_stamp_news_run(...)` on
11 prose controls incl. the class-83 `CameronBanga` row and the class-37
single-unit control).

### Cleanup + verify (the standard shape, all met)
Leak removed by signature -> **283 -> 282** records, `0 unparsable`, CRLF intact,
**49** structural-connection rows preserved, learner-gate census **1 -> 0** and
writer-gate census **1 -> 0**. 3-copy `md5sum` identical for BOTH modules
(`bded9e4a8a56aeedc66da17a8a9537f7` learner, `3808cc5fc2a3a58a8ed72f53bbf5f414`
store, then `576700b5...`/`9aada385...` after the LF-normalized remote verify) and
every one of the six files `exec_module`-verified (the `re` vs `_re` alias trap --
`ast.parse` was green the whole time).
Test appended as **pure bytes** to all THREE test copies (243,372 bytes each,
lone-LF census **58 -> 58** = no EOL churn; `numstat` 53/0, 53/0, 38/0).
`pytest tests/scripts/test_internet_learner_gate.py -q` -> **112 -> 113 passed**;
`pytest tests/scripts -q` -> **268 -> 269 passed**.
Commit `215386e1a` on the foreign branch `fix/28-respawn-test-psutil-hermetic`
(`merge-base --is-ancestor origin/main HEAD` -> FF_SAFE), pushed `HEAD:main`
(`071ff9b3a..215386e1a`, `-c` options BEFORE the subcommand). Verified:
`git branch -r --contains 215386e1a` -> `origin/main`,
`git cat-file blob origin/main:<file> | grep -c _is_relative_stamp_news_run`
-> **3 / 3**, test -> **1**, and the LF-normalized md5 (remote blob == local after
`tr -d '\r'`) MATCH for both modules. **The push exit code alone is not proof.**

Post-fix live: 3 x `--once` -> 1 rejected / 2 learned (real LLaMA fine-tuning
prose + a Space Colony agent-sim description); both new rows
`writer=False extract=False`, census **0 / 0** at 284 records.
**Read `buffer_junk` before calling a rejection a regression** -- again.



## Root cause AX — rate depression WITHOUT a gate regression: the gate was right, the deep-read URL selection was wrong (live 19.09.26)

Cron run began on the documented `cycle_g_security: rejected` line. Per-hour rate
was clearly down: `2026-09-19T02 ok=5 rej=14 rate=26.3%`, last-20 **25.0%**,
last-80 37.5% vs **all-time 76.6% (n=2017)** — the U/V signature — so U/V were
verified BEFORE inventing anything: `_search_urls(q, k=6)` → **6,6,6,6,6** on five
diverse queries and `_fair_share_window(5×4000, 4000)` → **5 slices / 800 chars
each**. Both intact → **no U/V regression**. `buffer_junk` last 160 =
`89 junk / 67 duplicate / 4 no-tech-signal`; of the 89 junk rows **40 were
SERP-shaped** (`… — <date>`, `… ; <next title>`) and 49 were the documented
`Self-critique:` echo / class-66 plan echo / model-degradation family.
**Rotation noise + an honest gate = no gate change warranted.** Same verdict as
root cause AI: rate analysis and leak-hunting are different jobs.

### THE NEW LESSON — do not read a depressed rate as a broken gate
The two live rejection drives are (a) the deep-read page being off-topic SERP
chrome and (b) `duplicate` at a buffer near its cap. Neither is fixable by a gate
edit (a gate change would either be a loosening — forbidden — or would eat real
prose). The actionable diagnosis order is:
1. per-hour table (a step change vs the 50–80% band, not the 7d aggregate);
2. `buffer_junk` reason MIX — a rising `junk` share with SERP-shaped `a` fields
   means the deep read is ranking search-result pages, not that the gate broke;
3. census BOTH gates over the whole buffer — if it reads **0 / 0**, the gates are
   NOT the problem and no class work is due.
If all three point that way, the correct output of the run is **a clean census +
a signature cleanup + the honest one-line report**, not a new marker.

### What the run DID fix — 4 stale model-degradation rows, gated-by-nobody ON PURPOSE
Buffer scan (short-`a` sweep) found four pre-existing fragments of the documented
un-gateable family (root cause AS: "no clean discriminator exists for the model
breaking down mid-generation — do not gate it"):

| idx | `a` | `u` |
|---|---|---|
| 280 | `These are older good launches.` | Structural connection between energy efficiency and system failure? |
| 32 | `This sounds agent reasoning?` | Structural connection between energy efficiency and system failure? |
| 214 | `Both are self-monitoring/optimization loops?` | Structural connection between energy efficiency and learning process? |
| 223 | `Sounds maybe quote from debugging?` | Structural connection between system failure and energy efficiency? |

All four measured `learner_junk=False writer=False store_is_junk=False` and are
**28–44 chars** — the `>=90` length trust never applied (class-33/65 precedent,
fourth occurrence: the trust is not the only way chrome gets in). Every candidate
discriminator is a topic-word or a normal interrogative (`Both are … loops?` is
ordinary English), so a marker here would be a false-positive factory.
**Removed by signature only, no code change** — same call as root cause AG and
the AS repetition row.

### Cleanup + verify (standard shape, all met)
Signature cleanup with the CRLF-split reader (`split("\r\n")`, never
`readlines()`), `assert len(drop) == 4` deliberately (it fired correctly), write
with `newline=""`/one record + CRLF: **285 → 281** records, `0 unparsable`,
**loneLF 0**, structural-connection rows **49 → 45**, writer census **0** and
learner census **0** after. Backup kept at
`online_buffer.jsonl.bak_cron20260919-030241`. (The historical "7 is the
baseline" and "53 structural rows" numbers have both decayed again — re-count
every time, never quote an old number.)

### Also re-confirmed
- The class-66 German plan echo (`KI-Performance-Optimierung: Python-Skript für
  RAM/Disk/Cron-Monitoring + Optimierungsvorschläge + Skill + Cron-Job alle 12h  2.`)
  is STILL alive in the junk stream and STILL correctly gated on both paths —
  no new work.
- The ticker row (`… The Economic Times Benchmarks CLOSED Nifty 23,346.`) is the
  class-AH leak reappearing in `buffer_junk` as `junk` — i.e. the marker added
  then is doing its job; it is NOT a new class.
- `git status --porcelain scripts/training tests/scripts` showed 6 modified files
  (`active_learn`, `knowledge_to_action`, `self_improve`, `smart_router`,
  `test_memory_consolidation`, `tool_server`) — inspected: all FOREIGN-cron edits
  (a `_training_dir()` fallback, `encoding="utf-8"` on opens), NOT unfinished gate
  work. The AV trap step still earns its place, but do not confuse foreign dirt
  with a previous run's gate fix: `git diff` for marker helpers
  (`_is_*_chrome`) before treating a dirty tree as incomplete work.
- `cycle_h_efficiency` took **355.9 s** (vs the usual 40–60 s) and still rejected.
  A single slow cycle is the deep-read falling through several fetch candidates,
  not a hang — the `--once` loop needs a >=400 s budget per cycle in this state.
