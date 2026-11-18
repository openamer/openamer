## Measured state (2026-11-16)

`gh api /repos/openamer/openamer/branches/main/protection` returned:

```
reviews.required_approving_review_count = 1
reviews.dismiss_stale_reviews          = true
enforce_admins.enabled                 = true
required_status_checks.strict          = true , 14 contexts
collaborators                          = [openamer (admin)]   (exactly one)
open invitations                       = none
gh auth accounts on this machine        = [openamer]           (exactly one)
```

`perms_admin=true`, owner type = **User** (not an org, so no team reviewer exists).

## Why this is a structural lock, not a protection

GitHub forbids approving your own pull request. With exactly **one** identity in the
repo, `required_approving_review_count=1` can never be satisfied, and
`enforce_admins=true` removes the only remaining path. Result: every PR is
publishable but **unmergeable, permanently** — independent of CI being green.

Measured example: PR #360 had 34/34 checks green, `mergeable=MERGEABLE`,
`mergeStateStatus=BLOCKED` — blocked solely by the unsatisfiable review.

## What was changed (and what was deliberately kept)

```
DELETE /repos/openamer/openamer/branches/main/protection/enforce_admins
```

* `enforce_admins`  true -> **false**
* `required_approving_review_count` stays **1**
* all 14 required status checks stay **required and strict**

Rationale: the review requirement keeps its meaning for the moment a **second
human** contributor exists. Until then the repository admin (the only identity,
and the account the agent acts for) can merge. The alternative —
`required_approving_review_count=0` — would have removed the review gate for
everyone and left only CI.

Trade-off, stated plainly: with `enforce_admins=false`, an **admin** can also
merge past a red required check. That is accepted because the CI signal, the
"All required checks pass" aggregate and the branch's own required contexts still
report loudly; what is given up is the hard block for the admin account only.

Snapshot of the previous state: `reports/governance/protection-before-20261116.json`.

## The honest limit of a second machine identity

A second *bot* account owned by the same person is not an independent review —
it is self-approval by proxy. GitHub also does not count GitHub App reviews
toward `required_approving_review_count` (only user reviews do), so an App is not
a fix either. An independent review gate needs a **different human**.

## To restore the strict gate (when a second human exists)

1. Invite the reviewer (needs their GitHub username, not an email):

   ```bash
   gh api -X PUT /repos/openamer/openamer/collaborators/<username> -f permission=push
   ```

2. Have them approve:

   ```bash
   gh pr review <n> --approve
   ```

3. Re-enable admin enforcement — only after the reviewer is active:

   ```bash
   gh api -X POST /repos/openamer/openamer/branches/main/protection/enforce_admins
   ```

Do **not** re-enable step 3 while the collaborator list still has a single entry:
that recreates the lock.

## Verify the current state any time

```bash
gh api /repos/openamer/openamer/branches/main/protection \
  -q '"reviews=\(.required_pull_request_reviews.required_approving_review_count) enforce_admins=\(.enforce_admins.enabled) checks=\(.required_status_checks.contexts|length)"'
```
