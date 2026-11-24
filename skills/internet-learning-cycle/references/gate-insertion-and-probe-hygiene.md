# Adding a guard to BOTH gates: interpreter split and probe hygiene

Live 17.09.26, while landing class 43 (`_is_metric_row_fragment`). Two traps that
cost a debug cycle each, both invisible to `ast.parse` and `py_compile`.

## 1. `re` vs `_re` — one block, two files, two blast radii

The two gates import regex differently:

| file | import |
|---|---|
| `internet_learner.py` | `import re` → use bare **`re`** |
| `buffer_store.py` | `import re as _re` → use **`_re`** |

If you assemble the guard block ONCE and paste it into both, the wrong copy
fails like this:

```
NameError: name '_re' is not defined. Did you mean: 're'?
  File ".../internet_learner.py", line 1234, in <module>
    _re.IGNORECASE)
```

Live instance: the learner copy ended `_re.IGNORECASE` while that module only
has `re` — three regexes (`_METRIC_RATIO_RE`, `_METRIC_XTILDE_RE`,
`_FINITE_VERB_RE`) went in together, and only the last line was wrong.

**Why it is easy to miss:**

- `ast.parse` passes — valid Python.
- `py_compile` passes — valid Python.
- The failure appears only on an `importlib` load or a real `--once`.

**The two directions differ in when they die** (worth knowing when triaging):

| wrong name | where it dies | symptom |
|---|---|---|
| `re` inside `buffer_store` | at **CALL** time | `NameError: name 're' is not defined` from inside the module; 29 tests red at once |
| `_re` inside `internet_learner` | at **IMPORT** time | module never loads; every cycle dead, traceback points at module scope |

**Check to run after inserting a shared block into both gates** (cheap, catches
it before the suite does):

```python
import importlib.util as u
for p, n in (("…/internet_learner.py", "il_chk"), ("…/buffer_store.py", "bs_chk")):
    s = u.spec_from_file_location(n, p)
    m = u.module_from_spec(s)
    s.loader.exec_module(m)          # <-- the load IS the check
    print("loaded OK:", m.__file__)
```

Plus a static grep of the inserted block for `_re` before writing the learner
copy — the string `_re` must not appear in `internet_learner.py` at all.

## 2. Temp probes get re-reported as changed files

Every delta/measurement probe is a `.py` file written into the live training dir,
and any later "what changed in this repo?" pass will list it. Rules:

- One `_tmp_` prefix for all of them; delete them in the SAME turn you stop using
  them:
  ```bash
  rm -f _tmp_*.py && ls _tmp_* 2>&1 | tail -1   # "No such file or directory" = clean
  ```
- Confirm with an explicit per-file existence loop — **never** a recursive `find`
  over `$OPENAMER_HOME` or `~/openamer-repo`; those trees hold node_modules and
  venvs and a `find` there was measured to time out at 60s.

## 3. Telling "already gone" from "foreign and pre-existing"

When a list of changed paths arrives, verify each one against the clock before
believing it belongs to your run:

```bash
ls -l --time-style=full-iso <file> && date
```

Live: a stale `_tmp_post.py` had mtime `02:18` while `date` said `16:49` — hours
outside the session, so it was never mine. Other deleted probes were re-reported
from memory. Both were correctly excluded.

Heuristic for the rest of the list: paths like `openamer_cli/kanban_db.py`,
`openamer_cli/service_manager.py`, `reports/darwin-*`,
`reports/trend-scout-latest.md`, `scripts/darwin_engine.py`, `docs/wiki/**`,
`acp_adapter/server.py`, `.bugbot/bugbot.log` belong to **other crons** running
against the same tree. Do not stage them, do not revert them, and say so
explicitly in the report rather than silently leaving them out. That is the same
rule as the sibling-cron hunks documented in the main SKILL.md, applied at
*reporting* time instead of commit time.
