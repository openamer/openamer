# `auto_skill_creation.py` — observed behaviour, and how to read a "0 new skills" run

Verified live 16.09.26 (30-min cron, `openamer-laptop` profile). Companion to the
`auto_skill_creation.py` bullet in SKILL.md.

## What the script actually does

Pipeline: `kta_log.jsonl` (last **10** lines) + `online_buffer.jsonl` (last **30**
lines) → `create_skill_from_insight()` → `skills/auto-generated/<slug>/SKILL.md`
(rendered from `SKILL_TEMPLATE`, `status: draft`) → registry entry in
`scripts/training/auto_skills.json`.

Two source passes, with **different** gates — this asymmetry is the #1 reason a
diagnosis goes wrong:

| source | key fields | length gate | extra gate |
|---|---|---|---|
| `kta_log.jsonl` | `insight_question`, `insight_answer` (+ `identified_gap` appended) | `len(answer) > 40` | readability only |
| `online_buffer.jsonl` | `u`, `a` | `len(a) > 80` | **keyword gate**: `u` must contain one of `trending`, `best practice`, `research`, `competitor`, `breakthrough` |

Both passes then require `is_usable_text(clean_text(answer))` (≥40 chars, ≥90 %
printable — this is the garbled/binary-blob guard).

Skill name = `"auto-" + slugify(insight_question)`; `slugify` lowercases, strips
non-alphanumerics, takes the **first 4 words**, caps at 40 chars.

## The dedupe guard (why the old "0 on second run" criterion is wrong)

```python
def dedupe_check(name, description, registry):
    if os.path.isdir(os.path.join(AUTO_SKILLS, name)):
        return True                      # skill dir already on disk
    for prev in registry["created"]:
        if prev.get("name") == name:      # PRIMARY guard
            return True
        if prev.get("description", "")[:50] == description[:50]:
            return True
    return False
```

Order matters: the **name** guard and the **dir-exists** guard fire first.
Description matching is a secondary catch and is unreliable in the other
direction too — the answer text drifts run-to-run, so the same insight produces a
different `description[:50]` and slips past it. Only the slug is stable.
Historic damage from relying on description: 195 registry entries for 33 unique
names (11.09.26).

## Decision table for `Total: 0 new skills created`

Run the replay diagnostic below rather than guessing. Per-line reject buckets map
to a cause:

| bucket | meaning | action |
|---|---|---|
| `dup` for every candidate | insight questions repeat → same slugs exist | benign. Exhausted corpus. Report "no new skills". |
| unreadable candidate (all other gates pass) | `is_usable_text` refused: <40 chars after cleaning, or <90 % printable | benign. Garbled/binary blob (the 15.09 mojibake class). Script prints `skipped unreadable insight: …`. |
| short candidate | `len(a) > 80` (buffer) / `> 40` (kta) failed | benign. Contentless capture — check the upstream learner's capture quality, not this script. |
| `kw_filter` hits in the buffer pass | source `u` lacks the 5 keywords | expected for sources like "security learning …" which do **not** carry a keyword — those only convert via the kta pass. |
| a candidate survives ALL predicates and still no skill appears | **race**, or a code path you didn't read | re-run the script once; if the same line still produces nothing, the replay's predicates diverge from the module (re-read `create_skill_from_insight` before concluding). |

### The race (verified, benign, do NOT patch it)

`internet-learner-247` and `auto-skill-creation` both run at minute `:30`. If
auto-skill reads the kta tail before the learner finishes appending, it sees one
fewer line and reports 0. Observed live: cron run printed `Total: 0 new skills
created`, the `01:30:47` "Security learning (How are you securing your GenAI
apps…)" insight was already in the log by then, and an **immediate re-run created
exactly that skill** (`auto-security-learning-how-are`, on-disk dirs 71 → 72,
registry count 71 → 72).

The 10-line scan window is the safety net: a late insight is simply picked up on
the next tick. So the race costs at most one cycle and never loses an insight.
A first-run 0 followed by a 1 is the expected signature — report it as such
("race, nothing lost"), never as a failure to fix.

## Replay diagnostic (re-runnable)

`scripts/replay_auto_skill_filters.py` re-uses the real module functions
(`load_registry`, `slugify`, `clean_text`, `is_usable_text`, `dedupe_check`) and
replays both tail windows, printing a per-line verdict plus one line per
surviving-but-unconverted candidate. Run it whenever the 0 is ambiguous:

```
python <openamer-laptop>/skills/autonomous-learning-architecture/scripts/replay_auto_skill_filters.py
```

It is read-only (imports the module, writes nothing, creates no skill dirs) — safe
to run against the live stores. Note it imports the module by path, so it exercises
the real predicates rather than a paraphrase of them.

## Path / environment facts

- `T` = `$OPENAMER_HOME/scripts/training` — falls back to
  `~/AppData/Local/openamer` (missing the `-laptop`), the same wrong default as
  `self_improve.py`.
- Unlike `self_improve.py`, the failure is **loud**: the `isdir(T)` guard at the
  top prints `[auto-skill] ABORT: training dir not found … refusing to write into a
  throwaway env` and exits 2. So `ABORT` ⇒ `OPENAMER_HOME` unset in this shell, not
  a broken script. Verified live: `OPENAMER_HOME=C:\Users\damir\AppData\Local\openamer-laptop`.
- `SKILLS_DIR` is `${HOME}/openamer-repo/skills` — the **repo** tree, hardcoded to
  the repo, *not* `OPENAMER_HOME/skills/`. A skill appears in the repo working tree
  as an untracked dir; it is not in the profile's `skills/`.

## Publishing is a separate cron (don't hand-commit)

The generated dir lands untracked in `openamer-repo`. A different, 6-hour
`no_agent` cron (`OPENAMER_HOME/scripts/cron-repo-autocommit.py`) publishes it —
its `SCOPED = ["reports", ".bugbot", "skills/auto-generated"]` deliberately stages
exactly those paths, and the docstring notes a broad `git add -A` would sweep
another cron's in-flight edits into a chore commit. So: after creating a skill,
**do not** `git add` it by hand to "finish the job" — verify the dir + registry
entry exist and say the autocommit cron will publish it. (Tracked vs on-disk
comparison is a clean check: `git ls-files skills/auto-generated/ | grep -c
'/SKILL.md$'` vs `ls -d skills/auto-generated/*/ | wc -l`.)
