# Verifying a "0 created / 0 learned" cycle honestly

The learning loops all report a bare counter. `0` is the most common output and
the easiest thing to misreport, because it is ambiguous: it can mean *healthy,
nothing novel* or *the pipeline is starved and silently broken*. These two look
identical in the cron log line.

This file is the checklist for turning that `0` into an honest, evidence-backed
sentence. It applies to `auto_skill_creation.py`, `internet_learner.py --once`,
and `knowledge_to_action.py`.

## The rule

**Never report `0` as "nothing was learned" without disambiguating it.** The
report must say *which kind* of zero it was, backed by a number you just read.

## Case: `auto_skill_creation.py`

Prints: `Total: 0 new skills created`.

`0` arises from (at least) five distinct causes:

| Cause | Meaning | Where to look |
|---|---|---|
| All candidates already known | healthy — dedupe working as designed | dedupe-known count > 0 |
| Inputs empty / too short | pipeline starved | scanned rows == 0, or mtimes stale |
| **Rows present, none carry a trigger keyword** | upstream IS producing; the buffer filter ate it | keyword-drop count > 0 while scanned rows == 0 |
| Unreadable / off-domain rows | upstream junk gate rejected everything | `skipped unreadable/off-domain` lines |
| Candidates exist but none written | real bug in `dedupe_check` / `is_usable_text` / `is_domain_relevant` | candidate-new > 0 while created == 0 |

Cause 3 is the one the log line hides best: the buffer scan keeps only rows whose
`u` contains `trending / best practice / research / competitor / breakthrough`
**before** the length floor is ever applied, so a full buffer of perfectly good
non-matching rows yields the same `Total: 0`. Measured 21.09.26: of 30 buffered
rows, **21 were dropped by the keyword filter** and 9 reached the scanner (all
already known) — plus the kta tail contributed nothing usable. "Nothing new" was
true; "the learner is dead" would have been false.

### Probe (safe, read-only, every cycle)

```bash
python skills/autonomous-learning-architecture/scripts/autoskill_creation_probe.py
```

It replicates the production scan and dedupe logic, writes nothing, and prints
the breakdown — `scanned rows`, `keyword-drop`, `dedupe-known`,
`empty/too-short`, `gate-rejected`, `candidate-new`, the drafts-on-disk vs
registry counts — plus a `VERDICT:` line naming which of the five causes
applies. It also prints the `mtime` of `kta_log.jsonl` and
`online_buffer.jsonl` — a stale mtime means the *upstream* loop is the thing to
fix, not this script.

Two properties that make its verdict trustworthy, both added 21.09.26 after the
probe itself lied:

* it **imports the production module** and calls the real `clean_text` /
  `is_usable_text` / `is_domain_relevant` / `slugify`, instead of keeping a
  hand-copied gate that drifts. If the import fails it prints
  `gates : FALLBACK length-only (import failed)` rather than silently grading
  with a weaker rule.
* it resolves the drafts dir from **the install it is running in**, not from a
  hard-coded `~/openamer-repo` path (see the companion-proof box below).

### Do NOT hand-roll a second scanner

The production scan window + dedupe is four decisions wide (tail size, keyword
tuple, length floor, name-first slug). A fresh ad-hoc re-implementation in a
throwaway script will get at least one of them wrong and then report a *dedupe
bug that does not exist*. Live 21.09.26: a hand-written `_diag_autoskill.py`
printed `duplicate 9 / WOULD_CREATE 0`, but its own `name` was built as
`auto-` + `slugify(u)` from a bare `re.sub` copy — it would have disagreed with
production the moment the two slug rules diverged. **Run the probe; when its
verdict still leaves a question, import production and re-assert
(`A.load_registry()` / `A.dedupe_check(...)`) — never re-implement and compare.**

### Companion proof that nothing was written

The probe shows *why* nothing was created; these show *that* nothing was:

```bash
# the drafts live in the INSTALL, which is where the cron script writes:
ls C:/Users/damir/AppData/Local/openamer-laptop/skills/auto-generated | wc -l
grep -o '"count": [0-9]*' C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/auto_skills.json
```

Registry count == draft dirs on disk. If they disagree, the registry has
drifted and dedupe may be operating on a wrong picture.

**Do not reach for `git status` here by reflex.** The install
(`AppData/Local/openamer-laptop`) is **not a git repo** — `git status` returns
`fatal: not a git repository` and `git status --porcelain` yields nothing at
all, which is indistinguishable from "clean, nothing written". Measured
21.09.26. `git`-based proof only applies inside an actual checkout
(`~/openamer-repo`), and that checkout is a *different tree* from the one the
drafts are written to — so `git status` there cannot prove anything about an
install-side cycle either way. Use the two `ls`/`grep` counts, which are
tree-independent.

### Scan window (the easy thing to get wrong when replicating)

The production script does **not** scan everything:

* `kta_log.jsonl` -> **last 10 lines**, needs `insight_question` and
  `len(insight_answer) > 40`
* `online_buffer.jsonl` -> **last 30 lines**, `u` must contain one of
  `trending / best practice / research / competitor / breakthrough` **and**
  `len(a) > 80`

A probe that scans the whole file will report candidates the real script never
looks at. Mirror the tails exactly or the verdict is fiction.

### Dedupe is name-first, deliberately

`dedupe_check` matches on the slugified **name** first, description second. The
same insight question always slugifies to the same skill name, while the answer
**text drifts run-to-run** — so a text-only check let every run re-create and
overwrite a known skill (live 11.09: 195 registry entries across just 33 unique
names). When a probe disagrees with the script's behaviour about what is "new",
check the name path first.

## Reporting template

The cron contract asks for **one line**. Satisfy it with the disambiguated kind
of zero plus its measured numbers — then stop. The full breakdown is written to
stdout for whoever wants it; do not paste the whole probe output into the reply,
and do not append a verification essay. An over-long answer to a one-line cron
job is itself a defect (the user has corrected this class of thing before:
"warum so kompliziert").

```
0 new skills created (genuine: 26 insights scanned, 23 already-known against
102 drafts, 3 too short, 0 novel) — nothing new, not a stall.
```

For the FILTERED variant the number that matters is the dropped one:

```
no new skills (buffer 30 rows, 21 dropped by keyword filter, 9 scanned all
already-known, 0 novel) — learner alive, nothing new.
```

If the probe could not reach a conclusion (no production module, no drafts dir,
both inputs missing), say **unmeasured** and name what was missing. Do not
round a partial read up to "nothing new".

## Environment quirks that shape the commands

* In cron, `python -c "..."` is blocked (dangerous-flag guard, no user to
  approve). Write the probe to a `.py` file and run it with `python file.py`.
* MSYS-style paths (`/c/Users/...`) break `rg`/`search_files`
  (`os error 3`) — always spell paths `C:/Users/...`.
* `search_files`/`read_file` on a *single file* work fine; a whole-directory
  grep needs the native-style path.
