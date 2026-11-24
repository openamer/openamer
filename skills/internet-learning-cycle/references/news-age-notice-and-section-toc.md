# Classes 163–165: a publisher AGE NOTICE, a paper section-TOC chain, and a refuted quant-table rule

All three live 23.09.26, all three found by running a real `--once`, reading the
LAST buffer row, and asking "is this on-topic?". All three passed BOTH gates the
same way: **the number-fed hole** (`_TECH_HINT_RE`'s alternation *starts* with
`\d+`, so a date, a version or a byte count counts as "technical signal") plus the
≥90-char long-prose trust.

The sequence: a `--once` stored the Guardian row (163) → the fix for it was
verified with another `--once` which stored the arXiv row (164) → the fix for
that was verified with a third `--once` which stored the quantization table
(165). **Each fix exposed the next leak; that cascade is the norm.**

---

## Class 163 — a publisher AGE NOTICE welded to its content-label pair (STRIP)

### The live row (verbatim, 300 chars, truncated by the extractor)

```
I violated every principle I was given’ This article is more than 4 months old
PocketOS was left scrambling after a rogue AI agent deleted swaths of code
underpinning its business Supported by About this content Sanya Mansoor Thu 30
Apr 2026 00.12 CEST Last modified on Wed 17 Jun 2026 11.55 CEST Sha
```

Structure, in order: a **pull-quote weld** (`I violated every principle I was
given’`), the publisher's **staleness notice**, the **LEDE** (real knowledge),
the site's **`Supported by About this content`** affordance, then the
byline/dateline block.

### Why both gates passed it

- the dates (`30 Apr 2026`, `00.12 CEST`, `17 Jun 2026 11.55`) feed
  `_TECH_HINT_RE`, whose alternation STARTS with `\d+`;
- 300 chars clears the ≥90 "long prose is trusted" rule;
- `_is_article_byline_chrome` (class 142) does not fire: it needs an *affordance*
  from `_ARTICLE_BYLINE_AFFORDANCE_RE` (`Written by`, `min read`, `Key
  Takeaways`, …) and this page ships none of them.

### Candidate measurements

Corpora (any one can veto): `online_buffer` 300 · `buffer_junk` 9,351 ·
`internet_learn_log` 2,751 · `longterm_episodes` 3,065 · asserted gate-test
literals 2,167 · every `.md`/`.txt` under the repo + the live skills tree
(7,362 long-form chunks).

| candidate | leak | buffer | junk | log | ep | lit | docs | prose FP |
|---|---|---|---|---|---|---|---|---|
| bare age notice | ✔ | 1 | 0 | 0 | 0 | 0 | 0 | **2** |
| bare `About this content` | ✔ | 1 | 0 | 0 | 0 | 0 | 0 | **1** |
| bare `Last modified on` | ✔ | 1 | 0 | 0 | 0 | 0 | 0 | **1** |
| bare `Supported by` | ✔ | 2 | 0 | 0 | 0 | **1** | 0 | 0 |
| age + `(About this content\|Last modified on)` | ✔ | 1 | 0 | 0 | 0 | 0 | 0 | **1** |
| **age + `Supported by About this content`** | ✔ | **1** | **0** | **0** | **0** | **0** | **0** | **0** |

The two killer prose FPs:

```
This article is more than 4 months old, so the benchmark numbers it quotes are
stale and the 2026 revision should be cited instead.
```
```
This article is more than 4 months old, so we re-measured it; the About this
content label the site renders is page furniture, and the 8-bit run stayed
within one point of fp16.
```

The second one is why the **wider** conjunction is the trap and not the safe
choice — it carries both halves inside ONE genuine sentence. The gate-test
literal that kills bare `Supported by`:

```
Tool calling and reasoning parsers are supported by the server.
```

### The shipped guard

```python
_NEWS_AGE_NOTICE_RE = re.compile(r"This article is more than \d+ (?:months?|years?|days?) old\b")
_NEWS_AGE_LABEL_RE  = re.compile(r"Supported by\s+About this content")
_NEWS_AGE_REGION    = 300
```

`_news_age_notice_span()` returns `(end_of_notice, start_of_label)` when both
markers fall inside the header window, else `None`. `_is_news_age_notice()` is
the REJECT predicate in both `internet_learner._is_junk` and
`buffer_store.is_junk`; `_strip_news_age_notice()` rescues the body.

