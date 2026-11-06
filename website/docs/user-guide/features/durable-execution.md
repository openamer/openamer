---
sidebar_position: 12
---

# Durable Execution

Crash-safe checkpoints and a persisted step journal, so a run that dies
mid-flight can be restarted without repeating the work it already finished.

This page covers two related surfaces that live in the same per-profile store:

- **Session checkpoints** — periodic snapshots of an agent session's messages
  (`openamer_cli/durable_execution.py`).
- **Durable runs** — a step journal for multi-step work, wired into the graph
  workflow runtime (`openamer_cli/graph_workflow.py`).

It is *not* a second agent framework, and it does not make remote effects
exactly-once. See [What a checkpoint cannot promise](#what-a-checkpoint-cannot-promise).

## Where state lives

Everything is under the **active profile's** home directory:

```
$OPENAMER_HOME/checkpoints/<session_id>/0001.json     session snapshots
$OPENAMER_HOME/checkpoints/runs/<run_id>/run.json     one step journal per run
$OPENAMER_HOME/workflows/<name>.json                  workflow definitions
```

Two profiles therefore cannot see each other's checkpoints, and every payload
also stamps `profile` / `profile_home` / `schema_version` so a file copied
between profiles is rejected instead of resumed.

Writes are atomic: payloads go to a temp sibling, are `fsync`ed, then
`os.replace`d into place. A process killed mid-write leaves the previous
checkpoint byte-for-byte intact, and the loader skips past a damaged newest
file instead of discarding the history.

## Running a workflow durably

```bash
openamer workflow create
openamer workflow run demo-workflow --durable --run-id nightly-1
openamer workflow run demo-workflow --durable --run-id nightly-1   # resumes
openamer workflow status nightly-1
```

The first invocation executes each `task` node and records its result. The
second invocation — a different process — restores the completed nodes from
the journal and reports them instead of running them again:

```
Durable steps executed now: ['parse', 'validate', 'process']
Durable steps restored from journal: ['parse', 'validate', 'process']
```

`--run-id` defaults to `<workflow>-<UTC timestamp>`. Reusing an id resumes that
run; the journal is compare-and-swap on a `revision` counter, so a second
executor touching the same run fails loudly rather than interleaving writes.

## Step states

| State | Meaning | What a resume does |
|---|---|---|
| `completed` | The step returned and its result is persisted | Returns the stored result. Never re-executes. |
| `failed` | The step raised, `retryable` records the verdict | Re-executes if `retryable`, otherwise refuses. |
| `in_flight` | The process died while the step was running | Retries if the effect is repeatable; **halts** if it is external. |

The in-flight intent record is written *before* the effect starts, which is the
commit boundary that makes a crash observable instead of invisible.

## Declaring effect safety

A node declares how dangerous it is to run twice through its config:

```json
{ "id": "publish", "type": "task", "name": "Publish", "config": { "durable_effect": "external" } }
```

| `durable_effect` | Use it for | Replayed after a crash? |
|---|---|---|
| `none` (default) | Pure computation, reads | Yes, safely |
| `idempotent` | Writes that converge when repeated (file replace, absolute `PUT`) | Yes |
| `external` | Non-idempotent remote effects (`POST`, deploy, `git push`, message send) | **No — the run halts** |

An unrecognized value is treated as `external`, so a typo can never downgrade a
non-repeatable effect into an automatically repeated one.

## What a checkpoint cannot promise

If a process dies while an external effect is in flight, the journal knows the
step *started* but not whether the remote side applied it. Replaying it may
duplicate the effect, so OpenAmer refuses:

```
HALTED: step 'publish' of run 'nightly-1' was interrupted while an external
effect was in flight; its outcome is unknown.
```

Verify the external system, then close the step explicitly:

```python
from openamer_cli.durable_execution import open_run

run = open_run("nightly-1")
run.resolve_ambiguous("publish", resolution="completed", result={"release": "1.4.2"})
# or, if the effect did NOT land:
# run.resolve_ambiguous("publish", resolution="retry")
```

`resolution="completed"` records the operator's verification and never
re-executes the step; `resolution="retry"` makes it retryable again. Exactly-once
delivery requires an idempotency key or deduplication on the remote side —
the journal alone cannot supply it.

## Inspecting the store

```bash
openamer checkpoint runs            # durable runs in this profile
openamer checkpoint show nightly-1  # step-by-step journal, flags ambiguity
openamer checkpoint stats           # snapshot storage totals
openamer checkpoint list <session>  # session snapshots
```

`openamer checkpoint` (singular) is the durable-execution store.
`openamer checkpoints` (plural) is the unrelated filesystem rollback store —
see [Checkpoints and rollback](./checkpoints-and-rollback.md).

## Limitations

- **Parallel nodes.** `--durable` refuses workflows containing a `parallel`
  node, because branch results would need a merged journal. Run those without
  the flag.
- **Persisted results are JSON-safe.** Results are redacted
  (`*token*`, `*secret*`, `*password*`, …), string-capped and size-bounded
  before they are written. A resumed step gets the persisted copy, so keep step
  results small and free of credentials rather than large object graphs.
- **One executor per run.** Two processes may not advance the same `run_id`
  concurrently; the second fails with `ConcurrentRunError`.
- **Profile-scoped.** Resuming from a different profile is a validation error,
  not a fallback.
