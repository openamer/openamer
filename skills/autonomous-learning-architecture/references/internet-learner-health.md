# Internet learner: measuring whether it is still learning

Measured 2026-10-10 on the live learner (2965 logged cycles). Four findings in
the order they should be checked. The learner's own skills are user-owned; the
durable technique belongs here.

---

## 1. The health metric already exists — `probe_rates.py`

Do not build another rate report. `scripts/training/probe_rates.py` prints all
four views, and defines `ok(r)` as
`"rejected" not in result and "no insight" not in result` — the predicate the
log's shape requires. Rows in `internet_learn_log.jsonl` are
`{ts, source, result, elapsed_s}`: there is **no `accepted` boolean**, a rejection
is the literal string
`"rejected, not trained (shallow + deep read both gated)"`, and an accept is
encoded as `<prefix>-learn: <text>` in the same field. Any check on
`r.get("accepted")` reports "0 accepts / learner is dead" on a healthy learner.

Live output that session:

```
per source (all time):   56 - 70 % per source
overall last 2965:       1890/2965 = 63.7 %
overall last  100:       35.0 %
overall last   60:       33.3 %
overall last   20:       30.0 %
overall last   10:        2/10  = 20.0 %
```

**Read the ladder, not one number.** A lifetime 64 % with the last ten at 20 % is
a trend; either figure alone misleads.

---

## 2. A uniform decline across ALL sources points at a shared component

| source | lifetime | last 300 |
|---|---|---|
| technews | 66 % | **33 %** |
| efficiency | 61 % | **35 %** |
| competitors | 67 % | **39 %** |
| github | 69 % | **47 %** |
| security | 67 % | **47 %** |
| papers | 67 % | **53 %** |
| docs | 73 % | **56 %** |
| multi_domain | 73 % | **58 %** |

**Eight independent sources, all down 15–20 points.** Content degradation cannot
look like that — a changed site layout or a dead feed moves *one* source. A
uniform drop means a **shared code path** (search, fetch, extraction, the store
gate) or a **systemic input condition** (§3). It tells you not to hunt
per-source.

---

## 3. `duplicate` dominating the rejections is arithmetic, not a bug

`scripts/training/buffer_junk.jsonl` is the store gate's own audit — rows are
`{a, reason, u}`. Histogram it before touching any gate:

```
{'duplicate': 5771, 'junk': 5256, 'writer-gate': 1137, 'pre-existing': 257,
 'no-tech-signal': 188, 'offtopic-drop': 36}
```

`duplicate` at ~46 % of all rejections is the dedup refusing an insight already
in the buffer. The cycles poll HN front-page headlines and a mostly-fixed query
set, and **the front page turns over slower than the poll rate** — so the same
story yields the same insight and is correctly refused.

**That is the input's economics, not a defect.** If a fix is wanted, the levers
are "poll less often" or "widen the source set", and both trade freshness for
novelty — a decision to report, not to make silently.

### The novelty ledger's capacity vs the rotation counter

```
.il_rotation        2994          # counter, incremented once per run
.il_seen_queries     800 lines    # trimmed to the last 800
                     143 unique   # 108 queries repeat; top ones 13x each
_recent_queries(n=60)             # what the novelty check actually reads
```

The counter long outgrew the window, and the window the check reads (60) is
smaller still — so a query used a few runs ago reads as novel again. These three
numbers are the ones to reconcile.

---

## 4. The `[INSIGHT]` extraction breaks with a thinking model — use `rsplit`

```python
if "[INSIGHT]" in content:
    content = content.split("[INSIGHT]", 1)[1].strip()     # FIRST marker
```

A thinking model writes the marker while *planning* ("I'll start with
`[INSIGHT]` …") before it writes the answer, so the first occurrence sits inside
the reasoning trace and the split returns **the rest of the trace** as the
insight. Live capture (`model=mini-openamer`, `routed_to=cloud`) began:

```
Here's a thinking process:

1.  **Analyze the User's Request:**
```

**Fix:** `content.rsplit("[INSIGHT]", 1)[1].strip()` — the final answer carries
the last marker. Two sites.

**Intermittent** — the router picks among several cloud models and a
non-thinking one returns a clean single-marker reply. One green call proves
nothing; a trace and a clean 77-char reply came from the same query minutes
apart. The Ollama fallback already used `rsplit("</think>", 1)` — the correct
pattern was in the file, applied to one marker and not the other.

---

## Isolation order that settled this (reuse it)

Search and fetch were healthy throughout — measure them before theorising about
the gate:

```
_search_urls(q, k=2)                    -> 2 URLs
_fetch_page(u) for each                 -> 6000 chars each
_is_news_index_page / is_off_topic_page -> False, False
deep_learn(q)                           -> ""            <- the failure is HERE
```

An extraction stage that returns `""` reaches that line only after the
deterministic sentence selection found nothing AND the cloud call produced
nothing usable AND the fallback produced nothing — so **measure the endpoints
directly** before concluding the model is down. Both answered (17 s cloud, 100 s
Ollama), and the 100 s figure is the useful one: a cycle completes in 50–60 s, so
it **never reaches the fallback**, which bounds where the fault can be.

**And do not edit `internet_learner.py` casually** — the Darwin autopilot rewrites
it, so re-read the file before every patch and confirm the change survived
afterwards. Also diff the copies: several exist, and a fix present in the repo
tree can be absent from the installed one that actually runs.
