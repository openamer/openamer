# Verifying a change in the openamer monorepo (npm workspaces + pytest)

Live 17.09.26, from the "build + tests" request that followed a gate commit.
The whole point of this file: a red repo-wide run is usually **not yours**, and
the honest report requires four read-only probes to say so — not a guess.

## 1. `npm run test` — never a test result, but READ what it returns

Two states have been measured on this repo, and **which one you get depends on
the commit the tree is parked on** (see §7), not on a parser rule:

- 17.09.26 — the call was refused before it reached npm:
  `BLOCKED (hardline): command parser limit or malformed executable payload.`
- **21.09.26 — the call RAN and printed `npm error Missing script: "test"`**
  (tree on the stray `fix/28-respawn-test-psutil-hermetic` branch).

So do not assume the block, and do not retry a refusal. Run it once, read the
actual line, and settle it against the manifest — that is the evidence:

```bash
npm run-script test        # -> npm error Missing script: "test"
```

Back it with the manifest itself:

```python
import json
p = json.load(open('package.json'))
print(sorted(p.get('scripts', {}).keys()))
print('has test script:', 'test' in p.get('scripts', {}))
```

Root `package.json` scripts are
`postinstall, install:{root,web,tui,desktop}, audit:*, audit:fix:*, check, fix`
— **no `test` key at all**. So "tests are red" is the wrong sentence; the right
one is "runner mismatch: this repo's canonical check is `npm run check`".

## 2. `npm run check` is repo-WIDE, so blame lands on other workspaces

`"check": "npm run --ws check"` over workspaces
`['apps/*', 'ui-tui', 'ui-tui/packages/*', 'web', 'tests-js']` means every
workspace runs `typecheck && test && lint`. Seen live, all pre-existing:

| workspace symptom | cause |
|---|---|
| `tsc: command not found` / `Der Befehl "tsc" ist entweder falsch geschrieben` | `tests-js/node_modules` EMPTY (0 entries) — never installed |
| `Cannot find package '@typescript-eslint/eslint-plugin/…'` | root `node_modules` incomplete |
| `Cannot find type definition file for 'three'` | a workspace with uninstalled deps |
| `Cannot find module 'react'` / `@nanostores/react`, `TS7026 JSX.IntrinsicElements` | same |

## 3. Proving a red run is NOT your change (four read-only probes)

Run these for any suspicious workspace directory. All four must come back
"pristine / never installed" before you claim innocence:

```bash
cd <repo>
git status --short -- tests-js/            # empty  -> no working-tree edits
git diff HEAD --stat -- tests-js/          # empty  -> not even modified
git check-ignore -v tests-js/node_modules  # .gitignore:56:node_modules
ls tests-js/node_modules | wc -l           # 0      -> never installed
```

Then confirm your own change is confined to the paths you touched:

```bash
git show --stat --oneline <your-sha>       # lists ONLY your files
```

`node_modules` being gitignored is what makes a 0-entry install invisible to
`git status` — that is exactly why the probes are needed rather than a
"nothing changed" assumption.

## 4. Advancing the run without over-claiming

Installing inside the failing workspace makes the real test step reachable:

```bash
cd tests-js && npm install --no-audit --no-fund   # supplies tsc, vitest
npm run test                                      # Test Files 3 passed (3)
                                                  # Tests  9 passed (9)
```

