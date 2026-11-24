# DETACHED HEAD after autoStash rebases

Verified live 2026-09-11. A git-state trap that silently breaks build tooling.

## The setup

`git -c rebase.autoStash=true pull --rebase origin main` is the only reliable push
path on this box: the growth crons rewrite tracked files (`.bugbot/`, `reports/`,
`skills/auto-generated/`) constantly, so a plain `pull --rebase` aborts with
`cannot pull with rebase: You have unstaged changes`, and even stashing those
paths by hand races the next cron write.

BUT repeated autostash rebases left the repository **detached**:

```
$ git status | head -1
HEAD detached at d4a418c99

$ git rev-parse --abbrev-ref HEAD
HEAD                      # <- the sentinel, not 'main'
```

## Two real consequences, both silent

**1. Commits can be orphaned.** In the observed case nothing was lost
(`main` == HEAD == origin/main), but a commit made while detached belongs to no
branch and is easy to drop on the next `checkout`.

**2. `write-build-stamp.mjs` wrote `"branch": null`.** It reads
`git rev-parse --abbrev-ref HEAD`, and `null` is not a usable branch:

```json
{ "schemaVersion": 1, "commit": "d4a418c9...", "branch": null, "dirty": true }
```

`scripts/test-desktop.mjs` then aborts:

```
install-stamp.json is missing the branch field: {...}
npm error Lifecycle script `test:desktop:all` failed with error:
```

This reads as a broken installer or a broken test. It is neither: the NSIS
installer **built successfully** and all 2304 desktop tests **passed** —
`npm run check --workspace apps/desktop` still exits 1.

## Diagnose + fix

```bash
git symbolic-ref -q HEAD || echo DETACHED    # no output = detached
git branch --show-current                     # empty = detached

# verify it is safe BEFORE re-attaching (no work only on the detached head)
git merge-base --is-ancestor HEAD main && echo "HEAD is on main — safe"
git rev-parse --short HEAD main origin/main

git checkout main                             # re-attach
git rev-parse --abbrev-ref HEAD               # must print 'main'
node scripts/write-build-stamp.mjs            # -> "branch": "main"
```

## The rule

**Check `git branch --show-current` after ANY autostash rebase** — before
trusting a build/test result, before pushing, and before concluding a
desktop/installer failure is real.

A detached HEAD is invisible in a `git status --short` scan you are only reading
for dirty files: the modified-file list looks completely normal.

## Related lesson: don't trust a single failing run under parallel load

The same session produced two false alarms that looked like regressions but were
load artifacts — `src/app/skills/index.test.tsx` (4 fails, one at 34 s) and
`src/app/messaging/index.test.tsx` (1 fail at 32 s). Both were **vitest timeouts**
while a 90-test Python suite ran concurrently in the same turn; both passed
isolated, and both passed on the commit *before* the change.

Pattern: when a UI test fails with a multi-second duration (not an assertion
error), re-run it **isolated** and compare against the parent commit before
attributing it to your change. Vitest reports a timeout with the same `×` marker
as a real failure.
