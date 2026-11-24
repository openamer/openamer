# Running a cycle under cron constraints

Traps hit on 21.09.26 while executing the standard `--once` cycle. None is an
internet-learner defect; all are about the *reporting* of a healthy run.

Sections: §1 60 s foreground clamp · §2/§2b search_files silent zero · §2c the
hand-written-probe error · §3 a rejection licenses no patch · §4 label a tail
slice · §5 `ls` a memory-cited path first · §6 denominator slip · **§7 a bare
`--once` lands on a rejection ~2× in 3 → re-run sequentially, do NOT compute a
rate to justify the retry** · **§8 tool traps: `--help` HANGS, `learn_rates.py`
is a phantom, and a `"learned" in result` census UNDERCOUNTS every `*-learn:` source** ·
**§9 corpora keys (`text` vs `a`), the 300-char `a` cap, accept corroboration without an
md5 'before', where a candidate may be filed without the AV trap, and lint-clean probes
(12.10.26)**.

## 1. The 60 s foreground clamp — `exit 124` is not a failed cycle

A foreground `terminal()` call in a cron session is killed at roughly 60 s
**whatever `timeout=` you passed**. Observed:

```
python scripts/training/internet_learner.py --once   timeout=300
-> [Command timed out after 60s]        exit_code: 124
```

The learner kept running **detached** and appended its log row ~60 s later
(`cycle_f_multi_domain … elapsed_s 76.6`). The run was healthy; the report of it
was not.

Read the signal correctly:

- `exit 124` **plus an elapsed time shorter than the budget you asked for** = the
  harness clamp, not a `subprocess.TimeoutExpired` raised inside the script.
  There is no traceback, and the script's own `try/except` guards are irrelevant —
  do not "repair" them for this.
- **Do not simply re-run it.** The first invocation is still live; a retry starts a
  SECOND worker against the same shared log/buffer, producing two rows and a
  muddled measurement. Instead wait and poll the artifact the script writes:
  `tail -3 scripts/training/internet_learn_log.jsonl` until the new row appears.
- For a genuinely long run use `background=true` + `notify_on_complete=true` and
  collect with `process(action='wait')`. The wait clamps to 60 s per call as well —
  poll until `status: exited`. Never a larger foreground `timeout=`.

## 2. A failed `search_files` must not push you into hand-writing a probe

`search_files` (rg) returns
`IO error 3 (Das System kann den angegebenen Pfad nicht finden.)` for the
`skills/` tree, and can even return a silent `total_count: 0` for a path that
exists. Both are covered in `references/skill-change-verification.md` §5.

What is new is the *consequence*: on 21.09.26 that error ended in a hand-written
throwaway `tmp/il_rate.py` recomputing the reject rate — which
`scripts/gate_attribution_probe.py` **already** computes (its sections 1–4 exist
precisely "so you do not hand-write the probes again"). The throwaway then had to
be removed and its absence proven, adding another entry to the unverified-path
census (§8 of the same reference).

Recovery, in order:

1. Get the real path from `skill_view`'s `skill_dir` field (present in every
   `skill_view` result) or from `ls <OPENAMER_HOME>/skills/` — do **not** retry the
   same search under a different path spelling.
2. If a probe script already exists for the measurement, run it.
3. Only if neither works, write a throwaway — and then treat it as a path you owe
   a cleanup proof for.

## 2b. The silent zero on `scripts/training` too — and the clamp on a directory-wide `grep` (22.09.26)

§2 covers `search_files` failing on the `skills/` tree. The **same silent zero also hits
`scripts/training`**, the busiest directory in this workflow, and there it is more
dangerous because the directory provably exists:

```
search_files(pattern='gate_attribution_probe|KNOWN_HELPERS', path='.../openamer-laptop/tests')
# -> search failed: rg: ... IO error 3 (Das System kann den angegebenen Pfad nicht finden.)
# -> a second call returned a bare `total_count: 0`, no error at all
```

Both spellings were tried. Per `references/skill-change-verification.md` §5 this is
**silence, not proof of absence** — and I had already `ls`-ed the same path successfully
in the same turn. So on this tree:

- The **packaged data files are confirmed to live in `scripts/training/`**
  (`internet_learn_log.jsonl`, `buffer_junk.jsonl`, `online_buffer.jsonl`,
  `.il_seen_queries`, plus `test_internet_learner_gate.py` there **and** under `tests/`),
  while the **probe scripts are packaged in the skill** (`skills/internet-learning-cycle/scripts/`).
  Do not let a 0-result search argue either tree away.
