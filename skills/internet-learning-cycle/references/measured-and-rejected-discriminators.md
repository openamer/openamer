# Measured-and-REJECTED discriminators — do not re-derive these

A candidate marker that looks perfectly precise on the training buffer can still
have a **legitimate** use in another corpus. This file is the counterpart to
`pending-candidates.md`: entries here were measured and **rejected on purpose**.
Never wire one. The point of recording them is that the next cron run does not
spend a cycle re-measuring the same idea.

The standing rule that falls out of every entry:

> **Scan a SECOND, semantically different corpus before wiring a marker.**
> The buffer is 300 rows and holds the leak by construction — it cannot tell you
> whether the shape is chrome. `memory/longterm_episodes.jsonl` (~8k rows of real,
> varied agent prose, key `text`) is where the false positive shows up. **One
> legitimate hit there kills the candidate.**

Corollary: the same probe against `scripts/training/buffer_junk.jsonl` (key `a`)
tells you whether an existing rule already covers the shape.

## REJECTED 2026-10-14 — `★` (U+2605) star glyph, and bare price tokens

**Shape seen** — one newly-stored `cycle_e_competitors` row in
`online_buffer.jsonl`, `len(a) = 215`:

```
u: Competitor intelligence: The secret recipe of powerful AI coding Agents
a: Engineers who want an agent to autonomously plan, edit across files and run
   tests on complex real-world work, and will pay for depth Pro $20/mo
   (annual $17); Max $100-$200/mo 2 OpenAI Codex ★★★★½ 4.
```

It reads like a pricing/review comparison-table run welded onto real prose — the
same family as class 169's intro-price-tier weld, and it passes BOTH gates.

**Measurement** (whole buffer + episode store, key `a` / `text`):

| corpus | `★` hits | verdict |
|---|---|---|
| `scripts/training/online_buffer.jsonl` (300 rows) | **1** | IS the leak |
| `memory/longterm_episodes.jsonl` (8,035 rows) | **1** | **legitimate** |

The single episode hit is real agent prose:

```
2026-10-10T09:47:40  kind=brain_assistant
"…**Hermes-Agent** — **233k★** ✓ confirmed…"
```

`★` is used in this domain as a GitHub **star-count** marker. A `★` gate would
delete real knowledge. 1 buffer hit / 1 real FP ⇒ **REJECTED**.

**Price tokens are already known-rejected** (class 169): price-alone and
`promo AND ANY price` both measured 2–8+ control FPs, and `$N/mo` already appears
**11×** in the gate test's own string literals. Do not re-propose them.

**Generalisation for this agent's corpora — glyph/symbol marks are a trap.**
`[✘✔]` was rejected earlier at 6 episode hits, and the assistant's OWN reports use
`★` and `✓` for star counts and checklist ticks, so they leak into `text` fields
legitimately. Prefer a bounded **conjunction of ASCII tokens** — *measure the
CONJUNCTION, not the phrase* (see `pending-candidates.md`).

## Operational — concurrent learner runs are NORMAL

- Cron job **`internet-learner-247`** (`cron/jobs.json`, `enabled: true`) runs
  `internet_learner.py --once` **every 5 minutes**.
- A manual `--once` loop therefore sees **foreign `cycle_*` lines** in
  `internet_learn_log.jsonl` that it did not produce. Measured 14.10.26: a
  `cycle_e_competitors` accept at `09:31:54` landed between two manual batches
  (my loop printed `f,g,h,a`; the log also had `e`). Never attribute a log line to
  your own loop without checking the timestamp, and never read the buffer census
  as "my run's output".
- This is also the documented **class-number collision** hazard: two writers can
  claim the same class number concurrently. Build any gate commit in a worktree off
  `origin/main`, and re-read the file before every patch.

## What a clean bill of health looks like for one cron run (14.10.26)

Nine `--once` cycles: **2 accepted, 7 rejected** — and the rejections were NOT a
regression. Evidence, cheapest-first:

1. **Search healthy** (root cause U/V absent): `il._search_urls(q, k=6)` →
   `6/6/6` on three diverse queries.
2. **Domain saturation** (root cause 128): `.il_seen_queries` = 800 entries but
   only **182 distinct**, top query repeated **13×** — the learner asks faster than
   the domain yields novelty (see the 5-minute cron above).
3. **Buffer at the cap** — 300 rows, `.il_rotation` = 3577. `buffer_junk.jsonl`
   last 40 reasons: `28 duplicate / 8 writer-gate / 3 junk / 1 no-tech-signal`.
   All documented shapes; the 8 `writer-gate` rows were uniformly SERP-shaped
   (`Title — snippet; Title — snippet`), i.e. correctly gated.
4. **Both gates over the WHOLE buffer**: `buffer_store._is_nav_chrome` flagged
   **0** rows ⇒ no chrome leak in the training data.
5. Repo tree clean for `scripts/training` + `tests/scripts`. The laptop copy being
   **ahead** of the repo is the delivered-but-unmerged classes 173–176
   (PRs #199, #200, #202, #203, #206, #207 open), **not drift** — check
   `git log --all --oneline -S "<marker>"` and `gh pr list` before "finishing" it.
6. Read the buffer **TAIL** regardless of the log line — a `learned` line is not
   proof of a clean row. Here 6/6 rows came back `writer=False extract=False`.

Verdict: rotation/saturation noise. **No gate change** — never wire a gate on a
rejection alone (measured-and-rejected ⇒ delete the signature, keep the rows).