**STRIP, not reject** — the lede is the knowledge. The strip is wired in three
places, and all three are needed:

1. `_clean_insight`'s transformation chain (so a row that reaches it is judged on
   the rescued text);
2. `store()`'s rescue block — because `_is_junk()` is evaluated on the **RAW**
   insight, the strip inside `_clean_insight` is otherwise unreachable (the
   class-142 follow-up pattern);
3. `buffer_store.is_junk` as the raw-form reject predicate, so every writer path
   agrees.

Measured on the live module: leak → `learner _is_junk True`, `writer is_junk
True`, strip → `PocketOS was left scrambling after a rogue AI agent deleted
swaths of code underpinning its business` (a pristine slice, 100 chars), and that
body is `False` on both gates and passes `_clean_insight` unchanged. End-to-end
`store()` on the leak writes the LEDE, not the chrome, to a temp buffer.

### Whitespace caveat (the class-11 trap, re-confirmed)

Only re-normalise whitespace when something was actually removed. A first probe
that re-stripped every row reported **2 touched** rows where only 1 was chrome
(`Qwen3-8B · H100 80GB · FP8 ISL=8192 …` changed purely by a trailing-space
collapse). The shipped strip returns `text` untouched when there is no notice.

---

## Class 164 — a paper page's section-TOC chain + `Download PDF` (REJECT)

### The live row (verbatim, 300 chars)

```
Report Issue Back to Abstract Download PDF Abstract 1 Introduction 2
DeepSeek-R1-Zero 2.1 Group Relative Policy Optimization 2.2 Reward Design 2.3
Incentivize Reasoning Capability in LLMs 3 DeepSeek-R1 3.1 Model-based Rewards
Helpful Reward Model Safety Reward Model 3.2 Training Details 3.2.1 Traini
```

An arXiv/paper page's own section listing welded to its PDF button, truncated
mid-word. Same family as classes 23/24/25 — **a listing is a label chain, a
sentence has grammar.**

### Candidate measurements

| candidate | leak | buffer | junk | log | ep | lit | docs | FP |
|---|---|---|---|---|---|---|---|---|
| numbered chain `N.N <Title>` alone | ✔ | 1 | 0 | 0 | **4** | 0 | 0 | 0 |
| `≥6 N.N pairs` | ✗ | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `≥6 pairs AND no finite verb` | ✗ | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| **`Download PDF` AND `≥3 N.N pairs`** | ✔ | **1** | **0** | **0** | **0** | **0** | **0** | **0** |

The chain alone dies on **4 real `longterm_episodes` rows**, e.g.
`Section 2 introduces the policy optimization, Section 3 covers training and 3.1
lists the reward models.` The `no finite verb` variant misses the leak because
`Download` reads as a verb. Threshold is stable for 2–5 pairs; 3 is chosen.

**Adversarial near-misses (7, all survive):** each carries BOTH a `Download PDF`
affordance AND version/section numbers inside a sentence, e.g. *"Download the PDF
of the report; it covers vLLM 0.13 and 12.4 CUDA, with section 3.1 on paged
attention."* and *"The docs page has a Download PDF button, and the release notes
list 0.13 Streaming Output and 0.9 KV-cache reuse."*

### The shipped guard

```python
_TOC_CHAIN_RE       = re.compile(r"\b\d+\.\d+\s+[A-Z][A-Za-z-]*")
_PDF_AFFORDANCE_RE  = re.compile(r"\bDownload\s+PDF\b")

def _is_section_toc_chain(text, min_chain=3):
    t = text or ""
    if not _PDF_AFFORDANCE_RE.search(t):
        return False
    return len(_TOC_CHAIN_RE.findall(t)) >= min_chain
```

Mirrored in `buffer_store` as `_is_section_toc_chain` using `_re` (the writer
module has **no bare `re`**).

---

## Class 165 — a quantization TABLE label chain (OBSERVED, UNGUARDED)

### The live row (verbatim)

```
B) 1B 3B 7B 13B 30B 70B 175B Quantization: FP32 (32-bit) FP16 (16-bit) BF16
(16-bit) INT8 (8-bit) INT4 (4-bit) Estimated Model Size: 13.04 GB Approximate
VRAM Requirements: Batch Size 1 19.56 GB Batch Size 8 52.15 GB Batch Size 32
130.39 GB Note: Memory requirements are approximate and include addit
```

Same family as class 43 (benchmark metric-table rows): **a table row is a label
block with no sentence.**

