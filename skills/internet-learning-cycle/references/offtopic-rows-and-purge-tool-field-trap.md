# Off-topic rows, and the purge TOOL's own field trap (live 23.09.26)

Sibling of §1c (the store-KEY trap): that section covers reading a store on the
wrong KEY and getting a false zero. This file covers the **same failure shape one
level up** — the purge TOOL searching the wrong FIELD — plus a defect class that
no gate can ever catch because the poison is in the QUERY, not the stored text.

**Why this lives here and not in `internet-learner-stall-fix`:** that skill is
USER-OWNED, so autonomous curator writes to it are refused. The two root causes
below (155/156 in that skill's numbering) were recorded there during the working
session; this file is the curator-managed mirror. If you need to edit the archive
yourself, the user must run `openamer curator adopt internet-learner-stall-fix`.

## 1. The purge tool searched only ONE field — and printed a reassuring lie

`purge_buffer_rows.py` (in `training-scripts-hygiene`) dropped rows by signature.
It defaulted to `--text-key a`, i.e. the ASSISTANT side only. A buffer row has
**two** text fields — `u` (user side: seed + generated query) and `a` (the
learned text) — so a signature living in `u` matched NOTHING and the script
printed:

    [purge] nothing to drop -- if you expected a hit, the signature is wrong,
            not the buffer.

**That message was a LIE whenever the signature was in `u`.** Live: the row
`Multi-domain learning (neural duhmer: how to implement duhmer's duhmer in
python): …` was still present, the dry run said `keep 300 / drop 0`, and a direct
`grep` of the raw file showed `duhmer rows 1`. The probe was wrong, not the file.

**FIXED:** the default is now ALL text fields (`u` AND `a`), each drop prints the
matched field (`DROP 1: [u] …`), and the no-hit message names the fields actually
searched. `--text-key` still forces a single field.

**The transferable rule: a dry run that disagrees with a direct `grep` of the raw
file means the PROBE is wrong, not the file.** Never conclude "nothing to drop"
from one field of a two-field row — and never accept a tool's "the signature is
wrong" message as a finding about your data.

## 2. Class 156 — a HALLUCINATED LLM query stored OFF-TOPIC (no gate can catch it)

`cycle_f_multi_domain` learned an unrelated lesson because `_llm_novel_query`
returned nonsense:

    q = "neural duhmer: how to implement duhmer's duhmer in python"
    stored a: 'Creating labels y = [[ 1 , 0 , 0 ], ... ] Step 2 : Visualizing the
               Dataset ... use Matplotlib to plot the images for each letter.'

The stored sentence is **ordinary code-tutorial prose**, so `_is_junk` is
*correct* to pass it. The poison is upstream, in the query generator. The row is
off-topic in the LoRA set.

**Why the obvious marker fails:** the garbled term is not a literal you can list
(`duhmer` today, anything tomorrow). A lexicon-free shape is needed.

**Measured candidate — REJECTED:** "a long token repeated >= 2x" fires on **53 of
800** recorded seen-queries, most of them legitimate NEWS HEADLINES ("AI Regex
Scientist: A Self-Improving Regex Solver", "Agent Memory in Portia AI's
Open-Source Agent Framework"). The learner's real headlines repeat common words,
so the rule is unusable.

**Consequence: do not auto-synthesise a rule from ONE leak.** Purge the row,
document the defect, and leave `_llm_novel_query` unchanged until a second
instance of the shape appears. **Count first, patch second** — and note this is
the same standing as root cause AG and §1b's avoid-window: generator-side work is
an architecture change, proposed not landed on a single observation.

**Where the next instance will be visible:** the bad query also landed in
`.il_seen_queries` (800 rows). The query LOG, not only `online_buffer.jsonl`, is
where a generator defect shows up — audit both when a row looks off-topic but
passes every gate (`scripts/query_ledger_audit.py`, §1b).

### Distinguishing this from the usual off-topic row

The ordinary off-topic row (`"The apartment has about 2,000 square feet
indoors…"`, class 43's session) is a **deep-read acceptance** — the page was
wrong for the query. That is handled by the dropper, never a pattern. This class
is different and worth naming separately: the QUERY ITSELF is garbage, so the
search legitimately returned *something* related to a nonsense term. Check the
`u` field first — if the query is nonsense, no stored-text gate was ever going to
help.

## 3. Class 155 — a raw vLLM server LOG LINE stored as knowledge (same session)

    u: Best practice from official docs: vLLM v2.12.0 kv_cache_prefill_prefetch
    a: 'Using max model len 98304 (APIServer pid=90) INFO 11-28 11:46:45 [scheduler.'

Chrome truncated mid-token; the digits fed the technical-signal gate and a 76-char
row cleared the length check. Markers added to BOTH gates: `apiserver pid=`,
`\[scheduler\.`, `\binfo \d{1,2}-\d{1,2} \d{1,2}:\d{2}:\d{2} `. Measured and
REJECTED: bare `\bpid=\d+` (1 episode FP) and `max model len` (topic-word trap).

**Quote the DELTA, not the absolute.** The whole `buffer_store.is_junk` flags
**422 of 3,064** episodes on this corpus, so a raw junk count proves nothing.
Isolate YOUR markers before claiming 0 collateral.

## 4. Two process traps this session paid for

**Class numbers collide across files.** Numbers live in the code comments
(`class N`), the test fixtures (`_IL<N>_`), AND `root-causes-archive.md`
(`## Root cause N`), each numbering independently. This class was first written as
150 — already used in the archive for an unrelated topic — and its archive max was
154. **Derive the next free number from ALL sources** (`max()` over the archive's
headings *and* a grep for `class N` in the modules) before writing one.

**The skill/reference files are a TWO-WAY mirror, like `scripts/training/`.** The
older `openamer-agent` tree's `SKILL.md` carried ONE line the live copy did not
(the 143/144 script-side note) and its archive was ~30 KB behind. A whole-file
`copy2` would have DELETED that unique line. Sync **additively** — anchor-insert
new pointer lines, append new archive entries — then assert the unique line still
survives. These files are LF-native: assert `b"\r\n" not in blob` before and after
every write.

## 5. A KNOWN off-topic family recurring is a PURGE check, not a gate fix (12.10.26)

`cycle_b_papers` and `cycle_g_security` stored the class-160/AG off-topic pairs
again on 12.10.26:

    u = "…Hardware Acceleration of LLMs: A comprehensive survey and comparison"
    a = "In 1936, Alan Turing developed the concept of the universal Turing machine…"
    u = "Security learning (… model weight backdoor detection best practices 2026)…"
    a = "OpenAI's GPT-6.1 model achieves 100% accuracy on the GSM8K math benchmark…"

Mechanism: `is_off_topic_page(query, page)` KEEPS a page when ANY query topic token
appears, and GENERIC academic/publishing words (`survey`, `comparison`,
`comprehensive`, `model`, `review`, `analysis`) are **not** in `_TOPIC_STOPWORDS`,
so a history-of-computing page that merely says "survey" passes the filter and the
PRIMARY deterministic extractor stores its Turing sentence.

**Do NOT re-fix the gate on a recurrence.** Both rows were already purged and
archived as `offtopic_pair_*` in `buffer_junk_archive.jsonl`. The cheap, honest
check is a grep of the STORE for the leak's distinctive strings:

```bash
grep -c "Turing" scripts/training/online_buffer.jsonl              # -> 0  (purged)
grep -c "GPT-6.1" scripts/training/online_buffer.jsonl             # -> 0  (purged)
grep -c "offtopic_pair" scripts/training/buffer_junk_archive.jsonl # -> 2 (archived)
```

0 hits in the store **plus** the audit copies present ⇒ the cycle is clean and the
run reports the recurrence as *handled*, not as a new leak. The candidate fix (add
the generic academic words to `_TOPIC_STOPWORDS`) stays **NOT SHIPPED**: dropping
tokens can DISABLE the off-topic check for queries whose only tokens were generic
(`tq < _OFF_TOPIC_MIN_TOKENS`), so it needs a real (query, page) FP sweep and a
`tq < 2` guard before it can be proven. Full mechanism + proof gates:
the USER-OWNED `internet-learner-stall-fix` archive (class 160/AG) — this file is
its curator-managed mirror.

## 6. The `foorilla` off-topic family -- a GitHub-trending spam blurb stored 3x (13.10.26)

`cycle_c_github` stored a media/hiring-tool blurb under the FIXED template query
`What new agent architectures are trending on GitHub?`. A grep of the STORE found
THREE copies (older sibling rows), all off-topic, all accepted by both gates:

    u = "What new agent architectures are trending on GitHub?"
    a = "foorilla's hiring process is built on a foundation of automated workflows, ..."
        "foorilla's hiring media code is a key driver of the platform's performance, ..."
        "foorilla foo is a tool for automating the process of finding and managing media ..."

Mechanism: the query template's own token `GitHub` IS a query topic token and the
spam repo's description carries generic automation vocabulary, so a repo blurb
clears `is_off_topic_page` -- the class-160/AG dilution shape one level UP, in
the source ranking rather than in the page text.

Handled as section 5 prescribes -- a PURGE check, NOT a gate fix:

    python ".../purge_buffer_rows.py" --sig "foorilla"            # dry: keep 297 / drop 3
    python ".../purge_buffer_rows.py" --sig "foorilla" --apply    # 300 -> 297, .bak written
    grep -c foorilla scripts/training/online_buffer.jsonl           # -> 0
    grep -c foorilla memory/longterm_episodes.jsonl                 # -> 0 of 8008 (never leaked)

Rows archived as `offtopic_pair_foorilla_{hiring_workflows,hiring_media_code,media_tool}`
in `buffer_junk_archive.jsonl` (CRLF-native: 326 -> 329 rows, lone LF 0 -> 0). The
4 pre-existing `buffer_junk.jsonl` hits for this family are ALL `reason=duplicate`
-- the family was already STORED and later attempts collided, which is why a
STORE grep (not the junk log) is what finds it.

Do NOT gate the vendor literal: `foorilla` will not generalise (class-138 rule)
and it is one source's spam -- purge on sight.

## 7. Decision recipe for ANY suspicious family -> `references/buffer-family-triage.md`

Sections 1-6 name the mechanisms and the individual cases; the *recipe* (count the
signature across `online_buffer.jsonl` + `buffer_junk.jsonl` +
`longterm_episodes.jsonl` in ONE Python pass, read the junk `reason`, then pick
purge / gate-candidate / leave) now lives in
`references/buffer-family-triage.md`. Two verdicts worth repeating here:

- **Recurring KNOWN off-topic family -> PURGE + archive, never a gate** (§5 rule,
  §6 exemplar). The junk log cannot see a family that was already STORED: its hits
  come back `reason=duplicate`, so only a STORE grep finds it.
- **Same `a` under several different `u` -> LEAVE THE ROWS** (13.10.26: a PEFT
  docs code block sat 3x, `Output: trainable params: … || all params: … ||
  trainable%: 0.062%`, plus 7 `reason=duplicate` refusals). It is ON-topic docs
  content and an `a`-keyed near-duplicate rule is MEASURED-AND-REJECTED — report
  the observation, do not purge, do not re-litigate.

Count with ONE Python pass: a multi-part shell `for s in …; do … done` loop (with
`$( )` inside) is BLOCKED by this terminal's hardline parser.
