# ACE verification evidence

## Scope

Base: `53f8041116b7a815d9eab13eddca81ad487183aa`.
Branch: `feat/ace-completion-integration`.
All tests and installations below ran in the isolated development worktree,
not by overwriting or restarting the active desktop installation.

## Before

Existing goal-manager/tool suite:

```text
2 files, 116 tests passed, 0 failed
```

An isolated execution of the baseline `openamer_cli/goals.py` source measured:

```json
{
  "baseline_revision": "53f8041116b7a815d9eab13eddca81ad487183aa",
  "unverified_completion_status": "done",
  "second_profile_database_is_first_profile": true
}
```

The baseline accepted `mark_done` without running a declared verification
criterion. Changing the profile after `openamer_state` was imported could open
the original profile's DB under the second profile's cache key. Both behaviors
have dedicated post-change regression tests.

## After

Final canonical run, with each test file in its own subprocess:

```text
13 files, 266 tests passed, 0 failed (100% complete) in 86.3s (3 workers)
```

The new files exercised 33 goal-completion scenarios and 13 execution-context
scenarios. Existing related tests additionally cover CLI interrupts, gateway
continuation/status/verdict handling, registry dispatch, Kanban goal mode,
provider fallback resilience, shell selection, and goal outcome storage.
The shell-selection suite skipped 4 POSIX-specific tests on Windows. The new
PowerShell/Bash/CMD interpreter tests actually executed on this host.

Command:

```bash
bash scripts/run_tests.sh \
  tests/openamer_cli/test_goal_completion.py \
  tests/tools/test_goal_execution_context.py \
  tests/openamer_cli/test_goals.py tests/agent/test_goal_tool.py \
  tests/tools/test_registry.py \
  tests/agent/test_auxiliary_fallback_chain_resilience.py \
  tests/tools/test_find_shell.py tests/openamer_cli/test_kanban_goal_mode.py \
  tests/gateway/test_goal_continuation_drain.py \
  tests/gateway/test_goal_status_notice.py tests/gateway/test_goal_verdict_send.py \
  tests/cli/test_cli_goal_interrupt.py tests/test_goal_engine.py -j 3 -q
```

On this worktree the canonical runner selected the existing development Python
via `OPENAMER_PYTHON`; it did not use an unrelated system `pip`.

## Real artifact / fresh-process smoke

`python scripts/ace_smoke.py` returned:

```json
{
  "outcome": "done",
  "resumed_in_new_process": true,
  "verification": {
    "output": "ACE_ARTIFACT_VERIFIED",
    "exit_code": 0,
    "error": null
  },
  "calls_used": 3,
  "failed_calls": 1,
  "learned": true,
  "initial_failure_exit_code": 1
}
```

Receipts in the full output additionally identify the real verification event,
canonical call signature and revision. The initial broken Python code was
intentional; successful output came from the repaired artifact, not a fabricated
provider response. A subprocess restart is real; no machine power-cycle was
performed. The repair in this deterministic smoke is scripted, not evidence of
universal model-level autonomous repair ability.

## Build/install verification

Wheel construction failed with the project's explicit policy:

```text
RuntimeError: Building wheels or sdists for openamer-agent is not supported.
If you are developing, use an editable install instead.
```

The supported alternative succeeded without changing the live installation:

```text
uv pip install --python <development-python> --target tmp/ace-artifacts/install \
  --no-deps --no-build-isolation -e .
Built openamer-agent @ file:///C:/Users/damir/wt-ace-completion
Installed 1 package
```

The isolated editable distribution was imported and the real smoke rerun. It
again reported `done`, actual artifact output, and `exit_code=0`. The final
source was rebuilt/reinstalled with the same supported editable mechanism.
Syntax/ruff checks and Git's CR-at-EOL-aware whitespace check succeeded. Existing
CRLF-tracked source files were preserved rather than reformatted tree-wide.

## Deliberate boundaries

- Proof enforcement is opt-in through executable goal checks. Legacy free-form
  goals remain compatible and judge-based.
- Provider failure tests inject faults; this run did not interrupt a real paid
  provider or perform financial operations.
- Drift guidance is a measurable progress-stall heuristic, not semantic certainty.
- Budgets limit new admissions/repeated repairs; existing turn/model/backend
  limits still handle other resources. No unimplemented token/RAM meter is claimed.
- Pending operations after a crash are uncertain, not automatically replayed.
- No Genesis directive, security permission, credential, finance automation,
  existing swarm transport, or live learning dataset was changed by testing.
- The code is published for review on a dedicated branch. This report does not
  claim it was merged or activated in the running desktop process.
