# Evidence for one cycle: what did it learn, and how deep?

The cycle command prints ONE line, and that line is a **claim**, not the evidence:

```
[internet-learn] cycle_a_technews: learned: Abstract Recent advances in large language mo… (44.6s)
```

`learned: <text>` only means one of the two gates ACCEPTED a string. It is not proof
that knowledge (rather than an abstract fragment) was stored. Report the claim plus
the store-side evidence; if you did not open the store, say "unverified".

## Reading the raw evidence (no `python -c` — cron blocks it)

Run the packaged collector — it reads all three artifacts below and prints the
verdict, including the `u`/`a` key handling and the stub tells:

```bash
python <OPENAMER_HOME>/skills/internet-learning-cycle/scripts/verify_cycle_evidence.py
python .../verify_cycle_evidence.py --tail 5          # more log rows
```

It exits non-zero only when a buffer row fails to parse, so it can gate a cron
chain. Do not hand-write a `python -c` one-liner for this: cron blocks it.

The three artifacts that matter:

| file | what it tells you |
|---|---|
| `scripts/training/internet_learn_log.jsonl` | one JSON row per cycle: `ts`, `source`, `result`, `elapsed_s`, plus `reason` on rejects. `tail -3` is enough — it carries the FULL `result`, while stdout truncates to 80 chars |
| `scripts/training/online_buffer.jsonl` | the actually-stored training pair. Keys are lowercase **`u`** (question) and **`a`** (answer) |
| `scripts/training/buffer_junk.jsonl` | rejects + reason (`duplicate` / `junk` / `no-tech-signal`) |

**Key trap:** `online_buffer.jsonl` rows use `u` / `a`, NOT `U` / `A`. A probe that
reads `d['U']` dies with `KeyError: 'U'` even though the printed `str(d)[:300]` shows
uppercase-looking labels — do not conclude the file is malformed. Print
`sorted(d.keys())` first and then read the actual `a` value in full.

`MAX_BUF = 300`, so the buffer sits pinned at 300 rows and only its **tail** is the
new entry — a row count of exactly 300 tells you nothing about recency.

## A `learned:` line can be a REPEAT, and stdout cannot tell you (live 21.09.26)

`learned:` also does not mean *new*. The efficiency cycle printed a normal
`efficiency-learn: YouTube's open-source SDKs (e.g., …)` line — and the log showed
the **same page stored three times** (19.09 00:24, 21.09 10:14, 21.09 16:04). The
third was a duplicate of the first, but `_is_duplicate` compares `(u, a)` for
**exact** equality and the deep-read sentence DRIFTS (`youtubei-python` /
`youtubei-webapp` → `youtubei1` / `youtubei2` / `youtubei3`), so no gate saw it.

So the cheap daily check is not the printed line — it is a **recurrence scan**
over the log: group rows by `source`, or grep one distinctive token:

```bash
grep -c "<distinctive token from the answer>" scripts/training/internet_learn_log.jsonl
```

A count that climbs over days for the same voice = a drifted-near-duplicate leak,
not accumulating knowledge. Report it as such (the row is not new knowledge), and
treat the leak itself as a chrome class to measure — see
`training-scripts-hygiene/references/duplicate-vs-near-duplicate-gates.md` for the
similarity-gate measurement (it fails: the leak scores *below* legitimate distinct
rows) and the narrow rule that shipped instead.

## Telling real knowledge from an accepted stub

`extract_insight()` returns a **search-result title / SERP snippet**, and that is
what the shallow path stores. Live example (21.09.26, `cycle_a_technews`): the stored
answer was 167 chars — the bare first sentence of an arxiv abstract that starts with
the literal word `Abstract` and stops mid-topic ("…capable of complex reasoning and
multi-step problem solving."). The question was far richer than the answer:

- `u`: `Internet learning (AI agents that "self-reflect" perform better in changing
  environments): What should an AI agent know?`
- `a`: `Abstract Recent advances in LLMs have enabled the development of autonomous
  agents capable of complex reasoning and multi-step problem solving.`

So the cycle cost 44.6 s and taught the model nothing the question did not already
contain. **Say that in the report** instead of parroting "learned: …". Two cheap
tells that the shallow path (not `deep_learn`) won:

1. the stored `a` starts with `Abstract` / repeats the SERP snippet verbatim;
2. `len(a)` is small (~150–260 chars) while the `u` is a full question;
3. the stored `a` opens with a bare absolute **DATE** (news-headline / SERP shape) and
   the stdout line cuts off mid-word at its 80-char truncation. Live 21.09.26,
   `cycle_c_github` (55.6 s), buffer tail:
   ```
   u: What new agent architectures are trending on GitHub?
   a: Sep 11, 2026 OpenAI rogue agents Hugging Face hack went further OpenAI agents
      built a 1,200-agent covert network inside tests, then seized admin control of
      a Hugging Face server.
   ```
   A news snippet — the `u` asked about trending agent **architectures** and the `a`
   never names one. Cost 55.6 s, so time spent is no proxy for depth either. The
   leading date is the fastest tell that a news cycle, not a repo/doc cycle, produced
   the answer.

Note the interaction with `store_or_deep`: the deep pass is only reached when the
shallow store is REJECTED. Since the shallow gate does not check length or
question/answer asymmetry, an abstract stub sails through and the deeper — better —
text is never fetched. That is the mechanism, not a one-off.

## Reporting template (one line, per the cron contract)

```
cycle_a_technews, 44.6s → learned: "<first 60–80 chars of a>"
  stored: online_buffer.jsonl tail #300 (u="…", a=167 chars — abstract stub, shallow
  path; deep_learn not reached). tool_server :8081 alive, 9 tools, no restart.
```

Lead with the real claim, then the depth qualifier, then the infra fact. Never
upgrade a stub to "learned X" in prose, and never report the count of stored rows as
if it measured learning.

### And the converse: an accept can be REAL prose — check before calling it a stub

22.09.26, `cycle_b_papers` (33.3 s) — the counter-example that proves the tells above
are discriminating rather than a blanket pessimism. Log row and buffer tail:

```
2026-09-22T00:26:30.237522 | cycle_b_papers | 33.3
u = Latest research insight: MegaTrain: Full Precision Training of 100B+ Parameter LLMs on a Single GPU
a = MegaTrain Full Precision Training of 100B+ Parameter LLMs on a Single GPU A RAM-centric
    architecture that stores parameters in host memory and treats GPUs as transient compute
    engines, enabling full-precision training of 100B+ models on a single GPU.
```

None of the three stub tells fire: no leading `Abstract`, no leading date, and the `a`
names the mechanism the `u` asked about (RAM-centric / host-memory / GPU-as-transient-
compute) rather than restating the question. That is a stored fact. Say so — applying
the stub verdict reflexively would be the mirror of parroting `learned: …`.

Also note the stdout line for that run was `paper-learn: MegaTrain … on a Single GPU A RAM-`
— cut mid-word at the 80-char clamp, **exactly like the news-snippet example above**. The
truncation is a property of stdout, not a shape signal; take the full `a` from the log
row/`online_buffer.jsonl` before classifying either way.

Cheap store-side census worth printing in the report (the numbers this session measured):
`online_buffer.jsonl` → **214 records**, all parseable, 0 blank lines, keys exactly
`['a', 'u']`, and the new row is the file's LAST line. Note 214 is a real count, not the
`300` cap — a record count away from `MAX_BUF` is not itself suspicious (see the
`cap-counts-lines-not-records.md` note in `rejection-triage.md` §1 for what a *pinned*
buffer means).
