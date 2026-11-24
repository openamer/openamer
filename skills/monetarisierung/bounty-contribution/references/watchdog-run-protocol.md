# Watchdog Run Protocol — recurring PR-check + bounty-scan cron

The autonomous bounty-pipeline watchdog runs on a fixed cadence with no user
present. It has two phases and a hard rule about what to do when blocked.

## Phase 1: check the in-flight PR

For the target PR (`copperheadhq/copperhead #350`):

1. `gh pr view 350 --repo copperheadhq/copperhead --json state,reviews,comments,mergeable`
2. `gh pr checks 350 --repo copperheadhq/copperhead`
3. Read reviews: a `CHANGES_REQUESTED` review → implement, run the repo's own
   verification (`npx vitest run test/create-e2e.test.ts` + `npm run typecheck`),
   commit, push to fork remote, reply to the review.
4. `MERGED` → comment thanks on the linked issue, then look up the payout path
   (Algora / repo docs) and record what you find.

**`gh pr checks` is unreliable on this host** — it POSTs to `api.github.com`
via a path that TCP-times out while `curl --tlsv1.2` to the same host works.
Fall back to the REST API: fetch the PR's `head.sha`, then
`commits/<sha>/check-runs` and `commits/<sha>/check-suites`. The
`pulls/{n}/check-runs` endpoint 404s on this repo (checks are filed under the
commit, not the PR number) — see `github-api-automation` §"PR check-runs".

## Phase 2: pick the next bounty (only if turns left and PR still open)

Run `python memory/si/bounty_issue_analyzer.py`. Then **verify each candidate
before authoring anything**:

- Repo is REAL: `stars >= 20`, not archived, not a mirror-farm.
- No crypto-payout nonsense in the body (Bitcoin/USDC addresses, "token reward").
- Maintainer active in the last 90 days.
- Issue is actually fixable within the ~30 min budget — if it needs a GPU kernel,
  a C++ toolchain, or statistical test infra that isn't present, **skip it and
  say why**. Don't clone and don't implement in the same run; just record the
  candidate + plan.

## When the GitHub API rate limit is exhausted (core = 0)

This is the recurring blocker. Unauthenticated core reads hit 0 fast; the
authenticated `gho_` token from `~/.git-credentials` (read via
`-u openamer:$TOKEN`, HTTP Basic auth) still works for everything authenticated.

If even authenticated calls are rate-limited:

1. **Log the blocker honestly** to `memory/si/bounty_pipeline_log.jsonl` — one
   compact JSON line per action (`ts`, `action`, `result`). Never fabricate a
   test result, a push outcome, or a review reply that you didn't produce.
2. **Do not invent a workaround that pretends to have succeeded.** Say plainly:
   "blocked, could not read/write, here is the exact error."
3. **Leave the local tree exactly as it was.** If the local checkout already
   matches the pushed commit (verified via `git status --porcelain` + `git log
   --oneline -1`), there is nothing to push — the block is on the GitHub side,
   not a missing commit. Don't re-commit or re-push.
4. Set the next run's first action to re-check the rate limit, then retry the
   blocked step.

## The pr-lint gate (copperheadhq specific)

`.github/workflows/pr-lint.yml` runs on `pull_request_target` and fails the build
if the PR body is missing the `## What` / `## Why` / `## Testing` sections or the
invariant checklist. A PR that passes locally can still show
`conclusion: action_required` because the CI job is gated behind it. When the
only red check is `pr-lint` and the body genuinely has those sections, the fix
is to edit the PR body (via `PATCH .../issues/{n}` or the pulls endpoint), not
the code — and to re-verify by reading the check-run conclusion after the edit,
not by assuming.

## No-op pattern (don't re-touch an open PR)

When the target PR is `state:OPEN` + `mergeable:MERGEABLE` and the only review is
from `github-actions` bot with `state:COMMENTED` (not `CHANGES_REQUESTED`), and
the repo's own gate jobs are green — there is **nothing to implement**. Log
`OPEN, no change-request` and move to the next-bounty step. Pinging again adds
noise.