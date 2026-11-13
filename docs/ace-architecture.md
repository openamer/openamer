# Autonomous Completion Engine (ACE): integration, not another scheduler

## Architecture audit

ACE extends the existing `GoalManager` and tool dispatch path. It does not create
another task queue, model client, shell executor, learning daemon, or swarm.

| Requirement | Existing implementation reused | Integration / boundary |
| --- | --- | --- |
| Standing goals, criteria and turn budgets | `openamer_cli/goals.py`: `GoalManager`, `GoalContract` | Same goal, completion contract and SessionDB |
| Persistent tasks / orchestration | `openamer_cli/kanban_db.py`, `plugins/kanban/` | Unchanged dispatcher and dependency graph; non-success judge verdicts block rather than finalize |
| Session restore / compaction | `load_goal`, `migrate_goal_to_session`, CLI/gateway resume | ACE journal migrates with the goal; it does not install a second reboot daemon |
| Repeated error detection | `agent/tool_guardrails.py`: `ToolCallSignature`, `classify_tool_failure`, read-only tool classifications | Reused canonical signatures/classification; ACE adds durable cross-turn counters and admission budgets |
| Execution and permissions | `tools/registry.py`, existing middleware and `tools/terminal_tool.py` | Observes real results; never executes verification commands outside normal approval flow |
| OS / shell | `tools/environments/local.py`: `_find_bash`, `_find_shell`; terminal backend factory | Describe the actual foreground Bash executable, not the parent Windows shell; remote target remains unknown until probed |
| Tools / skills | Existing registry discovery and skill tools | Missing skill is a recorded failure, not an invented replacement |
| Provider failover | `agent/auxiliary_client.py`, existing fallback chain | Unchanged; regressions cover failed candidates followed by working candidates |
| Delegation | Existing `delegate_task`, workflows, Swarm/A2A entry points | No new transport; delegated claims do not create local verification receipts |
| Learning / reuse | `agent/goal_engine.py`: `record_outcome`, `recent_outcomes` | Only executable-verified completions enter the existing outcome store |
| Specialized learning | `scripts/training/deep_task.py`, `session_outcome.py`, `analogy_engine.py`, `meta_learn.py` | Remain independent; ACE does not write incompatible rows into their data files |

The installed skill previously described `scripts/training/ace/ace_*.py` as an
implementation. The files were not present in the audited source tree. Treat
that text as a proposal, not implementation evidence.

## Executable completion contracts

The existing `goal` tool accepts optional `checks` and `budget` on `action=set`:

```json
{
  "action": "set",
  "goal": "Repair the artifact\nverify: execute the artifact assertion successfully",
  "checks": [{
    "id": "artifact",
    "tool": "terminal",
    "args": {"command": "python artifact.py", "workdir": "/project", "timeout": 30}
  }],
  "budget": {"max_calls": 80, "max_seconds": 1800, "max_repeats": 2}
}
```

Use the actual interpreter and shell-appropriate paths returned by `goal read`.
Run each check through the existing `terminal` tool with **exactly the declared
arguments**. Declaring a check does not execute or authorize it. A receipt requires
a structured foreground result with integer `exit_code=0`, no error, no running
status and no background process ID. A process-start acknowledgement is not proof.
Choose meaningful checks: ACE proves execution of the declared command, not that
an arbitrary command is an adequate specification or that passing tests prove all
possible behavior. These are operational completion guards, not a security
boundary against an adversarial agent able to rewrite its own contracts or DB.

Later potentially mutating calls invalidate earlier receipts. A failed rerun
revokes the old receipt. Parallel mutations invalidate checks that started on an
earlier revision. Unknown tools are conservatively considered mutating. Read-only
calls use the existing runtime classification, excluding arbitrary browser JS.

Both `goal report status=done` and judge-driven completion use the same atomic
receipt gate. Existing free-form goals remain compatible without executable
checks. They remain judge-based, not proof-enforced: opt into checks for strict ACE.

## Durability, recovery and budgets

`openamer_cli/goal_completion.py` stores a bounded journal under
`goal_completion:<session_id>` in the **existing** `SessionDB.state_meta` table.
Each admission is committed before invoking a tool; result recording is a second
transaction. Parallel/process workers reserve budget using SQLite's existing
`BEGIN IMMEDIATE` write machinery, not a new file store or in-memory counter.
Raw tool results and argument values are not copied into event history; contracts
contain declared commands and must not contain credentials.