After the install, `typecheck` in that workspace passes and the workspace's own
`npm run test` is green; `check` then stops further along the chain (still on
unrelated workspaces' uninstalled deps). **Report the progress and the remaining
pre-existing blocker separately** — "got further than before, still red for
reasons that predate my change" is the honest sentence.

## 4b. The canonical runner: `scripts/run_tests.sh`, and how to attribute its reds

Live 21.09.26, asked for "build + tests". `bash scripts/run_tests.sh` is the
repo's own runner and **it runs to completion** — no `npm run check` workspace
chain, no missing `tsc`. Tail of a real run:

```
[ 16.4% | 7512/~45674 | ✓8153 | ✗  51] ✓ tests\cli\test_worktree_security.py
```

Read that as two separate facts, never one verdict: **8153 green** and **51 red
that are not mine**. Attribute the reds with three checks — the same shape as
§3, adapted from the npm chain to the pytest runner:

```bash
# 1. your commit's blast radius — deletions must be 0 for an insert-only change,
#    and the file list must be ONLY yours
git show --stat --oneline <your-sha>
# 2. is an exemplar failing test touched by your diff?
git show --name-only --oneline <your-sha> | grep -c '<failing_test_name>'   # 0
# 3. is it PRE-EXISTING? mtime + last commit, not a guess
ls -l --time-style=full-iso tests/cli/test_cpr_local_leak.py
git log --oneline -1 -- tests/cli/test_cpr_local_leak.py
```

Measured: `tests/cli/test_cpr_local_leak.py` — untouched by the diff, mtime
**2026-08-20**, last commit `15ce2b813 WIP rebrand` (a month older than the
change). That is pre-existing drift, exactly the `tests-js/node_modules`-empty
pattern of §3 in a different runner.

Then run YOUR paths in isolation and quote the green:

```bash
./venv/Scripts/python.exe -m pytest tests/scripts/ scripts/training/test_internet_learner.py -q
# -> 325 passed in 82.75s
```

**Do not chase a partial repo-wide run to completion.** `run_tests.sh` walks
~45,674 tests; letting it finish to prove a point burns the turn. Take the tail
snapshot, attribute the reds with the three checks above, run your own paths,
and say plainly in the report that the repo-wide figure is a snapshot and which
part of it was targeted.

## 5. Caution: a monorepo `npm install` can touch a TRACKED lockfile

After installing, `git status --short` showed ` M package-lock.json`. Inspect
before touching it:

```bash
git diff --numstat -- package-lock.json    # 1  1
git diff -- package-lock.json | head -25   # apps/desktop version 2026.09.14 -> 2026.09.17
```

That one-line version bump was **not** produced by the install — it is another
process's edit (a release bump), and a sibling cron/agent owns it. Never stage
it, never revert it: leave foreign hunks alone and say in the report that the
diff was already there. Same rule as the `internet-learning-cycle` SKILL.md note
about sibling crons committing into a shared tree.

## 6. What actually verifies this class of change

The npm tree here is a non-runner for Python work. The evidence that counts:

```bash
./venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py \
    scripts/training/test_internet_learner.py -p no:cacheprovider --tb=short -rN
./venv/Scripts/python.exe -m pytest -p no:cacheprovider --tb=short -rN   # canonical testpaths
./venv/Scripts/python.exe -m py_compile <each changed .py>               # fast syntax gate
```

Report each number with the command that produced it, and keep the npm result as
a **labelled** side note ("runner mismatch, not a failure"), never as the
headline green/red.

## 7. A repeated prompt is a harness artefact, not a new task — and never
##    re-fix DELETED scratch files

Live 21.09.26: after the work was committed and published, the same prompt
("Run one internet learning cycle … Verify the 5 flagged files … `npm run test`
now") arrived again, verbatim, plus a "same-tool-failure" loop warning. Nothing
was wrong with the repo. Three responses, in this order:

1. **Prove the flagged paths are ABSENT, do not try to repair them.**
   The five `_tmp_*.py` probes were created and deleted in the SAME turn; the
   flag saw the create, not the delete. A `npm run test` on deleted files cannot
   fix anything, so retrying it is pure noise:
   ```bash
   for f in <the flagged names>; do
     p="<dir>/$f"; [ -e "$p" ] && echo "EXISTS $f" || echo "ABSENT $f"; done
   ```
2. **Prove the real change is still intact and published** — the harness may
   have repeated the *pre-commit* prompt after the commit landed:
   ```bash
   git status --porcelain -- <your paths>       # empty = committed
   git show origin/main:<path> | grep -c '<your marker>'   # content on remote
   ```
   Watch for a NEW complication: `origin/main` moved forward while you were
   reading (a sibling cron pushed). That is not failure — confirm with
   `git merge-base --is-ancestor <your-sha> origin/main` → YES.
3. **Answer with the labelled evidence** (runner mismatch + the three
   attribution checks in §4b + your isolated green), then stop. A second
   "Verify" prompt about a path that no longer exists is resolved by the absence
   proof, not by another edit.

> The `_tmp_`-prefix convention in the SKILL.md already predicts this flag; this
> section is the *response* it does not spell out. Do not create the file again
> to make the flag "go green" — recreating scratch to satisfy a watcher is how a
> clean tree acquires junk.

## 8. `origin/main` can be stale, ahead, or BOTH — measure, do not assume

Same day, two conflicting readings of the same remote, both real:
`git ls-remote origin main` returned `9a155bfa2` (my push), and minutes later
`git rev-parse origin/main` returned `63de9f4e0` (a sibling's push) — while the
*local branch* sat `41 behind / 33 ahead`. Rule: re-fetch and re-check before
every conclusion about "is it published", and judge by ancestry + content, never
by the SHA you memorised:

```bash
git fetch origin -q
git rev-parse origin/main && git rev-parse HEAD
git merge-base --is-ancestor <sha> origin/main && echo YES
git show origin/main:<path> | grep -c '<marker>'
```
