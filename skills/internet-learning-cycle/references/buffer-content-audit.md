# Auditing what the buffer ACTUALLY stored (content side, not gate side)

Distinct from gate attribution: here the question is not "why was this row
rejected" but **"is the row that DID get stored correct"**. Run this when a cron
report would otherwise be a bare "N cycles rejected" line and you want the
result to carry a measurement instead of a guess.

## Order that keeps a cron run honest (22.09.26)

1. `git status --porcelain scripts/training tests/scripts` + `git diff --stat`
   — a previous cron session can die after applying a gate fix but before
   committing; then the tree already carries the next class.
2. The rates table (`diagnose_learn_rates.py --training-dir <live training dir>`
   from the sibling `training-scripts-hygiene` skill). Read the **per-day**
   rows, not just the 7d aggregate. In-regime values measured 22.09.26 were
   per-source 40.6–55.1 % and per-day 16.7–61.5 %.
3. Only then look at content. A rejection + one odd row is **not** a warrant for
   a gate edit — that combination was measured and left untouched on 22.09.26.

## The finding worth re-checking: unrelated `a` on a clean `u`

A stored row can pair a perfectly good question with a topically unrelated
paragraph:

| field | value (truncated) |
|---|---|
| `u` | `Internet learning (MIT researchers develop an efficient way to train more reliable AI agents): What should an AI agent know?` |
| `a` | `The tool uses deep learning models trained on decades of viral sequences and lab test results to simulate how the flu virus might evolve and how the vaccines will respond.` |

Measured on that row: `_is_junk(a)` → **False**, `len(a)` → **171** (clears the
>=90 length-trust threshold), exact duplicates → **0 of 249** buffer rows. So it
is **not** duplicate exhaustion, **not** a marker gap, **not** a writer-gate
hole — it is the AG family (an unrelated whole article/paragraph ranked as `a`),
documented as deliberately unpatched. Do not "fix" it on a rejection; report it
as measured.

## Census + dupes in one shot

```python
import json
rows = [json.loads(l) for l in open('online_buffer.jsonl', encoding='utf-8') if l.strip()]
keys = {}
for r in rows:
    k = json.dumps(r, sort_keys=True)
    keys[k] = keys.get(k, 0) + 1
print('rows', len(rows), 'exact-dupes', sum(v - 1 for v in keys.values() if v > 1))
```

Also useful: `wc -l online_buffer.jsonl` — **not at the 300-row cap means
`duplicate` exhaustion is not the story**, which by itself rules out one whole
branch of diagnosis.

## A keyword screen is a screen, never a verdict

Screening for words present in `a` but absent from `u` flagged 3 rows on
22.09.26; re-reading the `u`/`a` pairs showed only **one** was genuinely
unrelated — the other two were on-topic prose it over-flagged (a German
LLM-security summary, a physics-simulation paragraph). Always read the pairs
before calling anything off-topic, and never write a junk marker from a keyword
screen alone (the topic-word trap: a bare topic word like `nifty` produced both
a hand and a live false positive).

## Probe API gotchas

- `internet_learner` exports the private `_is_junk`. `il.is_junk` raises
  `AttributeError: module 'internet_learner' has no attribute 'is_junk'` — there
  is **no public alias**.
- Helper names must not be guessed (`_has_tech_signal` does not exist). Resolve
  them with `getattr(mod, name, None)` in a loop and call only what resolves.

## Tooling note

`search_files` called with an **absolute MSYS-style** path into the skills tree
returned `IO error for operation on /c/Users/...: (os error 3)` while the
**cwd-relative** path returned every match, and `read_file` on the same absolute
path worked. On such an rg IO error: retry the relative path, or settle it with
`cd <dir> && grep -n -E '<pattern>'` in the terminal. Do not conclude the file
is missing.