- Ground truth for "does this path exist" is `ls` / `find` / `py_compile` — never a
  `search_files` count.
- The cheap replacement for a content search here is a targeted terminal `grep`:

```bash
cd /c/Users/damir/AppData/Local/openamer-laptop
grep -rn "_is_affiliation_author_list" scripts/training/*.py    # 2 defs, instant
```

**But keep the glob narrow — a recursive `grep -r` from the install root hits the 60 s
clamp (§1) and is then indistinguishable from a broken tool:**

```bash
grep -rln "gate_attribution_probe" --include="*.py" --include="*.sh" --include="*.md" .
# -> [Command timed out after 60s]   exit_code: 124
```

Two directories (`.`, the install root, with `node_modules`/`venv`/cache under it) is the
whole cause. Scope to `scripts/training/*.py` + `skills/<skill>/scripts/*.py`, or `find`
by name, which answered the same question in one call:

```bash
find C:/Users/damir/openamer-repo C:/Users/damir/AppData/Local/openamer-laptop \
     -name "gate_attribution_probe.py" -not -path "*/node_modules/*"
# -> one hit (the skill copy); no repo twin, so no sync owed
```

## 2c. The throwaway measurement recurred WITHOUT a search failure (22.09.26)

§2 frames the hand-written probe as something a **failed `search_files`** pushes you
into. That is too narrow, and the narrow framing is why the mistake happened again.
Measured 22.09.26: nothing failed, no search error, no confusion — a cycle came back
`rejected, not trained (shallow + deep read both gated) (58.7s)`, triage began, and the
first move was still to `write_file` a `tmp/rej_triage.py` recomputing a per-day and
per-hour reject table. `scripts/rejection_rate_table.py` does **exactly** that, and
`--hours 24 --last 100` is the flag pair for it.

The tell that should stop you before you type: **if the number you want is a rate,
count, share, or attribution over `internet_learn_log.jsonl` / `buffer_junk.jsonl`,
a packaged script already computes it.** Both probes are one call each and print a
verdict line, so there is no measurement in this workflow that justifies an ad-hoc
file:

| you want | run this | it ends in |
|---|---|---|
| reject rate, per-day + per-hour + per-source, trailing slice | `scripts/rejection_rate_table.py --hours 24 --last 100` | `VERDICT SHAPE: … rotation noise` (or stall) |
| which gate fires, per distinct candidate, leaf-helper histogram | `scripts/gate_attribution_probe.py --section gate` | `=> seed space exhausted, NOT a miscalibrated gate. Do not patch.` |

Note the `rejection_rate_table.py` shape also satisfies §4 in the same call: it emits
the per-day table *and* the per-hour table, so the "per-day or label it a tail slice"
requirement is met by running it rather than by hand-writing anything.

Reaching for the throwaway is not free even when the numbers come out right: it adds a
path to the changed-path census, which then owes a removal **and** a proof of removal
in the same session (§8 of `references/skill-change-verification.md`) — two extra calls
to un-do work that the packaged probe would have done in one. Correct opening move for
a rejection line is `rejection_rate_table.py`, then `gate_attribution_probe.py`; a
`write_file` of any `tmp*` measurement is the error, whatever prompted it.

**On cron specifically, `execute_code` is unavailable by policy** (`approvals.cron_mode`
blocks arbitrary local Python when no user is present to approve it; the refusal names
the setting). Do not treat that as a reason to fall back to an ad-hoc script — the
packaged probes run fine via `terminal`, and if a one-off really is unavoidable the
route is `write_file` + `python <file>` (never a shell heredoc, per the memory rule on
`\b` → `0x08`), followed by the deletion proof.

## 3. What a rejection line does and does not license

Three consecutive `rejected, not trained (shallow + deep read both gated)` results
(e, f, g) are **rotation exhaustion**, not a bug — see
`references/rejection-triage.md`. Do not touch a gate. Measure the rate
(`gate_attribution_probe.py`) and stop when the documented stopping state holds.
The correct output of such a session is the measurement plus the honest statement
that no code change was warranted — never a speculative patch to a gate.

## 4. Report the *kind* of rate measurement you actually took

`references/rejection-triage.md` step 1 wants a **per-day** table, and the reason
is diagnostic, not decorative: a step change (or uniformity across all eight
sources) is the tell that separates a real bug from rotation noise. A tail slice
cannot show that.

