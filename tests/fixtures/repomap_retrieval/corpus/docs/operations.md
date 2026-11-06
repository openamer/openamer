# Operations runbook

## Rollout

1. Tag the release and let CI publish the artifact.
2. Run `scripts/deploy.sh staging` and wait for the smoke check.
3. Promote to production only after the staging window closes.

## Rollback

Point the load balancer at the previous release and re-run the deploy script
with the previous tag. No database migration is reverted automatically.

## On-call notes

Failures during rollout are almost always a bad artifact, not a capacity
problem. Check the deploy log before scaling anything.
