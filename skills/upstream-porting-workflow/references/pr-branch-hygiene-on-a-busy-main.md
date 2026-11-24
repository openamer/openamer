# Shipping a docs/audit PR onto a busy main — the branch hygiene traps

**Live 2026-11-07, openamer/openamer.** A documentation + provenance-audit
change had to become a PR on `main`. The *content* was trivial (4 files, ~40
lines). The **branch hygiene** was where the entire session went — and the same
traps will hit any change made in a repo where background crons commit.

Every trap below cost measurable time and produced a *misleading* signal if
taken at face value.

---

## Trap 1 — a PR branch that carries unrelated history can never merge clean

The first PR was opened from a long-lived feature branch. It was `MERGEABLE`
at creation but flipped to **`mergeStateStatus: DIRTY` / `CONFLICTING`** as
soon as `main` moved.

Cause: that branch carried **~40 report files** from cron auto-commits
(`reports/darwin-fitness.json`, `reports/trend-scout-*.md`) plus an unrelated
feature (`agent/auxiliary_client.py` + its test). `main` had its own versions
of those report files → conflict on every one.

**The rule: build the PR branch from `origin/main` and carry ONLY your own
commits.**

```bash
# 1. a clean branch on the upstream tip
git branch feat/my-change origin/main
# 2. if your working tree is dirty, use a WORKTREE instead of stashing
git worktree add -b feat/my-change C:/tmp/wt-mychange origin/main
cd C:/tmp/wt-mychange
# 3. cherry-pick ONLY your commit(s)
git cherry-pick <sha>
# 4. verify the diff is yours and nothing else
git diff --stat origin/main
```

A cherry-pick of one commit onto `origin/main` should show **only your
files**. If it shows more, you picked up the wrong commit.

**Symptom that you did this wrong:** `git diff --stat origin/main` lists
`reports/` files you never touched. Stop and rebuild the branch.

## Trap 2 — rebasing onto a moving `main` conflicts in generated files

Rebasing the branch onto `origin/main` produced conflicts in exactly the
files that **cron regenerates constantly**:

```
CONFLICT (content): Merge conflict in reports/darwin-fitness.json
CONFLICT (content): Merge conflict in reports/darwin-history.jsonl
CONFLICT (content): Merge conflict in reports/darwin-report.md
CONFLICT (content): Merge conflict in reports/trend-scout-latest.md
```

These are **generated artifacts**, not authored content — there is no correct
merge for them. The resolution is to take one side wholesale, because the
next cron tick overwrites them anyway:

```bash
git checkout --theirs reports/darwin-fitness.json reports/darwin-history.jsonl \
                  reports/darwin-report.md reports/trend-scout-latest.md
git add reports/
GIT_EDITOR=true git rebase --continue
```

`GIT_EDITOR=true` matters — a rebase that stops for a commit message will
hang waiting on an editor in a non-interactive shell.

**Better: don't rebase at all.** Cherry-pick onto `origin/main` in a fresh
worktree (Trap 1). That sidesteps the conflict entirely, because your commit
never contained the report files.

## Trap 3 — `git worktree add` under MSYS creates a path you cannot `cd` into

This bit twice and produced a confusing "no such file or directory" while the
worktree plainly existed:

```bash
git worktree add /c/tmp/wt-prov origin/main
# → worktree created at C:/c/tmp/wt-prov   (note the DOUBLED c)
cd /c/tmp/wt-prov
# → bash: cd: /c/tmp/wt-prov: No such file or directory
```

MSYS rewrites `/c/tmp/...` into `C:/c/tmp/...`. The reliable fix is to use
the **native Windows path** when creating, and — critically — to read the
path back from git rather than assuming it:

```bash
git worktree list                       # ← read the ACTUAL path from here
git worktree remove "C:/c/tmp/wt-prov" --force
git worktree prune
```

`git worktree remove /c/tmp/wt-prov` fails with *"is not a working tree"*
because git knows the worktree under its canonical `C:/c/tmp/...` name. Always
pass the path exactly as `git worktree list` prints it.

**Corollary:** after any worktree operation, re-read `git worktree list`. A
leftover entry keeps the branch locked and the directory around.

## Trap 4 — a dirty working tree silently blocks the checkout you need

```
$ git checkout feat/provenance
error: Your local changes to the following files would be overwritten by checkout
```

In a repo where background crons commit, the working tree is rarely clean. The
untracked leftovers here were `_commit_msg.txt`, `_tmp_dshot.ps1`, `nul` and
fresh `reports/trend-scout-*.md` — none of them mine, all of them blocking.