A restored session carries the original goal, declared checks, checkpoint,
failed attempts, pending calls, receipts and remaining budgets. A pending call
has an **uncertain** result: inspect the actual artifact/process before deciding
how to proceed. Never silently replay a potentially irreversible operation.
This implementation blocks replay of an identical pending call. It does not
promise exactly-once external effects, automatically resolve unknown results, or
start tasks after OS boot without the existing CLI/gateway/dispatcher being run.

`goal checkpoint` records `reason` as progress and requires `next_step` to name a
declared check. Continuations include the checkpoint and missing criteria, so
work remains anchored to the original goal without changing the system prompt.
This is criterion-linked progress guidance, not a semantic proof that every
intermediate action is on-topic.

- `max_calls`: per-goal registry-call admission cap.
- `max_seconds`: wall-clock admission deadline, persisted across downtime.
- `max_repeats`: identical failed calls allowed without a successful intervention.
- A successful structured intervention permits a fresh bounded attempt; failed
  interventions and read-only calls do not clear repeated-failure counters.
- Resume cannot reset the ACE budget. An explicit **new goal** is a new contract.
- Existing goal turn budgets, model iteration/token limits, process timeouts and
  backend resource limits remain in force. ACE does not claim a new aggregate
  token meter or preemptively terminate external work already in progress.
- Goal controls remain available after exhaustion; no infinite repair loop.

GoalManager now explicitly opens `<current-profile>/state.db`. Previously its
cache key changed with profile, but `SessionDB()` could still use the path captured
at module import, defeating profile isolation and fresh-process recovery.

## Outcomes and verified learning

`done`, `partial`, `blocked`, and `failed` are distinct actual outcomes. Non-success
outcomes use the existing scheduler's `paused` state for backward-compatible
CLI/gateway control, with the actual verdict and reason persisted separately.
The judge can return each outcome; it no longer receives instructions to call a
permission/credential blocker successful completion.

Verified completion writes a measured outcome through existing
`GoalEngine.record_outcome`: receipt IDs/signatures, observed step signatures,
failed-call count and per-tool elapsed time/call counts. These observations do
not assert that a particular repair causally fixed a failure. Matching verified
strategies are recalled from the same store for a later contract. No unverified
model-generated repair advice is promoted into world-model/training files.
Learning export is at-least-once across a crash between the existing append-only
outcome write and the journal acknowledgement, not a distributed exactly-once
claim.

## Verification and reproducible before/after

Run from the repository with its development environment:

```bash
bash scripts/run_tests.sh tests/openamer_cli/test_goal_completion.py \
  tests/tools/test_goal_execution_context.py tests/openamer_cli/test_goals.py \
  tests/agent/test_goal_tool.py tests/tools/test_registry.py \
  tests/agent/test_auxiliary_fallback_chain_resilience.py \
  tests/tools/test_find_shell.py tests/openamer_cli/test_kanban_goal_mode.py
python scripts/ace_smoke.py
```

The smoke uses a new temporary profile and workspace, intentionally executes a
broken Python artifact, repairs it through the real `write_file` registry tool,
starts a fresh Python process, restores the goal/checkpoint, executes the real
terminal check, and reports the stored evidence. No fake provider responses or
fabricated success output substitute for artifact execution. All temporary DBs
are closed before Windows cleanup.

Baseline existing goal/tool tests: **116 passed, 0 failed**. Before the extension,
the new contract tests failed because the executable-completion integration was
absent. Preserve the actual runner exit code: setup errors are not successes even
if an older runner summary displays `0 failed` beside nonzero setup errors.
Provider outage and fallback scenarios use existing fault-injection regressions;
PowerShell/Bash/CMD tests execute installed interpreters, skipping absent ones.
Process restart is exercised for real; a physical machine reboot is not part of
this non-destructive test.

## Rollback / deployment

Develop on a dedicated branch and worktree. The existing running install is not
rewritten or restarted by these tests. Publish the branch as a reviewed PR; do
not merge while exact-head required CI is pending/red. Roll back a deployed
change by reverting its commits through the normal GitHub review workflow and
restoring the previous package version. No schema migration or destructive data
conversion is required: old runtimes ignore the additional metadata keys.
Existing Genesis directives, policy/approval rules and finance permissions are
not changed. No financial transaction, permission change or unattended external
provisioning is part of ACE.