### Measured and REFUTED — do not ship these

| candidate | leak | verdict |
|---|---|---|
| `≥3` PREC tokens ∧ `≥3` size tokens ∧ no finite verb | ✗ | misses the leak (`Download`-style verb reads) |
| `≥3` / `≥4` `PREC (N-bit)` pairs ∧ no function word | ✗ | misses the leak |
| `≥5` bare PREC tokens ∧ no function word | ✗ | misses the leak, 1 docs hit |
| `≥4` `PREC (N-bit)` pairs | ✔ | **1 hostile prose FP** |
| **`≥5` `PREC (N-bit)` pairs** | ✔ | **3 hostile prose FPs — REFUTED** |
| `≥6` `PREC (N-bit)` pairs | ✗ | loses the leak, still 2 hostile FPs |

The three prose FPs that kill `≥5` (all genuine knowledge statements):

```
The config exposes FP32 (32-bit), FP16 (16-bit), BF16 (16-bit), INT8 (8-bit) and
INT4 (4-bit) modes, and we benchmarked all five on the same device.
Our exporter supports FP32 (32-bit), FP16 (16-bit), BF16 (16-bit), FP8 (8-bit),
INT8 (8-bit) and INT4 (4-bit); the INT4 (4-bit) build is 4x smaller …
Choose between FP32 (32-bit), FP16 (16-bit), BF16 (16-bit), INT8 (8-bit) or INT4
(4-bit) depending on your VRAM budget, because INT4 (4-bit) needs the least.
```

**No clean marker found in this session.** The class is recorded as *observed,
unguarded*; the row was dropped with
`_drop_offtopic_row.py "FP32 (32-bit) FP16 (16-bit) BF16 (16-bit)"`
(`rows=300 dropped=1 kept=299`). A future session should look for a **structural**
discriminator (e.g. the table's own `Estimated … :` label pair plus a
`Batch Size N` run) rather than another count threshold.

---

## Class 166 — a repo-listing row's `<N><unit>agorelease` badge weld (REJECT)

### The live row (verbatim, 300 chars)

```
Latest AI Resources - ANUS: An Open Source AI Framework for Task Automation and
Multi-Agent Collaboration ANUS: An Open Source AI Framework for Task Automation
and Multi-Agent Collaboration Latest AI Resources 2yrs agorelease AI Sharing
Circle 101.9K 0 0 General Introduction ANUS (Advanced Neural Un
```

A GitHub-trending listing row: the card TITLE restated twice, the site label, the
`2yrs ago` + `release` badge **concatenated**, the feed counters (`101.9K 0 0`),
and a truncated description. Same family as classes 63/95 (listing rows).
Found by the **sixth** `--once` of this session — the cycle run to verify
class 164. Found the cheap way again: read the LAST buffer row.

### Candidate measurements

| candidate | leak | buffer | junk | log | ep | lit | docs | prose FP |
|---|---|---|---|---|---|---|---|---|
| loose `<n> <unit> ago release` (space allowed) | ✔ | 1 | 0 | 0 | 0 | 0 | 0 | **3** |
| **strict `<n><unit>agorelease` (no space)** | ✔ | **1** | **0** | **0** | **0** | **0** | **0** | **1** |
| age + bare counter triple `N N N` | ✗ | 0 | **2** | 0 | 0 | 0 | **2** | 0 |
| title-repeat(≥6 words) + age | ✗ | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

**The missing SPACE is the discriminator** — the class-9 `-->` argument once
more: key on markup that human prose cannot produce. A sentence writes
`<n> years ago` and, if it names a release, separates the words. The loose form
hits real prose:

```
2yrs ago release was announced in the changelog, and the 1.4 build followed a week later.
The model card was updated 6 months ago release notes say the int4 build lost 0.9 points.
```

The single remaining strict-form hit is the **meta control** — a fixture that
merely QUOTES the badge (`ExampleRepo 2yrs agorelease`). That string IS the chrome
the gate targets, so refusing it is correct. The honest fix was to rephrase the
control as a real sentence ABOUT the row, never to loosen the pattern. Same trap
as class 28's `subscribe` counter-case.

### The shipped guard

```python
_AGO_RELEASE_WELD_RE = re.compile(
    r"\b\d+\s*(?:yrs?|years?|months?|days?|hrs?|hours?|mins?)\s*agorelease\b",
    re.IGNORECASE)

def _is_ago_release_badge_weld(text):
    return bool(_AGO_RELEASE_WELD_RE.search(text or ""))
```