The `git checkout` was not needed: a **worktree** gives the same branch
without touching the dirty tree at all. Reach for the worktree first, not
`stash`.

## Trap 5 — untracked files that exist upstream block a rebase too

```
error: The following untracked working tree files would be overwritten by checkout:
	apps/desktop/e2e/preview-act-fixture.html
```

The file was untracked locally but **already committed on `origin/main`**. A
rebase that checks out `origin/main` cannot write it. Two checks decide
whether the local copy can simply be deleted:

```bash
git show origin/main:<path> > /tmp/x && diff -q /tmp/x <path>
# identical  -> local copy is redundant, delete it, proceed
# different   -> the local copy is REAL WORK -> move it aside first, never delete
```

Deleting a file that differs from upstream destroys someone's work. Diff first.

## Trap 6 — a raw `pytest` sweep is not CI-comparable, and the baseline proves it

The canonical runner reported **0 failed**:

```
=== Summary: 341 files, 7264 tests passed, 0 failed (100% complete) in 579.4s (8 workers) ===
```

A raw `python -m pytest tests/agent/` on the same tree showed **52 `F`
characters** in the progress bar. Running the same raw command on a clean
`origin/main` worktree showed the **same failures** — so they are pre-existing,
not caused by the change.

The lesson is the one already in `failure-attribution`: **a raw full-suite run
in a single pytest process creates flakes the canonical runner does not have**
(CI isolates each test file in a fresh subprocess). The runner is the arbiter.

But there is a **second** lesson here, specific to comparing two raw runs:

> **A raw run that is killed by your own `timeout` produces a partial progress
> bar and a truncated file — and `exit=124` is the timeout, not a verdict.**

The comparison is only valid if **both** runs completed. When the baseline run
hit `exit=124` at 78% and the branch run hit it at 50%, the F-positions still
matched at the shared prefix — but the totals did not, so the runs could not be
compared as counts. The honest statement is *"the canonical runner is 0 failed;
a raw sweep on both trees shows failures at identical positions, but neither raw
sweep completed, so it is a qualitative signal, not a count."*

**Report the canonical runner's number as the verdict and treat the raw sweep
as corroboration, never as the headline.**

## Trap 7 — `gh pr merge --admin` is the escape hatch for a green PR

`mergeStateStatus: UNSTABLE` (some checks still running) is not a veto. Once
the required checks show **pass** and there are **no `fail` lines**:

```bash
gh pr checks <pr> | grep -c "pass"      # count the passes
gh pr checks <pr> | grep -E "fail"      # must be EMPTY
gh pr merge <pr> --squash --admin --delete-branch=false
gh pr view <pr> --json state,mergeCommit
```

The repo's `review-labels` workflow gates on a `ci-reviewed` label, but it
reports `skipping` for PRs that don't trigger the CI-sensitive path — and
`--admin` bypasses the merge gate regardless. Verify the merge afterwards:

```bash
git fetch origin main
git merge-base --is-ancestor <merge-sha> origin/main && echo "VERIFIED IN MAIN"
git show origin/main:<file>            # read the actual content that landed
```

That last line matters: `MERGED` in the API is a claim; the content at
`origin/main` is the evidence.

---

## The reliable sequence, end to end

```bash
# 0. know where you stand
git status --short                        # dirty? foreign files?
git fetch origin main

# 1. work in a worktree on origin/main — never in the busy checkout
git worktree add -b feat/my-change C:/tmp/wt-mine origin/main
cd C:/tmp/wt-mine

# 2. bring ONLY your change across
git cherry-pick <sha>                    # or re-apply the edit here
git diff --stat origin/main              # must list ONLY your files

# 3. verify HERE, in the clean tree
python -m pytest <your test file> -q
PYTHONUTF8=1 bash scripts/run_tests.sh <scope> -j 8   # the canonical runner
ruff check <your files>

# 4. push + PR
git push -u origin feat/my-change
gh pr create --base main --head feat/my-change --title "..." --body "..."

# 5. wait for the checks, then merge and verify
gh pr checks <pr>
gh pr merge <pr> --squash --admin --delete-branch=false
git fetch origin main && git merge-base --is-ancestor <sha> origin/main

# 6. clean up
git worktree remove "C:/tmp/wt-mine" --force && git worktree prune
```

**Close superseded PRs explicitly.** When a second PR carries the first one's
content (plus more), close the older one with a comment naming the successor —
an open, stale PR keeps a branch alive and invites someone to merge it later.
