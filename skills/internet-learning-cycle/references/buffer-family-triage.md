# Triage a suspicious buffer family: purge, gate, or leave it

Companion to `offtopic-rows-and-purge-tool-field-trap.md`. That file names the two
mechanisms; this one is the DECISION RECIPE a cron run should follow when a fresh
`--once` stores something that looks wrong but passed BOTH learner gates.

## 1. Count the signature across THREE stores in ONE Python pass

Do NOT reach for a shell loop. A multi-part `for s in ...; do ... done` (with
`$( )` substitution inside) is BLOCKED by this terminal's hardline parser and
costs a cycle. One Python pass, always:

```python
import os
base = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
eps  = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/longterm_episodes.jsonl"
buf  = open(os.path.join(base, "online_buffer.jsonl"), encoding="utf-8", errors="replace").read()
junk = open(os.path.join(base, "buffer_junk.jsonl"), encoding="utf-8", errors="replace").read()
ep   = open(eps, encoding="utf-8", errors="replace").read()
for s in ("<sig1>", "<sig2>"):
    print(repr(s), "buffer=", buf.lower().count(s.lower()),
          "junk=", junk.lower().count(s.lower()),
          "episodes=", ep.lower().count(s.lower()))
```

Read it like this:

| buffer | junk | episodes | meaning |
|---|---|---|---|
| >0 | 0 | 0 | STORED and never refused → the live leak; **grep the STORE** |
| >0 | >0 | 0 | family was stored once, later attempts collided → still a STORE grep |
| 0 | >0 | 0 | already gated/refused → purge check on the archive, no action |
| 0 | 0 | >0 | leaked into long-term memory → escalate, this one is real |

Then read the `reason` of the junk hits: `duplicate` means the family was already
**stored** (only a STORE grep finds it); `junk` / `writer-gate` means a gate
already knows the shape (stale pre-gate rows only).

## 2. Verdict A — a KNOWN recurring off-topic family: PURGE, never a gate

Exemplar, live 13.10.26 (`cycle_c_github`): the fixed template query
`What new agent architectures are trending on GitHub?` had THREE copies of a
media/hiring-tool spam blurb (`foorilla …`). Mechanism: the query template's own
token `GitHub` IS a query topic token, so a repo blurb clears
`is_off_topic_page` — the class-160/AG dilution shape one level UP, in the source
ranking rather than in the page text.

```bash
python "C:/Users/damir/AppData/Local/openamer-laptop/skills/software-development/training-scripts-hygiene/scripts/purge_buffer_rows.py" --sig "foorilla"          # dry run
python ".../purge_buffer_rows.py" --sig "foorilla" --apply    # 300 -> 297 + .bak.purge<ts>
grep -c foorilla scripts/training/online_buffer.jsonl          # -> 0
grep -c foorilla memory/longterm_episodes.jsonl                # -> 0 of 8008 (never leaked)
```

Then archive the dropped rows (CRLF-native file — binary `ab` append, assert
`b"\n"` minus `b"\r\n"` is unchanged at 0, CRLF grows by exactly the line count):

```python
rec = {"reason": "offtopic_pair_foorilla_media_tool", "u": row["u"], "a": row["a"]}
open(arch, "ab").write(json.dumps(rec, ensure_ascii=False).encode() + b"\r\n")
```

Do NOT wire a gate on the vendor literal: `foorilla` does not generalise
(class-138 rule) and it is one source's spam — purge on sight and report it.

## 3. Verdict B — same `a` under several `u`: LEAVE THE ROWS

Exemplar, same run (`cycle_d_docs`): the PEFT LoRA docs code block
`Output: trainable params: 4,194,304 || all params: 6,742,609,920 || trainable%:
0.062% # Training from transformers import Trainer , TrainingArguments …` sat in
the buffer **3×** with three DIFFERENT `u` (`…limitations` / `…benchmark` /
`…production`) plus 7 `reason=duplicate` refusals.

- The content is ON-topic (it is the docs page for the query's own subject) and
  the docs cycle legitimately returns one page for variant queries, so the
  triplication is expected, not a leak.
- An `a`-keyed near-duplicate rule is **MEASURED-AND-REJECTED** — it would delete
  the legitimately-repeating vLLM doc cycles to save a couple of rows. Do not
  re-litigate it, do not purge: report the observation and stop.

## 4. Two hard rules for the cron turn

- **Never half-implement a gate unattended.** A found leak goes into
  `references/pending-candidates.md` with its 0-FP measurement; the gate itself is
  a dedicated session (3-copy sync, pytest, commit, push). The AV trap is real: an
  earlier cron died after applying a gate but before committing it.
- **Read the rate table before concluding anything.** One `rejected, not trained`
  line is noise. `diagnose_learn_rates.py --days 5` gives the per-hour table; a
  ~40-70 % band with accepts minutes apart is a healthy rotation, and the last row
  is a PARTIAL hour — never read it as a decline.