REJECT, not strip — a listing has no prose to rescue. Mirrored in `buffer_store`
with `_re`; pinned by `test_ago_release_badge_weld_is_gated_on_both_paths` and
`test_ago_release_badge_weld_requires_the_missing_space`. A seventh `--once` after
shipping reported an honest `rejected, not trained`.

**A gate-test test that touches the WRITER module must `import buffer_store`
INSIDE the test body.** The file has no module-level `BS` alias — a test written
against `BS.is_junk(...)` dies with `NameError: name 'BS' is not defined` at the
first assertion and never reaches the gate. Measured cost this session: one red
suite run. Copy the local-import pattern the existing writer-gate tests use.

---

## Probe hygiene, learned the hard way in this session

- **A backtracking regex in a throwaway probe hung past 400 s** over 9k junk rows
  (`(?:[A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,2}\s+){3,}[\s\S]{0,120}?…`). Bound every
  quantifier, and prefer counting `findall()` matches over nested
  `[\s\S]{0,n}` scans. The same run's simpler candidates finished in seconds.
- **Load the LIVE modules with `assert mod.__file__.endswith(filename)`.**
  `probe_marker_candidates.py --training-dir` needs the **native** path form
  (`C:/Users/...`) — an MSYS `/c/...` path is concatenated into
  `C:\c/Users/...` and the load dies with `FileNotFoundError`.
- **The fifth (long-form prose) corpus is what caught the `≥6 N.N pairs`
  variant**; the packaged four-corpus probe has no `.md`/`.txt` corpus, which is
  exactly where a count threshold misfires.
- **Delete every `_tmp_*.py` in the same turn** and confirm with a per-file
  existence loop (never a recursive `find`).

## Commit mechanics used (mixed-EOL repo)

- `internet_learner.py` and `buffer_store.py` carry lone LFs in HEAD (184);
  `tests/scripts/test_internet_learner_gate.py` is pure CRLF (0 lone LF). My
  inserts preserved each file's count exactly — asserted after every write
  (`loneLF before == after`, `b"\r\r" not in raw`).
- A **sibling cron** inserted a `_SITE_NAV_LABELS` block into `buffer_store.py`
  **mid-session** with LF-styled newlines: `new-lone-LF lines=43, EOL-flips=0`.
  `git diff --cached --numstat` and the same with `--ignore-cr-at-eol` returned
  **identical** counts, proving no whole-file CRLF flip; the foreign block rode
  along and is named in the commit message. Never `git checkout --` it.
- `git commit -F <file> -- <paths>` (options first, then `--`, then paths) —
  `git commit <paths> -m "…"` fails because `-m` is parsed as a pathspec.
- Heredoc into `/tmp` fails under git-bash (the file is not visible to `git`) —
  write the message with the file tool, then `git commit -F <that file>`.

## A PIPED command's exit code is the LAST stage's — it cannot verify a push

The most damaging mistake of this session, and it produced a **false success
claim** before it was caught:

```bash
git push origin HEAD 2>&1 | tail -6; echo "PUSH_EXIT=$?"   # WRONG
```

`$?` here is **`tail`'s** status, not `git`'s. It printed `PUSH_EXIT=0` while the
push had actually not landed (the network call exceeded the command timeout and
git was killed mid-transfer). The only thing that exposed it was checking the
remote ref independently:

```bash
git ls-remote origin refs/heads/<branch>     # still the OLD sha -> NOT pushed
git rev-list --left-right --count origin/<branch>...HEAD   # 0  2 -> 2 commits unpushed
```

**Rule: never conclude a network operation succeeded from a piped exit code.**
Redirect to a file and read the file's own status, or assert the remote state:

```bash
git push origin HEAD > /tmp/push.log 2>&1; echo "REAL_EXIT=$?"; tail -20 /tmp/push.log
```

and then verify with `git ls-remote` (or `git rev-list --left-right --count`).
Report a push as done only after the remote ref matches the local SHA. This is
the repo-local instance of the standing rule: *a count/metric/capability you have
not just measured does not exist.*

**Corollary for scheduled runs:** a `git push` on a slow link can exceed the
command timeout and be killed without a trace. Give it `background=true` with a
log file, or raise the timeout, and check the remote ref afterwards — a killed
push leaves no error text, only an unchanged remote.