So when you report a tail slice, label it as one — do not present it as the trend.
Measured 21.09.26 as an example of the weaker form: 2,244 rows total,
last 20 = 11/20 rejected (55 %), last 50 = 29/50 (58 %), last 100 = 62/100 (62 %).
Those numbers are honest but **cannot** distinguish "steady ~55 % for weeks" from
"55 % appeared today, 20 % yesterday" — which is the whole question. Either pair
them with the per-day table, or say plainly that only the tail was measured and
that the trend is therefore unmeasured.

## 5. A path cited by memory may be DEAD — `ls` it before you follow it (21.09.26)

The memory block is injected into every cron turn and can outlive the files it
names. Measured 21.09.26: memory named

- `references/buffer-saturation-duplicates.md` (as the home for new
  internet-learner findings, once the skill's SKILL.md hit its cap), and
- `scripts/buffer_answer_dup_probe.py`

as remediation paths for this skill family. **Neither exists.** The
`internet-learner-stall-fix` skill has **no `scripts/` directory at all** — its
only support file is `references/root-causes-archive.md`. Chasing the phantom cost
five calls: a `find C:/Users/damir -type d -name …` that hit the 60 s clamp
(`exit 124`, §1) and a `git log --all --diff-filter=A -- '*dup_probe*'` that
returned nothing, i.e. the files were never in history either.

Real state, measured the same session — use these, they are append-hostile:

| path | bytes | note |
|---|---|---|
| `skills/devops/internet-learner-stall-fix/SKILL.md` | 102,360 | **over the 100 KB cap** → do not grow it; pointer-only edits |
| `.../internet-learner-stall-fix/references/root-causes-archive.md` | 219,331 | the real destination for new root causes; **LF-native** — append LF, a CRLF append flips ~60 lines |

**Resolving a SKILL DIRECTORY by name is its own trap.** `search_files` returns a
silent `total_count: 0` for a directory that plainly exists — the same failure
class as `skill-change-verification.md` §5, but for directories rather than files.
Skills are *categorized*, so a bare `skills/<name>` glob misses them. Use a direct
glob, which answers in one call:

```bash
ls -d <OPENAMER_HOME>/skills/*/<skill-name>     # -> skills/devops/internet-learner-stall-fix
```

**Standing rules from this:**

- Before acting on any path that memory or a skill body cites, `ls` it. A dead
  path is a *memory-staleness* signal: fix the memory entry in the same session
  rather than working around it, or the next cron run repeats the search.
- Prefer the file the skill actually ships over the file a note remembers.
- **Do not edit `internet-learner-stall-fix` from an autonomous session** — it is
  user-owned; only `openamer curator adopt internet-learner-stall-fix` opens it.
  Note the near-name collision with THIS skill: `internet-learning-cycle` is the
  curator-managed one and is the correct target for cycle-level findings. Read the
  name twice before patching.

## 6. Denominator slip, caught live (21.09.26)

A reason histogram was taken over the **whole** `buffer_junk.jsonl` — 7,412 rows:
`junk 3992 / duplicate 3062 / pre-existing 238 / no-tech-signal 91 /
offtopic-drop 31`. That has the wrong denominator: the store is **shared** with
foreign writers, so those counts overstate the learner's own rejects. The
`OWNERS`-prefix filter in `references/rejection-triage.md` §2 is what makes a
`duplicate`-vs-`junk` split meaningful; report the owned denominator (`owned: N
of M`) alongside the counter, and say it is a tail slice, not a trend (§4). The
`duplicate` share here (3062 of 7412) is the rotation-exhaustion signature the
triage documents — **not** a gate bug.

## 7. The job's single `--once` usually lands on a rejection — retry, do NOT measure (22.09.26)

The cron brief asks for ONE run and ONE learned line. At the measured rate that
deliverable fails by default, and the first instinct — compute the health yourself
to see whether a retry is justified — is §2c recurring a **second** time.

Measured 22.09.26 over `scripts/training/internet_learn_log.jsonl`, last 80 rows
(tail slice — label it as one per §4; the trend is **not** measured):

| outcome | rows |
|---|---|
| `rejected, not trained (shallow + deep read both gated)` | 51 |
| `learned:` / `*-learn:` | 26 |
| `no insight` | 3 |
| → learn rate | **26/80 = 32 %** |

So a bare `--once` returns a rejection line roughly **two times in three**, with no
fault anywhere: that is the gate rotation doing its documented job (§3,
`references/rejection-triage.md`). Correct handling:

1. **Read the line's SHAPE before reacting.** A COMPLETED cycle prints its
   `[internet-learn] …` line *and* appends a row carrying `elapsed_s` — re-running
   is safe and expected. A CLAMPED run (§1: `exit 124`, no line, elapsed shorter
   than the budget) is still live — never re-run that one.
2. **Re-run sequentially**, each after the previous completed, until a
   `learned:` / `*-learn:` row lands. Measured: 4 sequential cycles → 3 learns
   (technews, arXiv, GitHub) with one rejection interleaved. Sequential is fine —
   the rotation is designed to be walked; only the §1 clamp forbids the retry.

2b. **A landed `learned:` row is NOT the stopping condition — a NOVEL one is.**
   This step 2 is under-specified and cost a full extra session's worth of cycles
   on 22.09.26. The job's deliverable is "report what was learned", so stopping at
   the first `learned:` row delivers a repeat about two times in three — the same
   trap `references/cycle-evidence-reporting.md` documents independently, but that
   file's warning was never wired into this stopping rule.

   Measured 22.09.26, 12 rows from 18:00 (7 rejects, 5 learns). Recurrence scan per
   `cycle-evidence-reporting.md` (grep one distinctive token across the log AND the
   buffer) classified all 5 learns:

   | row | verdict |
   |---|---|
   | `cycle_e_competitors` "coding skeptic" | **REPEAT** — 3rd occurrence (15.09 21:05, 17.09 05:02, 22.09 18:10) |
   | `cycle_a_technews` "Part 2: Introduction to Quantization" | **REPEAT** — 3rd occurrence (17.09 06:15, 22.09 09:22, 22.09 18:14) |
   | `cycle_b_papers` "Harness-Zero" | **STUB + MISMATCH** — `u` asked "recover unlearned knowledge for LLMs", `a` is the SERP snippet of a *different* paper |
   | `cycle_f_multi_domain` H-1B fee snippet | **OFF-TOPIC** — news snippet (visa fees) answering "What should an intelligent agent know?" |
   | `cycle_d_docs` vLLM GPU memory | **NOVEL** — `grep -c "three pools"` = 1 buffer / 0 log; names the mechanism the `u` asked for |

   So 1 of 5 learns was knowledge. Correct loop: run, then recurrence-scan each
   learn, and keep walking the rotation **until the scan clears one as novel** —
   a rejection run plus a repeat run are both non-deliverables. Three tells that
   clear a learn cheaply (all three are in `cycle-evidence-reporting.md`, applied
   here rather than re-derived): token count 0 in the log, `a` names the mechanism
   the `u` asked about, no leading `Abstract`/date, `len(a)` not ~150–260 with a
   full-question `u`.

   Corollary: **the rotation re-serves already-stored pages.** A repeat is not a
   gate bug and licenses no patch (§3) — it is the same rotation-exhaustion
   signature, now visible on the *accept* side rather than the reject side. Report
   it as "stored, but a repeat — not new knowledge", never as "learned X".
3. **Do not compute a health metric to justify the retry.** Wanting a rate *is* the
   §2c tell: `scripts/rejection_rate_table.py --hours 24 --last 100` prints the
   verdict (`rotation noise` vs stall) in one call. An ad-hoc `tmp*` recomputation
   here re-commits the §2c error — now measured **twice**, the second time with
   nothing broken anywhere, which is precisely the point of the tell.
4. **Report the learns, and the rejections as context** — never present N runs as
   if one was asked for, and never present a completed rejection as a failure.

## 8. Three tool traps measured 23.09.26 (all cost a call, none is a defect)

**8a. `--help` on `internet_learner.py` does not print help — it hangs (60 s clamp).**
`python scripts/training/internet_learner.py --help` exited `124` with
`[Command timed out after 120s]` and no usage text: the flag is not a supported
subcommand, so the script falls through to its normal rotation work (§1 clamp).
**Never probe this CLI for a flag list.** Everything the cycle accepts is in the
cron brief / this skill; if you genuinely need the argument surface, read the
`argparse` block with `search_files` instead of executing the script.

**8b. `learn_rates.py` is a PHANTOM name — the rate reader is `rejection_rate_table.py`.**
`ls scripts/training/learn_rates.py` → nothing, and the same name is absent from
`~/openamer-repo/scripts/training/` too; it exits **2** (no output), which reads
like an empty result rather than a missing file. This is the §2c/`diagnose_learn_rates.py`
trap recurring under a *different invented spelling* — the bare-name-gluing habit
keeps regenerating plausible filenames. The two real readers are:

| you want | run |
|---|---|
| reject/learn rate, per-day + per-hour + per-source, with a verdict line | `<skill>/scripts/rejection_rate_table.py --hours 24 --last 100` |
| which gate fires per candidate + leaf-helper histogram | `<skill>/scripts/gate_attribution_probe.py --section gate` |

`internet-learn`'s data files stay in `scripts/training/`; the probe scripts do
not. Do not invent a third path.

**8c. Counting learns with the token `learned` UNDERCOUNTS — every non-`learned`
source uses a `-learn:` suffix.** A one-line census written as
`"learned" in r["result"]` reported **4 learns for a day that had far more**,
because the result strings are `doc-learn:`, `paper-learn:`, `github-learn:`,
`competitor-learn:`, `domain-learn:`, `security-learn:`, `efficiency-learn:`
— the substring `learned` appears in none of them. Only `cycle_a_technews` (and
the rare connection cycles) emit the bare `learned:` form. Use
`"rejected" not in result and "no insight" not in result`, or test both
`"learned" in r` and `"-learn" in r`. **A learn census is the one number this
whole workflow exists to report** — an undercount here is the most damaging
measurement error available, because it makes a healthy rotation look stalled.
Cross-check any learn count against `rejection_rate_table.py`'s
`pass%` before quoting it.

## 9. Corpora keys, the 300-char cap, accept corroboration, filing, probe lint (12.10.26)

Measured 12.10.26 on a cycle that ACCEPTED a LinkedIn byline + GitHub project-page chrome
row (`cycle_g_security`, 55.4 s). The final measurement was right, but the **first** probe
ran against an *empty* episode corpus and still printed a confident, plausible table.

**9a. The two corpora use DIFFERENT keys — `text` vs `a`.** `memory/longterm_episodes.jsonl`
rows are `{ts, kind, text, meta}`; `online_buffer.jsonl` and `buffer_junk.jsonl` rows are
`{u, a}`. A loader written as `o.get("a")` yields **0 rows** for episodes, and the census then
prints `episodes=0` — which reads as "0 FPs on the episode corpus" instead of "no corpus
loaded". Load with `o.get("a") or o.get("text")`, and **sanity-check the counts against a
known ballpark** (episodes ≈ 8.5 k, `online_buffer.jsonl` exactly 300 at its cap,
`buffer_junk.jsonl` ≈ 14 k) before believing any 0 in the table. A 0 in the *episodes* column
is the tell that the corpus is empty, not clean.

**9b. `a` rows are CAPPED at 300 chars.** Accept strings end mid-word at exactly 300
(measured `len(leak) == 300`). So the string you grep is a *slice*, not the page: a regex
anchored with `$` matches at the cap rather than at a real sentence end, and a candidate
whose window exceeds ~300 chars can never hit any corpus row. Measure bounded windows.

**9c. Corroborating an accept when you did NOT take an md5 'before'.** The standing rule is
md5 before/after; a cron run starting cold cannot take the 'before'. Fallback evidence, both
measured 12.10.26: (i) the buffer row's `mtime` equals the cycle's own log-row `ts` to the
second (`…16:51:39.402` vs `…16:51:39.441`), and (ii) the row's `u` equals the query printed in
that log line. Together they prove a REAL append — say *which* evidence you used instead of
dropping the verification or claiming the accept is unproven.

**9d. Where a measured candidate may be filed without creating the AV trap.**
`OPENAMER_HOME` **is not a git repo** — `git -C <HOME> rev-parse --show-toplevel` returns
`fatal: not a git repository`. Writing `skills/internet-learning-cycle/references/pending-candidates.md`
(a HOME-local skill reference) therefore leaves **nothing uncommitted** anywhere; the AV-trap
warning is about the `openamer-repo` tree, not HOME. Before invoking the diverged-pair rule,
check for a repo twin: `ls <repo>/skills/<skill>/references/<file>` — `pending-candidates.md`
has **no** twin (no twin ⇒ no divergence ⇒ safe to append). The divergence hazard is specific
to `root-causes-archive.md`, which does have a real repo copy.

**9e. Write throwaways lint-clean the FIRST time.** The repo ruff config rejects `UP031`
(`%`-format → f-strings), `FURB167` (`re.I`/`re.S` → `re.IGNORECASE`/`re.DOTALL`), `RUF100`
(unused `# noqa`) and `S112`/`BLE001` (`except Exception` in a parse loop → catch
`json.JSONDecodeError`). A probe that trips ruff costs a rewrite round *and* makes the
evidence script look unverified — the 12.10.26 probe did exactly that and needed a second
write before `ruff check` returned 0. Keep it in `OPENAMER_HOME/logs/_tmp_<what>.py`
(outside git) and **name it in the report** so the measurement stays traceable.
